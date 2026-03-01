"""git whence queue — Inspect and manage the local event queue."""

import sys

from .. import queue
from ..exitcodes import SUCCESS, USER_ERROR


def register(subparsers):
    p = subparsers.add_parser("queue", help="Inspect and manage the local event queue")
    sub = p.add_subparsers(dest="subcommand")

    # list (default)
    list_p = sub.add_parser("list", help="Show queued events")
    list_p.add_argument("--since", default=None, help="Show events after this timestamp")
    list_p.add_argument("--tool", default=None, help="Filter by tool identifier")
    list_p.set_defaults(func=run_list)

    # count
    count_p = sub.add_parser("count", help="Print number of unconsumed events")
    count_p.set_defaults(func=run_count)

    # clear
    clear_p = sub.add_parser("clear", help="Delete all events from the queue")
    clear_p.add_argument("--force", action="store_true", help="Required safety check")
    clear_p.set_defaults(func=run_clear)

    # export
    export_p = sub.add_parser("export", help="Dump queue contents as NDJSON")
    export_p.set_defaults(func=run_export)

    p.set_defaults(func=run_default)


def run_default(args) -> int:
    """Default: show list."""
    return run_list(args)


def run_list(args) -> int:
    events = queue.read_events()
    if not events:
        print("Queue: 0 events")
        return 1

    # Apply filters
    if hasattr(args, "since") and args.since:
        events = [e for e in events if e.get("timestamp", "") > args.since]
    if hasattr(args, "tool") and args.tool:
        events = [e for e in events if e.get("tool") == args.tool]

    print(f"Queue: {len(events)} events")
    print()
    for i, event in enumerate(events, 1):
        ts = event.get("timestamp", "unknown")
        tool = event.get("tool", "unknown")
        prompt = event.get("prompt", "")
        # Truncate long prompts for display
        if len(prompt) > 80:
            prompt = prompt[:77] + "..."
        files = event.get("files", [])
        files_str = ", ".join(files) if files else ""

        print(f"  {i}. [{ts}] {tool}")
        print(f'     "{prompt}"')
        if files_str:
            print(f"     Files: {files_str}")
        print()
    return SUCCESS


def run_count(args) -> int:
    n = queue.count()
    print(n)
    return SUCCESS


def run_clear(args) -> int:
    n = queue.count()
    if n == 0:
        print("Queue is already empty")
        return SUCCESS

    if not args.force:
        print(f"Queue has {n} events. Use --force to clear.", file=sys.stderr)
        return USER_ERROR

    cleared = queue.clear()
    print(f"Cleared {cleared} events from queue")
    return SUCCESS


def run_export(args) -> int:
    content = queue.export_ndjson()
    if not content.strip():
        return 1
    sys.stdout.write(content)
    return SUCCESS
