"""git whence attach — Bundle queued events into a trace and attach to a commit."""

import sys

from .. import git, queue, hashing, redaction, envelope, trace, config
from ..exitcodes import SUCCESS, USER_ERROR, POLICY_FAIL, NOT_FOUND


def register(subparsers):
    p = subparsers.add_parser(
        "attach",
        help="Bundle queued events into a trace and attach to a commit",
    )
    p.add_argument("commit", nargs="?", default="HEAD", help="Commit SHA or ref (default: HEAD)")
    p.add_argument("--since", default=None, help="Only attach events after this commit's timestamp")
    p.add_argument("--interactive", action="store_true", help="Interactively select events")
    p.add_argument(
        "--redaction",
        choices=["full", "hash-response", "hash-all"],
        default=None,
        help="Override redaction mode for this trace",
    )
    p.add_argument("--force", action="store_true", help="Attach even if secrets detected")
    p.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p.add_argument("--patch", action="store_true", help="Compute context.patch_hash from diff")
    p.add_argument(
        "--patch-source",
        choices=["staged", "working-tree"],
        default="staged",
        help="Patch source (default: staged)",
    )
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_whence_initialized()
    cfg = config.load()

    # Resolve target commit
    try:
        target_sha = git.rev_parse(args.commit)
    except git.GitError:
        print(f"Error: commit not found: {args.commit}", file=sys.stderr)
        return NOT_FOUND

    # Read events
    all_events = queue.read_events()
    if not all_events:
        print("Error: no events in queue (nothing to attach)", file=sys.stderr)
        return USER_ERROR

    # Filter events
    use_filter = False
    if args.since:
        use_filter = True
        try:
            since_ts = _get_commit_timestamp(args.since)
        except git.GitError:
            print(f"Error: --since commit not found: {args.since}", file=sys.stderr)
            return NOT_FOUND
        events = [e for e in all_events if e.get("timestamp", "") > since_ts]
    elif args.interactive:
        use_filter = True
        events = _interactive_select(all_events)
    else:
        events = all_events

    if not events:
        print("Error: no events selected for attachment", file=sys.stderr)
        return USER_ERROR

    # Determine redaction mode
    redaction_mode = args.redaction or cfg.default_redaction

    # Load custom redaction patterns
    custom_patterns = None
    if cfg.redact_patterns_file:
        patterns_path = git.whence_dir() / cfg.redact_patterns_file
        custom_patterns = redaction.load_custom_patterns(patterns_path)

    # Run redaction pipeline
    total_secrets = 0
    high_confidence = []

    for event in events:
        # Redact prompt
        if "prompt" in event:
            result = redaction.scan_and_redact(event["prompt"], custom_patterns)
            event["prompt"] = result.text
            event["prompt_hash"] = hashing.sha256_text(result.text)
            if result.was_redacted:
                event["redacted"] = True
            total_secrets += result.secret_count
            high_confidence.extend(result.high_confidence_types)

        # Redact response if captured
        response_captured = event.get("response_captured", True)
        if response_captured and "response" in event:
            result = redaction.scan_and_redact(event["response"], custom_patterns)
            event["response"] = result.text
            event["response_hash"] = hashing.sha256_text(result.text)
            if result.was_redacted:
                event["redacted"] = True
            total_secrets += result.secret_count
            high_confidence.extend(result.high_confidence_types)

    # Check for high-confidence secrets
    if high_confidence and not args.force:
        types = ", ".join(set(high_confidence))
        print(
            f"Error: high-confidence secrets detected ({types}). "
            f"Use --force to override.",
            file=sys.stderr,
        )
        return POLICY_FAIL

    # Apply redaction mode constraints
    for event in events:
        response_captured = event.get("response_captured", True)

        if redaction_mode == "hash-response":
            # Keep prompt, remove response text (keep hash)
            if response_captured and "response" in event:
                if "response_hash" not in event:
                    event["response_hash"] = hashing.sha256_text(event["response"])
                del event["response"]
        elif redaction_mode == "hash-all":
            # Remove both prompt and response text (keep hashes)
            if "prompt" in event:
                if "prompt_hash" not in event:
                    event["prompt_hash"] = hashing.sha256_text(event["prompt"])
                del event["prompt"]
            if response_captured and "response" in event:
                if "response_hash" not in event:
                    event["response_hash"] = hashing.sha256_text(event["response"])
                del event["response"]
        # mode == "full": keep both prompt and response

    # Compute patch hash if requested
    if args.patch:
        if args.patch_source == "staged":
            diff_text = git.diff_staged()
        else:
            diff_text = git.diff_working()
        if diff_text.strip():
            for event in events:
                if "context" not in event:
                    event["context"] = {}
                event["context"]["patch_hash"] = hashing.sha256_text(diff_text)
                event["context"]["patch_source"] = args.patch_source
                event["context"]["patch_format"] = "git-unified-diff"

    # Get branch
    branch = git.current_branch()

    # Assemble trace
    trace_obj = trace.assemble(events, target_sha, redaction_mode, branch)

    if args.dry_run:
        print("Dry run — would attach:")
        _print_summary(trace_obj, total_secrets)
        return SUCCESS

    # Build envelope
    env = envelope.serialize(trace_obj)

    # Check for existing note and append
    existing = git.notes_show(target_sha)
    if existing:
        env = existing.rstrip("\n") + "\n---\n" + env

    # Write note
    git.notes_add(target_sha, env)

    # Consume events from queue
    if use_filter:
        consumed_ids = {e["event_id"] for e in events}
        queue.consume_filtered(lambda e: e.get("event_id") in consumed_ids)
    else:
        queue.consume_all()

    _print_summary(trace_obj, total_secrets)
    return SUCCESS


def _print_summary(trace_obj: dict, secrets_redacted: int) -> None:
    """Print the attach summary."""
    short_sha = trace_obj["target"]["id"][:7]
    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
    print(f"Attached trace {trace_obj['trace_id']} to {short_sha}")
    print(f"  Events: {trace_obj['event_count']}")
    print(f"  Tool: {tool}")
    print(f"  Redaction: {trace_obj['redaction_mode']}")
    print(f"  Secrets redacted: {secrets_redacted}")
    print(f"  Trace hash: {trace_obj['integrity']['trace_hash']}")


def _get_commit_timestamp(commit_ref: str) -> str:
    """Get the ISO timestamp of a commit."""
    from subprocess import run as sp_run
    result = sp_run(
        ["git", "log", "-1", "--format=%aI", commit_ref],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def _interactive_select(events: list[dict]) -> list[dict]:
    """Interactively select events from the queue."""
    print("Select events to attach:")
    print()
    for i, event in enumerate(events, 1):
        ts = event.get("timestamp", "unknown")
        tool = event.get("tool", "unknown")
        prompt = event.get("prompt", "")
        if len(prompt) > 60:
            prompt = prompt[:57] + "..."
        print(f"  {i}. [{ts}] {tool}: \"{prompt}\"")
    print()

    selection = input("Enter event numbers (comma-separated, or 'all'): ").strip()
    if selection.lower() == "all":
        return events

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",")]
        return [events[i] for i in indices if 0 <= i < len(events)]
    except (ValueError, IndexError):
        print("Invalid selection", file=sys.stderr)
        return []
