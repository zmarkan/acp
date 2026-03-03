"""git whence init — Initialize WHENCE in the current Git repository."""

import sys

from .. import git
from ..config import WHENCEConfig, save
from ..exitcodes import SUCCESS


def register(subparsers):
    p = subparsers.add_parser("init", help="Initialize WHENCE in the current Git repository")
    p.add_argument(
        "--redaction",
        choices=["full", "hash-response", "hash-all"],
        default="hash-response",
        help="Default redaction mode (default: hash-response)",
    )
    p.add_argument(
        "--tool",
        default=None,
        help="Default tool identifier for record commands",
    )
    p.set_defaults(func=run)


def run(args) -> int:
    try:
        git.git_root()
    except git.NotAGitRepo:
        print("Error: not a Git repository", file=sys.stderr)
        return 1

    whence = git.whence_dir()

    # Check if already initialized
    if (whence / "config.json").exists():
        from ..config import load
        cfg = load()
        print(f"WHENCE already initialized in {whence}", file=sys.stderr)
        print(f"  redaction: {cfg.default_redaction}", file=sys.stderr)
        print(f"  tool: {cfg.default_tool}", file=sys.stderr)
        return 2

    # Create directory structure
    whence.mkdir(parents=True, exist_ok=True)

    # Write config
    cfg = WHENCEConfig(
        default_redaction=args.redaction,
        default_tool=args.tool,
    )
    save(cfg, whence / "config.json")

    # Create empty queue
    (whence / "queue.ndjson").write_text("")

    # Configure git to fetch WHENCE notes
    existing_fetch = git.config_get_all("remote.origin.fetch")
    whence_fetch = "+refs/notes/whence:refs/notes/whence"
    if whence_fetch not in existing_fetch:
        try:
            git.config_add("remote.origin.fetch", whence_fetch)
        except git.GitError:
            # No remote origin configured yet -- that's fine
            pass

    # Configure notes rewriting for rebase
    git.config_set("notes.rewriteRef", "refs/notes/whence")
    git.config_set("notes.rewriteMode", "concatenate")

    print(f"Initialized WHENCE in {whence}")
    print(f"  redaction: {cfg.default_redaction}")
    if cfg.default_tool:
        print(f"  tool: {cfg.default_tool}")
    return SUCCESS
