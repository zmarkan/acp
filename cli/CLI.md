# git-whence CLI Reference

### The reference implementation of ACP (AI Code Provenance)

---

## Installation

```bash
# pip
pip install git-whence

# From source
git clone https://github.com/zmarkan/acp.git
cd acp/cli
pip install -e .
```

Once installed, Git auto-discovers the `git-whence` binary and `git whence <command>` works natively.

---

## Quick start

```bash
# Set up ACP in a repository
git whence init

# Record a prompt event (manual capture)
git whence record --tool claude-code --prompt "Refactor auth middleware to use dependency injection"

# ... do work, commit, rebase, clean up history ...

# Attach queued events to your final commit
git whence attach

# Push traces to the remote
git push origin refs/notes/acp

# View traces
git whence log
```

---

## Commands

### `git whence init`

Initialize ACP in the current Git repository.

```bash
git whence init [--redaction <mode>] [--tool <identifier>]
```

**What it does:**

1. Creates `.git/acp/` directory
2. Creates `.git/acp/config.json` with defaults (or provided options)
3. Creates empty `.git/acp/queue.ndjson`
4. Adds `refs/notes/acp` to the fetch refspec in `.git/config`:
   ```ini
   [remote "origin"]
       fetch = +refs/notes/acp:refs/notes/acp
   ```
5. Configures `notes.rewriteRef` for automatic note rewriting during rebase:
   ```ini
   [notes]
       rewriteRef = refs/notes/acp
       rewriteMode = concatenate
   ```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--redaction <mode>` | `hash-response` | Default redaction mode: `full`, `hash-response`, `hash-all` |
| `--tool <identifier>` | `null` | Default tool identifier for `record` commands |

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Initialized successfully |
| 1 | Not a Git repository |
| 2 | ACP already initialized (no-op, prints current config) |

---

### `git whence record`

Record a prompt event to the local queue.

```bash
git whence record --prompt <text> [options]
```

This is the primary way events enter the queue during manual workflows. For tools with native ACP integration, the tool writes directly to `queue.ndjson` in the same format — `record` provides the same capability via the command line.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt <text>` | *required* | The prompt text. Use `-` to read from stdin. |
| `--tool <identifier>` | Config default | Tool identifier (e.g., `claude-code`, `codex`) |
| `--session <id>` | `null` | Session or conversation identifier |
| `--response <text>` | `null` | Response text, if captured. Use `-` to read from stdin (after prompt). |
| `--response-file <path>` | `null` | Read response from a file |
| `--no-response` | `false` | Explicitly mark response as not captured (`response_captured: false`) |
| `--files <paths...>` | `null` | Files the prompt relates to (space-separated) |
| `--branch <name>` | Current branch | Override detected branch |
| `--model <identifier>` | `null` | Model identifier if known |
| `--tags <tags...>` | `null` | User-defined tags (space-separated) |
| `--context` | `false` | Auto-populate context fields (git_base_sha, workspace_state) |
| `--input-artifacts <paths...>` | `null` | Files provided to the AI tool (hashed at record time) |

**Behaviour:**

1. Generates `event_id` (prefixed `evt_`) and `timestamp`
2. If `--context` is set: captures `git_base_sha` from HEAD, `workspace_state` from `git status`, and hashes any `--input-artifacts` as raw bytes
3. Serializes the event as a single JSON line
4. Appends to `.git/acp/queue.ndjson`

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Event recorded |
| 1 | Missing required `--prompt` flag |
| 2 | ACP not initialized (run `git whence init`) |

**Examples:**

```bash
# Simple prompt recording
git whence record --tool claude-code --prompt "Refactor auth middleware to use DI"

# With context capture and input artifacts
git whence record --tool claude-code \
  --prompt "Optimize the user lookup query" \
  --files src/db/users.ts \
  --input-artifacts src/db/users.ts src/db/schema.ts \
  --context

# Response not captured (interactive coding session)
git whence record --tool cursor --prompt "Fix the failing test" --no-response

# Prompt from stdin (useful for long prompts or piping)
echo "Refactor the entire auth module to use..." | git whence record --tool claude-code --prompt -

# With response captured
git whence record --tool claude-code \
  --prompt "Write a migration for adding the index" \
  --response-file /tmp/claude-response.txt
```

