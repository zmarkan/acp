"""Tests for hashing module."""

import hashlib
import json

from git_whence.hashing import (
    canonical_json,
    normalize_text,
    sha256_bytes,
    sha256_text,
    trace_hash,
)


def test_normalize_text_lf():
    assert normalize_text("hello\nworld") == b"hello\nworld"


def test_normalize_text_crlf():
    assert normalize_text("hello\r\nworld") == b"hello\nworld"


def test_normalize_text_cr():
    assert normalize_text("hello\rworld") == b"hello\nworld"


def test_normalize_text_preserves_whitespace():
    assert normalize_text("  hello  ") == b"  hello  "


def test_sha256_text():
    result = sha256_text("hello")
    expected = "sha256:" + hashlib.sha256(b"hello").hexdigest()
    assert result == expected


def test_sha256_text_prefix():
    result = sha256_text("test")
    assert result.startswith("sha256:")
    assert len(result) == 7 + 64  # "sha256:" + 64 hex chars


def test_sha256_bytes():
    data = b"\x00\x01\x02"
    result = sha256_bytes(data)
    expected = "sha256:" + hashlib.sha256(data).hexdigest()
    assert result == expected


def test_canonical_json_excludes_integrity():
    obj = {"a": 1, "integrity": {"hash": "xxx"}, "b": 2}
    result = json.loads(canonical_json(obj))
    assert "integrity" not in result
    assert "a" in result and "b" in result


def test_canonical_json_sorts_keys():
    obj = {"z": 1, "a": 2, "m": 3}
    result = canonical_json(obj).decode("utf-8")
    assert result == '{"a":2,"m":3,"z":1}'


def test_canonical_json_nested_sort():
    obj = {"b": {"z": 1, "a": 2}, "a": 1}
    result = canonical_json(obj).decode("utf-8")
    assert result == '{"a":1,"b":{"a":2,"z":1}}'


def test_canonical_json_compact():
    obj = {"key": "value"}
    result = canonical_json(obj).decode("utf-8")
    assert " " not in result


def test_canonical_json_arrays_preserve_order():
    obj = {"items": [3, 1, 2]}
    result = canonical_json(obj).decode("utf-8")
    assert result == '{"items":[3,1,2]}'


def test_trace_hash_deterministic():
    trace = {
        "spec_version": "0.1.0",
        "trace_id": "test",
        "created_at": "2026-01-01T00:00:00.000Z",
        "target": {"type": "git-commit", "id": "abc123"},
        "redaction_mode": "hash-response",
        "event_count": 0,
        "events": [],
        "integrity": {"algorithm": "sha256-canonical-json"},
    }
    h1 = trace_hash(trace)
    h2 = trace_hash(trace)
    assert h1 == h2
    assert h1.startswith("sha256:")
