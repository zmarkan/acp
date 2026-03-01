# ACP — AI Code Provenance

### An open standard for recording how AI contributed to your codebase

---

## The problem

Software is increasingly co-authored by humans and AI. Developers prompt Claude Code, Codex, Cursor, Copilot, and a growing list of tools — then commit the results. The commit message says *what* changed. The diff shows *how*. But the reasoning — the prompts, the iterations, the intent — vanishes the moment the session closes.

This matters because:

- **Code review is flying blind.** Reviewers see output but not intent. Was this a one-shot generation or the result of fifteen refinements? Did the developer ask the AI to optimize for performance or readability? That context changes how you review.
- **Auditing is impossible.** When a vulnerability surfaces in AI-assisted code, there's no trail back to the prompt that produced it. No way to ask "what were they trying to do?" after the fact.
- **Institutional knowledge is lost.** The same way commit messages preserve *why* a change was made, prompt history preserves *how* a team uses AI — their patterns, their shortcuts, their mistakes. Without records, every developer starts from zero.
- **Supply chain accountability has a gap.** We have SBOMs for dependencies, signed commits for authorship, and SLSA for build provenance. But there's no equivalent for AI contributions — the fastest-growing input to modern codebases.

ACP closes that gap.

---

## What ACP is

ACP is three things:

1. **A data format** — a specification for recording AI development events (prompts, tool metadata, session context) and bundling them into immutable traces.
2. **A linking convention** — a standard way to attach those traces to version control artifacts, with a defined binding for Git.
3. **A set of principles** — shared by default, redacted at write time, tool-agnostic, and built to survive real-world development workflows.

ACP is **not** a product, a platform, or a service. It's an open interchange format. Any tool can produce ACP traces. Any CI system can consume them. The reference implementation is a CLI, but the standard lives independently.

---

## Specification layers

ACP consists of two layers:

**The Trace Format** (Part 1) defines the data model for events, traces, redaction, and integrity verification. It is transport-agnostic and can be implemented independently of any linking mechanism.

**A Linking Binding** (Part 2) defines how traces attach to version control artifacts. This spec defines one binding: **ACP-Git**, which uses Git notes under `refs/notes/acp`. Future revisions may define additional bindings (GitHub Checks API, Bitbucket Code Insights, GitLab CI metadata, etc.).

The trace format is the standard. An ACP trace is valid regardless of where it's stored. Bindings define how traces connect to the things they describe.

---

## Design principles

### 1. Shared by default

ACP traces exist so that reviewers can see intent, auditors can verify provenance, and teams can build institutional knowledge. None of that works if traces stay on a developer's laptop. ACP traces are designed to be shared. Local-only operation is available but is opt-out, not opt-in. Organizations with strict compliance requirements may default to `hash-all` mode, which shares trace structure and metadata while keeping all content as hashes.

### 2. Redacted at write time

Because traces are shared, sensitive content must be caught before it enters storage. ACP runs secret detection and redaction at **attach time** — the moment events move from the local queue into a trace record. Once a trace is written, it's treated as immutable. Redaction is prevention, not remediation.

### 3. Don't pollute history

The ACP-Git binding uses Git notes as the linking mechanism. Notes attach metadata to commits without changing commit hashes and without cluttering `git log`.

### 4. Tool-agnostic

The format doesn't assume any particular AI tool. A trace produced by Claude Code, Codex, Cursor, a custom wrapper, or a manual entry should all be valid ACP.

### 5. Machine-readable, human-scannable

Traces are structured data with plain-text envelopes. Both are parseable by scripts and glanceable by humans.

### 6. Survive real workflows

Developers squash, rebase, amend, and force-push. ACP is designed around this. The local queue survives history rewriting. Traces attach to final-form commits. Recovery behaviour for edge cases is implementation-defined.

---

## Architecture overview

**The local queue** — a working buffer on the developer's machine. Events accumulate here during development as NDJSON. The queue lives outside the version control object store, unaffected by rebases or squashes.

**The trace record** — the shared artifact. When a developer runs `attach`, queued events are redacted, bundled into a trace, and written via the appropriate binding. The trace is self-contained.

```
Development phase:              Attach phase:              Share phase:
┌─────────────┐                ┌──────────────┐           ┌──────────────┐
│ Local queue  │  ──attach──>  │ Trace record │  ──push─> │ Shared trace │
│ (NDJSON)     │    redact      │ (via binding)│           │ (via binding)│
│              │    bundle      │              │           │              │
└─────────────┘    hash         └──────────────┘           └──────────────┘
```

---

# Part 1: Trace Format

Everything in this section is binding-agnostic.

## Spec version