---

### `git whence queue`

Inspect and manage the local event queue.

```bash
git whence queue [subcommand]
```

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `list` (default) | Show queued events |
| `count` | Print number of unconsumed events |
| `clear` | Delete all events from the queue |
| `export` | Dump queue contents to stdout as NDJSON |

**`git whence queue list`**

```bash
git whence queue list [--since <timestamp>] [--tool <identifier>]
```

Displays queued events in human-readable format:

```
Queue: 4 events

  1. [2026-02-28T10:21:33Z] claude-code
     "Refactor auth middleware to use DI"
     Files: src/middleware/auth.ts

  2. [2026-02-28T10:45:12Z] claude-code
     "Add tests for DI auth middleware"
     Files: src/middleware/auth.test.ts

  3. [2026-02-28T11:02:44Z] claude-code
     "Optimize user lookup query"
     Files: src/db/users.ts

  4. [2026-02-28T11:15:01Z] codex
     "Generate API client from OpenAPI spec"
     Files: src/api/client.ts
```

**`git whence queue clear`**

```bash
git whence queue clear [--force]
```

Deletes all events. Requires `--force` if queue has more than 0 events (safety check). Prints number of events cleared.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Queue is empty (for `list`, `export`) |
| 2 | ACP not initialized |

---

### `git whence attach`

Bundle queued events into a trace and attach to a commit via ACP-Git notes.

```bash
git whence attach [<commit>] [options]
```

This is the core command. It reads events from the queue, runs the redaction pipeline, computes hashes, assembles a trace, writes it as an ACP-Git envelope to `refs/notes/acp`, and marks the consumed events.

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `<commit>` | `HEAD` | Commit SHA or ref to attach the trace to |

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--since <sha>` | `null` | Only attach events recorded after this commit's timestamp |
| `--interactive` | `false` | Interactively select which events to attach |
| `--redaction <mode>` | Config default | Override redaction mode for this trace |
| `--force` | `false` | Attach even if redaction detects high-confidence secrets |
| `--dry-run` | `false` | Show what would be attached without writing |
| `--patch` | `false` | Compute `context.patch_hash` from the staged diff at attach time |
| `--patch-source <source>` | `staged` | Patch source: `staged`, `working-tree` |

**Behaviour:**

1. Read unconsumed events from `.git/acp/queue.ndjson`
2. Apply event filters (`--since`, `--interactive`) if specified
3. For each event with storable content:
   a. Run the secret scanner against prompt text (and response if captured)
   b. Replace matches with `[REDACTED:<type>]` tokens
   c. Set `redacted: true` on the event if any replacements occurred
4. Compute `prompt_hash` on the redacted prompt text (UTF-8, newline-normalized)
5. If `response_captured` is true: compute `response_hash` on the redacted response text, then discard response text if redaction mode doesn't store it
6. If `--patch` is set: compute `context.patch_hash` from `git diff --staged --no-color` (or `git diff --no-color` for `--patch-source working-tree`)
7. Resolve `target` from the commit argument: `{ "type": "git-commit", "id": "<full SHA>" }`
8. Assemble the trace object with all required fields
9. Compute `trace_hash` via canonical JSON serialization (RFC 8785, excluding `integrity` object)
10. Build the envelope (headers + compact single-line JSON body)
11. If a note already exists on the target commit: read existing note, append `\n---\n`, append new envelope
12. Write the note: `git notes --ref=refs/notes/acp add -f --file=- <commit>`
13. Mark consumed events in the queue (or clear queue if no filters were used)
14. Print summary

**Output:**

```
✓ Attached trace 20260228T103215Z_7f2c to a1b2c3d
  Events: 3
  Tool: claude-code
  Redaction: hash-response
  Secrets redacted: 0
  Trace hash: sha256:9f86d08...
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Trace attached successfully |
| 1 | No unconsumed events in queue (nothing to attach) |
| 2 | ACP not initialized |
| 3 | High-confidence secret detected and `--force` not set |
| 4 | Target commit not found |

**Examples:**

