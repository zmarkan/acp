# Broken Provenance Example

This file was added by an AI coding assistant, but the developer forgot to run
`git whence attach` before committing. As a result, this commit carries no ACP
trace — no record of the prompt that produced it, no integrity hash, no event
metadata.

## What went wrong

Lorem ipsum dolor sit amet, consectetur adipiscing elit. The developer opened
their AI coding tool, prompted it to generate this file, reviewed the output,
and staged it for commit. So far, so normal. Sed do eiusmod tempor incididunt
ut labore et dolore magna aliqua — but at the critical moment between staging
and committing, the provenance step was skipped entirely.

Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut
aliquip ex ea commodo consequat. The local event queue had the prompt recorded.
The redaction pipeline was ready. The attach command would have bundled
everything into a trace and written it to `refs/notes/acp`. Duis aute irure
dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
pariatur.

## Why CI should catch this

Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia
deserunt mollit anim id est laborum. A commit that self-identifies as
AI-assisted (via a `Co-authored-by` trailer) but carries no ACP trace is a
verifiable policy violation. The CI pipeline runs `git whence verify` with the
`co-author` policy, which flags exactly this scenario.

Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Without the trace, reviewers
cannot see the original prompt, cannot verify integrity, and cannot determine
whether the output was a one-shot generation or the result of careful
iteration. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.

## The missing step

The developer should have run:

```bash
git whence attach
```

This would have taken the queued events, run the redaction pipeline, computed
integrity hashes, and written the trace to the Git note on this commit. Instead,
the prompt context is gone — lost the moment the session closed.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu
fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
culpa qui officia deserunt mollit anim id est laborum.
