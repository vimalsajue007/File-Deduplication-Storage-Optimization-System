"""Audit-log helper."""
from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    if get_settings().TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def record(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    request: Request | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id)[:255] if resource_id is not None else None,
        ip_address=client_ip(request),
        user_agent=(request.headers.get("user-agent", "")[:255] if request else None),
        details=details,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
