# Contributing to ACP

ACP is an open standard. Contributions are welcome — whether that's feedback on the spec, improvements to git-whence, new CI examples, or bug reports.

## How to contribute

**Feedback on the spec:** Open an issue. Describe the problem, what the spec currently says, and what you think it should say. Even "this section confused me" is useful.

**Bug reports:** Open an issue with steps to reproduce, expected behaviour, and actual behaviour. Include your git-whence version (`git whence --version`) and Git version (`git --version`).

**Code contributions:** Fork the repo, create a branch, make your changes, open a PR. PRs should include tests for new functionality.

**CI examples:** If you've set up ACP verification in a CI system not already covered (GitLab CI, Jenkins, Buildkite, etc.), we'd love to include it. Add your config to `examples/ci/` with a brief README explaining any platform-specific considerations.

## Proposing spec changes

The spec is versioned. Changes follow different processes depending on scope:

**Editorial fixes** (typos, clarifications that don't change meaning): open a PR directly.

**Non-breaking additions** (new optional fields, new guidance, new CI policy types): open an issue first describing the addition and its motivation. Discussion happens on the issue. If there's consensus, submit a PR. These are included in patch or minor version bumps.

**Breaking changes** (changes to required fields, changes to hashing or redaction behaviour, changes to envelope format): open an RFC issue using the RFC template. Breaking changes require a spec minor or major version bump and a documented migration path. These have a higher bar — they need clear justification and consideration of backward compatibility.

## Development setup

```bash
git clone https://github.com/zmarkan/acp.git
cd acp
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Lint:

```bash
ruff check .
```

## ACP on ACP

This repository uses ACP. AI-assisted commits carry provenance traces. If you use AI tools when contributing, we encourage you to record and attach traces to your commits:

```bash
git whence init
git whence record --tool <your-tool> --prompt "your prompt"
# ... work and commit ...
git whence attach
```

This isn't required for contributions, but it helps us dogfood the standard and gives reviewers useful context on your PR.

## Code of conduct

Be respectful. Assume good intent. Focus on the work.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.