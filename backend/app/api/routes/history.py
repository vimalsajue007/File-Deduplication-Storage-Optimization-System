import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AuditLog, DeletionHistory, User
from app.schemas import AuditLogOut, DeletionHistoryOut, Page

router = APIRouter(prefix="/history", tags=["History & Audit"])


@router.get("/deletions", response_model=Page[DeletionHistoryOut], summary="Deletion history")
def deletions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[DeletionHistoryOut]:
    base = select(DeletionHistory).where(DeletionHistory.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(DeletionHistory.deleted_at.desc(), DeletionHistory.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[DeletionHistoryOut](
        items=[DeletionHistoryOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, pages=max(math.ceil(total / page_size), 1),
    )


@router.get("/audit", response_model=Page[AuditLogOut], summary="Audit log (admins can see all users)")
def audit_logs(
    all_users: bool = Query(False, description="Admins only"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[AuditLogOut]:
    base = select(AuditLog)
    if not (all_users and user.is_admin):
        base = base.where(AuditLog.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, pages=max(math.ceil(total / page_size), 1),
    )