All ACP artifacts include a `spec_version` field. The current version is `0.1.0`. Consumers must check this field and handle unknown versions gracefully.

## Events

An **event** is the atomic unit of ACP: one user-issued prompt interaction with an AI tool. Events inherit redaction rules from their enclosing trace; events do not carry their own `redaction_mode`.

In v0.1, ACP does not standardize sub-prompt tool calls or multi-step agent actions. Producers should record one event per user-issued prompt. Internal tool calls, file edits, and iterative agent steps within a single prompt may be represented as additional events in future spec versions.

```json
{
  "spec_version": "0.1.0",
  "event_id": "evt_a1b2c3d4",
  "timestamp": "2026-02-28T10:21:33.123Z",
  "tool": "claude-code",
  "session_id": "sess_x9y8z7",
  "prompt": "Refactor the auth middleware to use dependency injection",
  "prompt_hash": "sha256:9f86d08...",
  "response_hash": "sha256:a3c1e2b...",
  "response_captured": true,
  "redacted": false,
  "branch": "feature/auth-refactor",
  "files": ["src/middleware/auth.ts", "src/middleware/auth.test.ts"],
  "cwd": "/home/dev/project",
  "context": {
    "git_base_sha": "abc123def456...",
    "workspace_state": "dirty",
    "input_artifacts": [
      { "path": "src/middleware/auth.ts", "hash": "sha256:..." }
    ],
    "patch_hash": "sha256:...",
    "patch_source": "staged",
    "patch_format": "git-unified-diff"
  }
}
```

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `spec_version` | string | ACP spec version (semver) |
| `event_id` | string | Unique identifier (prefixed `evt_`) |
| `timestamp` | string | ISO 8601 UTC |
| `prompt_hash` | string | SHA-256 of normalized, post-redaction prompt text, prefixed `sha256:` |

### Conditionally required fields

| Field | Condition | Description |
|-------|-----------|-------------|
| `prompt` | Required unless trace `redaction_mode` is `hash-all` | The prompt text (post-redaction) |
| `response` | Present only when trace `redaction_mode` is `full` and `response_captured` is `true` | The AI response text (post-redaction) |
| `response_hash` | Required when `response_captured` is `true` and response text is not stored | SHA-256 of normalized, post-redaction response |

### Response capture semantics

Not all AI tools provide reliable access to response content. Interactive coding flows often stream changes directly into files without exposing the response as text.

| `response_captured` | `response_hash` | `response` | Meaning |
|---------------------|-----------------|-------------|---------|
| `true` | Required (unless stored in full) | Per redaction mode | Response was available; hash computed from redacted text |
| `false` | Must be omitted | Must be omitted | Response was not capturable |

When `response_captured` is `false`, producers should populate `context.patch_hash` (the hash of the resulting diff) to give reviewers concrete provenance tied to the code change.

`response_captured` defaults to `true` if omitted, preserving backward compatibility.

### Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Tool identifier (see Tool Registration) |
| `session_id` | string | Session/conversation identifier |
| `branch` | string | Git branch at time of event |
| `files` | string[] | Files the prompt relates to |
| `cwd` | string | Working directory |
| `tags` | string[] | User-defined tags |
| `model` | string | Model identifier if known |
| `tokens_in` | integer | Input token count if available |
| `tokens_out` | integer | Output token count if available |
| `redacted` | boolean | `true` if any content was modified by the redaction pipeline |
| `context` | object | Code provenance context (see below) |

### Code provenance context

The optional `context` object captures what code the AI tool had access to and what changes resulted. This is what makes ACP "code provenance" rather than a prompt diary.

| Field | Type | Description |
|-------|------|-------------|
| `context.git_base_sha` | string | Commit the working tree was based on at time of prompting |
| `context.workspace_state` | string | `clean` or `dirty` |
| `context.input_artifacts` | array | Files provided to the tool: `[{ "path": "...", "hash": "sha256:..." }]` |
| `context.patch_hash` | string | SHA-256 of the resulting diff/patch (see Patch hashing below) |
| `context.patch_source` | string | Origin of the patch: `staged`, `working-tree`, or `tool-export` |
| `context.patch_format` | string | Format of the patch text, e.g. `git-unified-diff` |
| `context.diff_summary` | string | Short human-readable description of what changed |

All `context` fields are optional. Tools should populate what they can. Even partial context (`git_base_sha` and `workspace_state`) is significantly more useful than none.

When `response_captured` is `false`, producers should make a best effort to populate `context.patch_hash` at attach time to give reviewers concrete provenance tied to the code change.

**Patch hashing:** `context.patch_hash` is the SHA-256 of the patch text after UTF-8 encoding and line-ending normalization (per the Hashing section). Producers should compute the patch from the following sources in order of preference:

