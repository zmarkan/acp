"""git whence init — Initialize ACP in the current Git repository."""

import sys

from .. import git
from ..config import ACPConfig, save
from ..exitcodes import ENV_ERROR, SUCCESS


def register(subparsers):
    p = subparsers.add_parser("init", help="Initialize ACP in the current Git repository")
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
        root = git.git_root()
    except git.NotAGitRepo:
        print("Error: not a Git repository", file=sys.stderr)
        return 1

    acp = git.acp_dir()

    # Check if already initialized
    if (acp / "config.json").exists():
        from ..config import load
        cfg = load()
        print(f"ACP already initialized in {acp}", file=sys.stderr)
        print(f"  redaction: {cfg.default_redaction}", file=sys.stderr)
        print(f"  tool: {cfg.default_tool}", file=sys.stderr)
        return 2

    # Create directory structure
    acp.mkdir(parents=True, exist_ok=True)

    # Write config
    cfg = ACPConfig(
        default_redaction=args.redaction,
        default_tool=args.tool,
    )
    save(cfg, acp / "config.json")

    # Create empty queue
    (acp / "queue.ndjson").write_text("")

    # Configure git to fetch ACP notes
    existing_fetch = git.config_get_all("remote.origin.fetch")
    acp_fetch = "+refs/notes/acp:refs/notes/acp"
    if acp_fetch not in existing_fetch:
        try:
            git.config_add("remote.origin.fetch", acp_fetch)
        except git.GitError:
            # No remote origin configured yet -- that's fine
            pass

    # Configure notes rewriting for rebase
    git.config_set("notes.rewriteRef", "refs/notes/acp")
    git.config_set("notes.rewriteMode", "concatenate")

    print(f"Initialized ACP in {acp}")
    print(f"  redaction: {cfg.default_redaction}")
    if cfg.default_tool:
        print(f"  tool: {cfg.default_tool}")
    return SUCCESS
