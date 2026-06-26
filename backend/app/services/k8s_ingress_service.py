"""
Kubernetes Ingress and Service management for deployed apps.
Only used when DEPLOY_BACKEND=kubernetes. The Docker path continues to use nginx_service.py.
"""
import logging
from kubernetes import client, config as k8s_config
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

APPS_NAMESPACE = "gatekeeperai-apps"


def _load_k8s_config() -> None:
    """Load in-cluster config when running in a pod, fall back to kubeconfig for local dev."""
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def write_app_ingress(
    safe_name: str,
    internal_port: int,
    app_base_url: str,
    visibility: str = "private",
) -> None:
    """
    Create or update the Ingress + ClusterIP Service for a deployed app.

    For private/restricted apps, nginx-ingress auth-url annotation gates every request
    through the GatekeeperAI verify endpoint — same behaviour as the nginx auth_request
    directive in the Docker path.

    For public apps (visibility="public"), auth annotations are omitted.
    """
    _load_k8s_config()
    networking_v1 = client.NetworkingV1Api()
    core_v1 = client.CoreV1Api()

    service_name = f"gk-app-{safe_name}"
    ingress_name = f"gk-app-{safe_name}"

    # Parse hostname from app_base_url (strip scheme)
    from urllib.parse import urlparse
    hostname = urlparse(app_base_url).hostname or app_base_url

    # --- ClusterIP Service ---
    # Points to pods with label app=gk-app-{safe_name} (created in Phase 3).
    # In Phase 2 this service is created but has no pods behind it yet — that's fine,
    # nginx-ingress will return 502 until Phase 3 creates the pods.
    service_body = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace=APPS_NAMESPACE,
            labels={"managed-by": "gatekeeperai", "app": service_name},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": service_name},
            ports=[client.V1ServicePort(port=internal_port, target_port=internal_port)],
            type="ClusterIP",
        ),
    )

    try:
        core_v1.read_namespaced_service(service_name, APPS_NAMESPACE)
        core_v1.replace_namespaced_service(service_name, APPS_NAMESPACE, service_body)
        logger.info("Updated K8s Service for app %s", safe_name)
    except ApiException as e:
        if e.status == 404:
            core_v1.create_namespaced_service(APPS_NAMESPACE, service_body)
            logger.info("Created K8s Service for app %s", safe_name)
        else:
            raise

    # --- Ingress annotations ---
    annotations = {
        "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
        # Inject correct base href so relative assets resolve under /apps/{safe_name}/
        "nginx.ingress.kubernetes.io/configuration-snippet": (
            f'sub_filter \'<head>\' \'<head><base href="/apps/{safe_name}/">\';'
            "sub_filter_once on;"
        ),
    }

    if visibility != "public":
        annotations.update({
            "nginx.ingress.kubernetes.io/auth-url": (
                f"https://{hostname}/api/v1/auth/verify?app={safe_name}"
            ),
            "nginx.ingress.kubernetes.io/auth-signin": (
                f"https://{hostname}/login?next=$escaped_request_uri"
            ),
            "nginx.ingress.kubernetes.io/auth-response-headers": "X-Auth-User",
        })

    # --- Ingress resource ---
    ingress_body = client.V1Ingress(
        metadata=client.V1ObjectMeta(
            name=ingress_name,
            namespace=APPS_NAMESPACE,
            annotations=annotations,
            labels={"managed-by": "gatekeeperai", "app": service_name},
        ),
        spec=client.V1IngressSpec(
            ingress_class_name="nginx",
            rules=[
                client.V1IngressRule(
                    host=hostname,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                # Capture group (/apps/{name}/)(...) so rewrite-target strips prefix
                                path=f"/apps/{safe_name}(/|$)(.*)",
                                path_type="ImplementationSpecific",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=service_name,
                                        port=client.V1ServiceBackendPort(number=internal_port),
                                    )
                                ),
                            )
                        ]
                    ),
                )
            ],
        ),
    )

    try:
        networking_v1.read_namespaced_ingress(ingress_name, APPS_NAMESPACE)
        networking_v1.replace_namespaced_ingress(ingress_name, APPS_NAMESPACE, ingress_body)
        logger.info("Updated K8s Ingress for app %s", safe_name)
    except ApiException as e:
        if e.status == 404:
            networking_v1.create_namespaced_ingress(APPS_NAMESPACE, ingress_body)
            logger.info("Created K8s Ingress for app %s", safe_name)
        else:
            raise


def remove_app_ingress(safe_name: str) -> None:
    """Delete the Ingress and ClusterIP Service for an app."""
    _load_k8s_config()
    networking_v1 = client.NetworkingV1Api()
    core_v1 = client.CoreV1Api()

    ingress_name = f"gk-app-{safe_name}"
    service_name = f"gk-app-{safe_name}"

    for delete_fn, resource, name in [
        (networking_v1.delete_namespaced_ingress, "Ingress", ingress_name),
        (core_v1.delete_namespaced_service, "Service", service_name),
    ]:
        try:
            delete_fn(name, APPS_NAMESPACE)
            logger.info("Deleted K8s %s for app %s", resource, safe_name)
        except ApiException as e:
            if e.status != 404:
                raise