1. The staged diff (`git diff --staged --no-color`)
2. The working-tree diff (`git diff --no-color`)
3. A tool-exported patch if the AI tool provides one

Set `context.patch_source` to indicate which source was used. Set `context.patch_format` to `git-unified-diff` for Git-produced diffs.

**Input artifact hashing:** `context.input_artifacts[].hash` is the SHA-256 of the **raw file bytes** at time of prompting, with no text normalization applied. This differs from prompt/response hashing (which normalizes line endings) because files may be binary.

## Traces

A **trace** bundles one or more events into a record linked to a version control artifact.

```json
{
  "spec_version": "0.1.0",
  "trace_id": "20260228T103215Z_7f2c",
  "created_at": "2026-02-28T10:32:15.000Z",
  "target": {
    "type": "git-commit",
    "id": "def456abc789..."
  },
  "branch": "feature/auth-refactor",
  "tool_summary": {
    "primary_tool": "claude-code",
    "tools_used": ["claude-code"],
    "sessions": ["sess_x9y8z7"]
  },
  "redaction_mode": "hash-response",
  "event_count": 5,
  "events": [],
  "integrity": {
    "trace_hash": "sha256:...",
    "algorithm": "sha256-canonical-json"
  }
}
```

### Required trace fields

| Field | Type | Description |
|-------|------|-------------|
| `spec_version` | string | ACP spec version |
| `trace_id` | string | Unique identifier (timestamp + random suffix) |
| `created_at` | string | ISO 8601 UTC |
| `target` | object | The artifact this trace is linked to |
| `target.type` | string | Artifact type (e.g., `git-commit`) |
| `target.id` | string | Artifact identifier (e.g., full commit object name) |
| `redaction_mode` | string | One of: `full`, `hash-response`, `hash-all` |
| `event_count` | integer | Number of events in this trace |
| `events` | Event[] | Array of event objects |
| `integrity.trace_hash` | string | SHA-256 of canonical JSON (see Hashing) |
| `integrity.algorithm` | string | Hash algorithm and method identifier |

### Redaction mode authority

A trace has exactly one `redaction_mode`. All events in the trace must conform to it:

- In `full` mode: events may contain `prompt` and `response` (when captured)
- In `hash-response` mode: events must contain `prompt`; response must not be stored, only `response_hash`
- In `hash-all` mode: events must not contain `prompt` or `response`; only hashes

Events do not carry their own `redaction_mode`. The trace-level field is authoritative. Mixed-mode traces are not permitted in v0.1.

### No truncation in v0.1

Prompt and response text must be stored in full (post-redaction) or not at all. Truncated previews are not permitted because they break the property that hashes are verifiable against stored content.

If a trace would exceed practical size limits due to large prompts, producers should either split into multiple traces on the same artifact or use `hash-all` mode. Future spec revisions may define a truncation scheme with dual hashes.

---

## Redaction

### Modes

| Mode | Prompt | Response | Use case |
|------|--------|----------|----------|
| `full` | Stored (post-redaction) | Stored (post-redaction) | Private repos, full audit trail |
| `hash-response` | Stored (post-redaction) | Hash only | **Default.** Keep prompts, protect output |
| `hash-all` | Hash only | Hash only | Maximum privacy, compliance-sensitive |

### Write-time redaction pipeline

Redaction runs **at attach time**, before the trace record is created. This is the only gate.

The pipeline:

1. Read queued events
2. For each event with capturable content (prompt, and response if `response_captured` is `true`):
   a. Run the secret scanner against the text
   b. Replace any matches with `[REDACTED:<type>]` tokens
   c. Set `"redacted": true` on the event if any replacements occurred
3. Compute all hashes on the **redacted** content
4. Discard any plaintext that the redaction mode does not permit storing (e.g., response text in `hash-response` mode)
5. Assemble the trace
6. Write the trace via the appropriate binding

**Critical rule:** hashes are always computed on the redacted text, even for content that will not be stored. In `hash-response` mode, the producer runs redaction on the response, computes `response_hash` from the redacted response, then discards the response text. The hash corresponds to the redacted form, never the original.

### Automatic secret patterns

Implementations must scan for and replace:

| Pattern | Token | Examples |
|---------|-------|----------|
| API keys with common prefixes | `[REDACTED:api-key]` | `sk-`, `ak_`, `AKIA`, `ghp_`, `gho_`, `xoxb-` |
| JWT-format strings | `[REDACTED:jwt]` | Three base64url segments separated by dots |
| Bearer tokens | `[REDACTED:bearer-token]` | `Bearer ` followed by a token-like string |
| AWS access keys | `[REDACTED:aws-key]` | `AKIA` followed by 16 alphanumeric characters |
| Private keys | `[REDACTED:private-key]` | `-----BEGIN ... PRIVATE KEY-----` blocks |
| User-defined patterns | `[REDACTED:custom]` | Patterns from user-configured redaction rules |

