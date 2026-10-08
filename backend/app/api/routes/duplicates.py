import math
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models import DuplicateGroup, File, User
from app.schemas import CleanupRequest, DeletionResult, DuplicateGroupOut, FileOut, Page
from app.services import audit, dedupe, file_service
from app.tasks.tasks import rescan_user_task

router = APIRouter(prefix="/duplicates", tags=["Duplicates"])

_SORTS = {
    "savings": DuplicateGroup.potential_savings.desc(),
    "size": DuplicateGroup.file_size.desc(),
    "count": DuplicateGroup.file_count.desc(),
    "recent": DuplicateGroup.updated_at.desc(),
}


def _to_out(group: DuplicateGroup, files: list[File]) -> DuplicateGroupOut:
    original = next((f for f in files if f.id == group.original_file_id), None)
    duplicates = [f for f in files if f.id != group.original_file_id]
    return DuplicateGroupOut(
        id=group.id,
        content_hash=group.content_hash,
        file_size=group.file_size,
        file_count=group.file_count,
        total_storage=group.total_storage,
        potential_savings=group.potential_savings,
        original=FileOut.model_validate(original) if original else None,
        duplicates=[FileOut.model_validate(f) for f in duplicates],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _get_group(db: Session, user_id: int, group_id: int) -> DuplicateGroup:
    group = db.scalar(select(DuplicateGroup).where(DuplicateGroup.id == group_id, DuplicateGroup.owner_id == user_id))
    if group is None:
        raise NotFoundError("That duplicate group does not exist.")
    return group


@router.get("/groups", response_model=Page[DuplicateGroupOut], summary="List duplicate groups")
def list_groups(
    sort_by: Literal["savings", "size", "count", "recent"] = Query("savings"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[DuplicateGroupOut]:
    base = select(DuplicateGroup).where(DuplicateGroup.owner_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    groups = db.scalars(
        base.order_by(_SORTS[sort_by], DuplicateGroup.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    files_by_group = dedupe.load_group_files(db, [g.id for g in groups])
    return Page[DuplicateGroupOut](
        items=[_to_out(g, files_by_group.get(g.id, [])) for g in groups],
        total=total, page=page, page_size=page_size, pages=max(math.ceil(total / page_size), 1),
    )


@router.get("/groups/{group_id}", response_model=DuplicateGroupOut, summary="One duplicate group")
def get_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DuplicateGroupOut:
    group = _get_group(db, user.id, group_id)
    return _to_out(group, dedupe.load_group_files(db, [group.id]).get(group.id, []))


@router.post(
    "/groups/{group_id}/cleanup",
    response_model=DeletionResult,
    summary="Delete every unprotected duplicate in a group, keeping the original",
)
def cleanup_group(
    group_id: int, payload: CleanupRequest, request: Request,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict:
    group = _get_group(db, user.id, group_id)
    duplicate_ids = list(
        db.scalars(
            select(File.id).where(File.duplicate_group_id == group.id, File.id != group.original_file_id)
        ).all()
    )
    if not duplicate_ids:
        return {"deleted_ids": [], "deleted_count": 0, "freed_bytes": 0, "redundant_bytes_removed": 0, "skipped_protected_ids": []}
    return file_service.delete_files(
        db, user, duplicate_ids, confirm=payload.confirm, reason=payload.reason or "Duplicate clean-up",
        request=request, skip_protected=True,
    )


@router.post("/rescan", status_code=202, summary="Re-scan all your files for duplicates (background job)")
def rescan(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    audit.record(db, "duplicates.rescan", user_id=user.id, request=request, commit=True)
    try:
        task = rescan_user_task.delay(user.id)
    except Exception:  # noqa: BLE001
        return {"queued": False, "task_id": None}
    return {"queued": True, "task_id": task.id}