```bash
# Attach all queued events to HEAD
git whence attach

# Attach to a specific commit
git whence attach abc123

# Attach only recent events, keep older ones in queue
git whence attach --since def456

# Interactive selection
git whence attach --interactive

# Preview without writing
git whence attach --dry-run

# Include patch hash for code provenance
git whence attach --patch

# Full redaction mode override
git whence attach --redaction full
```

---

### `git whence show`

Display the ACP trace(s) attached to a commit.

```bash
git whence show [<commit>] [options]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `<commit>` | `HEAD` | Commit SHA or ref |

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format <format>` | `text` | Output format: `text`, `json`, `envelope` |
| `--prompts-only` | `false` | Show only prompt text from each event |
| `--context` | `false` | Show code provenance context (input artifacts, patch info) |
| `--verify` | `false` | Verify integrity hashes while displaying |

**Output (default text format):**

```
Commit: a1b2c3d feat: refactor auth middleware
Trace: 20260228T103215Z_7f2c
Tool: claude-code | Events: 3 | Redaction: hash-response
Integrity: ✓ valid

  Event 1 [2026-02-28T10:21:33Z]
  Prompt: "Refactor auth middleware to use dependency injection"
  Response: [hash-only] sha256:a3c1e2b...
  Files: src/middleware/auth.ts

  Event 2 [2026-02-28T10:33:45Z]
  Prompt: "The DI container should be passed in the constructor, not as a parameter"
  Response: [hash-only] sha256:b4d2f3c...
  Files: src/middleware/auth.ts

  Event 3 [2026-02-28T10:41:02Z]
  Prompt: "Add unit tests for the refactored middleware"
  Response: [hash-only] sha256:c5e3a4d...
  Files: src/middleware/auth.test.ts
```

**Output (`--prompts-only`):**

```
Commit: a1b2c3d — 3 prompts via claude-code

  1. "Refactor auth middleware to use dependency injection"
  2. "The DI container should be passed in the constructor, not as a parameter"
  3. "Add unit tests for the refactored middleware"
```

**Output (`--context`):**

```
Commit: a1b2c3d feat: refactor auth middleware
Trace: 20260228T103215Z_7f2c

  Base SHA: def456... (clean workspace)
  Input artifacts:
    src/middleware/auth.ts  sha256:7a8b9c...
    src/types/container.ts  sha256:1d2e3f...
  Patch: sha256:4g5h6i... (staged, git-unified-diff)

  Events: 3 via claude-code
  ...
```

**Output (`--format json`):**

Outputs the raw trace JSON object(s) — the JSON body from the envelope, not the envelope itself.

**Output (`--format envelope`):**

Outputs the raw envelope content as stored in the Git note, including headers.

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Trace(s) found and displayed |
| 1 | No ACP trace on this commit |
| 2 | ACP not initialized or notes ref not found |
| 3 | Integrity verification failed (with `--verify`) |

---

### `git whence log`

Show ACP trace summaries across a range of commits.

```bash
git whence log [<revision-range>] [options]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `<revision-range>` | `HEAD~10..HEAD` | Standard Git revision range |

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format <format>` | `text` | Output format: `text`, `json` |
| `--all` | `false` | Show all commits in range, including those without traces |
| `--stats` | `false` | Show summary statistics at the end |

**Output (default):**

```
a1b2c3d feat: refactor auth middleware
  ACP: 3 events via claude-code (hash-response)

d4e5f6a fix: optimize user lookup query
  ACP: 2 events via claude-code (hash-response)

7g8h9i0 chore: update CI config
  (no ACP trace)

b2c3d4e feat: add API client
  ACP: 1 event via codex (hash-response)
```

Without `--all`, commits without traces are omitted.

**Output (`--stats`):**

Appends a summary block:

