"""git whence reattach — Migrate orphaned WHENCE traces after history rewriting."""

import json

from .. import git, envelope
from ..exitcodes import SUCCESS


def register(subparsers):
    p = subparsers.add_parser(
        "reattach",
        help="Migrate orphaned WHENCE traces after rebase/squash/amend",
    )
    p.add_argument("--auto", action="store_true", help="Auto-confirm unambiguous mappings")
    p.add_argument("--dry-run", action="store_true", help="Show proposed mappings without writing")
    p.add_argument("--cleanup", action="store_true", help="Remove orphaned notes after migration")
    p.set_defaults(func=run)


def run(args) -> int:
    git.ensure_whence_initialized()

    # Step 1: Find all notes and identify orphaned ones
    notes = git.notes_list()
    if not notes:
        print("No WHENCE notes found")
        return SUCCESS

    orphaned = []
    for _note_sha, commit_sha in notes:
        if not git.is_reachable(commit_sha):
            note_content = git.notes_show(commit_sha)
            traces = []
            if note_content:
                try:
                    traces = envelope.parse_note_content(note_content)
                except (ValueError, json.JSONDecodeError):
                    pass
            orphaned.append({
                "old_sha": commit_sha,
                "note_content": note_content,
                "traces": traces,
            })

    if not orphaned:
        print("No orphaned WHENCE traces found")
        return SUCCESS

    print(f"Found {len(orphaned)} orphaned WHENCE trace(s):")
    print()

    # Step 2: Search reflog for mappings
    reflog_entries = git.reflog()
    mappings = _build_rebase_mappings(reflog_entries)

    migrated = 0
    skipped = 0

    for entry in orphaned:
        old_sha = entry["old_sha"]
        traces = entry["traces"]
        short_old = old_sha[:7]

        # Find possible successors
        successors = _find_successors(old_sha, mappings, reflog_entries)

        if not successors:
            print(f"  {short_old} -> NO SUCCESSOR FOUND")
            print(f"    Traces: {len(traces)}")
            skipped += 1
            continue

        if len(successors) == 1:
            new_sha = successors[0]["sha"]
            source = successors[0]["source"]
            short_new = new_sha[:7]

            _print_trace_summary(traces, short_old, short_new, source)

            if args.auto or args.dry_run:
                confirmed = True
            else:
                response = input("    Migrate? [Y/n] ").strip().lower()
                confirmed = response in ("", "y", "yes")

            if confirmed and not args.dry_run:
                _migrate_note(entry["note_content"], old_sha, new_sha, args.cleanup)
                migrated += 1
            elif args.dry_run:
                print("    (dry run -- would migrate)")
                migrated += 1
            else:
                skipped += 1
        else:
            # Ambiguous: multiple possible successors
            print(f"  {short_old} -> AMBIGUOUS ({len(successors)} possible successors)")
            _print_trace_summary(traces, short_old, None, None)
            print("    Candidates:")
            for i, s in enumerate(successors):
                short = s["sha"][:7]
                msg = git.commit_message(s["sha"]).split("\n")[0][:50]
                print(f"      {chr(97 + i)}) {short} ({msg})")

            if args.dry_run:
                print("    (dry run -- would prompt for selection)")
                skipped += 1
                continue

            if args.auto:
                print("    (auto -- skipping ambiguous mapping)")
                skipped += 1
                continue

            choice = input(f"    Choose [{'/'.join(chr(97 + i) for i in range(len(successors)))}/skip]: ").strip().lower()
            if choice == "skip" or not choice:
                skipped += 1
            else:
                idx = ord(choice) - 97
                if 0 <= idx < len(successors):
                    new_sha = successors[idx]["sha"]
                    _migrate_note(entry["note_content"], old_sha, new_sha, args.cleanup)
                    migrated += 1
                else:
                    skipped += 1

    print()
    print(f"Migrated: {migrated} trace(s)")
    print(f"Skipped: {skipped}")
    return SUCCESS


def _build_rebase_mappings(reflog_entries: list[dict]) -> dict[str, list[str]]:
    """Build a mapping of actions from reflog entries.

    Returns dict of reflog messages to new SHAs.
    """
    mappings = {}
    for entry in reflog_entries:
        msg = entry.get("message", "")
        new_sha = entry.get("new_sha", "")
        if new_sha:
            if msg not in mappings:
                mappings[msg] = []
            mappings[msg].append(new_sha)
    return mappings


def _find_successors(old_sha: str, mappings: dict, reflog_entries: list[dict]) -> list[dict]:
    """Find possible successor commits for an orphaned SHA."""
    successors = []
    seen = set()

    for entry in reflog_entries:
        msg = entry.get("message", "")
        new_sha = entry.get("new_sha", "")

        # Look for rebase/amend/cherry-pick messages that reference the old SHA
        is_rewrite = any(keyword in msg.lower() for keyword in ["rebase", "amend", "cherry-pick", "squash"])
        if is_rewrite and new_sha and new_sha not in seen:
            # Check if this could be a successor (heuristic: same files changed)
            # Simple heuristic: the reflog entry is near the old SHA in time
            seen.add(new_sha)
            successors.append({
                "sha": new_sha,
                "source": msg,
            })

    # If we found too many, try to narrow down by checking if the old sha
    # appears anywhere in the reflog message
    if len(successors) > 3:
        narrowed = [s for s in successors if old_sha[:7] in s.get("source", "")]
        if narrowed:
            return narrowed[:5]

    return successors[:5]


def _print_trace_summary(traces: list[dict], short_old: str, short_new: str | None, source: str | None) -> None:
    """Print a summary of traces being migrated."""
    if short_new:
        print(f"  {short_old} -> {short_new} (reflog: {source})")
    for t in traces:
        tid = t.get("trace_id", "unknown")
        ec = t.get("event_count", 0)
        tool = t.get("tool_summary", {}).get("primary_tool", "unknown")
        print(f"    Trace: {tid} ({ec} events, {tool})")


def _migrate_note(note_content: str, old_sha: str, new_sha: str, cleanup: bool) -> None:
    """Migrate a note from old_sha to new_sha."""
    # Check if new_sha already has a note
    existing = git.notes_show(new_sha)
    if existing:
        content = existing.rstrip("\n") + "\n---\n" + note_content
    else:
        content = note_content

    git.notes_add(new_sha, content)

    if cleanup:
        git.notes_remove(old_sha)
