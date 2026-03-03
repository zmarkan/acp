"""git whence record — Record a prompt event to the local queue."""

import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import git, queue, hashing, ids, config
from ..exitcodes import SUCCESS, USER_ERROR


def register(subparsers):
    p = subparsers.add_parser("record", help="Record a prompt event to the local queue")
    p.add_argument(
        "--prompt",
        required=True,
        help="The prompt text. Use '-' to read from stdin.",
    )
    p.add_argument("--tool", default=None, help="Tool identifier (e.g., claude-code)")
    p.add_argument("--session", default=None, help="Session/conversation identifier")
    p.add_argument("--response", default=None, help="Response text, if captured. Use '-' for stdin.")
    p.add_argument("--response-file", default=None, help="Read response from a file")
    p.add_argument(
        "--no-response",
        action="store_true",
        help="Mark response as not captured",
    )
    p.add_argument("--files", nargs="*", default=None, help="Files the prompt relates to")
    p.add_argument("--branch", default=None, help="Override detected branch")
    p.add_argument("--model", default=None, help="Model identifier if known")
    p.add_argument("--tags", nargs="*", default=None, help="User-defined tags")
    p.add_argument(
        "--context",
        action="store_true",
        help="Auto-populate context fields (git_base_sha, workspace_state)",
    )
    p.add_argument(
        "--input-artifacts",
        nargs="*",
        default=None,
        help="Files provided to the AI tool (hashed at record time)",
    )
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_whence_initialized()
    cfg = config.load()

    # Read prompt
    prompt_text = args.prompt
    if prompt_text == "-":
        prompt_text = sys.stdin.read()

    if not prompt_text:
        print("Error: --prompt is required and cannot be empty", file=sys.stderr)
        return USER_ERROR

    # Build event
    now = datetime.now(timezone.utc)
    event = {
        "spec_version": "0.1.0",
        "event_id": ids.generate_event_id(),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "prompt": prompt_text,
        "prompt_hash": hashing.sha256_text(prompt_text),
    }

    # Tool
    tool = args.tool or cfg.default_tool
    if tool:
        event["tool"] = tool

    # Session
    if args.session:
        event["session_id"] = args.session

    # Branch
    branch = args.branch or git.current_branch()
    if branch:
        event["branch"] = branch

    # Files
    if args.files:
        event["files"] = args.files

    # Model
    if args.model:
        event["model"] = args.model

    # Tags
    if args.tags:
        event["tags"] = args.tags

    # Response handling
    if args.no_response:
        event["response_captured"] = False
    else:
        response_text = None
        if args.response:
            response_text = args.response if args.response != "-" else sys.stdin.read()
        elif args.response_file:
            response_text = Path(args.response_file).read_text()

        if response_text is not None:
            event["response_captured"] = True
            event["response"] = response_text
            event["response_hash"] = hashing.sha256_text(response_text)

    # Context
    if args.context:
        ctx = {}
        try:
            ctx["git_base_sha"] = git.rev_parse("HEAD")
        except git.GitError:
            pass
        ctx["workspace_state"] = "clean" if git.is_working_tree_clean() else "dirty"

        if args.input_artifacts:
            artifacts = []
            for path_str in args.input_artifacts:
                p = Path(path_str)
                if p.exists():
                    raw = p.read_bytes()
                    artifacts.append({
                        "path": path_str,
                        "hash": hashing.sha256_bytes(raw),
                    })
            if artifacts:
                ctx["input_artifacts"] = artifacts

        event["context"] = ctx

    # Working directory
    event["cwd"] = str(Path.cwd())

    # Append to queue
    queue.append_event(event)

    # Warn if queue is getting large
    n = queue.count()
    if n > cfg.max_queue_events:
        print(f"Warning: queue has {n} events (exceeds {cfg.max_queue_events})", file=sys.stderr)

    print(f"Recorded event {event['event_id']}")
    return SUCCESS