```
---
Commits in range: 10
Commits with traces: 7 (70%)
Total events: 18
Tools: claude-code (15 events), codex (3 events)
Co-authored commits without traces: 0
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Success (even if no traces found) |
| 1 | Invalid revision range |
| 2 | ACP not initialized or notes ref not found |

---

### `git whence verify`

Validate ACP traces on commits against integrity rules and CI policies.

```bash
git whence verify [<revision-range>] --policy <policy> [options]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `<revision-range>` | Commits in current PR/branch | Standard Git revision range |

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--policy <policy>` | `integrity` | Policy to verify (see below) |
| `--threshold <float>` | `0.5` | Coverage threshold for `coverage` policy (0.0–1.0) |
| `--paths <glob...>` | `null` | Path patterns for `path-based` policy |
| `--format <format>` | `text` | Output format: `text`, `json` |
| `--quiet` | `false` | Suppress output, exit code only |

**Policies:**

**`integrity`** — Validate all traces present on commits in the range:

1. Envelope has all required headers
2. `ACP-Trace-Id`, `ACP-Event-Count`, `ACP-Redaction` headers match JSON body
3. JSON body parses and contains all required fields
4. `event_count` matches length of `events` array
5. `ACP-Trace-Hash` matches recomputed canonical JSON hash
6. Each event's `prompt_hash` matches SHA-256 of stored, normalized prompt (when present)
7. Events with `redacted: true` contain at least one `[REDACTED:...]` token
8. Events with `response_captured: false` do not have `response_hash` or `response`
9. All events conform to trace-level `redaction_mode`

Exits 0 if all traces valid (or no traces present). Exits 3 if any trace is invalid.

**`co-author`** — Check that commits with AI co-author signals have ACP traces:

1. Scan commit messages and trailers for co-author patterns:
   - `Co-authored-by:` trailers containing known AI tool identifiers
   - Known patterns: `Claude`, `GitHub Copilot`, `Cursor Tab`
2. For each commit with a co-author signal: verify an ACP trace exists
3. Report violations

Exits 0 if all co-authored commits have traces. Exits 3 if any co-authored commit lacks a trace.

**`coverage`** — Check that a minimum percentage of commits carry valid traces:

1. Count commits with valid traces vs total commits in range
2. Compare against `--threshold`

Exits 0 if coverage meets threshold. Exits 3 if below.

**`path-based`** — Require traces on commits touching specific paths:

1. For each commit in range: check if changed files match any `--paths` glob
2. For matching commits: verify an ACP trace exists

Exits 0 if all matching commits have traces. Exits 3 if any lack traces.

**`attestation`** — Require either an ACP trace or a `No-AI-Used` trailer:

1. For each commit in range: check for ACP trace OR `No-AI-Used` trailer in commit message
2. Report commits that have neither

Exits 0 if all commits are accounted for. Exits 3 if any commit has neither trace nor attestation.

**Output:**

```
Verifying policy: integrity
Range: origin/main..HEAD (6 commits)

  a1b2c3d ✓ valid (3 events, claude-code)
  d4e5f6a ✓ valid (2 events, claude-code)
  7g8h9i0 — no trace
  b2c3d4e ✓ valid (1 event, codex)
  e5f6a7b — no trace
  f6a7b8c ✓ valid (4 events, claude-code)

Result: PASS (4 traces verified, 0 invalid, 2 commits without traces)
```

```
Verifying policy: co-author
Range: origin/main..HEAD (6 commits)

  a1b2c3d Co-authored-by: Claude → trace present ✓
  d4e5f6a Co-authored-by: Claude → trace present ✓
  7g8h9i0 no co-author signal — skipped
  b2c3d4e no co-author signal — skipped
  e5f6a7b Co-authored-by: Claude → NO TRACE ✗
  f6a7b8c no co-author signal — skipped

Result: FAIL (1 co-authored commit without ACP trace)
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Policy passed |
| 1 | Invalid arguments or revision range |
| 2 | ACP not initialized or notes ref not found |
| 3 | Policy failed (violations found) |

---

### `git whence report`

Generate a provenance report for a set of commits.

```bash
git whence report [<revision-range>] [options]
```

Designed for CI integration. Produces structured output suitable for PR comments, artifacts, and dashboards.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format <format>` | `text` | Output format: `text`, `json`, `markdown` |
| `--commits <shas...>` | `null` | Explicit list of commit SHAs (alternative to revision range) |

**Output (`--format markdown`):**

```markdown
## ACP Provenance Summary

**AI-assisted commits:** 4 of 6 (67%)
**Tools used:** claude-code (3 commits), codex (1 commit)
**Total prompt events:** 12
**Integrity:** All traces valid ✓

