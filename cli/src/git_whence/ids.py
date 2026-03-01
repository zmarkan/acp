"""ID generation for ACP traces and events."""

import os
from datetime import datetime, timezone


def generate_trace_id() -> str:
    """Generate a trace ID: UTC timestamp + random hex suffix.

    Format: 20260228T103215Z_7f2c
    """
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = os.urandom(2).hex()
    return f"{ts}_{suffix}"


def generate_event_id() -> str:
    """Generate an event ID: evt_ prefix + random hex.

    Format: evt_a1b2c3d4
    """
    return f"evt_{os.urandom(4).hex()}"
