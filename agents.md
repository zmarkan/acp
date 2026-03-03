# agents.md — Using git-whence in this repository

> This is a self-referential guide. The spec and reference implementation it describes were built using the same tool, in the same process, recorded by the same system. Run `git whence log --all --stats` to see the provenance of the document you're reading.

---

## What is this repo?

WHENCE is an open standard for recording how AI contributed to a codebase. `git-whence` is its reference CLI implementation. Every AI-assisted commit in this repository carries a provenance trace — the prompts, tool metadata, and integrity hashes that explain *how* the code was produced.

## Prerequisites

```bash
# Install git-whence from source (the CLI lives in cli/)
cd cli && pip install -e . && cd ..

# Initialize WHENCE in your working copy (idempotent)
git whence init

# Fetch existing traces from the remote
git fetch origin refs/notes/whence:refs/notes/whence
```

After installation, Git auto-discovers the `git-whence` binary — all commands work as `git whence <command>`.

---

## The workflow

WHENCE uses a **queue-then-attach** model. Events accumulate locally during development. You attach them to final-form commits after rebasing and cleanup.

### 1. Record events as you work

If your AI tool has native WHENCE integration (e.g. writes directly to `.git/whence/queue.ndjson`), events are captured automatically. Otherwise, record manually:

```bash
git whence record --tool claude-code \
  --prompt "Refactor auth middleware to use dependency injection" \
  --files src/middleware/auth.ts
```

For long prompts, pipe from stdin:

```bash
echo "Your prompt here..." | git whence record --tool claude-code --prompt -
```

### 2. Work normally — commit, rebase, squash

The queue is a plain file (`.git/whence/queue.ndjson`) outside Git's object store. Rebases, squashes, and amends don't touch it. Clean up your history however you like.

### 3. Attach traces to final commits

```bash
# Attach all queued events to HEAD
git whence attach

# Or attach to a specific commit
git whence attach abc123

# Preview what would be attached
git whence attach --dry-run
```

Attach runs the redaction pipeline (secret scanning), computes integrity hashes, bundles events into a trace, and writes it as a Git note under `refs/notes/whence`.

### 4. Push traces to the remote

```bash
git whence push
# Equivalent to: git push origin refs/notes/whence
```

---

## Reading traces

```bash
# See trace summaries across recent commits
git whence log

# See traces for a specific range
git whence log origin/main..HEAD

# Full trace detail for a commit
git whence show <commit>

# Just the prompts (quick scan of intent)
git whence show <commit> --prompts-only

# Raw JSON output
git whence show <commit> --format json

# Stats across the repo
git whence log --all --stats
```

---

## Verification

```bash
# Check that all traces have valid hashes and structure
git whence verify origin/main..HEAD --policy integrity

# Flag AI co-authored commits that lack traces
git whence verify origin/main..HEAD --policy co-author

# Generate a markdown report (useful for PR comments)
git whence report origin/main..HEAD --format markdown
```

---

## CI integration

This repository runs WHENCE verification in CI via GitHub Actions (`.github/workflows/whence-provenance.yml`). The pipeline:

1. Fetches WHENCE notes from the remote
2. Verifies trace integrity across all PR commits
3. Checks co-author compliance (commits with `Co-authored-by: Claude` must have traces)
4. Generates provenance reports (markdown + JSON)
5. Posts a summary comment on the PR

---

## Redaction modes

Traces are redacted at write time. The mode is set during `init` or overridden per `attach`.

| Mode | Prompt | Response | When to use |
|------|--------|----------|-------------|
| `full` | Stored | Stored | Private repos, full audit trail |
| `hash-response` | Stored | Hash only | **Default.** Keep prompts, protect output |
| `hash-all` | Hash only | Hash only | Maximum privacy, compliance-sensitive |

```bash
# Override for a single attach
git whence attach --redaction full
```

---

## After history rewriting

If you've already attached traces and then rebase:

```bash
# Migrate orphaned traces to new commit SHAs
git whence reattach --dry-run   # preview
git whence reattach             # execute

# If traces were already pushed, force-push the notes ref
git push --force origin refs/notes/whence
```

The recommended workflow avoids this: attach *after* rebasing, not before.

---

## Queue management

```bash
# See what's queued
git whence queue list

# Count pending events
git whence queue count

# Clear the queue (requires --force if non-empty)
git whence queue clear --force

# Export queue as NDJSON
git whence queue export
```

---

## For AI agents working on this repo

If you are an AI coding agent contributing to this repository:

1. **Your contributions are recorded.** The human operator will attach WHENCE traces to commits that include your work. The prompt that initiated your session becomes part of the permanent provenance record.

2. **Add the co-author trailer.** Include `Co-authored-by: Claude Opus 4.6 <noreply@anthropic.com>` (or the appropriate identifier) in commit messages. CI checks for this signal and verifies a matching trace exists.

3. **Don't modify `.git/whence/` directly.** Use `git whence record` and `git whence attach` commands. The queue format and envelope format are specified — direct manipulation risks producing invalid traces.

4. **Understand what gets shared.** In the default `hash-response` mode, your prompts are stored in full but your responses are hashed. In `full` mode, both are stored. In `hash-all` mode, both are hashed. The human operator chooses the mode.

5. **Secrets are caught at attach time.** The redaction pipeline scans for API keys, JWTs, private keys, and other credential patterns before writing traces. If you include secrets in prompts or responses, they will be replaced with `[REDACTED:<type>]` tokens.

---

## Quick reference

| Task | Command |
|------|---------|
| Initialize WHENCE | `git whence init` |
| Record a prompt | `git whence record --tool claude-code --prompt "..."` |
| View the queue | `git whence queue list` |
| Attach to HEAD | `git whence attach` |
| Attach to specific commit | `git whence attach <sha>` |
| View traces on a commit | `git whence show <sha>` |
| View trace log | `git whence log` |
| Verify integrity | `git whence verify --policy integrity` |
| Generate report | `git whence report --format markdown` |
| Push traces | `git whence push` |
| Fetch traces | `git whence fetch` |
| Migrate after rebase | `git whence reattach` |

---

## Further reading

- [SPEC.md](SPEC.md) — the full WHENCE specification (trace format, Git binding, guidance)
- [cli/CLI.md](cli/CLI.md) — complete CLI reference with all flags and examples
- [README.md](README.md) — project overview and quick start
