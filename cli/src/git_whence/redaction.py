"""Secret scanning and redaction pipeline.

Redaction runs at attach time (the only gate). Patterns detect common
secret formats and replace them with [REDACTED:<type>] tokens.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# --- Built-in secret patterns ---
# Ordered from most specific (multiline) to least specific (prefixes).

_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # Private key blocks (multiline)
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        "[REDACTED:private-key]",
    ),
    # AWS access keys
    (
        "aws-key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED:aws-key]",
    ),
    # JWT tokens (three base64url segments separated by dots)
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
        "[REDACTED:jwt]",
    ),
    # Bearer tokens
    (
        "bearer-token",
        re.compile(r"Bearer\s+[A-Za-z0-9_\-.~+/]{20,}=*"),
        "[REDACTED:bearer-token]",
    ),
    # API keys with common prefixes
    (
        "api-key",
        re.compile(
            r"\b(?:"
            r"sk-[A-Za-z0-9]{20,}"
            r"|ak_[A-Za-z0-9]{20,}"
            r"|ghp_[A-Za-z0-9]{36,}"
            r"|gho_[A-Za-z0-9]{36,}"
            r"|xoxb-[A-Za-z0-9\-]{20,}"
            r")\b"
        ),
        "[REDACTED:api-key]",
    ),
]

# Patterns that should block attach unless --force
HIGH_CONFIDENCE_TYPES = {"private-key", "aws-key"}


@dataclass
class RedactionResult:
    """Result of scanning and redacting text."""

    text: str
    was_redacted: bool = False
    secret_count: int = 0
    high_confidence_types: list[str] = field(default_factory=list)


def load_custom_patterns(path: Path) -> list[tuple[re.Pattern, str]]:
    """Load custom redaction patterns from a file.

    One regex per line. Lines starting with # are comments.
    Empty lines are skipped.
    """
    patterns = []
    if not path.exists():
        return patterns
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append((re.compile(line), "[REDACTED:custom]"))
    return patterns


def scan_and_redact(
    text: str,
    custom_patterns: list[tuple[re.Pattern, str]] | None = None,
) -> RedactionResult:
    """Run the redaction pipeline on text.

    Applies built-in patterns first (most specific to least specific),
    then custom patterns. Returns the redacted text and metadata.
    """
    result = RedactionResult(text=text)

    # Apply built-in patterns
    for pattern_type, pattern, replacement in _PATTERNS:
        new_text, count = pattern.subn(replacement, result.text)
        if count > 0:
            result.text = new_text
            result.was_redacted = True
            result.secret_count += count
            if pattern_type in HIGH_CONFIDENCE_TYPES:
                if pattern_type not in result.high_confidence_types:
                    result.high_confidence_types.append(pattern_type)

    # Apply custom patterns
    if custom_patterns:
        for pattern, replacement in custom_patterns:
            new_text, count = pattern.subn(replacement, result.text)
            if count > 0:
                result.text = new_text
                result.was_redacted = True
                result.secret_count += count

    return result
