"""git whence push — Push ACP notes to a remote."""

import sys

from .. import git
from ..exitcodes import SUCCESS


def register(subparsers):
    p = subparsers.add_parser("push", help="Push ACP notes to a remote")
    p.add_argument("remote", nargs="?", default="origin", help="Remote name (default: origin)")
    p.set_defaults(func=run)


def run(args) -> int:
    rc = git.push_ref(args.remote, "refs/notes/acp")
    if rc != 0:
        print(f"Error: failed to push refs/notes/acp to {args.remote}", file=sys.stderr)
    return rc
