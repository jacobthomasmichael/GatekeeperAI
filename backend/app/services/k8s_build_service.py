"""
Kaniko-based image build service for Kubernetes deployments.
Uploads build context to S3, creates a Kaniko Job, polls until completion.
Only used when DEPLOY_BACKEND=kubernetes.
"""
import logging
import time
import uuid
import tarfile
import tempfile
import os
import boto3
from kubernetes import client, config as k8s_config
from kubernetes.client.exceptions import ApiException
from app.config import settings

logger = logging.getLogger(__name__)

BUILD_NAMESPACE = "gatekeeperai-builds"
KANIKO_IMAGE = "gcr.io/kaniko-project/executor:v1.23.0"
BUILD_TIMEOUT_SECONDS = 600  # 10 minutes


def _load_k8s_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def build_and_push(
    build_dir: str,
    safe_name: str,
    ecr_registry: str,
    commit_sha: str,
) -> str:
    """
    Tar the build_dir, upload to S3, create a Kaniko Job, poll until done.
    Returns the full ECR image URI including tag.
    ecr_registry: e.g. "123456789.dkr.ecr.us-east-1.amazonaws.com"
    """
    image_tag = f"{commit_sha[:12]}" if commit_sha else str(uuid.uuid4())[:12]
    image_uri = f"{ecr_registry}/gatekeeperai-apps/{safe_name}:{image_tag}"
    s3_key = f"builds/{safe_name}/{image_tag}.tar.gz"
    # K8s names max 63 chars: "build-" (6) + safe_name + "-" (1) + image_tag (12) ≤ 63
    _build_name = safe_name[:44]

    # --- Upload build context to S3 ---
    context_tar = _create_context_tar(build_dir)
    try:
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        s3.upload_file(context_tar, settings.BUILD_CONTEXT_BUCKET, s3_key)
        logger.info("Uploaded build context for %s to s3://%s/%s", safe_name, settings.BUILD_CONTEXT_BUCKET, s3_key)
    finally:
        os.unlink(context_tar)

    # --- Create Kaniko Job ---
    _load_k8s_config()
    batch_v1 = client.BatchV1Api()

    job_name = f"build-{_build_name}-{image_tag}"
    job_body = _kaniko_job(
        job_name=job_name,
        image_uri=image_uri,
        s3_bucket=settings.BUILD_CONTEXT_BUCKET,
        s3_key=s3_key,
        aws_region=settings.AWS_REGION,
    )

    try:
        batch_v1.create_namespaced_job(BUILD_NAMESPACE, job_body)
    except ApiException as e:
        if e.status == 409:
            # Stale job from a previous attempt — delete and recreate.
            logger.warning("Kaniko Job %s already exists; deleting and recreating", job_name)
            batch_v1.delete_namespaced_job(
                job_name, BUILD_NAMESPACE,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
            _wait_for_job_deletion(batch_v1, job_name, BUILD_NAMESPACE)
            batch_v1.create_namespaced_job(BUILD_NAMESPACE, job_body)
        else:
            raise
    logger.info("Created Kaniko Job %s", job_name)

    # --- Poll until complete or timeout ---
    _wait_for_job(batch_v1, job_name, BUILD_NAMESPACE)

    logger.info("Build complete: %s", image_uri)
    return image_uri


def _create_context_tar(build_dir: str) -> str:
    """Create a .tar.gz of build_dir, return path to the temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp.close()
    with tarfile.open(tmp.name, "w:gz") as tar:
        tar.add(build_dir, arcname=".")
    return tmp.name


def _kaniko_job(
    job_name: str,
    image_uri: str,
    s3_bucket: str,
    s3_key: str,
    aws_region: str,
) -> client.V1Job:
    return client.V1Job(
        metadata=client.V1ObjectMeta(
            name=job_name,
            namespace=BUILD_NAMESPACE,
            labels={"managed-by": "gatekeeperai"},
        ),
        spec=client.V1JobSpec(
            ttl_seconds_after_finished=3600,  # auto-clean after 1 hour
            backoff_limit=0,  # no retries — a failed build means bad code
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"managed-by": "gatekeeperai"}),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    service_account_name="gatekeeperai-worker",  # IRSA role has ECR + S3 permissions
                    containers=[
                        client.V1Container(
                            name="kaniko",
                            image=KANIKO_IMAGE,
                            args=[
                                f"--context=s3://{s3_bucket}/{s3_key}",
                                f"--destination={image_uri}",
                                "--cache=true",
                                f"--cache-repo={image_uri.rsplit(':', 1)[0]}-cache",
                                "--snapshot-mode=redo",
                                "--use-new-run",
                            ],
                            env=[
                                client.V1EnvVar(name="AWS_REGION", value=aws_region),
                                client.V1EnvVar(name="AWS_SDK_LOAD_CONFIG", value="true"),
                            ],
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": "500m", "memory": "512Mi"},
                                limits={"cpu": "2", "memory": "2Gi"},
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def _wait_for_job_deletion(batch_v1: client.BatchV1Api, job_name: str, namespace: str) -> None:
    """Wait until the job is gone so we can recreate it with the same name."""
    for _ in range(30):
        try:
            batch_v1.read_namespaced_job_status(job_name, namespace)
            time.sleep(2)
        except ApiException as e:
            if e.status == 404:
                return
            raise
    raise TimeoutError(f"Timed out waiting for job {job_name} to be deleted")


def _wait_for_job(batch_v1: client.BatchV1Api, job_name: str, namespace: str) -> None:
    """Poll job status until succeeded or failed. Raises on failure or timeout."""
    deadline = time.monotonic() + BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        job = batch_v1.read_namespaced_job_status(job_name, namespace)
        if job.status.succeeded:
            return
        if job.status.failed:
            raise RuntimeError(f"Kaniko build job {job_name} failed")
        time.sleep(10)
    raise TimeoutError(f"Kaniko build job {job_name} timed out after {BUILD_TIMEOUT_SECONDS}s")