**Note on PII:** ACP is not a data loss prevention system. The patterns above target secrets and credentials. Teams handling PII or customer data should use `hash-all` mode and implement additional scanning appropriate to their compliance requirements.

### Failure behaviour

If the scanner detects a high-confidence secret (private key blocks, AWS key format) and the redaction mode would store the content in plaintext, the implementation should either redact in-place or refuse the attach unless `--force` is provided. High-confidence secrets must never be silently written to a trace in plaintext.

### Post-hoc remediation

If a secret enters a shared trace, remediation is binding-specific (see ACP-Git binding). In all cases: **treat the secret as compromised and rotate it immediately.**

---

## Hashing

### Algorithms

All hashes use SHA-256, prefixed with `sha256:`.

### Text normalization

Before hashing any text content (prompts, responses, patches):

1. Encode as UTF-8
2. Normalize line endings to `\n` (replace `\r\n` and `\r` with `\n`)
3. Do **not** trim leading/trailing whitespace
4. Hash the resulting byte sequence

### What gets hashed

- **`prompt_hash`**: SHA-256 of the normalized, post-redaction prompt text
- **`response_hash`**: SHA-256 of the normalized, post-redaction response text. This applies even when the response is not stored: the producer redacts, hashes, then discards the text.
- **`trace_hash`**: SHA-256 of the canonical JSON encoding of the trace (see below)
- **`context.patch_hash`**: SHA-256 of the normalized patch text (line-ending normalization applies)
- **`context.input_artifacts[].hash`**: SHA-256 of the **raw file bytes** (no text normalization; files may be binary)

### Canonical JSON for trace hashing

ACP uses a canonical JSON encoding aligned with RFC 8785 (JSON Canonicalization Scheme):

1. Serialize the trace object as JSON
2. **Exclude** the `integrity` object from the serialization
3. Sort all object keys lexicographically (Unicode code point order) at every nesting level
4. Arrays preserve their original element order
5. Use compact encoding: no whitespace between tokens (no spaces after `:` or `,`)
6. Strings: escape `"`, `\`, and control characters U+0000–U+001F; all other characters appear as literal UTF-8. ACP does not perform Unicode normalization (NFC/NFD); strings are serialized as given after redaction.
7. Numbers: shortest representation, no trailing zeros, no leading zeros, no positive sign. Producers should avoid non-integer numbers where possible for canonicalization simplicity.
8. Encode the result as UTF-8 and hash the byte sequence

Implementations should validate their canonical JSON output against test vectors provided in the reference implementation.

---

## Tool registration

ACP maintains a non-normative registry of known tool identifiers:

| Identifier | Tool |
|------------|------|
| `claude-code` | Anthropic Claude Code |
| `codex` | OpenAI Codex CLI |
| `cursor` | Cursor IDE |
| `copilot` | GitHub Copilot |
| `aider` | Aider |
| `cline` | Cline |
| `windsurf` | Windsurf |
| `custom` | Any unregistered tool |

Tool identifiers should use lowercase alphanumeric characters and hyphens. Producers may also use reverse-DNS identifiers (e.g., `com.anthropic.claude-code`) for collision resistance. The registry is non-normative; consumers must accept any string as a valid tool identifier. Future spec revisions may introduce a formal registry.

---

# Part 2: ACP-Git Binding

The ACP-Git binding defines how ACP traces attach to Git commits using Git notes.

## Target type

For ACP-Git, the trace `target` must be:

```json
{
  "type": "git-commit",
  "id": "<full commit object name>"
}
```

The `id` is the canonical commit object name as returned by `git rev-parse <commit>`. This works for both SHA-1 and SHA-256 Git repositories.

## Notes ref

ACP-Git uses the ref `refs/notes/acp`.

## Envelope format

ACP-Git stores traces in an **envelope format** — plain-text headers followed by a compact JSON body. This is designed for human scannability and safe multi-trace appending.

### Single trace

```
ACP-Spec-Version: 0.1.0
ACP-Trace-Id: 20260228T103215Z_7f2c
ACP-Trace-Hash: sha256:a1b2c3...
ACP-Event-Count: 5
ACP-Tool: claude-code
ACP-Redaction: hash-response

