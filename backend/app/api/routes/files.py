import logging
import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File as FormFile, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import AppError, FileValidationError, NotFoundError
from app.db.base import utcnow
from app.db.session import get_db
from app.models import STATUS_FAILED, STATUS_PENDING, DuplicateGroup, File, FileMetadata, User
from app.schemas import (
    BulkDeleteRequest,
    DeletionPreview,
    DeletionPreviewRequest,
    DeletionResult,
    DuplicateFilter,
    FileCategory,
    FileDetail,
    FileOut,
    GroupBrief,
    Page,
    ProtectionUpdate,
    UploadRejected,
    UploadResponse,
)
from app.services import audit, file_service, storage
from app.services.validation import HEADER_BYTES, validate_upload
from app.tasks.tasks import process_file_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["Files"])


def _enqueue(file_id: int) -> bool:
    """Queue background hashing. A broker outage must not fail the upload itself."""
    try:
        process_file_task.delay(file_id)
        return True
    except Exception:  # noqa: BLE001 - kombu/redis raise a variety of connection errors
        logger.exception("Could not enqueue hashing task for file %s", file_id)
        return False


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    summary="Upload one or more files",
    description=(
        "Files are validated, streamed to disk in chunks and saved immediately. Hashing and "
        "duplicate detection then run in a Celery worker, so the response returns right away "
        "with `status: pending`."
    ),
)
def upload_files(
    request: Request,
    files: list[UploadFile] = FormFile(..., description="One or more files"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    settings = get_settings()
    if len(files) > settings.MAX_FILES_PER_UPLOAD:
        raise FileValidationError(f"You can upload at most {settings.MAX_FILES_PER_UPLOAD} files at a time.")

    accepted: list[File] = []
    rejected: list[UploadRejected] = []

    for upload in files:
        display_name = upload.filename or "unnamed"
        storage_key: str | None = None
        try:
            header = upload.file.read(HEADER_BYTES)
            upload.file.seek(0)
            checked = validate_upload(upload.filename, upload.content_type, header, settings.blocked_extensions_set)

            storage_key = storage.new_storage_key(user.id)
            size = storage.save_stream(
                upload.file, storage_key, settings.max_upload_bytes, settings.copy_chunk_bytes
            )

            record = File(
                owner_id=user.id,
                original_filename=checked.filename,
                storage_key=storage_key,
                size_bytes=size,
                mime_type=checked.detected_mime,
                extension=checked.extension,
                category=checked.category,
                status=STATUS_PENDING,
                uploaded_at=utcnow(),
            )
            record.file_metadata = FileMetadata(
                extension=checked.extension,
                declared_mime=(checked.declared_mime or None),
                detected_mime=checked.detected_mime,
                signature=checked.signature,
                is_text=checked.is_text,
                extra={"original_name": display_name},
            )
            db.add(record)
            db.flush()
            accepted.append(record)
        except AppError as exc:
            rejected.append(UploadRejected(filename=display_name, reason=exc.message))
            if storage_key:
                storage.delete_physical(storage_key)
        finally:
            upload.file.close()

    if not accepted:
        db.rollback()
        first = rejected[0].reason if rejected else "No files were provided."
        raise FileValidationError(first, details={"rejected": [r.model_dump() for r in rejected]})

    audit.record(
        db, "file.upload", user_id=user.id, request=request, resource_type="file",
        resource_id=",".join(str(f.id) for f in accepted)[:255],
        details={"count": len(accepted), "rejected": len(rejected), "bytes": sum(f.size_bytes for f in accepted)},
    )
    db.commit()  # commit BEFORE enqueueing so the worker can see the rows

    queued = all([_enqueue(f.id) for f in accepted])
    for f in accepted:
        db.refresh(f)
    return UploadResponse(uploaded=[FileOut.model_validate(f) for f in accepted], rejected=rejected, queued=queued)


@router.get("", response_model=Page[FileOut], summary="Search, filter, sort and paginate files")
def list_files(
    q: str | None = Query(None, max_length=255, description="Filename contains (case-insensitive)"),
    file_type: FileCategory | None = Query(None),
    extension: str | None = Query(None, max_length=32),
    min_size: int | None = Query(None, ge=0, description="Bytes"),
    max_size: int | None = Query(None, ge=0, description="Bytes"),
    duplicates: DuplicateFilter = Query("all", description="all | any (in a group) | copies (redundant only) | unique"),
    uploaded_from: date | None = Query(None),
    uploaded_to: date | None = Query(None),
    status: Literal["pending", "processing", "ready", "failed"] | None = Query(None),
    sort_by: Literal["name", "size", "uploaded_at", "type"] = Query("uploaded_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[FileOut]:
    filters = file_service.FileFilters(
        q=q, file_type=file_type, extension=extension, min_size=min_size, max_size=max_size,
        duplicates=duplicates, uploaded_from=uploaded_from, uploaded_to=uploaded_to, status=status,
        sort_by=sort_by, sort_order=sort_order,
    )
    rows, total = file_service.list_files(db, user.id, filters, page, page_size)
    return Page[FileOut](
        items=[FileOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size, pages=max(math.ceil(total / page_size), 1),
    )


@router.post("/deletion-preview", response_model=DeletionPreview, summary="Preview the impact of deleting files")
def deletion_preview(
    payload: DeletionPreviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return file_service.build_deletion_preview(db, user.id, payload.file_ids)


@router.post("/bulk-delete", response_model=DeletionResult, summary="Delete several files (requires confirm=true)")
def bulk_delete(
    payload: BulkDeleteRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return file_service.delete_files(
        db, user, payload.file_ids, confirm=payload.confirm, reason=payload.reason, request=request
    )


@router.get("/{file_id}", response_model=FileDetail, summary="File details and metadata")
def get_file(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileDetail:
    file = file_service.get_owned_file(db, user.id, file_id)
    detail = FileDetail.model_validate(file)
    if file.duplicate_group_id:
        group = db.get(DuplicateGroup, file.duplicate_group_id)
        if group:
            original = db.get(File, group.original_file_id) if group.original_file_id else None
            detail.group = GroupBrief(
                id=group.id, file_count=group.file_count, original_file_id=group.original_file_id,
                original_filename=original.original_filename if original else None,
                potential_savings=group.potential_savings,
            )
    return detail


@router.get("/{file_id}/download", summary="Download a file")
def download_file(
    file_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FileResponse:
    file = file_service.get_owned_file(db, user.id, file_id)
    try:
        path = storage.resolve_storage_path(file.storage_key)
    except ValueError:
        raise NotFoundError("The stored file could not be found.")
    if not path.is_file():
        logger.error("File %s is in the database but missing on disk (%s)", file.id, file.storage_key)
        raise NotFoundError("The stored file could not be found.")
    audit.record(db, "file.download", user_id=user.id, request=request, resource_type="file", resource_id=file.id, commit=True)
    return FileResponse(
        path,
        filename=file.original_filename,
        media_type="application/octet-stream",  # always a download, never rendered in the browser
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.patch("/{file_id}/protection", response_model=FileOut, summary="Protect or unprotect a file")
def set_protection(
    file_id: int, payload: ProtectionUpdate, request: Request,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> File:
    file = file_service.get_owned_file(db, user.id, file_id)
    file.is_protected = payload.is_protected
    audit.record(
        db, "file.protect" if payload.is_protected else "file.unprotect", user_id=user.id,
        request=request, resource_type="file", resource_id=file.id,
    )
    db.commit()
    return file


@router.post("/{file_id}/reprocess", response_model=FileOut, status_code=202, summary="Re-queue hashing for a file")
def reprocess(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> File:
    file = file_service.get_owned_file(db, user.id, file_id)
    if file.status not in (STATUS_FAILED, STATUS_PENDING):
        raise FileValidationError("Only pending or failed files can be reprocessed.")
    file.status = STATUS_PENDING
    file.status_message = None
    db.commit()
    _enqueue(file.id)
    db.refresh(file)
    return file


@router.delete("/{file_id}", response_model=DeletionResult, summary="Delete one file (requires confirm=true)")
def delete_file(
    file_id: int,
    request: Request,
    confirm: bool = Query(False, description="Must be true to actually delete"),
    reason: str | None = Query(None, max_length=255),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return file_service.delete_files(db, user, [file_id], confirm=confirm, reason=reason, request=request)
