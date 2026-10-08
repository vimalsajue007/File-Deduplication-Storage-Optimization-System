"""File queries and the safe-deletion workflow."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import Request
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    ConfirmationRequiredError,
    NotFoundError,
    ProtectedFileError,
)
from app.models import DeletionHistory, DuplicateGroup, File, User
from app.services import audit, storage
from app.services.dedupe import rebuild_group

logger = logging.getLogger(__name__)

SORT_COLUMNS = {
    "name": File.original_filename,
    "size": File.size_bytes,
    "uploaded_at": File.uploaded_at,
    "type": File.category,
}


# ---------------------------------------------------------------- listing ----
@dataclass
class FileFilters:
    q: str | None = None
    file_type: str | None = None
    extension: str | None = None
    min_size: int | None = None
    max_size: int | None = None
    duplicates: Literal["all", "any", "copies", "unique"] = "all"
    uploaded_from: date | None = None
    uploaded_to: date | None = None
    status: str | None = None
    sort_by: str = "uploaded_at"
    sort_order: Literal["asc", "desc"] = "desc"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def apply_filters(stmt: Select, owner_id: int, f: FileFilters) -> Select:
    stmt = stmt.where(File.owner_id == owner_id)
    if f.q:
        stmt = stmt.where(File.original_filename.ilike(f"%{_escape_like(f.q.strip())}%", escape="\\"))
    if f.file_type:
        stmt = stmt.where(File.category == f.file_type)
    if f.extension:
        stmt = stmt.where(File.extension == f.extension.lower().lstrip("."))
    if f.min_size is not None:
        stmt = stmt.where(File.size_bytes >= f.min_size)
    if f.max_size is not None:
        stmt = stmt.where(File.size_bytes <= f.max_size)
    if f.duplicates == "any":
        stmt = stmt.where(File.duplicate_group_id.is_not(None))
    elif f.duplicates == "copies":
        stmt = stmt.where(File.is_duplicate.is_(True))
    elif f.duplicates == "unique":
        stmt = stmt.where(File.duplicate_group_id.is_(None))
    if f.uploaded_from:
        stmt = stmt.where(File.uploaded_at >= datetime.combine(f.uploaded_from, time.min))
    if f.uploaded_to:  # inclusive of the whole end day
        stmt = stmt.where(File.uploaded_at < datetime.combine(f.uploaded_to + timedelta(days=1), time.min))
    if f.status:
        stmt = stmt.where(File.status == f.status)
    return stmt


def list_files(db: Session, owner_id: int, f: FileFilters, page: int, page_size: int) -> tuple[list[File], int]:
    base = apply_filters(select(File), owner_id, f)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    column = SORT_COLUMNS.get(f.sort_by, File.uploaded_at)
    order = column.asc() if f.sort_order == "asc" else column.desc()
    rows = db.scalars(
        base.options(selectinload(File.file_hash))
        .order_by(order, File.id.desc())  # id keeps pagination stable when values tie
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), total


def get_owned_file(db: Session, owner_id: int, file_id: int) -> File:
    """Other users' files are reported as 'not found' so their existence is not revealed."""
    file = db.scalar(
        select(File)
        .where(File.id == file_id, File.owner_id == owner_id)
        .options(selectinload(File.file_hash), selectinload(File.file_metadata))
    )
    if file is None:
        raise NotFoundError("That file does not exist.")
    return file


# --------------------------------------------------------------- deletion ----
def _load_owned_files(db: Session, owner_id: int, file_ids: list[int]) -> list[File]:
    ids = list(dict.fromkeys(file_ids))
    files = db.scalars(
        select(File).where(File.owner_id == owner_id, File.id.in_(ids)).options(selectinload(File.file_hash))
    ).all()
    missing = sorted(set(ids) - {f.id for f in files})
    if missing:
        raise NotFoundError("Some selected files do not exist.", details={"missing_ids": missing})
    return list(files)


@dataclass
class _GroupContext:
    totals: dict[int, int]
    originals: dict[int, int | None]
    sizes: dict[int, int]
    selected: Counter


def _group_context(db: Session, files: list[File]) -> _GroupContext:
    group_ids = {f.duplicate_group_id for f in files if f.duplicate_group_id}
    totals: dict[int, int] = {}
    originals: dict[int, int | None] = {}
    sizes: dict[int, int] = {}
    if group_ids:
        for gid, count in db.execute(
            select(File.duplicate_group_id, func.count()).where(File.duplicate_group_id.in_(group_ids)).group_by(File.duplicate_group_id)
        ):
            totals[gid] = count
        for g in db.scalars(select(DuplicateGroup).where(DuplicateGroup.id.in_(group_ids))):
            originals[g.id] = g.original_file_id
            sizes[g.id] = g.file_size
    selected = Counter(f.duplicate_group_id for f in files if f.duplicate_group_id)
    return _GroupContext(totals, originals, sizes, selected)


