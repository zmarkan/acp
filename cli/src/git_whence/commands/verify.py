"""git whence verify — Validate ACP traces against integrity rules and CI policies."""

import fnmatch
import json
import sys

from .. import git, envelope, hashing
from ..exitcodes import SUCCESS, USER_ERROR, ENV_ERROR, POLICY_FAIL


def register(subparsers):
    p = subparsers.add_parser("verify", help="Validate ACP traces against policies")
    p.add_argument(
        "revision_range",
        nargs="?",
        default=None,
        help="Git revision range (default: auto-detect PR range)",
    )
    p.add_argument(
        "--policy",
        choices=["integrity", "co-author", "coverage", "path-based", "attestation"],
        default="integrity",
        help="Policy to verify (default: integrity)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Coverage threshold for 'coverage' policy (0.0-1.0)",
    )
    p.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Path patterns for 'path-based' policy",
    )
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress output, exit code only")
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_acp_initialized()

    # Determine revision range
    revision_range = args.revision_range
    if not revision_range:
        # Try to auto-detect: origin/main..HEAD
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
        if not args.quiet:
            print("No commits in range")
        return SUCCESS

    # Gather trace data
    commit_data = []
    for commit in commits:
        note = git.notes_show(commit["sha"])
        traces = []
        if note:
            try:
                traces = envelope.parse_note_content(note)
            except (ValueError, json.JSONDecodeError):
                pass
        commit_data.append({
            "commit": commit,
            "traces": traces,
            "note_content": note,
        })

    # Dispatch to policy
    policy = args.policy
    if policy == "integrity":
        return _verify_integrity(commit_data, args)
    elif policy == "co-author":
        return _verify_co_author(commit_data, args)
    elif policy == "coverage":
        return _verify_coverage(commit_data, args)
    elif policy == "path-based":
        return _verify_path_based(commit_data, args)
    elif policy == "attestation":
        return _verify_attestation(commit_data, args)

    return USER_ERROR


def _verify_integrity(commit_data: list[dict], args) -> int:
    """Verify all traces are structurally valid and integrity-checked."""
    if not args.quiet:
        print(f"Verifying policy: integrity")
        print(f"Range: {len(commit_data)} commits")
        print()

    invalid_count = 0
    valid_count = 0

    for entry in commit_data:
        commit = entry["commit"]
        traces = entry["traces"]
        sha = commit["short_sha"]

        if not traces:
            if not args.quiet:
                print(f"  {sha} -- no trace")
            continue

        for trace_obj in traces:
            errors = _validate_trace(trace_obj, entry.get("note_content", ""))
            if errors:
                invalid_count += 1
                if not args.quiet:
                    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
                    ec = trace_obj.get("event_count", 0)
                    print(f"  {sha} INVALID ({ec} events, {tool})")
                    for err in errors:
                        print(f"    - {err}")
            else:
                valid_count += 1
                if not args.quiet:
                    tool = trace_obj.get("tool_summary", {}).get("primary_tool", "unknown")
                    ec = trace_obj.get("event_count", 0)
                    print(f"  {sha} valid ({ec} events, {tool})")

    no_trace = sum(1 for e in commit_data if not e["traces"])
    if not args.quiet:
        print()
        if invalid_count == 0:
            print(f"Result: PASS ({valid_count} traces verified, {no_trace} commits without traces)")
        else:
            print(f"Result: FAIL ({invalid_count} invalid, {valid_count} valid, {no_trace} without traces)")

    return POLICY_FAIL if invalid_count > 0 else SUCCESS


def _validate_trace(trace_obj: dict, note_content: str) -> list[str]:
    """Run the 9-point integrity validation. Returns list of error messages."""
    errors = []

    # 1. Check required trace fields
    required = ["spec_version", "trace_id", "created_at", "target", "redaction_mode", "event_count", "events", "integrity"]
    for field in required:
        if field not in trace_obj:
            errors.append(f"missing required field: {field}")

    if errors:
        return errors

    # 2. Check spec_version
    if trace_obj["spec_version"] != "0.1.0":
        errors.append(f"unrecognized spec_version: {trace_obj['spec_version']}")

    # 3. event_count matches events length
    if trace_obj["event_count"] != len(trace_obj.get("events", [])):
        errors.append(f"event_count ({trace_obj['event_count']}) != events length ({len(trace_obj.get('events', []))})")

    # 4. Verify trace hash
    expected_hash = trace_obj.get("integrity", {}).get("trace_hash", "")
    actual_hash = hashing.trace_hash(trace_obj)
    if expected_hash and expected_hash != actual_hash:
        errors.append(f"trace_hash mismatch: expected {expected_hash}, got {actual_hash}")

    # 5. Validate events
    redaction_mode = trace_obj.get("redaction_mode", "hash-response")
    for i, event in enumerate(trace_obj.get("events", []), 1):
        event_errors = _validate_event(event, redaction_mode, i)
        errors.extend(event_errors)

    # 6. Verify header-body consistency (if we have note content)
    if note_content:
        header_errors = _validate_headers(trace_obj, note_content)
        errors.extend(header_errors)

    return errors


