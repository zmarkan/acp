# WHENCE

An open standard for recording how AI contributed to your codebase.

> This repository is built with WHENCE. Every AI-assisted commit carries a provenance trace. Run `git whence log` to see how the standard that defines provenance was itself built.

## The problem

Software is increasingly co-authored by humans and AI. The commit message says *what* changed, the diff shows *how*, but the reasoning — the prompts, the iterations, the intent — vanishes when the session closes.

WHENCE closes that gap by providing:

1. **A data format** for recording AI development events (prompts, tool metadata, session context) as immutable traces
2. **A linking convention** for attaching those traces to version control artifacts (Git notes for the reference binding)
3. **A set of principles** — shared by default, redacted at write time, tool-agnostic, built to survive real workflows

## Quick start

### Viewing traces on this repo

```bash
git clone https://github.com/zmarkan/whence.git
cd whence
git fetch origin refs/notes/whence:refs/notes/whence
git whence log
```

### Recording traces (Phase 1 — bootstrap)

Before the `git-whence` CLI exists, use the bootstrap script to attach traces manually:

```bash
# After an AI-assisted commit
./scripts/whence-bootstrap.sh $(git rev-parse HEAD) claude-code "Your prompt here"

# Push traces to remote
git push origin refs/notes/whence
```

### Recording traces (Phase 2 — git-whence)

Once the CLI is available:

```bash
# Traces accumulate in a local queue during development
# After rebasing/squashing, attach to final commits
git whence attach

# View traces
git whence log
git whence show <commit>

# Verify integrity
git whence verify --policy integrity

# Push traces
git push origin refs/notes/whence
```

## How it works

```
Development phase:              Attach phase:              Share phase:
┌─────────────┐                ┌──────────────┐           ┌──────────────┐
│ Local queue  │  ──attach──>  │ Trace record │  ──push─> │ Shared trace │
│ (NDJSON)     │    redact     │ (via binding)│           │ (via binding)│
│              │    bundle     │              │           │              │
└─────────────┘    hash        └──────────────┘           └──────────────┘
```

Events accumulate in a local queue during development. When you run `attach`, they are redacted, bundled into a trace, and written as a Git note. Traces attach to **final-form commits** — after rebasing and squashing — so they survive real workflows.

## Redaction modes

| Mode | Prompt | Response | Use case |
|------|--------|----------|----------|
| `full` | Stored | Stored | Private repos, full audit trail |
| `hash-response` | Stored | Hash only | **Default.** Keep prompts, protect output |
| `hash-all` | Hash only | Hash only | Maximum privacy, compliance-sensitive |

Secrets are detected and redacted at write time, before traces are created. Once written, traces are immutable.

## Supported tools

WHENCE is tool-agnostic. Any AI coding tool can produce valid traces:

| Identifier | Tool |
|------------|------|
| `claude-code` | Anthropic Claude Code |
| `codex` | OpenAI Codex CLI |
| `cursor` | Cursor IDE |
| `copilot` | GitHub Copilot |
| `aider` | Aider |
| `cline` | Cline |
| `windsurf` | Windsurf |

## Repository structure

```
whence/
├── SPEC.md                    # The specification
├── LICENSE                    # Apache 2.0
├── CONTRIBUTING.md            # How to propose changes
├── README.md                  # This file
├── scripts/
│   └── whence-bootstrap.sh    # Phase 1 manual trace attachment
├── cli/                       # git-whence source (planned)
├── examples/                  # Example traces (planned)
└── schema/                    # JSON Schema for validation (planned)
```

## CI integration

```yaml
whence-verify:
  steps:
    - run: git fetch origin refs/notes/whence:refs/notes/whence
    - run: git whence verify --policy integrity
    - run: git whence verify --policy co-author
    - run: git whence report --format json > whence-report.json
```

## Specification

The full specification is in [SPEC.md](SPEC.md). It covers:

- **Part 1: WHENCE Trace Format** — events, traces, redaction, hashing, integrity
- **Part 2: WHENCE Git Binding** — envelope format, Git notes, history rewriting, CI policies
- **Part 3: Guidance** — size limits, review integration, alternative linking

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). To propose changes, open an RFC issue. Breaking changes require a spec version bump and a migration path.

## License

Apache 2.0 — see [LICENSE](LICENSE).





