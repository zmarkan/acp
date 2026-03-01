"""SHA-256 hashing, text normalization, and canonical JSON (RFC 8785)."""

import hashlib
import json


def normalize_text(text: str) -> bytes:
    """Normalize text for hashing: UTF-8 encode with LF line endings.

    Per spec: replace \\r\\n and \\r with \\n, encode as UTF-8,
    do NOT trim leading/trailing whitespace.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.encode("utf-8")


def sha256_text(text: str) -> str:
    """SHA-256 of normalized text, prefixed with sha256:.

    Used for prompt_hash, response_hash, and context.patch_hash.
    """
    digest = hashlib.sha256(normalize_text(text)).hexdigest()
    return f"sha256:{digest}"


def sha256_bytes(data: bytes) -> str:
    """SHA-256 of raw bytes, prefixed with sha256:.

    Used for context.input_artifacts[].hash (no text normalization).
    """
    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"


def canonical_json(obj: dict) -> bytes:
    """RFC 8785 canonical JSON encoding as UTF-8 bytes.

    - Exclude the 'integrity' key from the top-level object
    - Sort all object keys lexicographically at every nesting level
    - Compact encoding (no whitespace)
    - Strings: escape control chars, literal UTF-8 for everything else
    - Arrays preserve original element order
    """
    clean = {k: v for k, v in obj.items() if k != "integrity"}
    return json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def trace_hash(trace_obj: dict) -> str:
    """Compute trace_hash: SHA-256 of canonical JSON excluding integrity."""
    digest = hashlib.sha256(canonical_json(trace_obj)).hexdigest()
    return f"sha256:{digest}"
