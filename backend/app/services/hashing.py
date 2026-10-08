"""Streaming content hashing.

Files are read in fixed-size chunks into a single reusable buffer, so memory use stays
constant (one chunk) no matter how large the file is. SHA-256 is used because it is
collision-resistant: two files with the same digest *and* size are treated as identical.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB


def hash_stream(stream: BinaryIO, chunk_size: int = DEFAULT_CHUNK_SIZE, algorithm: str = "sha256") -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.new(algorithm)
    buffer = bytearray(chunk_size)
    view = memoryview(buffer)
    while True:
        read = stream.readinto(buffer)  # type: ignore[attr-defined]
        if not read:
            break
        digest.update(view[:read])
    return digest.hexdigest()


def hash_file(path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE, algorithm: str = "sha256") -> str:
    # buffering=0 -> raw file object, we do our own chunking
    with open(path, "rb", buffering=0) as fh:
        return hash_stream(fh, chunk_size, algorithm)