| Commit | Tool | Events | First prompt |
|--------|------|--------|--------------|
| a1b2c3d | claude-code | 5 | "Refactor auth middleware to use DI" |
| d4e5f6a | claude-code | 3 | "Optimize query for user lookup" |
| 7g8h9i0 | codex | 2 | "Generate API client from OpenAPI spec" |
| b2c3d4e | claude-code | 2 | "Update error handling to match new middleware" |

**Co-authored commits without traces:** 1 ⚠️
- e5f6a7b `Co-authored-by: Claude` — missing ACP trace
```

**Output (`--format json`):**

```json
{
  "range": "origin/main..HEAD",
  "total_commits": 6,
  "traced_commits": 4,
  "coverage": 0.67,
  "total_events": 12,
  "tools": {
    "claude-code": { "commits": 3, "events": 10 },
    "codex": { "commits": 1, "events": 2 }
  },
  "integrity_valid": true,
  "co_author_violations": [
    { "sha": "e5f6a7b", "co_author": "Claude", "trace": null }
  ],
  "commits": [
    {
      "sha": "a1b2c3d",
      "message": "feat: refactor auth middleware",
      "trace_id": "20260228T103215Z_7f2c",
      "tool": "claude-code",
      "event_count": 5,
      "redaction_mode": "hash-response",
      "valid": true
    }
  ]
}
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Report generated |
| 1 | Invalid arguments or revision range |
| 2 | ACP not initialized or notes ref not found |

---

### `git whence reattach`

Migrate orphaned ACP traces after history rewriting (rebase, squash, amend).

```bash
git whence reattach [options]
```

**Behaviour:**

1. Find all notes in `refs/notes/acp` whose target SHAs are not reachable from any branch
2. For each orphaned note: search the reflog for a rebase/squash mapping to a successor commit
3. Present proposed mappings for user confirmation
4. For confirmed mappings: write new envelope records on successor commits
5. Optionally remove orphaned notes

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--auto` | `false` | Auto-confirm unambiguous mappings (still prompts for ambiguous ones) |
| `--dry-run` | `false` | Show proposed mappings without writing |
| `--cleanup` | `false` | Remove orphaned notes after successful migration |

**Output:**

```
Found 3 orphaned ACP traces:

  old-sha-1 → new-sha-a (reflog: rebase)
    Trace: 20260228T103215Z_7f2c (3 events, claude-code)
    Migrate? [Y/n] y

  old-sha-2 → new-sha-b (reflog: squash, 3 commits → 1)
    Trace: 20260228T112000Z_4d5e (2 events, claude-code)
    Trace: 20260228T113000Z_6f7g (1 event, codex)
    Migrate both to new-sha-b? [Y/n] y

  old-sha-3 → AMBIGUOUS (2 possible successors)
    Trace: 20260228T120000Z_8h9i (1 event, claude-code)
    Candidates:
      a) new-sha-c (feat: add caching layer)
      b) new-sha-d (fix: cache invalidation)
    Choose [a/b/skip]: a

Migrated: 3 traces
Skipped: 0
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Migration complete (or nothing to migrate) |
| 1 | No reflog available (pruned or shallow clone) |
| 2 | ACP not initialized or notes ref not found |

---

### `git whence push`

Convenience wrapper for pushing ACP notes to a remote.

```bash
git whence push [<remote>]
```

Equivalent to `git push <remote> refs/notes/acp`. Default remote is `origin`.

---

### `git whence fetch`

Convenience wrapper for fetching ACP notes from a remote.

```bash
git whence fetch [<remote>]
```

Equivalent to `git fetch <remote> refs/notes/acp:refs/notes/acp`. Default remote is `origin`.

If the fetch refspec is already configured (via `init`), this is a no-op — `git fetch` already pulls notes. This command exists for repos where `init` wasn't run or the refspec was removed.

---

## Queue file format

`.git/acp/queue.ndjson` — one JSON object per line. Events are appended during `record` and consumed during `attach`.

```jsonl
{"event_id":"evt_a1b2c3d4","timestamp":"2026-02-28T10:21:33.123Z","tool":"claude-code","prompt":"Refactor auth middleware to use DI","prompt_hash":"sha256:9f86d08...","response_captured":false,"files":["src/middleware/auth.ts"],"context":{"git_base_sha":"abc123...","workspace_state":"dirty"}}
{"event_id":"evt_e5f6a7b8","timestamp":"2026-02-28T10:45:12.456Z","tool":"claude-code","prompt":"Add tests for DI auth middleware","prompt_hash":"sha256:b4d2f3c...","response_captured":false,"files":["src/middleware/auth.test.ts"]}
```