def _redundant_bytes(ctx: _GroupContext) -> int:
    """Storage that is genuinely redundant: copies removed while at least one copy is kept."""
    total = 0
    for gid, selected in ctx.selected.items():
        removable = min(selected, ctx.totals.get(gid, 0) - 1)
        if removable > 0:
            total += removable * ctx.sizes.get(gid, 0)
    return total


def build_deletion_preview(db: Session, owner_id: int, file_ids: list[int]) -> dict:
    files = _load_owned_files(db, owner_id, file_ids)
    ctx = _group_context(db, files)

    items, warnings = [], []
    for f in files:
        gid = f.duplicate_group_id
        total = ctx.totals.get(gid, 1) if gid else 1
        remaining = (total - ctx.selected[gid]) if gid else 0
        is_original = bool(gid) and ctx.originals.get(gid) == f.id
        items.append(
            {
                "id": f.id,
                "filename": f.original_filename,
                "size_bytes": f.size_bytes,
                "is_protected": f.is_protected,
                "is_duplicate": f.is_duplicate,
                "is_original": is_original,
                "duplicate_group_id": gid,
                "copies_remaining": max(remaining, 0),
            }
        )
        if gid is None:
            warnings.append(f"“{f.original_filename}” has no duplicates — deleting it removes your only copy.")
        elif remaining <= 0:
            warnings.append(f"Every copy of “{f.original_filename}” is selected — no copy will be kept.")
        elif is_original:
            warnings.append(
                f"“{f.original_filename}” is the original. The oldest remaining copy becomes the new original."
            )

    protected_ids = [f.id for f in files if f.is_protected]
    return {
        "items": items,
        "total_bytes": sum(f.size_bytes for f in files),
        "redundant_bytes_removed": _redundant_bytes(ctx),
        "protected_ids": protected_ids,
        "warnings": list(dict.fromkeys(warnings)),
        "can_delete": not protected_ids,
    }


def delete_files(
    db: Session,
    user: User,
    file_ids: list[int],
    *,
    confirm: bool,
    reason: str | None = None,
    request: Request | None = None,
    skip_protected: bool = False,
) -> dict:
    """Delete files after explicit confirmation, recording history and audit entries.

    Protected files are never deleted: they abort the request, unless ``skip_protected``
    is set (used by group clean-up, which reports what it skipped).
    """
    if not confirm:
        raise ConfirmationRequiredError("Deletion must be confirmed explicitly (confirm=true).")

    files = _load_owned_files(db, user.id, file_ids)
    protected = [f for f in files if f.is_protected]
    if protected and not skip_protected:
        raise ProtectedFileError(
            "Protected files cannot be deleted. Remove their protection first.",
            details={"protected_ids": [f.id for f in protected], "filenames": [f.original_filename for f in protected]},
        )
    targets = [f for f in files if not f.is_protected]
    if not targets:
        return {
            "deleted_ids": [], "deleted_count": 0, "freed_bytes": 0, "redundant_bytes_removed": 0,
            "skipped_protected_ids": [f.id for f in protected],
        }

    ctx = _group_context(db, targets)
    redundant = _redundant_bytes(ctx)
    storage_keys: list[str] = []
    digests: set[str] = set()

    for f in targets:
        gid = f.duplicate_group_id
        db.add(
            DeletionHistory(
                user_id=user.id,
                file_id=f.id,
                filename=f.original_filename,
                size_bytes=f.size_bytes,
                content_hash=f.content_hash,
                category=f.category,
                was_duplicate=f.is_duplicate,
                was_original=bool(gid) and ctx.originals.get(gid) == f.id,
                duplicate_group_id=gid,
                reason=reason,
            )
        )
        if f.content_hash:
            digests.add(f.content_hash)
        storage_keys.append(f.storage_key)
        db.delete(f)
    db.flush()

    # Re-elect originals / dissolve groups that dropped below two files.
    for digest in digests:
        rebuild_group(db, user.id, digest)

    freed = sum(f.size_bytes for f in targets)
    audit.record(
        db, "file.delete", user_id=user.id, request=request, resource_type="file",
        resource_id=",".join(str(f.id) for f in targets)[:255],
        details={"count": len(targets), "freed_bytes": freed, "reason": reason, "files": [f.original_filename for f in targets][:50]},
    )
    db.commit()

    # Remove bytes from disk only after the database commit succeeded.
    for key in storage_keys:
        storage.delete_physical(key)

    logger.info("User %s deleted %s file(s), freed %s bytes", user.id, len(targets), freed)
    return {
        "deleted_ids": [f.id for f in targets],
        "deleted_count": len(targets),
        "freed_bytes": freed,
        "redundant_bytes_removed": redundant,
        "skipped_protected_ids": [f.id for f in protected],
    }
