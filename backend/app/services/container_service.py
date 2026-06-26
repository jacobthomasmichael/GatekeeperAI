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

    # Remove any existing container with this name before starting the new one.
    # For updates this replaces the running container; for retries it clears orphans.
    try:
        client.containers.get(container_name).remove(force=True)
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
        # Drop all Linux capabilities — submitted apps get no elevated privileges.
        cap_drop=["ALL"],
        # Prevent setuid/setgid binaries from re-acquiring privileges at runtime.
        security_opt=["no-new-privileges:true"],
        # Read-only root filesystem; /tmp is writable via tmpfs (covers HOME=/tmp,
        # Streamlit cache, Gradio temp files, etc.).
        read_only=True,
        tmpfs={"/tmp": "size=128m,mode=1777"},
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


def get_container_health(container_id: str, log_tail: int = 30) -> dict:
    """Return live status, restart count, and recent logs (when crashing)."""
    client = _client()
    try:
        container = client.containers.get(container_id)
        status = container.status
        restart_count = container.attrs.get("RestartCount", 0)
        logs = None
        if status in ("restarting", "exited", "dead"):
            logs = container.logs(tail=log_tail, timestamps=False).decode(errors="replace")
        return {"status": status, "restart_count": restart_count, "logs": logs}
    except NotFound:
        return {"status": "removed", "restart_count": 0, "logs": None}


def get_container_logs(container_id: str, tail: int = 200) -> str:
    client = _client()
    try:
        container = client.containers.get(container_id)
        return container.logs(tail=tail, timestamps=True).decode(errors="replace")
    except NotFound:
        return ""


def pick_external_port(base: int = 8600) -> int:
    """Find the next host port in 8600-9000 not already bound by a container.

    Queries Docker directly — socket.bind() inside the worker container cannot
    see host-level port allocations, so it would always return 8600.
    """
    client = _client()
    used: set[int] = set()
    for c in client.containers.list():
        for bindings in (c.ports or {}).values():
            for b in (bindings or []):
                try:
                    used.add(int(b["HostPort"]))
                except (KeyError, ValueError):
                    pass

    with _port_lock:
        for port in range(base, 9000):
            if port not in used:
                return port
    raise RuntimeError("No free ports available in range 8600-9000")
