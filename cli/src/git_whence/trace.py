"""Trace assembly: build a complete trace object from events."""

from datetime import datetime, timezone

from . import hashing, ids


def assemble(
    events: list[dict],
    target_commit: str,
    redaction_mode: str,
    branch: str | None = None,
) -> dict:
    """Build a complete trace object from a list of events.

    Computes tool_summary, event_count, and integrity hash.
    """
    trace_id = ids.generate_trace_id()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Build tool_summary
    tools_used = []
    sessions = []
    for event in events:
        tool = event.get("tool")
        if tool and tool not in tools_used:
            tools_used.append(tool)
        session = event.get("session_id")
        if session and session not in sessions:
            sessions.append(session)

    primary_tool = tools_used[0] if tools_used else "unknown"

    tool_summary = {
        "primary_tool": primary_tool,
        "tools_used": tools_used or ["unknown"],
    }
    if sessions:
        tool_summary["sessions"] = sessions

    trace = {
        "spec_version": "0.1.0",
        "trace_id": trace_id,
        "created_at": now,
        "target": {
            "type": "git-commit",
            "id": target_commit,
        },
        "redaction_mode": redaction_mode,
        "event_count": len(events),
        "events": events,
        "integrity": {
            "algorithm": "sha256-canonical-json",
        },
    }

    if branch:
        trace["branch"] = branch

    trace["tool_summary"] = tool_summary

    # Compute trace hash (must be done after all other fields are set)
    trace["integrity"]["trace_hash"] = hashing.trace_hash(trace)

    return trace
