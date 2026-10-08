import hashlib
import io

import pytest

from app.services.hashing import hash_file, hash_stream


def test_matches_hashlib(tmp_path):
    data = b"hello duplicate world" * 1000
    p = tmp_path / "a.bin"
    p.write_bytes(data)
    assert hash_file(p) == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("chunk", [1, 7, 64, 4096, 1024 * 1024])
def test_result_is_independent_of_chunk_size(chunk):
    data = bytes(range(256)) * 500
    assert hash_stream(io.BytesIO(data), chunk) == hashlib.sha256(data).hexdigest()


def test_empty_file(tmp_path):
    p = tmp_path / "empty"
    p.write_bytes(b"")
    assert hash_file(p) == hashlib.sha256(b"").hexdigest()


def test_identical_content_different_names_same_hash(tmp_path):
    a, b = tmp_path / "report_final.pdf", tmp_path / "copy of notes (1).txt"
    a.write_bytes(b"same bytes")
    b.write_bytes(b"same bytes")
    assert hash_file(a) == hash_file(b)


def test_one_byte_difference_changes_hash(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"x" * 1000 + b"a")
    b.write_bytes(b"x" * 1000 + b"b")
    assert hash_file(a) != hash_file(b)


def test_large_file_is_streamed_in_chunks(tmp_path):
    """A 24 MB file hashed with a 64 KB chunk must never be read in one go."""
    p = tmp_path / "big.bin"
    block = b"0123456789abcdef" * 4096  # 64 KB
    with open(p, "wb") as fh:
        for _ in range(384):
            fh.write(block)

    class Spy(io.BufferedReader):
        max_read = 0

        def readinto(self, buf):
            n = super().readinto(buf)
            Spy.max_read = max(Spy.max_read, len(buf))
            return n

    with open(p, "rb", buffering=0) as raw:
        digest = hash_stream(Spy(raw), chunk_size=64 * 1024)
    assert Spy.max_read == 64 * 1024
    expected = hashlib.sha256()
    for _ in range(384):
        expected.update(block)
    assert digest == expected.hexdigest()


def test_invalid_chunk_size():
    with pytest.raises(ValueError):
        hash_stream(io.BytesIO(b"x"), 0)
