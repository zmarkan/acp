"""git whence report — Generate a provenance report for a set of commits."""

import json
import sys

from .. import git, envelope, hashing
from ..exitcodes import SUCCESS, USER_ERROR


def register(subparsers):
    p = subparsers.add_parser("report", help="Generate a provenance report")
    p.add_argument(
        "revision_range",
        nargs="?",
        default=None,
        help="Git revision range",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument(
        "--commits",
        nargs="*",
        default=None,
        help="Explicit list of commit SHAs",
    )
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_whence_initialized()

    # Gather commits
    if args.commits:
        commits = []
        for sha in args.commits:
            try:
                full_sha = git.rev_parse(sha)
                msg = git.commit_message(sha).split("\n")[0]
                commits.append({
                    "sha": full_sha,
                    "short_sha": full_sha[:7],
                    "message": msg,
                    "trailers": git.commit_trailers(sha),
                })
            except git.GitError:
                print(f"Warning: commit not found: {sha}", file=sys.stderr)
    else:
        revision_range = args.revision_range
        if not revision_range:
            try:
                git.rev_parse("origin/main")
                revision_range = "origin/main..HEAD"
            except git.GitError:
                revision_range = "HEAD~10..HEAD"

        try:
            commits = git.log_range(revision_range)
        except git.GitError:
            print(f"Error: invalid revision range: {revision_range}", file=sys.stderr)
            return USER_ERROR

    if not commits:
        print("No commits to report on")
        return SUCCESS

    # Gather trace data
    report_data = _gather_report_data(commits)

    if args.output_format == "json":
        _output_json(report_data)
    elif args.output_format == "markdown":
        _output_markdown(report_data)
    else:
        _output_text(report_data)

    return SUCCESS


def _gather_report_data(commits: list[dict]) -> dict:
    """Gather all data needed for the report."""
    total = len(commits)
    traced_commits = []
    untraced_commits = []
    co_author_violations = []
    all_tools: dict[str, dict] = {}  # tool -> {"commits": int, "events": int}
    total_events = 0
    integrity_valid = True

    for commit in commits:
        note = git.notes_show(commit["sha"])
        traces = []
        if note:
            try:
                traces = envelope.parse_note_content(note)
            except (ValueError, json.JSONDecodeError):
                pass

        if traces:
            for trace_obj in traces:
                ec = trace_obj.get("event_count", 0)
                total_events += ec
                tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")

                if tool not in all_tools:
                    all_tools[tool] = {"commits": 0, "events": 0}
                all_tools[tool]["commits"] += 1
                all_tools[tool]["events"] += ec

                # Quick integrity check
                expected = trace_obj.get("integrity", {}).get("trace_hash", "")
                actual = hashing.trace_hash(trace_obj)
                if expected and expected != actual:
                    integrity_valid = False

                # Get first prompt for summary
                first_prompt = ""
                events = trace_obj.get("events", [])
                if events:
                    first_prompt = events[0].get("prompt", "[hash-only]")
                    if len(first_prompt) > 60:
                        first_prompt = first_prompt[:57] + "..."

                traced_commits.append({
                    "sha": commit["sha"],
                    "short_sha": commit["short_sha"],
                    "message": commit["message"],
                    "trace_id": trace_obj.get("trace_id", ""),
                    "tool": tool,
                    "event_count": ec,
                    "redaction_mode": trace_obj.get("redaction_mode", ""),
                    "first_prompt": first_prompt,
                    "valid": expected == actual if expected else True,
                })
        else:
            untraced_commits.append(commit)
            # Check for co-author violations
            full_msg = git.commit_message(commit["sha"])
            co_author = _find_ai_co_author(full_msg)
            if co_author:
                co_author_violations.append({
                    "sha": commit["short_sha"],
                    "co_author": co_author,
                })

    return {
        "total_commits": total,
        "traced_commits": traced_commits,
        "untraced_commits": untraced_commits,
        "coverage": len(traced_commits) / total if total > 0 else 0,
        "total_events": total_events,
        "tools": all_tools,
        "integrity_valid": integrity_valid,
        "co_author_violations": co_author_violations,
    }


def _output_text(data: dict) -> None:
    total = data["total_commits"]
    traced = len(data["traced_commits"])
    pct = data["coverage"] * 100

    print("WHENCE Provenance Report")
    print(f"  AI-assisted commits: {traced} of {total} ({pct:.0f}%)")

    tools_str = ", ".join(
        f"{t} ({d['commits']} commits)"
        for t, d in sorted(data["tools"].items())
    )
    if tools_str:
        print(f"  Tools: {tools_str}")
    print(f"  Total events: {data['total_events']}")
    integrity = "All valid" if data["integrity_valid"] else "ISSUES FOUND"
    print(f"  Integrity: {integrity}")
    print()

    for tc in data["traced_commits"]:
        print(f"  {tc['short_sha']} {tc['tool']} ({tc['event_count']} events): \"{tc['first_prompt']}\"")

    if data["co_author_violations"]:
        print()
        print(f"  Co-authored commits without traces: {len(data['co_author_violations'])}")
        for v in data["co_author_violations"]:
            print(f"    {v['sha']} Co-authored-by: {v['co_author']}")


def _output_json(data: dict) -> None:
    output = {
        "total_commits": data["total_commits"],
        "traced_commits": len(data["traced_commits"]),
        "coverage": round(data["coverage"], 2),
        "total_events": data["total_events"],
        "tools": data["tools"],
        "integrity_valid": data["integrity_valid"],
        "co_author_violations": data["co_author_violations"],
        "commits": data["traced_commits"],
    }
    print(json.dumps(output, indent=2))


def _output_markdown(data: dict) -> None:
    total = data["total_commits"]
    traced = len(data["traced_commits"])
    pct = data["coverage"] * 100

    tools_str = ", ".join(
        f"{t} ({d['commits']} commits)"
        for t, d in sorted(data["tools"].items())
    )
    integrity = "All traces valid" if data["integrity_valid"] else "Issues found"

    print("## WHENCE Provenance Summary")
    print()
    print(f"**AI-assisted commits:** {traced} of {total} ({pct:.0f}%)")
    if tools_str:
        print(f"**Tools used:** {tools_str}")
    print(f"**Total prompt events:** {data['total_events']}")
    print(f"**Integrity:** {integrity}")
    print()

    if data["traced_commits"]:
        print("| Commit | Tool | Events | First prompt |")
        print("|--------|------|--------|--------------|")
        for tc in data["traced_commits"]:
            print(f"| {tc['short_sha']} | {tc['tool']} | {tc['event_count']} | \"{tc['first_prompt']}\" |")
        print()

    violations = data["co_author_violations"]
    if violations:
        print(f"**Co-authored commits without traces:** {len(violations)}")
        for v in violations:
            print(f"- {v['sha']} `Co-authored-by: {v['co_author']}` -- missing WHENCE trace")


def _find_ai_co_author(message: str) -> str | None:
    ai_names = ["Claude", "GitHub Copilot", "Cursor Tab", "Copilot"]
    for line in message.splitlines():
        lower = line.lower()
        if "co-authored-by:" in lower:
            for name in ai_names:
                if name.lower() in lower:
                    return name
    return None
