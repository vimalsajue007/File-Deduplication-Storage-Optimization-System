from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.base import utcnow
from app.db.session import get_db
from app.models import STATUS_PENDING, STATUS_PROCESSING, DuplicateGroup, File, User
from app.schemas import AnalyticsSummary, CategoryUsage, FileOut, TimelinePoint

router = APIRouter(prefix="/analytics", tags=["Analytics"])

TIMELINE_DAYS = 14


@router.get("/summary", response_model=AnalyticsSummary, summary="Dashboard statistics")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AnalyticsSummary:
    total_files, total_storage = db.execute(
        select(func.count(File.id), func.coalesce(func.sum(File.size_bytes), 0)).where(File.owner_id == user.id)
    ).one()

    duplicate_files = db.scalar(
        select(func.count(File.id)).where(File.owner_id == user.id, File.is_duplicate.is_(True))
    ) or 0
    in_groups, group_count, group_storage, savings = db.execute(
        select(
            func.coalesce(func.sum(DuplicateGroup.file_count), 0),
            func.count(DuplicateGroup.id),
            func.coalesce(func.sum(DuplicateGroup.total_storage), 0),
            func.coalesce(func.sum(DuplicateGroup.potential_savings), 0),
        ).where(DuplicateGroup.owner_id == user.id)
    ).one()

    pending = db.scalar(
        select(func.count(File.id)).where(File.owner_id == user.id, File.status.in_([STATUS_PENDING, STATUS_PROCESSING]))
    ) or 0

    categories = [
        CategoryUsage(category=c, count=n, bytes=int(b))
        for c, n, b in db.execute(
            select(File.category, func.count(File.id), func.coalesce(func.sum(File.size_bytes), 0))
            .where(File.owner_id == user.id)
            .group_by(File.category)
            .order_by(func.sum(File.size_bytes).desc())
        )
    ]

    since = (utcnow() - timedelta(days=TIMELINE_DAYS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day = func.date(File.uploaded_at)
    per_day = {
        str(d): (n, int(b))
        for d, n, b in db.execute(
            select(day, func.count(File.id), func.coalesce(func.sum(File.size_bytes), 0))
            .where(File.owner_id == user.id, File.uploaded_at >= since)
            .group_by(day)
        )
    }
    timeline = []
    for i in range(TIMELINE_DAYS):
        d = (since + timedelta(days=i)).date().isoformat()
        count, size = per_day.get(d, (0, 0))
        timeline.append(TimelinePoint(date=d, count=count, bytes=size))

    largest = db.scalars(
        select(File).where(File.owner_id == user.id).options(selectinload(File.file_hash))
        .order_by(File.size_bytes.desc(), File.id.desc()).limit(8)
    ).all()
    recent = db.scalars(
        select(File).where(File.owner_id == user.id).options(selectinload(File.file_hash))
        .order_by(File.uploaded_at.desc(), File.id.desc()).limit(8)
    ).all()

    total_storage = int(total_storage)
    savings = int(savings)
    return AnalyticsSummary(
        total_files=total_files,
        total_storage=total_storage,
        duplicate_files=duplicate_files,
        files_in_duplicate_groups=int(in_groups),
        duplicate_groups=group_count,
        duplicate_storage=int(group_storage),
        potential_savings=savings,
        savings_percent=round(savings / total_storage * 100, 1) if total_storage else 0.0,
        pending_files=pending,
        storage_by_category=categories,
        uploads_timeline=timeline,
        largest_files=[FileOut.model_validate(f) for f in largest],
        recent_uploads=[FileOut.model_validate(f) for f in recent],
    )
