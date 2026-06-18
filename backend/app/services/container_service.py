import logging
import threading
from pathlib import Path

import docker
from docker.errors import DockerException, NotFound
from docker.models.containers import Container

logger = logging.getLogger(__name__)
_port_lock = threading.Lock()

_DEFAULT_MEMORY = "512m"
_DEFAULT_CPU = 0.5  # cpus quota


def _client() -> docker.DockerClient:
    return docker.from_env()


def build_image(build_path: str, image_tag: str) -> str:
    """Build a Docker image from build_path and return the image ID."""
    client = _client()
    image, logs = client.images.build(
        path=build_path,
        tag=image_tag,
        rm=True,
        forcerm=True,
    )
    for chunk in logs:
        if "stream" in chunk:
            logger.debug("docker build: %s", chunk["stream"].strip())
    return image.id


def start_container(
    image_tag: str,
    container_name: str,
    internal_port: int,
    external_port: int,
    env_vars: dict[str, str],
    allowed_egress_urls: list[str],
) -> Container:
    """Start a container and return the Container object."""
    client = _client()

    # Remove any stopped container with the same name left by a previous failed attempt
    try:
        existing = client.containers.get(container_name)
        if existing.status != "running":
            existing.remove(force=True)
    except Exception:
        pass

    ports = {f"{internal_port}/tcp": external_port}

    container = client.containers.run(
        image_tag,
        name=container_name,
        detach=True,
        ports=ports,
        environment=env_vars,
        mem_limit=_DEFAULT_MEMORY,
        nano_cpus=int(_DEFAULT_CPU * 1e9),
        restart_policy={"Name": "unless-stopped"},
        labels={
            "managed-by": "gatekeeperai",
            "allowed-egress": ",".join(allowed_egress_urls),
        },
    )
    return container


def stop_container(container_id: str) -> None:
    client = _client()
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=10)
        container.remove()
    except NotFound:
        pass


def get_container_status(container_id: str) -> str:
    client = _client()
    try:
        container = client.containers.get(container_id)
        return container.status
    except NotFound:
        return "removed"


def get_container_logs(container_id: str, tail: int = 200) -> str:
    client = _client()
    try:
        container = client.containers.get(container_id)
        return container.logs(tail=tail, timestamps=True).decode(errors="replace")
    except NotFound:
        return ""


def pick_external_port(base: int = 8600) -> int:
    """Find the next unused port starting from base.

    The threading lock prevents two concurrent calls within the same process
    from racing to the same port. Cross-process races (multiple Celery workers)
    are handled by the docker-start error path in deploy_task.
    """
    import socket
    with _port_lock:
        for port in range(base, 9000):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("0.0.0.0", port))
                    return port
                except OSError:
                    continue
    raise RuntimeError("No free ports available in range 8600-9000")
