"""Hash helpers used to build deterministic IDs and cache keys."""

from __future__ import annotations

import hashlib


def sha256_text(value: str) -> str:
    """Return SHA-256 hex digest for UTF-8 text."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Return SHA-256 hex digest for bytes payload."""

    return hashlib.sha256(value).hexdigest()
