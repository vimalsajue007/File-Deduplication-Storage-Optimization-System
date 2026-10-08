"""Celery tasks: hashing/duplicate detection runs here so the API never blocks."""
from __future__ import annotations

import logging

from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal
from app.services import dedupe
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="files.process_file",
    autoretry_for=(OperationalError,),   # transient DB errors only; file errors are recorded on the file
    retry_backoff=True,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 5},
)
def process_file_task(self, file_id: int) -> dict:
    with SessionLocal() as db:
        result = dedupe.process_file(db, file_id)
    if result is None:
        return {"file_id": file_id, "status": "missing"}
    return {
        "file_id": result.file_id,
        "status": result.status,
        "sha256": result.sha256,
        "group_id": result.group_id,
        "is_duplicate": result.is_duplicate,
    }


@celery_app.task(
    bind=True,
    name="files.rescan_user",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def rescan_user_task(self, user_id: int) -> dict:
    with SessionLocal() as db:
        return dedupe.rebuild_all_for_user(db, user_id)
