"""CLI entry point: argparse dispatcher for git-whence commands."""

import argparse
import sys

from . import __version__
from .exitcodes import ENV_ERROR, USER_ERROR
from .git import ACPNotInitialized, NotAGitRepo
from .commands import (
    init,
    record,
    queue_cmd,
    attach,
    show,
    log,
    verify,
    report,
    reattach,
    push,
    fetch,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="git-whence",
        description="ACP (AI Code Provenance) reference implementation",
    )
    parser.add_argument(
        "--version", action="version", version=f"git-whence {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    # Register all commands
    modules = [
        init, record, queue_cmd, attach, show,
        log, verify, report, reattach, push, fetch,
    ]
    for module in modules:
        module.register(subparsers)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return USER_ERROR

    try:
        return args.func(args)
    except NotAGitRepo:
        print("Error: not a Git repository", file=sys.stderr)
        return ENV_ERROR
    except ACPNotInitialized:
        print("Error: ACP not initialized (run 'git whence init')", file=sys.stderr)
        return ENV_ERROR
    except KeyboardInterrupt:
        return 130
