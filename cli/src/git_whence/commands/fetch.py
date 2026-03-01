"""git whence fetch — Fetch ACP notes from a remote."""

import sys

from .. import git
from ..exitcodes import SUCCESS


def register(subparsers):
    p = subparsers.add_parser("fetch", help="Fetch ACP notes from a remote")
    p.add_argument("remote", nargs="?", default="origin", help="Remote name (default: origin)")
    p.set_defaults(func=run)


def run(args) -> int:
    rc = git.fetch_ref(args.remote, "refs/notes/acp", "refs/notes/acp")
    if rc != 0:
        print(f"Error: failed to fetch refs/notes/acp from {args.remote}", file=sys.stderr)
    return rc
