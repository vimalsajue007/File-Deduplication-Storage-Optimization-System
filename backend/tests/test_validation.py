import pytest

from app.core.exceptions import FileValidationError
from app.services.validation import categorize, sanitize_filename, validate_upload

BLOCKED = frozenset({"exe", "bat", "sh"})
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"x" * 32


def ok(name, header, mime=None):
    return validate_upload(name, mime, header, BLOCKED)


def test_accepts_valid_png_and_pdf():
    assert ok("a.png", PNG).detected_mime == "image/png"
    assert ok("a.pdf", PDF).category == "document"


def test_accepts_plain_text_and_unicode_names():
    v = ok("தமிழ்-குறிப்பு.txt", "வணக்கம் hello".encode())
    assert v.is_text and v.filename == "தமிழ்-குறிப்பு.txt"


def test_blocked_extension_rejected():
    with pytest.raises(FileValidationError):
        ok("setup.exe", b"anything")


def test_double_extension_uses_last_one():
    with pytest.raises(FileValidationError):
        ok("invoice.pdf.exe", PDF)


def test_executable_disguised_as_image_rejected():
    elf = b"\x7fELF" + b"\x00" * 60
    with pytest.raises(FileValidationError):
        ok("photo.png", elf)


def test_windows_pe_disguised_as_text_rejected():
    pe = bytearray(b"MZ" + b"\x00" * 0x3E + b"\x00" * 64)
    pe[0x3C:0x40] = (0x80).to_bytes(4, "little")
    pe[0x80:0x84] = b"PE\x00\x00"
    with pytest.raises(FileValidationError):
        ok("notes.txt", bytes(pe))


def test_text_starting_with_mz_is_not_an_executable():
    assert ok("note.txt", b"MZ is a nice abbreviation").is_text


def test_extension_content_mismatch_rejected():
    with pytest.raises(FileValidationError):
        ok("fake.png", PDF)
    with pytest.raises(FileValidationError):
        ok("fake.pdf", b"just some text")


def test_office_docs_are_zip_containers():
    assert ok("a.docx", b"PK\x03\x04" + b"\x00" * 20).detected_mime.endswith("wordprocessingml.document")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\a.txt", "a.txt"),
        ("we\x00ird\nname.txt", "weirdname.txt"),
        ("  .hidden. ", "hidden"),
        ('a<b>:"c|d?.txt', "a_b___c_d_.txt"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "...", "/"])
def test_sanitize_rejects_empty(raw):
    with pytest.raises(FileValidationError):
        sanitize_filename(raw)


def test_long_filename_is_truncated_keeping_extension():
    name = sanitize_filename("a" * 400 + ".pdf")
    assert len(name) == 255 and name.endswith(".pdf")


def test_categorize():
    assert categorize("mp4", None) == "video"
    assert categorize("", "image/webp") == "image"
    assert categorize("xyz", None) == "other"
