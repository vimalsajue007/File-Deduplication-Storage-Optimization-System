"""Duplicate-detection logic.

Two layers:

* **Pure functions** (``select_original``, ``calculate_group_stats``, ``find_duplicate_groups``)
  contain the rules and have no I/O, so they are trivial to unit-test.
* **Database functions** (``process_file``, ``rebuild_group``, ``rebuild_all_for_user``) apply
  those rules to stored files.

Rules
-----
* Files are duplicates when they belong to the same owner and have the same SHA-256 digest
  *and* size — filename, upload time and location are irrelevant.
* A group exists only while it has two or more files.
* The **original** is the earliest upload (ties broken by lowest id); every other file is a duplicate.
* Potential savings = size × (file_count − 1): the storage that would be freed by keeping one copy.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError

from app.core.config import get_settings
from app.db.base import utcnow
from app.models import (
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_READY,
    DuplicateGroup,
    File,
    FileHash,
)
from app.services.hashing import hash_file
from app.services.storage import resolve_storage_path

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- pure logic ----
class HasOrder(Protocol):
    id: int
    uploaded_at: datetime


T = TypeVar("T")


def select_original(files: Sequence[HasOrder]) -> HasOrder:
    """The earliest upload is the original; the id breaks ties deterministically."""
    if not files:
        raise ValueError("Cannot select an original from an empty group")
    return min(files, key=lambda f: (f.uploaded_at, f.id))


@dataclass(frozen=True)
class GroupStats:
    file_count: int
    file_size: int
    total_storage: int
    duplicate_count: int
    potential_savings: int


def calculate_group_stats(file_size: int, file_count: int) -> GroupStats:
    if file_size < 0 or file_count < 0:
        raise ValueError("file_size and file_count must be non-negative")
    duplicates = max(file_count - 1, 0)
    return GroupStats(
        file_count=file_count,
        file_size=file_size,
        total_storage=file_size * file_count,
        duplicate_count=duplicates,
        potential_savings=file_size * duplicates,
    )


def find_duplicate_groups(
    items: Iterable[T], key: Callable[[T], Hashable]
) -> dict[Hashable, list[T]]:
    """Bucket items by content key and keep only buckets with 2+ members."""
    buckets: dict[Hashable, list[T]] = defaultdict(list)
    for item in items:
        buckets[key(item)].append(item)
    return {k: v for k, v in buckets.items() if len(v) > 1}


# -------------------------------------------------------------- DB operations ----
@dataclass
class ProcessResult:
    file_id: int
    status: str
    sha256: str | None = None
    group_id: int | None = None
    is_duplicate: bool = False


def _fail(db: Session, file: File, message: str) -> ProcessResult:
    file.status = STATUS_FAILED
    file.status_message = message[:500]
    file.processed_at = utcnow()
    db.commit()
    logger.warning("File %s processing failed: %s", file.id, message)
    return ProcessResult(file_id=file.id, status=STATUS_FAILED)


def process_file(db: Session, file_id: int) -> ProcessResult | None:
    """Hash a stored file (streaming) and update its duplicate group.

    Idempotent: safe to re-run after a worker crash or from the 'reprocess' endpoint.
    Returns None if the file no longer exists (e.g. deleted while queued).
    """
    file = db.get(File, file_id)
    if file is None:
        logger.info("process_file: file %s no longer exists, skipping", file_id)
        return None

    file.status = STATUS_PROCESSING
    file.status_message = None
    db.commit()

    try:
        path = resolve_storage_path(file.storage_key)
        if not path.is_file():
            return _fail(db, file, "The stored file is missing on disk.")
        digest = hash_file(path, get_settings().hash_chunk_bytes)
        actual_size = path.stat().st_size
    except (OSError, ValueError) as exc:
        return _fail(db, file, f"Could not read the file: {exc}")

    try:
        record = file.file_hash or FileHash(file_id=file.id)
        previous_digest = record.sha256 if record.id else None
        record.owner_id = file.owner_id
        record.algorithm = "sha256"
        record.sha256 = digest
        record.size_bytes = actual_size
        record.computed_at = utcnow()
        if record.id is None:
            db.add(record)
        file.size_bytes = actual_size
        file.status = STATUS_READY
        file.processed_at = utcnow()
        db.commit()
    except (StaleDataError, ObjectDeletedError):
        db.rollback()
        logger.info("process_file: file %s was deleted while hashing", file_id)
        return None

    # If the content changed since the last hash, the old group must be refreshed too.
    if previous_digest and previous_digest != digest:
        rebuild_group_safe(db, file.owner_id, previous_digest)
    group = rebuild_group_safe(db, file.owner_id, digest)

    db.refresh(file)
    return ProcessResult(
        file_id=file.id,
        status=file.status,
        sha256=digest,
        group_id=group.id if group else None,
        is_duplicate=file.is_duplicate,
    )


def rebuild_group(db: Session, owner_id: int, digest: str) -> DuplicateGroup | None:
    """Recompute the duplicate group for ``digest``: membership, original and statistics.

    Returns the group, or None when fewer than two files share the content (the group is
    removed and any remaining file is marked as unique). Caller commits.
    """
    files = db.scalars(
        select(File)
        .join(FileHash, FileHash.file_id == File.id)
        .where(File.owner_id == owner_id, FileHash.sha256 == digest, File.status == STATUS_READY)
        .order_by(File.uploaded_at, File.id)
    ).all()

    group = db.scalar(
        select(DuplicateGroup)
        .where(DuplicateGroup.owner_id == owner_id, DuplicateGroup.content_hash == digest)
        .with_for_update()
    )

    if len(files) < 2:
        for f in files:
            f.is_duplicate = False
            f.duplicate_group_id = None
        if group is not None:
            db.flush()
            db.delete(group)
        db.flush()
        return None

    original = select_original(files)
    stats = calculate_group_stats(original.size_bytes, len(files))

    if group is None:
        group = DuplicateGroup(owner_id=owner_id, content_hash=digest, file_size=stats.file_size)
        db.add(group)
        db.flush()  # may raise IntegrityError if a concurrent worker created it first

    group.file_size = stats.file_size
    group.file_count = stats.file_count
    group.total_storage = stats.total_storage
    group.potential_savings = stats.potential_savings
    group.original_file_id = original.id
    db.flush()

    for f in files:
        f.duplicate_group_id = group.id
        f.is_duplicate = f.id != original.id
    db.flush()
    return group


def rebuild_group_safe(db: Session, owner_id: int, digest: str, attempts: int = 3) -> DuplicateGroup | None:
    """``rebuild_group`` + commit, retrying when two workers race to create the same group."""
    for attempt in range(1, attempts + 1):
        try:
            group = rebuild_group(db, owner_id, digest)
            db.commit()
            return group
        except IntegrityError:
            db.rollback()
            logger.info("Concurrent group creation for %s (attempt %s/%s)", digest[:12], attempt, attempts)
    raise RuntimeError(f"Could not rebuild duplicate group {digest[:12]} after {attempts} attempts")


def rebuild_all_for_user(db: Session, owner_id: int) -> dict[str, int]:
    """Full re-scan: recompute every duplicate group for a user."""
    digests = set(
        db.scalars(
            select(FileHash.sha256)
            .join(File, File.id == FileHash.file_id)
            .where(File.owner_id == owner_id, File.status == STATUS_READY)
        ).all()
    )
    stale = db.scalars(
        select(DuplicateGroup).where(DuplicateGroup.owner_id == owner_id)
    ).all()
    digests.update(g.content_hash for g in stale)

    groups = 0
    for digest in digests:
        if rebuild_group_safe(db, owner_id, digest):
            groups += 1
    logger.info("Re-scan for user %s: %s hashes checked, %s duplicate groups", owner_id, len(digests), groups)
    return {"hashes_checked": len(digests), "duplicate_groups": groups}


def load_group_files(db: Session, group_ids: Sequence[int]) -> dict[int, list[File]]:
    """Fetch the files of several groups in one query (original first)."""
    if not group_ids:
        return {}
    rows = db.scalars(
        select(File)
        .where(File.duplicate_group_id.in_(group_ids))
        .options(selectinload(File.file_hash))
        .order_by(File.uploaded_at, File.id)
    ).all()
    result: dict[int, list[File]] = defaultdict(list)
    for f in rows:
        result[f.duplicate_group_id].append(f)  # type: ignore[index]
    return result
