import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_NGINX_APPS_DIR = Path("/nginx-apps")


def write_app_config(safe_name: str, external_port: int, visibility: str = "private") -> str:
    """Write a per-app nginx location block and reload nginx. Returns the public URL."""
    public_url = f"{settings.APP_BASE_URL}/apps/{safe_name}/"

    if not _NGINX_APPS_DIR.exists():
        return public_url

    base = f"/apps/{safe_name}"
    shim = (
        f"<base href=\"{base}/\">"
        f"<script>(function(){{"
        f"var B=\"{base}\";"
        f"function p(u){{return typeof u===\"string\"&&u.startsWith(\"/\")&&!u.startsWith(B)?B+u:u}}"
        f"var f=window.fetch;window.fetch=function(u,o){{return f.call(this,p(u),o)}};"
        f"var x=XMLHttpRequest.prototype.open;"
        f"XMLHttpRequest.prototype.open=function(m,u,a,b,c){{return x.call(this,m,p(u),a,b,c)}}"
        f"}})()</script>"
    )

    auth_block = ""
    if visibility != "public":
        auth_block = (
            f"    auth_request /api/v1/auth/verify;\n"
            f"    error_page 401 = @app_login_redirect;\n"
        )

    conf = (
        f"location /apps/{safe_name}/ {{\n"
        f"{auth_block}"
        f"    proxy_pass http://host.docker.internal:{external_port}/;\n"
        f"    proxy_http_version 1.1;\n"
        f"    proxy_set_header Upgrade $http_upgrade;\n"
        f"    proxy_set_header Connection \"upgrade\";\n"
        f"    proxy_set_header Host $host;\n"
        f"    proxy_set_header X-Real-IP $remote_addr;\n"
        f"    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        f"    proxy_set_header X-Forwarded-Proto https;\n"
        f"    proxy_set_header Accept-Encoding \"\";\n"
        f"    proxy_read_timeout 60s;\n"
        f"    sub_filter_once on;\n"
        f"    sub_filter_types text/html;\n"
        f"    sub_filter '<head>' '<head>{shim}';\n"
        f"}}\n"
    )
    (_NGINX_APPS_DIR / f"{safe_name}.conf").write_text(conf)
    reload_nginx()
    return public_url


def remove_app_config(safe_name: str) -> None:
    if not _NGINX_APPS_DIR.exists():
        return
    (_NGINX_APPS_DIR / f"{safe_name}.conf").unlink(missing_ok=True)
    reload_nginx()


def reload_nginx() -> None:
    try:
        import docker as _docker
        nginx = _docker.from_env().containers.get("infra-nginx")
        nginx.exec_run("nginx -s reload")
    except Exception as e:
        logger.warning("nginx reload skipped: %s", e)
