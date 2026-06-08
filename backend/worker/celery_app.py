from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "gatekeeperai",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.scanners.pipeline", "worker.deploy_task", "worker.sla_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-sla-deadlines": {
            "task": "worker.sla_task.check_sla_deadlines",
            "schedule": crontab(minute="*/15"),
        },
    },
)
