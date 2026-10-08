"""SQLAlchemy models: users, files, file_hashes, duplicate_groups, file_metadata,
deletion_history and audit_logs."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

# BIGINT on MySQL, INTEGER on SQLite (needed for SQLite autoincrement in tests)
BigInt = BigInteger().with_variant(Integer, "sqlite")

# File processing states
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_owner_uploaded", "owner_id", "uploaded_at"),
        Index("ix_files_owner_size", "owner_id", "size_bytes"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)  # relative path under UPLOAD_DIR
    size_bytes: Mapped[int] = mapped_column(BigInt)
    mime_type: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(32), index=True, default="")
    category: Mapped[str] = mapped_column(String(32), index=True, default="other")
    status: Mapped[str] = mapped_column(String(16), index=True, default=STATUS_PENDING)
    status_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duplicate_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("duplicate_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    file_hash: Mapped["FileHash | None"] = relationship(
        back_populates="file", uselist=False, cascade="all, delete-orphan"
    )
    file_metadata: Mapped["FileMetadata | None"] = relationship(
        back_populates="file", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def content_hash(self) -> str | None:
        return self.file_hash.sha256 if self.file_hash else None


class FileHash(Base):
    __tablename__ = "file_hashes"
    __table_args__ = (Index("ix_file_hashes_owner_sha256", "owner_id", "sha256"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), unique=True)
    owner_id: Mapped[int] = mapped_column(Integer)  # denormalised: duplicates are matched per owner
    algorithm: Mapped[str] = mapped_column(String(16), default="sha256")
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInt)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    file: Mapped[File] = relationship(back_populates="file_hash")


class DuplicateGroup(Base):
    __tablename__ = "duplicate_groups"
    __table_args__ = (UniqueConstraint("owner_id", "content_hash", name="uq_duplicate_groups_owner_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(BigInt)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    # Plain column (no ORM relationship) to avoid a circular files <-> groups dependency.
    original_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL", use_alter=True, name="fk_duplicate_groups_original_file_id_files"),
        nullable=True,
    )
    total_storage: Mapped[int] = mapped_column(BigInt, default=0)
    potential_savings: Mapped[int] = mapped_column(BigInt, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), unique=True)
    extension: Mapped[str] = mapped_column(String(32), default="")
    declared_mime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_mime: Mapped[str] = mapped_column(String(255))
    signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_text: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    file: Mapped[File] = relationship(back_populates="file_metadata")


class DeletionHistory(Base):
    __tablename__ = "deletion_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # no FK: the file row is gone
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInt)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="other")
    was_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    was_original: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_action_resource_created", "action", "resource_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