Each line is a complete event object as defined in the ACP spec (Part 1: Events). The `prompt_hash` is computed at record time on the raw prompt text (pre-redaction). Redaction is applied at `attach` time and the hash is recomputed on the redacted text.

Events are consumed by `attach` in order. When `attach` runs without filters, the entire file is cleared after successful attachment. When filters are used (`--since`, `--interactive`), consumed events are removed and remaining events are rewritten to the file.

---

## Config file format

`.git/acp/config.json`:

```json
{
  "spec_version": "0.1.0",
  "notes_ref": "refs/notes/acp",
  "default_redaction": "hash-response",
  "default_tool": null,
  "max_queue_events": 5000,
  "redact_patterns_file": null
}
```

| Field | Description |
|-------|-------------|
| `spec_version` | ACP spec version this config was created with |
| `notes_ref` | Git ref for ACP notes (should not need changing) |
| `default_redaction` | Default redaction mode for `attach` |
| `default_tool` | Default tool identifier for `record` |
| `max_queue_events` | Warn when queue exceeds this count |
| `redact_patterns_file` | Path to custom redaction patterns file (relative to `.git/acp/`) |

---

## Custom redaction patterns

`.git/acp/redact_patterns.txt` — one regex pattern per line. Lines starting with `#` are comments.

```
# Company-specific API keys
MYCOMPANY-[A-Za-z0-9]{32}

# Internal service tokens
svc_tok_[A-Za-z0-9]{48}

# Project-specific secrets pattern
PROJECT_SECRET=[^\s]+
```

Custom patterns produce `[REDACTED:custom]` tokens. They run in addition to the built-in patterns defined in the spec.

---

## Native tool integration

Tools with native ACP support can write directly to `queue.ndjson` instead of requiring `git whence record`. The integration contract is:

1. Check that `.git/acp/queue.ndjson` exists (ACP is initialized)
2. Append one JSON line per prompt event, conforming to the event schema in ACP spec Part 1
3. Compute `prompt_hash` at record time on raw prompt text
4. If response is captured: include `response_captured: true` and the response text or hash
5. If response is not captured: set `response_captured: false`
6. Do not perform redaction (that happens at `attach` time)

Tools should not write to `refs/notes/acp` directly. The `attach` command is the single gate for redaction and trace assembly.

**Environment variable:** Tools can check for `ACP_QUEUE_PATH` as an override for the queue file location. Default is `.git/acp/queue.ndjson` relative to the repository root.

---

## Full pipeline example

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  acp-provenance:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install git-whence
          command: pip install -e .
          working_directory: cli
      - run:
          name: Fetch ACP notes
          command: git fetch origin refs/notes/acp:refs/notes/acp 2>/dev/null || true
      - run:
          name: Verify trace integrity
          command: git whence verify origin/main..HEAD --policy integrity
      - run:
          name: Check co-author compliance
          command: git whence verify origin/main..HEAD --policy co-author || true  # warn, don't block
      - run:
          name: Generate provenance report
          command: |
            git whence report origin/main..HEAD --format markdown > acp-summary.md
            git whence report origin/main..HEAD --format json > acp-report.json
      - run:
          name: Post PR comment
          command: |
            if [ -n "$CIRCLE_PULL_REQUEST" ]; then
              gh pr comment --body-file acp-summary.md
            fi
      - store_artifacts:
          path: acp-report.json
          destination: acp-report.json
      - store_artifacts:
          path: acp-summary.md
          destination: acp-summary.md

workflows:
  build-and-verify:
    jobs:
      - build
      - test
      - acp-provenance:
          requires:
            - build
```

---

## Exit code summary

All commands follow a consistent exit code scheme:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | User error (bad arguments, empty queue, invalid range) |
| 2 | Environment error (not a Git repo, ACP not initialized, notes ref missing) |
| 3 | Verification or policy failure |
| 4 | Target not found (commit doesn't exist) |