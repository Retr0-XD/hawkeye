"""Shared id sanitization (kept in sync with processing storage._safe_id).

Firestore document ids cannot contain '/' or '.' in a way that breaks the path,
so resource ids of the form ``gcp://compute/...`` are sanitized before use as
a document key and unsanitized for display.
"""
from __future__ import annotations


def _safe_id(raw_id: str) -> str:
    return raw_id.replace("/", "__").replace(".", "_dot_")


def _unsafe_id(safe_id: str) -> str:
    """Best-effort reverse mapping for display (not round-trip safe for '.')."""
    return safe_id.replace("__", "/").replace("_dot_", ".")
