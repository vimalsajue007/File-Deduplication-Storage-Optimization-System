"""On-disk storage for uploaded files.

Files are stored under random names (``<owner_id>/<uuid>``), never under the
user-supplied name, so path traversal and name collisions are impossible.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, FileValidationError

logger = logging.getLogger(__name__)


def upload_root() -> Path:
    root = Path(get_settings().UPLOAD_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_storage_key(owner_id: int) -> str:
    return f"{owner_id}/{uuid.uuid4().hex}"


def resolve_storage_path(storage_key: str) -> Path:
    """Map a storage key to an absolute path, refusing anything outside the upload root."""
    root = upload_root()
    path = (root / storage_key).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Storage key escapes the upload directory")
    return path


def save_stream(src: BinaryIO, storage_key: str, max_bytes: int, chunk_size: int) -> int:
    """Copy ``src`` to disk in chunks, enforcing the size limit. Returns bytes written."""
    dest = resolve_storage_path(storage_key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    written = 0
    try:
        with open(partial, "wb") as out:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise FileTooLargeError(
                        f"The file is larger than the {max_bytes // (1024 * 1024)} MB upload limit."
                    )
                out.write(chunk)
        if written == 0:
            raise FileValidationError("The file is empty.")
        os.replace(partial, dest)  # atomic: readers never see half-written files
        return written
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def delete_physical(storage_key: str) -> bool:
    try:
        resolve_storage_path(storage_key).unlink(missing_ok=True)
        return True
    except (OSError, ValueError):
        logger.exception("Could not remove stored file %s (orphaned on disk)", storage_key)
        return False
