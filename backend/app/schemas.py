"""Pydantic request/response schemas."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator


def _to_utc_iso(value: datetime) -> str:
    # DB timestamps are naive UTC; make that explicit for API consumers.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


UTCDateTime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=str, when_used="json")]

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------- auth ----
class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", v):
            raise ValueError("Use letters, numbers, dots, dashes or underscores only")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class UserOut(ORMModel):
    id: int
    email: EmailStr
    username: str
    is_admin: bool
    created_at: UTCDateTime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# --------------------------------------------------------------- files ----
class FileMetadataOut(ORMModel):
    extension: str
    declared_mime: str | None
    detected_mime: str
    signature: str | None
    is_text: bool
    extra: dict | None


class FileOut(ORMModel):
    id: int
    original_filename: str
    size_bytes: int
    mime_type: str
    extension: str
    category: str
    status: str
    status_message: str | None
    is_protected: bool
    is_duplicate: bool
    duplicate_group_id: int | None
    content_hash: str | None
    uploaded_at: UTCDateTime
    processed_at: UTCDateTime | None


class GroupBrief(BaseModel):
    id: int
    file_count: int
    original_file_id: int | None
    original_filename: str | None
    potential_savings: int


class FileDetail(FileOut):
    file_metadata: FileMetadataOut | None
    group: GroupBrief | None = None


class UploadRejected(BaseModel):
    filename: str
    reason: str


class UploadResponse(BaseModel):
    uploaded: list[FileOut]
    rejected: list[UploadRejected]
    queued: bool


class ProtectionUpdate(BaseModel):
    is_protected: bool


# ------------------------------------------------------------ deletion ----
class DeletionPreviewRequest(BaseModel):
    file_ids: list[int] = Field(min_length=1, max_length=500)


class DeletionPreviewItem(BaseModel):
    id: int
    filename: str
    size_bytes: int
    is_protected: bool
    is_duplicate: bool
    is_original: bool
    duplicate_group_id: int | None
    copies_remaining: int


class DeletionPreview(BaseModel):
    items: list[DeletionPreviewItem]
    total_bytes: int
    redundant_bytes_removed: int
    protected_ids: list[int]
    warnings: list[str]
    can_delete: bool


class BulkDeleteRequest(BaseModel):
    file_ids: list[int] = Field(min_length=1, max_length=500)
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=255)


class CleanupRequest(BaseModel):
    confirm: bool = False
    reason: str | None = Field(default=None, max_length=255)


class DeletionResult(BaseModel):
    deleted_ids: list[int]
    deleted_count: int
    freed_bytes: int
    redundant_bytes_removed: int
    skipped_protected_ids: list[int] = []


# ----------------------------------------------------------- duplicates ----
class DuplicateGroupOut(BaseModel):
    id: int
    content_hash: str
    file_size: int
    file_count: int
    total_storage: int
    potential_savings: int
    original: FileOut | None
    duplicates: list[FileOut]
    created_at: UTCDateTime
    updated_at: UTCDateTime


# ------------------------------------------------------------- history ----
class DeletionHistoryOut(ORMModel):
    id: int
    file_id: int | None
    filename: str
    size_bytes: int
    content_hash: str | None
    category: str
    was_duplicate: bool
    was_original: bool
    duplicate_group_id: int | None
    reason: str | None
    deleted_at: UTCDateTime


class AuditLogOut(ORMModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    details: dict | None
    created_at: UTCDateTime


# ----------------------------------------------------------- analytics ----
class CategoryUsage(BaseModel):
    category: str
    count: int
    bytes: int


class TimelinePoint(BaseModel):
    date: str
    count: int
    bytes: int


class AnalyticsSummary(BaseModel):
    total_files: int
    total_storage: int
    duplicate_files: int          # redundant copies (everything except each group's original)
    files_in_duplicate_groups: int
    duplicate_groups: int
    duplicate_storage: int        # storage used by every file that belongs to a duplicate group
    potential_savings: int        # storage used by the redundant copies only
    savings_percent: float
    pending_files: int
    storage_by_category: list[CategoryUsage]
    uploads_timeline: list[TimelinePoint]
    largest_files: list[FileOut]
    recent_uploads: list[FileOut]


FileCategory = Literal["image", "video", "audio", "document", "archive", "code", "other"]
DuplicateFilter = Literal["all", "any", "copies", "unique"]
