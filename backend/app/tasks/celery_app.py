from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dedupe",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,              # re-deliver if a worker dies mid-hash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,     # long hashing jobs: don't hoard tasks
    task_track_started=True,
    task_time_limit=60 * 60 * 3,
    task_soft_time_limit=60 * 60 * 3 - 60,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=False,
)
