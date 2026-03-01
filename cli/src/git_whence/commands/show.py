"""git whence show — Display ACP trace(s) attached to a commit."""

import json
import sys

from .. import git, envelope, hashing
from ..exitcodes import SUCCESS, USER_ERROR, ENV_ERROR, POLICY_FAIL


def register(subparsers):
    p = subparsers.add_parser("show", help="Display ACP trace(s) attached to a commit")
    p.add_argument("commit", nargs="?", default="HEAD", help="Commit SHA or ref (default: HEAD)")
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json", "envelope"],
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument("--prompts-only", action="store_true", help="Show only prompt text")
    p.add_argument("--context", action="store_true", dest="show_context", help="Show code provenance context")
    p.add_argument("--verify", action="store_true", help="Verify integrity hashes")
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_acp_initialized()

    try:
        commit_sha = git.rev_parse(args.commit)
    except git.GitError:
        print(f"Error: commit not found: {args.commit}", file=sys.stderr)
        return USER_ERROR

    # Read note
    note_content = git.notes_show(commit_sha)
    if not note_content:
        print(f"No ACP trace on {commit_sha[:7]}", file=sys.stderr)
        return USER_ERROR

    # Raw envelope output
    if args.output_format == "envelope":
        sys.stdout.write(note_content)
        return SUCCESS

    # Parse traces
    try:
        traces = envelope.parse_note_content(note_content)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error: failed to parse ACP note: {e}", file=sys.stderr)
        return ENV_ERROR

    if not traces:
        print(f"No valid ACP traces on {commit_sha[:7]}", file=sys.stderr)
        return USER_ERROR

    # JSON output
    if args.output_format == "json":
        if len(traces) == 1:
            print(json.dumps(traces[0], indent=2))
        else:
            print(json.dumps(traces, indent=2))
        return SUCCESS

    # Text output
    short_sha = commit_sha[:7]
    commit_msg = git.commit_message(commit_sha).split("\n")[0] if hasattr(git, "commit_message") else ""

    for trace_obj in traces:
        if args.prompts_only:
            _print_prompts_only(trace_obj, short_sha, commit_msg)
        elif args.show_context:
            _print_with_context(trace_obj, short_sha, commit_msg)
        else:
            _print_full(trace_obj, short_sha, commit_msg, verify=args.verify)
        print()

    # Verify if requested
    if args.verify:
        all_valid = True
        for trace_obj in traces:
            if not _verify_trace(trace_obj):
                all_valid = False
        if not all_valid:
            return POLICY_FAIL

    return SUCCESS


def _print_full(trace_obj: dict, short_sha: str, commit_msg: str, verify: bool = False) -> None:
    """Print full trace details."""
    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
    event_count = trace_obj.get("event_count", 0)
    redaction_mode = trace_obj.get("redaction_mode", "unknown")
    trace_id = trace_obj.get("trace_id", "unknown")

    integrity = "not checked"
    if verify:
        integrity = "valid" if _verify_trace(trace_obj) else "INVALID"

    print(f"Commit: {short_sha} {commit_msg}")
    print(f"Trace: {trace_id}")
    print(f"Tool: {tool} | Events: {event_count} | Redaction: {redaction_mode}")
    print(f"Integrity: {integrity}")

    events = trace_obj.get("events", [])
    for i, event in enumerate(events, 1):
        print()
        ts = event.get("timestamp", "unknown")
        print(f"  Event {i} [{ts}]")

        prompt = event.get("prompt")
        if prompt:
            print(f'  Prompt: "{prompt}"')
        else:
            prompt_hash = event.get("prompt_hash", "")
            print(f"  Prompt: [hash-only] {prompt_hash}")

        response = event.get("response")
        response_captured = event.get("response_captured", True)
        if not response_captured:
            print("  Response: [not captured]")
        elif response:
            # Truncate long responses
            display = response if len(response) <= 200 else response[:197] + "..."
            print(f"  Response: {display}")
        else:
            response_hash = event.get("response_hash", "")
            if response_hash:
                print(f"  Response: [hash-only] {response_hash}")

        files = event.get("files", [])
        if files:
            print(f"  Files: {', '.join(files)}")


def _print_prompts_only(trace_obj: dict, short_sha: str, commit_msg: str) -> None:
    """Print only prompts."""
    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
    events = trace_obj.get("events", [])
    print(f"Commit: {short_sha} -- {len(events)} prompts via {tool}")
    print()
    for i, event in enumerate(events, 1):
        prompt = event.get("prompt", "[hash-only]")
        print(f'  {i}. "{prompt}"')


def _print_with_context(trace_obj: dict, short_sha: str, commit_msg: str) -> None:
    """Print trace with code provenance context."""
    trace_id = trace_obj.get("trace_id", "unknown")
    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
    events = trace_obj.get("events", [])

    print(f"Commit: {short_sha} {commit_msg}")
    print(f"Trace: {trace_id}")
    print()

    # Show context from first event that has it
    for event in events:
        ctx = event.get("context", {})
        if ctx:
            base_sha = ctx.get("git_base_sha", "unknown")
            ws = ctx.get("workspace_state", "unknown")
            print(f"  Base SHA: {base_sha[:12]}... ({ws} workspace)")

            artifacts = ctx.get("input_artifacts", [])
            if artifacts:
                print("  Input artifacts:")
                for art in artifacts:
                    print(f"    {art['path']}  {art['hash']}")

            patch_hash = ctx.get("patch_hash")
            if patch_hash:
                source = ctx.get("patch_source", "unknown")
                fmt = ctx.get("patch_format", "unknown")
                print(f"  Patch: {patch_hash} ({source}, {fmt})")
            print()
            break

    print(f"  Events: {len(events)} via {tool}")
    for i, event in enumerate(events, 1):
        prompt = event.get("prompt", "[hash-only]")
        if len(prompt) > 60:
            prompt = prompt[:57] + "..."
        print(f'    {i}. "{prompt}"')


def _verify_trace(trace_obj: dict) -> bool:
    """Verify integrity hashes of a trace. Returns True if valid."""
    # Recompute trace hash
    expected = trace_obj.get("integrity", {}).get("trace_hash", "")
    actual = hashing.trace_hash(trace_obj)
    if expected != actual:
        print(f"  INTEGRITY FAIL: trace_hash mismatch", file=sys.stderr)
        print(f"    expected: {expected}", file=sys.stderr)
        print(f"    actual:   {actual}", file=sys.stderr)
        return False

    # Verify event prompt hashes
    redaction_mode = trace_obj.get("redaction_mode", "hash-response")
    for i, event in enumerate(trace_obj.get("events", []), 1):
        prompt = event.get("prompt")
        prompt_hash = event.get("prompt_hash")
        if prompt and prompt_hash:
            computed = hashing.sha256_text(prompt)
            if computed != prompt_hash:
                print(f"  INTEGRITY FAIL: event {i} prompt_hash mismatch", file=sys.stderr)
                return False

    return True