def _validate_event(event: dict, redaction_mode: str, index: int) -> list[str]:
    """Validate a single event against spec rules."""
    errors = []
    prefix = f"event {index}"

    # Required event fields
    for field in ["spec_version", "event_id", "timestamp", "prompt_hash"]:
        if field not in event:
            errors.append(f"{prefix}: missing required field: {field}")

    # Verify prompt_hash matches prompt when stored
    prompt = event.get("prompt")
    prompt_hash = event.get("prompt_hash")
    if prompt and prompt_hash:
        computed = hashing.sha256_text(prompt)
        if computed != prompt_hash:
            errors.append(f"{prefix}: prompt_hash mismatch")

    # Check redacted flag consistency
    if event.get("redacted"):
        # Should contain at least one [REDACTED:...] token
        text_to_check = (event.get("prompt", "") + " " + event.get("response", ""))
        if "[REDACTED:" not in text_to_check:
            errors.append(f"{prefix}: redacted=true but no [REDACTED:...] token found")

    # Check response_captured consistency
    response_captured = event.get("response_captured", True)
    if response_captured is False:
        if "response_hash" in event:
            errors.append(f"{prefix}: response_captured=false but response_hash present")
        if "response" in event:
            errors.append(f"{prefix}: response_captured=false but response present")

    # Check redaction mode conformance
    if redaction_mode == "hash-all":
        if "prompt" in event:
            errors.append(f"{prefix}: hash-all mode but prompt text stored")
        if "response" in event:
            errors.append(f"{prefix}: hash-all mode but response text stored")
    elif redaction_mode == "hash-response":
        if "response" in event:
            errors.append(f"{prefix}: hash-response mode but response text stored")
    elif redaction_mode in ("full", "hash-response"):
        if "prompt" not in event:
            errors.append(f"{prefix}: {redaction_mode} mode but prompt text missing")

    return errors


def _validate_headers(trace_obj: dict, note_content: str) -> list[str]:
    """Validate envelope headers match JSON body."""
    errors = []
    # Find the envelope record for this trace
    headers = envelope.parse_headers(note_content)
    if not headers:
        return errors

    # ACP-Trace-Id
    header_id = headers.get("acp-trace-id", "")
    body_id = trace_obj.get("trace_id", "")
    if header_id and body_id and header_id != body_id:
        errors.append(f"header ACP-Trace-Id ({header_id}) != body trace_id ({body_id})")

    # ACP-Event-Count
    header_count = headers.get("acp-event-count", "")
    body_count = str(trace_obj.get("event_count", ""))
    if header_count and body_count and header_count != body_count:
        errors.append(f"header ACP-Event-Count ({header_count}) != body event_count ({body_count})")

    # ACP-Redaction
    header_mode = headers.get("acp-redaction", "")
    body_mode = trace_obj.get("redaction_mode", "")
    if header_mode and body_mode and header_mode != body_mode:
        errors.append(f"header ACP-Redaction ({header_mode}) != body redaction_mode ({body_mode})")

    return errors


