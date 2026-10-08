"""Secure upload validation: filename sanitising, extension blocklist and
magic-byte (file signature) inspection."""
from __future__ import annotations

import mimetypes
import re
import unicodedata
from dataclasses import dataclass

from app.core.exceptions import FileValidationError

HEADER_BYTES = 8192
MAX_FILENAME_LENGTH = 255

# (label, mime, extensions this signature is valid for, offset, magic bytes)
_SIGNATURES: list[tuple[str, str, frozenset[str], int, bytes]] = [
    ("PNG image", "image/png", frozenset({"png"}), 0, b"\x89PNG\r\n\x1a\n"),
    ("JPEG image", "image/jpeg", frozenset({"jpg", "jpeg"}), 0, b"\xff\xd8\xff"),
    ("GIF image", "image/gif", frozenset({"gif"}), 0, b"GIF87a"),
    ("GIF image", "image/gif", frozenset({"gif"}), 0, b"GIF89a"),
    ("BMP image", "image/bmp", frozenset({"bmp"}), 0, b"BM"),
    ("PDF document", "application/pdf", frozenset({"pdf"}), 0, b"%PDF-"),
    ("ZIP container", "application/zip", frozenset({"zip", "docx", "xlsx", "pptx", "odt", "ods", "epub"}), 0, b"PK\x03\x04"),
    ("ZIP container (empty)", "application/zip", frozenset({"zip"}), 0, b"PK\x05\x06"),
    ("GZIP archive", "application/gzip", frozenset({"gz", "tgz"}), 0, b"\x1f\x8b"),
    ("7-Zip archive", "application/x-7z-compressed", frozenset({"7z"}), 0, b"7z\xbc\xaf\x27\x1c"),
    ("RAR archive", "application/vnd.rar", frozenset({"rar"}), 0, b"Rar!\x1a\x07"),
    ("OLE2 document", "application/x-ole-storage", frozenset({"doc", "xls", "ppt", "msg"}), 0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
]

_OFFICE_MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

# Executable formats are rejected whatever the filename says.
_EXECUTABLE_MAGIC: list[tuple[str, bytes]] = [
    ("ELF executable", b"\x7fELF"),
    ("Mach-O executable", b"\xfe\xed\xfa\xce"),
    ("Mach-O executable", b"\xfe\xed\xfa\xcf"),
    ("Mach-O executable", b"\xce\xfa\xed\xfe"),
    ("Mach-O executable", b"\xcf\xfa\xed\xfe"),
    ("Java class file", b"\xca\xfe\xba\xbe"),
]

_CATEGORY_BY_EXT = {
    "image": {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "tif", "tiff", "heic", "ico"},
    "video": {"mp4", "mkv", "mov", "avi", "webm", "wmv", "flv", "m4v"},
    "audio": {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma"},
    "document": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "rtf", "odt", "ods", "csv", "epub"},
    "archive": {"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz"},
    "code": {"py", "js", "ts", "tsx", "jsx", "java", "c", "cpp", "h", "cs", "go", "rs", "rb", "php",
             "html", "css", "json", "xml", "yml", "yaml", "sql", "sh", "toml", "ini"},
}

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_RESERVED_CHARS = re.compile(r'[<>:"|?*]')


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    extension: str
    declared_mime: str | None
    detected_mime: str
    category: str
    signature: str | None
    is_text: bool


def sanitize_filename(raw: str | None) -> str:
    """Strip any path components and unsafe characters; keep Unicode (e.g. Tamil) names."""
    if not raw:
        raise FileValidationError("The file has no name.")
    name = unicodedata.normalize("NFC", raw).replace("\\", "/").split("/")[-1]
    name = _CONTROL_CHARS.sub("", name)
    name = _RESERVED_CHARS.sub("_", name).strip().strip(".")
    if not name:
        raise FileValidationError("The file name is empty after removing unsafe characters.")
    if len(name) > MAX_FILENAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 16:
            name = stem[: MAX_FILENAME_LENGTH - len(ext) - 1] + "." + ext
        else:
            name = name[:MAX_FILENAME_LENGTH]
    return name


def get_extension(filename: str) -> str:
    _, dot, ext = filename.rpartition(".")
    return ext.lower() if dot and ext else ""


def _is_windows_pe(header: bytes) -> bool:
    if not header.startswith(b"MZ") or len(header) < 0x40:
        return False
    offset = int.from_bytes(header[0x3C:0x40], "little")
    return offset + 4 <= len(header) and header[offset : offset + 4] == b"PE\x00\x00"


def detect_executable(header: bytes) -> str | None:
    if _is_windows_pe(header):
        return "Windows executable"
    for label, magic in _EXECUTABLE_MAGIC:
        if header.startswith(magic):
            return label
    return None


def looks_like_text(header: bytes) -> bool:
    if not header or b"\x00" in header:
        return False
    try:
        header.decode("utf-8")
        return True
    except UnicodeDecodeError as exc:
        # A multi-byte character may simply be cut off at the end of the sample.
        return exc.start >= len(header) - 4


def categorize(extension: str, mime: str | None) -> str:
    for category, exts in _CATEGORY_BY_EXT.items():
        if extension in exts:
            return category
    if mime:
        major = mime.split("/")[0]
        if major in {"image", "video", "audio"}:
            return major
        if mime in {"application/pdf", "text/plain"}:
            return "document"
    return "other"


def _match_signature(header: bytes) -> tuple[str, str, frozenset[str]] | None:
    for label, mime, exts, offset, magic in _SIGNATURES:
        if header[offset : offset + len(magic)] == magic:
            return label, mime, exts
    return None


def validate_upload(
    filename: str | None,
    declared_mime: str | None,
    header: bytes,
    blocked_extensions: frozenset[str],
) -> ValidatedFile:
    """Raise FileValidationError if the upload is unsafe; otherwise describe it."""
    name = sanitize_filename(filename)
    extension = get_extension(name)

    if extension in blocked_extensions:
        raise FileValidationError(f"“.{extension}” files are not allowed.")

    executable = detect_executable(header)
    if executable:
        raise FileValidationError(f"Executable content ({executable}) is not allowed.")

    signature = _match_signature(header)
    sig_label: str | None = None
    detected_mime: str | None = None
    if signature:
        sig_label, detected_mime, valid_exts = signature
        # Extension claims a format that the bytes contradict (e.g. a ".png" that is really a PDF).
        if extension and extension in _enforced_extensions() and extension not in valid_exts:
            raise FileValidationError(
                f"The content looks like a {sig_label}, which does not match the “.{extension}” extension."
            )
        if extension in _OFFICE_MIME:
            detected_mime = _OFFICE_MIME[extension]
    elif extension in _enforced_extensions():
        raise FileValidationError(f"The content is not a valid “.{extension}” file.")

    is_text = False
    if detected_mime is None:
        guessed, _ = mimetypes.guess_type(name)
        is_text = looks_like_text(header)
        detected_mime = guessed or ("text/plain" if is_text else "application/octet-stream")
    elif detected_mime.startswith("text/"):
        is_text = True

    return ValidatedFile(
        filename=name,
        extension=extension,
        declared_mime=declared_mime,
        detected_mime=detected_mime,
        category=categorize(extension, detected_mime),
        signature=sig_label,
        is_text=is_text,
    )


def _enforced_extensions() -> frozenset[str]:
    # Extensions whose content we can verify with a signature.
    return frozenset().union(*(exts for _, _, exts, _, _ in _SIGNATURES)) - {"msg", "tgz"}
