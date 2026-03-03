"""WHENCE configuration management (.git/whence/config.json)."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import git


@dataclass
class WHENCEConfig:
    spec_version: str = "0.1.0"
    notes_ref: str = "refs/notes/whence"
    default_redaction: str = "hash-response"
    default_tool: str | None = None
    max_queue_events: int = 5000
    redact_patterns_file: str | None = None


def config_path() -> Path:
    """Return the path to config.json."""
    return git.ensure_whence_initialized() / "config.json"


def load() -> WHENCEConfig:
    """Load config from .git/whence/config.json."""
    path = config_path()
    data = json.loads(path.read_text())
    return WHENCEConfig(
        spec_version=data.get("spec_version", "0.1.0"),
        notes_ref=data.get("notes_ref", "refs/notes/whence"),
        default_redaction=data.get("default_redaction", "hash-response"),
        default_tool=data.get("default_tool"),
        max_queue_events=data.get("max_queue_events", 5000),
        redact_patterns_file=data.get("redact_patterns_file"),
    )


def save(cfg: WHENCEConfig, path: Path | None = None) -> None:
    """Write config to .git/whence/config.json."""
    if path is None:
        path = git.whence_dir() / "config.json"
    data = asdict(cfg)
    path.write_text(json.dumps(data, indent=2) + "\n")
