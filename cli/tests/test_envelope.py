"""Tests for envelope module."""

import json

from git_whence.envelope import serialize, parse_note_content, parse_headers


def _make_trace(**overrides):
    trace = {
        "spec_version": "0.1.0",
        "trace_id": "20260228T103215Z_7f2c",
        "created_at": "2026-02-28T10:32:15.000Z",
        "target": {"type": "git-commit", "id": "abc123"},
        "tool_summary": {"primary_tool": "claude-code", "tools_used": ["claude-code"]},
        "redaction_mode": "hash-response",
        "event_count": 1,
        "events": [{
            "spec_version": "0.1.0",
            "event_id": "evt_test1234",
            "timestamp": "2026-02-28T10:21:33.123Z",
            "prompt": "test prompt",
            "prompt_hash": "sha256:" + "a" * 64,
        }],
        "integrity": {
            "trace_hash": "sha256:" + "b" * 64,
            "algorithm": "sha256-canonical-json",
        },
    }
    trace.update(overrides)
    return trace


def test_serialize_has_headers():
    trace = _make_trace()
    env = serialize(trace)
    assert "ACP-Spec-Version: 0.1.0" in env
    assert "ACP-Trace-Id: 20260228T103215Z_7f2c" in env
    assert "ACP-Event-Count: 1" in env
    assert "ACP-Tool: claude-code" in env
    assert "ACP-Redaction: hash-response" in env


def test_serialize_has_json_body():
    trace = _make_trace()
    env = serialize(trace)
    # Body is after the blank line
    parts = env.split("\n\n", 1)
    assert len(parts) == 2
    body = json.loads(parts[1])
    assert body["trace_id"] == "20260228T103215Z_7f2c"


def test_parse_single_envelope():
    trace = _make_trace()
    env = serialize(trace)
    traces = parse_note_content(env)
    assert len(traces) == 1
    assert traces[0]["trace_id"] == "20260228T103215Z_7f2c"


def test_parse_multiple_envelopes():
    t1 = _make_trace(trace_id="trace_1")
    t2 = _make_trace(trace_id="trace_2")
    env = serialize(t1) + "\n---\n" + serialize(t2)
    traces = parse_note_content(env)
    assert len(traces) == 2
    assert traces[0]["trace_id"] == "trace_1"
    assert traces[1]["trace_id"] == "trace_2"


def test_parse_bare_json():
    trace = _make_trace()
    content = json.dumps(trace)
    traces = parse_note_content(content)
    assert len(traces) == 1
    assert traces[0]["trace_id"] == "20260228T103215Z_7f2c"


def test_parse_bare_json_array():
    t1 = _make_trace(trace_id="a")
    t2 = _make_trace(trace_id="b")
    content = json.dumps([t1, t2])
    traces = parse_note_content(content)
    assert len(traces) == 2


def test_parse_headers():
    env = serialize(_make_trace())
    headers = parse_headers(env)
    assert headers["acp-spec-version"] == "0.1.0"
    assert headers["acp-tool"] == "claude-code"


def test_parse_empty():
    assert parse_note_content("") == []
    assert parse_note_content("  ") == []
