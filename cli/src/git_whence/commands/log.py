"""git whence log — Show ACP trace summaries across a range of commits."""

import json
import sys

from .. import git, envelope
from ..exitcodes import SUCCESS, USER_ERROR, ENV_ERROR


def register(subparsers):
    p = subparsers.add_parser("log", help="Show ACP trace summaries across commits")
    p.add_argument(
        "revision_range",
        nargs="?",
        default="HEAD~10..HEAD",
        help="Git revision range (default: HEAD~10..HEAD)",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument("--all", action="store_true", dest="show_all", help="Include commits without traces")
    p.add_argument("--stats", action="store_true", help="Show summary statistics")
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_acp_initialized()

    try:
        commits = git.log_range(args.revision_range)
    except git.GitError:
        print(f"Error: invalid revision range: {args.revision_range}", file=sys.stderr)
        return USER_ERROR

    if not commits:
        print("No commits in range")
        return SUCCESS

    # Gather trace data for each commit
    entries = []
    for commit in commits:
        note = git.notes_show(commit["sha"])
        traces = []
        if note:
            try:
                traces = envelope.parse_note_content(note)
            except (ValueError, json.JSONDecodeError):
                pass

        entries.append({
            "commit": commit,
            "traces": traces,
        })

    if args.output_format == "json":
        return _output_json(entries, args)

    return _output_text(entries, args)


def _output_text(entries: list[dict], args) -> int:
    for entry in entries:
        commit = entry["commit"]
        traces = entry["traces"]
        sha = commit["short_sha"]
        msg = commit["message"]

        if traces:
            for trace_obj in traces:
                event_count = trace_obj.get("event_count", 0)
                tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
                mode = trace_obj.get("redaction_mode", "unknown")
                print(f"{sha} {msg}")
                print(f"  ACP: {event_count} events via {tool} ({mode})")
                print()
        elif args.show_all:
            print(f"{sha} {msg}")
            print("  (no ACP trace)")
            print()

    if args.stats:
        _print_stats(entries)

    return SUCCESS


def _output_json(entries: list[dict], args) -> int:
    result = []
    for entry in entries:
        commit = entry["commit"]
        traces = entry["traces"]
        item = {
            "sha": commit["sha"],
            "short_sha": commit["short_sha"],
            "message": commit["message"],
            "traces": traces,
        }
        result.append(item)
    print(json.dumps(result, indent=2))

    if args.stats:
        _print_stats(entries)

    return SUCCESS


def _print_stats(entries: list[dict]) -> None:
    total = len(entries)
    traced = sum(1 for e in entries if e["traces"])
    total_events = 0
    tools: dict[str, int] = {}

    for entry in entries:
        for trace_obj in entry["traces"]:
            ec = trace_obj.get("event_count", 0)
            total_events += ec
            tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
            tools[tool] = tools.get(tool, 0) + ec

    # Check for co-authored commits without traces
    co_authored_no_trace = 0
    for entry in entries:
        if not entry["traces"]:
            trailers = entry["commit"].get("trailers", "")
            if _has_ai_co_author(trailers):
                co_authored_no_trace += 1

    pct = (traced / total * 100) if total > 0 else 0
    tools_str = ", ".join(f"{t} ({n} events)" for t, n in sorted(tools.items()))

    print("---")
    print(f"Commits in range: {total}")
    print(f"Commits with traces: {traced} ({pct:.0f}%)")
    print(f"Total events: {total_events}")
    if tools_str:
        print(f"Tools: {tools_str}")
    print(f"Co-authored commits without traces: {co_authored_no_trace}")


def _has_ai_co_author(trailers: str) -> bool:
    """Check if trailers contain AI co-author signals."""
    lower = trailers.lower()
    ai_signals = ["claude", "github copilot", "cursor tab", "copilot"]
    for signal in ai_signals:
        if signal in lower and "co-authored-by" in lower:
            return True
    return False
