"""NDJSON event queue management (.git/whence/queue.ndjson).

Events are appended during 'record' and consumed during 'attach'.
The queue is a local scratch file -- never committed, never shared.
"""

import json
import os
import tempfile
from pathlib import Path

from . import git


def queue_path() -> Path:
    """Resolve queue path from WHENCE_QUEUE_PATH env or default."""
    env_path = os.environ.get("WHENCE_QUEUE_PATH")
    if env_path:
        return Path(env_path)
    return git.ensure_whence_initialized() / "queue.ndjson"


def read_events() -> list[dict]:
    """Read all events from queue.ndjson."""
    path = queue_path()
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def append_event(event: dict) -> None:
    """Append a single event as one JSON line."""
    path = queue_path()
    with open(path, "a") as f:
        f.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")


def count() -> int:
    """Count events without loading all."""
    path = queue_path()
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text().splitlines():
        if line.strip():
            n += 1
    return n


def clear() -> int:
    """Clear the queue. Returns count of events cleared."""
    path = queue_path()
    n = count()
    path.write_text("")
    return n


def consume_all() -> list[dict]:
    """Read and clear the queue. Returns consumed events."""
    events = read_events()
    path = queue_path()
    path.write_text("")
    return events


def consume_filtered(predicate) -> tuple[list[dict], list[dict]]:
    """Read, split by predicate. Returns (consumed, remaining).

    Consumed events match the predicate. Remaining are rewritten to the queue.
    Uses atomic write (temp file + rename) for safety.
    """
    events = read_events()
    consumed = [e for e in events if predicate(e)]
    remaining = [e for e in events if not predicate(e)]

    path = queue_path()
    # Atomic rewrite of remaining events
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            for event in remaining:
                f.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise

    return consumed, remaining


def export_ndjson() -> str:
    """Dump queue contents as NDJSON string."""
    path = queue_path()
    if not path.exists():
        return ""
    return path.read_text()
