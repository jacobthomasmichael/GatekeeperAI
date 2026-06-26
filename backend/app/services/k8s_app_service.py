"""
Kubernetes Deployment/Service/Secret lifecycle for deployed apps.
Only used when DEPLOY_BACKEND=kubernetes.
"""
import base64
import logging
from kubernetes import client, config as k8s_config
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

APPS_NAMESPACE = "gatekeeperai-apps"


def _load_k8s_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def deploy_app(
    safe_name: str,
    image_uri: str,
    internal_port: int,
    env_vars: dict[str, str],
) -> str:
    """
    Create or update a K8s Secret, Deployment, and ClusterIP Service for an app.
    The ClusterIP Service was already created by k8s_ingress_service in Phase 2,
    but we replace_namespaced_service here to ensure the port matches.
    Returns the deployment name.
    """
    _load_k8s_config()
    apps_v1 = client.AppsV1Api()
    core_v1 = client.CoreV1Api()

    deployment_name = f"gk-app-{safe_name}"
    secret_name = f"gk-app-{safe_name}-secrets"

    # --- K8s Secret for app env vars ---
    secret_data = {
        k: base64.b64encode(v.encode()).decode()
        for k, v in env_vars.items()
    }
    secret_body = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name,
            namespace=APPS_NAMESPACE,
            labels={"managed-by": "gatekeeperai", "app": deployment_name},
        ),
        type="Opaque",
        data=secret_data,
    )
    try:
        core_v1.read_namespaced_secret(secret_name, APPS_NAMESPACE)
        core_v1.replace_namespaced_secret(secret_name, APPS_NAMESPACE, secret_body)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_secret(APPS_NAMESPACE, secret_body)
        else:
            raise

    # --- Deployment ---
    deployment_body = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=deployment_name,
            namespace=APPS_NAMESPACE,
            labels={"managed-by": "gatekeeperai", "app": deployment_name},
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": deployment_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": deployment_name}),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="app",
                            image=image_uri,
                            ports=[client.V1ContainerPort(container_port=internal_port)],
                            env_from=[
                                client.V1EnvFromSource(
                                    secret_ref=client.V1SecretEnvSource(name=secret_name)
                                )
                            ],
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": "250m", "memory": "256Mi"},
                                limits={"cpu": "500m", "memory": "512Mi"},
                            ),
                        )
                    ]
                ),
            ),
        ),
    )
    try:
        apps_v1.read_namespaced_deployment(deployment_name, APPS_NAMESPACE)
        apps_v1.replace_namespaced_deployment(deployment_name, APPS_NAMESPACE, deployment_body)
        logger.info("Updated K8s Deployment for app %s", safe_name)
    except ApiException as e:
        if e.status == 404:
            apps_v1.create_namespaced_deployment(APPS_NAMESPACE, deployment_body)
            logger.info("Created K8s Deployment for app %s", safe_name)
        else:
            raise

    return deployment_name


def stop_app(safe_name: str) -> None:
    """Scale the Deployment to 0 replicas (preserves the object for easy restart)."""
    _load_k8s_config()
    apps_v1 = client.AppsV1Api()
    deployment_name = f"gk-app-{safe_name}"
    try:
        apps_v1.patch_namespaced_deployment(
            deployment_name,
            APPS_NAMESPACE,
            {"spec": {"replicas": 0}},
        )
        logger.info("Scaled K8s Deployment %s to 0", deployment_name)
    except ApiException as e:
        if e.status != 404:
            raise


def start_app(safe_name: str) -> None:
    """Scale the Deployment back to 1 replica."""
    _load_k8s_config()
    apps_v1 = client.AppsV1Api()
    deployment_name = f"gk-app-{safe_name}"
    try:
        apps_v1.patch_namespaced_deployment(
            deployment_name,
            APPS_NAMESPACE,
            {"spec": {"replicas": 1}},
        )
        logger.info("Scaled K8s Deployment %s to 1", deployment_name)
    except ApiException as e:
        if e.status != 404:
            raise


def get_app_logs(safe_name: str, tail_lines: int = 200) -> str:
    """Return recent logs from the running app pod."""
    _load_k8s_config()
    core_v1 = client.CoreV1Api()
    deployment_name = f"gk-app-{safe_name}"

    pods = core_v1.list_namespaced_pod(
        APPS_NAMESPACE,
        label_selector=f"app={deployment_name}",
    )
    if not pods.items:
        return "No running pods found."

    # Use the most recently started pod
    pod = sorted(pods.items, key=lambda p: p.metadata.creation_timestamp or "", reverse=True)[0]
    try:
        return core_v1.read_namespaced_pod_log(
            pod.metadata.name,
            APPS_NAMESPACE,
            tail_lines=tail_lines,
        )
    except ApiException:
        return "Unable to retrieve logs."


def get_app_status(safe_name: str) -> dict:
    """Return deployment status as a dict with keys: ready_replicas, total_replicas, available."""
    _load_k8s_config()
    apps_v1 = client.AppsV1Api()
    deployment_name = f"gk-app-{safe_name}"
    try:
        d = apps_v1.read_namespaced_deployment_status(deployment_name, APPS_NAMESPACE)
        return {
            "ready_replicas": d.status.ready_replicas or 0,
            "total_replicas": d.status.replicas or 0,
            "available": (d.status.ready_replicas or 0) > 0,
        }
    except ApiException as e:
        if e.status == 404:
            return {"ready_replicas": 0, "total_replicas": 0, "available": False}
        raise


def delete_app(safe_name: str) -> None:
    """Delete Deployment, Service, and Secret for an app (Ingress deleted by k8s_ingress_service)."""
    _load_k8s_config()
    apps_v1 = client.AppsV1Api()
    core_v1 = client.CoreV1Api()
    deployment_name = f"gk-app-{safe_name}"

    for fn, name in [
        (apps_v1.delete_namespaced_deployment, deployment_name),
        (core_v1.delete_namespaced_secret, f"{deployment_name}-secrets"),
    ]:
        try:
            fn(name, APPS_NAMESPACE)
        except ApiException as e:
            if e.status != 404:
                raise
