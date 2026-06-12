"""
Forward audit events to external logging platforms.

Each sink fires only when its config key is set. All sinks run in a
daemon thread so failures never affect the originating request.
"""
import json
import logging
import socket
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def forward_audit_event(event: dict) -> None:
    """Dispatch event to all configured sinks. Never raises, never blocks."""
    threading.Thread(target=_dispatch, args=(event,), daemon=True).start()


def _dispatch(event: dict) -> None:
    from app.config import settings

    if settings.LOG_FORWARD_WEBHOOK_URL:
        _send_webhook(event, settings.LOG_FORWARD_WEBHOOK_URL)

    if settings.LOG_FORWARD_SYSLOG_HOST:
        _send_syslog(
            event,
            settings.LOG_FORWARD_SYSLOG_HOST,
            settings.LOG_FORWARD_SYSLOG_PORT,
            settings.LOG_FORWARD_SYSLOG_PROTOCOL,
        )

    if settings.LOG_FORWARD_LOKI_URL:
        _send_loki(event, settings.LOG_FORWARD_LOKI_URL)

    if settings.LOG_FORWARD_CLOUDWATCH_LOG_GROUP:
        _send_cloudwatch(
            event,
            settings.LOG_FORWARD_CLOUDWATCH_LOG_GROUP,
            settings.LOG_FORWARD_CLOUDWATCH_LOG_STREAM,
            settings.LOG_FORWARD_CLOUDWATCH_REGION,
            settings.LOG_FORWARD_CLOUDWATCH_ACCESS_KEY,
            settings.LOG_FORWARD_CLOUDWATCH_SECRET_KEY,
        )


# ── Sinks ─────────────────────────────────────────────────────────────────────

def _send_webhook(event: dict, url: str) -> None:
    try:
        import httpx
        with httpx.Client(timeout=5) as client:
            client.post(url, json=event)
    except Exception as exc:
        logger.warning("log_forwarder: webhook failed: %s", exc)


def _send_syslog(event: dict, host: str, port: int, protocol: str) -> None:
    try:
        ts = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        hostname = socket.gethostname()
        # RFC 5424 — PRI 134 = facility local0 (16) + severity info (6)
        line = f"<134>1 {ts} {hostname} gatekeeperai - - - {json.dumps(event)}\n"
        raw = line.encode()

        if protocol.upper() == "TCP":
            with socket.create_connection((host, port), timeout=5) as s:
                s.sendall(raw)
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(raw, (host, port))
    except Exception as exc:
        logger.warning("log_forwarder: syslog failed: %s", exc)


def _send_loki(event: dict, url: str) -> None:
    try:
        import httpx
        ts_ns = str(int(datetime.now(timezone.utc).timestamp() * 1e9))
        payload = {
            "streams": [{
                "stream": {
                    "app": "gatekeeperai",
                    "action": event.get("action", "unknown"),
                    "event_type": event.get("event_type", "audit"),
                },
                "values": [[ts_ns, json.dumps(event)]],
            }]
        }
        with httpx.Client(timeout=5) as client:
            client.post(url, json=payload)
    except Exception as exc:
        logger.warning("log_forwarder: loki failed: %s", exc)


def _send_cloudwatch(
    event: dict,
    log_group: str,
    log_stream: str,
    region: str,
    access_key: str,
    secret_key: str,
) -> None:
    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client(
            "logs",
            region_name=region,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

        try:
            client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise

        ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        client.put_log_events(
            logGroupName=log_group,
            logStreamName=log_stream,
            logEvents=[{"timestamp": ts_ms, "message": json.dumps(event)}],
        )
    except ImportError:
        logger.warning("log_forwarder: boto3 not installed — CloudWatch sink skipped")
    except Exception as exc:
        logger.warning("log_forwarder: cloudwatch failed: %s", exc)