def _verify_co_author(commit_data: list[dict], args) -> int:
    """Check that commits with AI co-author signals have ACP traces."""
    if not args.quiet:
        print(f"Verifying policy: co-author")
        print(f"Range: {len(commit_data)} commits")
        print()

    violations = []
    for entry in commit_data:
        commit = entry["commit"]
        traces = entry["traces"]
        sha = commit["short_sha"]
        trailers = commit.get("trailers", "")
        # Also check full commit message
        full_msg = git.commit_message(commit["sha"])
        co_author = _find_ai_co_author(full_msg)

        if co_author:
            if traces:
                if not args.quiet:
                    print(f"  {sha} Co-authored-by: {co_author} -> trace present")
            else:
                violations.append({"sha": sha, "co_author": co_author})
                if not args.quiet:
                    print(f"  {sha} Co-authored-by: {co_author} -> NO TRACE")
        else:
            if not args.quiet:
                print(f"  {sha} no co-author signal -- skipped")

    if not args.quiet:
        print()
        if not violations:
            print("Result: PASS (all co-authored commits have traces)")
        else:
            print(f"Result: FAIL ({len(violations)} co-authored commit(s) without ACP trace)")

    return POLICY_FAIL if violations else SUCCESS


def _find_ai_co_author(message: str) -> str | None:
    """Find AI co-author signal in commit message."""
    ai_names = ["Claude", "GitHub Copilot", "Cursor Tab", "Copilot"]
    for line in message.splitlines():
        lower = line.lower()
        if "co-authored-by:" in lower:
            for name in ai_names:
                if name.lower() in lower:
                    return name
    return None


def _verify_coverage(commit_data: list[dict], args) -> int:
    """Check that a minimum percentage of commits carry valid traces."""
    total = len(commit_data)
    traced = sum(1 for e in commit_data if e["traces"])
    coverage = traced / total if total > 0 else 0

    if not args.quiet:
        print(f"Verifying policy: coverage")
        print(f"Range: {total} commits")
        print(f"Coverage: {traced}/{total} ({coverage:.0%})")
        print(f"Threshold: {args.threshold:.0%}")
        print()
        if coverage >= args.threshold:
            print(f"Result: PASS (coverage {coverage:.0%} >= threshold {args.threshold:.0%})")
        else:
            print(f"Result: FAIL (coverage {coverage:.0%} < threshold {args.threshold:.0%})")

    return SUCCESS if coverage >= args.threshold else POLICY_FAIL


def _verify_path_based(commit_data: list[dict], args) -> int:
    """Require traces on commits touching specific paths."""
    if not args.paths:
        print("Error: --paths required for path-based policy", file=sys.stderr)
        return USER_ERROR

    if not args.quiet:
        print(f"Verifying policy: path-based")
        print(f"Paths: {', '.join(args.paths)}")
        print()

    violations = []
    for entry in commit_data:
        commit = entry["commit"]
        traces = entry["traces"]
        sha = commit["short_sha"]

        # Get files changed in this commit
        changed_files = git.diff_names(commit["sha"])
        matches = any(
            fnmatch.fnmatch(f, pattern)
            for f in changed_files
            for pattern in args.paths
        )

        if matches:
            if traces:
                if not args.quiet:
                    print(f"  {sha} touches monitored path -> trace present")
            else:
                violations.append(sha)
                if not args.quiet:
                    print(f"  {sha} touches monitored path -> NO TRACE")
        elif not args.quiet:
            print(f"  {sha} no matching paths -- skipped")

    if not args.quiet:
        print()
        if not violations:
            print("Result: PASS (all matching commits have traces)")
        else:
            print(f"Result: FAIL ({len(violations)} matching commit(s) without traces)")

    return POLICY_FAIL if violations else SUCCESS


def _verify_attestation(commit_data: list[dict], args) -> int:
    """Require either an ACP trace or a No-AI-Used trailer."""
    if not args.quiet:
        print(f"Verifying policy: attestation")
        print(f"Range: {len(commit_data)} commits")
        print()

    violations = []
    for entry in commit_data:
        commit = entry["commit"]
        traces = entry["traces"]
        sha = commit["short_sha"]

        if traces:
            if not args.quiet:
                print(f"  {sha} has ACP trace")
            continue

        # Check for No-AI-Used trailer
        full_msg = git.commit_message(commit["sha"])
        if "No-AI-Used" in full_msg:
            if not args.quiet:
                print(f"  {sha} has No-AI-Used attestation")
            continue

        violations.append(sha)
        if not args.quiet:
            print(f"  {sha} MISSING (no trace, no attestation)")

    if not args.quiet:
        print()
        if not violations:
            print("Result: PASS (all commits accounted for)")
        else:
            print(f"Result: FAIL ({len(violations)} commit(s) with neither trace nor attestation)")

    return POLICY_FAIL if violations else SUCCESS
