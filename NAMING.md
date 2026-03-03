# WHENCE Naming Decisions

This document records the naming conventions adopted for the WHENCE project.

## Decision: Rename ACP → WHENCE

**Date:** 2026-03-03
**Recorded in:** WHENCE prompt log (this commit)

### Rationale

The original name "ACP — AI Code Provenance" was overloaded by at least two unrelated AI projects. To avoid confusion and establish a distinct identity, the project was renamed to **WHENCE**.

### Canonical Name

**WHENCE** — WHENCE Helps Explain Non-obvious Code Edits

- Internal nickname: **WTF** (Whence Trace Format)
- Optional long form: **WIT** (Whence Intent Trace)

### Naming Map

| Old (ACP)                        | New (WHENCE)                          |
|----------------------------------|---------------------------------------|
| ACP — AI Code Provenance         | WHENCE                                |
| ACP Trace Format                 | WHENCE Trace Format (Part 1 of spec)  |
| ACP-Git Binding                  | WHENCE Git Binding (Part 2 of spec)   |
| `refs/notes/acp`                 | `refs/notes/whence`                   |
| `.git/acp/`                      | `.git/whence/`                        |
| `ACP-*` envelope headers         | `WHENCE-*` envelope headers           |
| `ACPConfig`                      | `WHENCEConfig`                        |
| `ACPNotInitialized`              | `WHENCENotInitialized`                |
| `acp_dir()`                      | `whence_dir()`                        |
| `ensure_acp_initialized()`       | `ensure_whence_initialized()`         |
| `ACP_QUEUE_PATH`                 | `WHENCE_QUEUE_PATH`                   |
| `acp-bootstrap.sh`               | `whence-bootstrap.sh`                 |
| `acp-trace-v0.1.0.json`          | `whence-trace-v0.1.0.json`            |
| `acp-provenance.yml` (CI)        | `whence-provenance.yml` (CI)          |
| `acp_initialized` (test fixture) | `whence_initialized` (test fixture)   |

### What Did NOT Change

- The CLI tool name: **git-whence** (unchanged)
- The Python package name: **git-whence** (unchanged)
- The spec version: **0.1.0** (unchanged)
- The JSON data schema fields (e.g., `spec_version`, `trace_id`) — these are internal to the envelope body and remain the same
- The `evt_` prefix for event IDs (unchanged)

### Envelope Header Examples

Before:
```
ACP-Spec-Version: 0.1.0
ACP-Trace-Id: 20250101T120000Z_a1b2
ACP-Trace-Hash: sha256:abc123...
ACP-Event-Count: 3
ACP-Tool: claude-code
ACP-Redaction: hash-response
```

After:
```
WHENCE-Spec-Version: 0.1.0
WHENCE-Trace-Id: 20250101T120000Z_a1b2
WHENCE-Trace-Hash: sha256:abc123...
WHENCE-Event-Count: 3
WHENCE-Tool: claude-code
WHENCE-Redaction: hash-response
```
