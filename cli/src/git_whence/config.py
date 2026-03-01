"""ACP configuration management (.git/acp/config.json)."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import git


@dataclass
class ACPConfig:
    spec_version: str = "0.1.0"
    notes_ref: str = "refs/notes/acp"
    default_redaction: str = "hash-response"
    default_tool: str | None = None
    max_queue_events: int = 5000
    redact_patterns_file: str | None = None


def config_path() -> Path:
    """Return the path to config.json."""
    return git.ensure_acp_initialized() / "config.json"


def load() -> ACPConfig:
    """Load config from .git/acp/config.json."""
    path = config_path()
    data = json.loads(path.read_text())
    return ACPConfig(
        spec_version=data.get("spec_version", "0.1.0"),
        notes_ref=data.get("notes_ref", "refs/notes/acp"),
        default_redaction=data.get("default_redaction", "hash-response"),
        default_tool=data.get("default_tool"),
        max_queue_events=data.get("max_queue_events", 5000),
        redact_patterns_file=data.get("redact_patterns_file"),
    )


def save(cfg: ACPConfig, path: Path | None = None) -> None:
    """Write config to .git/acp/config.json."""
    if path is None:
        path = git.acp_dir() / "config.json"
    data = asdict(cfg)
    path.write_text(json.dumps(data, indent=2) + "\n")