{"spec_version":"0.1.0","trace_id":"20260228T103215Z_7f2c",...}
```

### Multiple traces on one commit

Multiple traces are separated by a line containing exactly `---`:

```
ACP-Spec-Version: 0.1.0
ACP-Trace-Id: 20260228T103215Z_7f2c
ACP-Trace-Hash: sha256:a1b2c3...
ACP-Event-Count: 5
ACP-Tool: claude-code
ACP-Redaction: hash-response

{"spec_version":"0.1.0","trace_id":"20260228T103215Z_7f2c",...}
---
ACP-Spec-Version: 0.1.0
ACP-Trace-Id: 20260228T154500Z_9a3e
ACP-Trace-Hash: sha256:d4e5f6...
ACP-Event-Count: 3
ACP-Tool: codex
ACP-Redaction: hash-response

{"spec_version":"0.1.0","trace_id":"20260228T154500Z_9a3e",...}
```

### Producer rules

1. Each envelope record starts with header lines in the format `Key: Value`
2. A blank line separates headers from the JSON body
3. The JSON body must be the complete trace object serialized as **compact single-line JSON**. Producers must not pretty-print or insert newlines into the JSON body. Newlines within JSON string values must be escaped as `\n`.
4. The separator line must be exactly `---` with no surrounding whitespace
5. When appending a new trace to an existing note: read the existing note, append `\n---\n`, then append the new envelope record. Do not parse or modify existing records.

**Required headers:**

| Header | Description |
|--------|-------------|
| `ACP-Spec-Version` | Spec version of this trace |
| `ACP-Trace-Id` | Trace identifier |
| `ACP-Trace-Hash` | Integrity hash of the JSON body |
| `ACP-Event-Count` | Number of events in the trace |
| `ACP-Tool` | Primary tool identifier |
| `ACP-Redaction` | Redaction mode used |

**Header–body relationship:** The JSON body is the canonical source of truth. Headers are informational summaries for scanning and quick validation. Consumers should validate that `ACP-Trace-Id`, `ACP-Event-Count`, and `ACP-Redaction` match the corresponding fields in the JSON body. Mismatches indicate a malformed record.

### Consumer rules

1. **Primary parsing:** Split note content on `\n---\n` to get individual records. For each record, split on the first blank line to separate headers from JSON body. Parse the JSON body as a trace object.
2. **Fallback for concatenated notes:** If `---` separators are missing (e.g., due to `notes.rewriteMode concatenate`), scan for lines starting with `ACP-Spec-Version:` as record boundaries. For each record: read headers until blank line, then read the next non-empty line as the JSON body.
3. **Bare JSON fallback:** If the note content starts with `{`, treat it as a single trace object. If it starts with `[`, treat it as a JSON array where each element is an independent trace object. This supports forward compatibility with alternative producers.
4. Headers are case-insensitive for matching purposes.

## Sharing and transport

### Pushing notes (default and recommended)

```bash
git push origin refs/notes/acp
```

Teams should configure automatic fetching:

```ini
[remote "origin"]
    fetch = +refs/notes/acp:refs/notes/acp
```

Without this, notes must be fetched explicitly:

```bash
git fetch origin refs/notes/acp:refs/notes/acp
```

### What travels with the note

The note is self-contained. It carries the full trace including all event data (post-redaction), metadata, and integrity hashes. No external files or secondary storage is required.

### Local-only operation

Teams that require local-only traces don't push the notes ref. This is opt-out, not opt-in.

## Post-hoc remediation (ACP-Git)

If a secret enters a pushed note:

1. Overwrite the note locally with corrected envelope content
2. Force-push the notes ref: `git push --force origin refs/notes/acp`
3. **Treat the secret as compromised.** Rotate immediately.

ACP treats traces as immutable by convention. ACP-Git remediation may overwrite notes for secret removal; such overwrites should be treated as history-altering events equivalent to rewriting published metadata. Overwriting a note doesn't rewrite commit history — only the notes ref changes.

## History rewriting: rebases, squashes, and amends

### The problem

When you rebase or squash, Git creates new commits with new SHAs. Notes are keyed by SHA. After a squash, notes point at orphaned commits and new commits have no notes.

Git's `notes.rewriteRef` config can copy notes during rebase, but it's unreliable in practice — most developers don't configure it, most GUI tools don't trigger it, and squashing many commits into one produces overlapping notes.

### The recommended workflow: attach late

**Attach traces to final-form commits, not work-in-progress ones.**

The local queue is the buffer for this. Events accumulate during development regardless of how many intermediate commits, rebases, or squashes happen. The queue is a plain file outside Git's object store — history rewriting doesn't touch it.

The workflow:

1. Work on your feature branch. Prompts accumulate in the queue.
2. Rebase, squash, amend — clean up your history.
3. Run `attach` against your final commits.

Traces map to **logical changes** — the squashed commits that represent meaningful units of work — rather than messy development history.

### Attaching to specific commits

By default, `attach` links all queued events to HEAD. For more granular control:

- `attach <sha>` — attach to a specific commit
- `attach --since <sha>` — attach only events recorded after a specific commit's timestamp; remaining events stay in the queue
- `attach --interactive` — choose which events map to which commits

When `attach` is run without filters, all unconsumed events are included and the queue is cleared. When filters are used (`--since`, `--interactive`), only selected events are consumed; the rest remain in the queue for future attaches.

### Recovery: reattach

If traces have already been attached and then history is rewritten, `reattach` attempts to migrate orphaned notes:

1. Find notes pointing at SHAs not reachable from any branch
2. Use the reflog to identify the rebase/squash mapping
3. Present the proposed migration for confirmation
4. Write new envelope records onto the new SHAs

This is **best-effort**. Ambiguous mappings require user confirmation. The implementation must never silently remap.

### Force-push considerations

If you've pushed notes then rebased and force-pushed a branch:

1. Reattach locally
2. Force-push the notes ref: `git push --force origin refs/notes/acp`

CI systems should handle missing notes gracefully during the window between a branch force-push and the notes force-push.

### Configuration for automatic note rewriting

```bash
git config notes.rewriteRef refs/notes/acp
git config notes.rewriteMode concatenate
```

When Git concatenates notes, it may produce records without `---` separators. Consumers handle this via the fallback parsing rule (scan for `ACP-Spec-Version:` headers). The attach-late workflow is the primary recommendation.

## Local storage (ACP-Git)

```
.git/acp/
├── config.json              # Local configuration
├── queue.ndjson             # Pending events (local buffer)
└── redact_patterns.txt      # User-defined redaction patterns (optional)
```

### config.json

```json
{
  "spec_version": "0.1.0",
  "notes_ref": "refs/notes/acp",
  "default_redaction": "hash-response",
  "default_tool": null,
  "max_queue_events": 5000
}
```

### queue.ndjson

One JSON event per line. Events are appended during development and consumed when `attach` runs. The queue is a local scratch file — never committed, never shared, never enters a Git object.

## Compliance and verification (ACP-Git)

### Detecting ACP

A repository uses ACP if the ref `refs/notes/acp` exists and contains at least one valid envelope record.

### Validating a trace

A trace is valid if:

1. The envelope record has all required headers
2. `ACP-Trace-Id`, `ACP-Event-Count`, and `ACP-Redaction` headers match the JSON body
3. The JSON body parses and contains all required trace fields
4. `spec_version` is a recognized version
5. `event_count` matches the length of `events`
6. `ACP-Trace-Hash` matches the recomputed canonical JSON hash
7. Each event's `prompt_hash` matches the SHA-256 of its stored, normalized `prompt` (when present)
8. Events with `"redacted": true` contain at least one `[REDACTED:...]` token
9. Events with `"response_captured": false` do not have `response_hash` or `response` fields
10. All events conform to the trace-level `redaction_mode`

### CI integration

AI-assisted code is entering pipelines faster than teams can review it. Provenance traces give CI systems context that diffs alone don't carry: which tool produced the change, whether the developer iterated or accepted a first-pass generation, and what files the AI had access to. This context enables smarter validation decisions.

**What CI can do:** verify that traces present on commits are structurally valid and integrity-checked, report what proportion of commits carry traces, require attestation for commits that don't, and enforce trace requirements on specific paths or branches.

**What CI cannot do:** determine whether a commit without a trace was genuinely hand-written or was AI-assisted with no trace attached. ACP can verify provenance that exists. It cannot prove a negative. Policies should be designed with this limitation in mind.

**Important nuance: some tools self-identify.** Some AI coding tools add co-author signals to commits — for example, Claude Code adds a `Co-authored-by` trailer. When present, these signals give CI a reliable detection mechanism: a commit that self-identifies as AI-assisted but carries no ACP trace is a verifiable policy violation. However, many tools (Codex, Cursor, Copilot, and any manual copy-paste from a chat interface) do not add co-author signals. For those commits, CI cannot distinguish AI-assisted from hand-written. Policies should account for this asymmetry.

Example pipeline step:

```yaml
# .circleci/config.yml (or equivalent)
acp-verify:
  steps:
    - run: git whence verify --policy integrity
    - run: git whence verify --policy co-author  # flag AI co-authored commits without traces
    - run: git whence report --format json > acp-report.json
    - store_artifacts:
        path: acp-report.json
```

### Recommended CI policies

**Integrity (always recommended):** All traces present on commits in the PR are structurally valid — hashes match, events conform to the trace redaction mode, required fields are present. This catches malformed or tampered traces. It says nothing about commits without traces.

**Coverage reporting (recommended starting point):** Report the percentage of commits in the PR that carry ACP traces, the tools used, and event counts. Non-blocking. Gives teams visibility into AI-assisted development patterns before enforcing anything.

**Coverage threshold:** Require that a minimum percentage of commits (e.g., 50%) carry valid traces, or that at least one commit per PR has a trace. Commits without traces are permitted — they may be hand-written, config changes, or merge commits.

**Path-based:** Require valid traces on commits that touch specified paths (e.g., `src/auth/`, `security/`, `infrastructure/`). Commits touching other paths are not checked for trace presence. Useful for high-risk areas where provenance matters most.

**Co-author-aware:** Commits containing AI co-author signals (e.g., `Co-authored-by` trailers from Claude Code) must have a valid ACP trace. This is the strongest enforceable policy because the tool has self-identified — a commit that says it was AI-assisted but carries no provenance is a clear violation. Commits without co-author signals are not blocked but may still be subject to coverage reporting.

**Attestation:** Commits without traces and without co-author signals require an explicit `No-AI-Used` trailer or equivalent. This shifts the burden to developers to attest when they *didn't* use AI. Teams should understand that this is a social contract, not a technical guarantee — it relies on developer honesty for tools that don't self-identify.

Teams should start with integrity checking and coverage reporting, then adopt stricter policies as their workflow matures.

---

# Part 3: Guidance

## Size and retention

ACP does not impose hard size limits in v0.1. Recommended guidance:

- **Aim to keep individual traces under 256KB.** This keeps note operations fast and tooling responsive.
- **For long sessions (50+ events), split** across multiple traces on the same commit rather than creating one large trace.
- **For very large prompts,** use `hash-all` mode rather than attempting truncation. Truncation is not permitted in v0.1 because it breaks hash verifiability.

Future spec revisions may introduce normative size limits based on real-world usage data.

## Review integration

ACP traces carry the context that code review currently lacks. The goal is not a separate "provenance page" that reviewers have to visit — it's making AI development context available at the point of review, where it changes decisions.

### Level 1: PR summary (CI-generated)

The simplest integration. A CI job runs `git whence report` across all commits in the PR and posts a summary as a PR comment or check annotation.

```yaml
# Pipeline step
acp-review-summary:
  steps:
    - run: git fetch origin refs/notes/acp:refs/notes/acp
    - run: |
        git whence report \
          --commits $(git log --format=%H origin/main..HEAD) \
          --format markdown > acp-summary.md
    - run: gh pr comment --body-file acp-summary.md
```

The summary answers the questions reviewers actually ask:

```markdown
## ACP Provenance Summary

**AI-assisted commits:** 4 of 6 (67%)
**Tools used:** claude-code (3 commits), codex (1 commit)
**Total prompt events:** 12

| Commit | Tool | Events | Prompt summary |
|--------|------|--------|----------------|
| a1b2c3d | claude-code | 5 | "Refactor auth middleware to use DI" → 3 iterations, "Add tests for DI auth" → 2 iterations |
| d4e5f6a | claude-code | 3 | "Optimize query for user lookup" → 1 iteration, "Add index migration" → 2 iterations |
| 7g8h9i0 | codex | 2 | "Generate API client from OpenAPI spec" → 1 iteration, "Fix type errors in generated client" → 1 iteration |
| b2c3d4e | claude-code | 2 | "Update error handling to match new middleware pattern" → 2 iterations |
| e5f6a7b | — | — | No ACP trace (hand-written or untracked) |
| f6a7b8c | — | — | No ACP trace (hand-written or untracked) |

**Commits with co-author signals but no trace:** 0
**Integrity:** All traces valid ✓
```

This is the demo you can build first. A reviewer glances at this before reading the diff and already knows: most of this PR was AI-assisted, the auth refactor went through multiple iterations (worth reviewing closely), the API client was generated in one shot from a spec (check the spec, not the generated code), and two commits have no traces.

### Level 2: Local review with git whence

Reviewers who want to dig deeper can use the CLI alongside their normal review workflow:

```bash
# Show traces for all commits in a branch
git whence log origin/main..HEAD

# Show full trace for a specific commit
git whence show a1b2c3d

# Show just the prompts (quick scan of intent)
git whence show a1b2c3d --prompts-only

# Show which files the AI had access to vs which files changed
git whence show a1b2c3d --context
```

The `--context` output is particularly useful for reviewers. When `input_artifacts` shows the AI only saw two files but the commit touches five, the reviewer knows the AI didn't have full context for the change. When `patch_hash` is present but `response_captured` is false, the reviewer knows this was an interactive coding session — the AI streamed changes directly into files.

### Level 3: Inline annotations (future bindings)

The full vision requires platform-specific bindings (ACP-GitHub, ACP-Bitbucket, ACP-GitLab). These would surface trace data inline in the diff view:

- Hovering over a function shows the prompt that generated it and the iteration count
- Files are annotated with whether they were AI-generated, AI-modified, or untouched
- Review checklists adapt based on provenance — one-shot generations get flagged for closer review, multi-iteration refinements get lighter treatment

The trace format already carries everything these integrations need. The data model doesn't change; only the presentation layer does. This is why the spec separates trace format from bindings.

### What reviewers learn from trace metadata

Event count per commit is a proxy for refinement. A single event means the developer accepted the first output. Ten events means they iterated. High iteration counts on critical code paths are reassuring. Single-event generation of complex logic is a flag.

`context.input_artifacts` reveals scope. If the AI saw the full module, it had context for its changes. If it saw a single file in isolation, it may have made assumptions about interfaces or dependencies.

`context.workspace_state: dirty` means the AI was working on top of uncommitted changes — the generation may depend on code that isn't in the diff yet.

Prompt text (in `full` or `hash-response` mode) reveals intent. "Optimize for readability" and "optimize for performance" produce very different code that looks equally valid in a diff. Knowing the intent changes the review.

## Optional: alternative linking mechanisms (ACP-Git)

### Commit trailers

For teams that want AI provenance visible in `git log`:

```
feat: refactor auth middleware

ACP-Trace-Id: 20260228T103215Z_7f2c
ACP-Trace-Hash: sha256:...
ACP-Event-Count: 5
```

**Warning:** Adding trailers to existing commits requires `--amend`, which rewrites the commit hash.

### Ledger commits

For teams that want traces in the commit graph:

```bash
git commit --allow-empty -m "acp: trace 20260228T103215Z_7f2c (5 events, claude-code)"
```

**Warning:** This adds commits to history. Use only with explicit team agreement.

---

## Roadmap

**Trace format:**
- Signed traces (GPG/SSH signing)
- Trace status lifecycle (`active` → `superseded` → `revoked`)
- Formal tool identifier registry
- Truncation scheme with dual hashes
- Normative size limits
- RFC 2119 conformance language

**Bindings:**
- ACP-GitHub (Checks API, PR annotations)
- ACP-Bitbucket (Code Insights, build annotations)
- ACP-GitLab (CI metadata, merge request notes)

**Tooling:**
- Import adapters for tool-native logs (Claude Code, Codex, Cursor)
- CI templates for surfacing ACP data in pull request UIs
- Aggregate queries across traces
- Trace export to Markdown, HTML, PDF
- VS Code and JetBrains extensions

---

## FAQ

**Why not just use better commit messages?**
Commit messages describe *what* changed. ACP records *how* and *why* through AI interaction. They're complementary.

**Why Git notes for the reference binding?**
Built into Git, travel with the repo, same push/fetch semantics as branches, no external infrastructure required.

**Could ACP use something other than Git notes?**
Yes. The trace format is binding-agnostic. Future revisions may define bindings for other platforms.

**Why are traces shared by default?**
Because blind code review, impossible auditing, and lost institutional knowledge all require that traces be accessible beyond the original developer.

**Why hash responses instead of storing them?**
AI responses can contain sensitive information or be very large. The default `hash-response` mode stores prompts (which the developer controls) while protecting model output.

**What if a tool can't capture the response?**
Set `response_captured: false`. Producers should populate `context.patch_hash` to provide concrete provenance.

**What happens when I rebase?**
The local queue is unaffected. Attach traces after rebasing. If already attached, use `reattach` to migrate notes.

**What if a secret gets into a pushed note?**
Overwrite the note and force-push the notes ref. Treat the secret as compromised.

**Can CI require ACP traces on all AI-assisted commits?**
Only when the AI tool self-identifies. Claude Code adds `Co-authored-by` trailers, which CI can detect and require matching traces for. Tools that don't signal co-authorship (Codex, Cursor, Copilot) produce commits indistinguishable from hand-written ones. For those, ACP relies on coverage reporting, team conventions, and optional attestation — not technical enforcement.

---

## Contributing

ACP is an open standard developed in the open. The specification, reference implementation, and related tooling live at https://github.com/zmarkan/acp.

To propose changes, open an RFC issue. Breaking changes require a spec version bump and a migration path.

---

*ACP v0.1.0 — Draft*