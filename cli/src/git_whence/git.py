"""Git subprocess wrapper.

All interaction with Git goes through this module. Each function maps to
one git command and raises typed exceptions on failure.
"""

import subprocess
from pathlib import Path


class GitError(Exception):
    """General Git operation failure."""


class NotAGitRepo(GitError):
    """Current directory is not inside a Git repository."""


class WHENCENotInitialized(GitError):
    """WHENCE has not been initialized in this repository."""


def _run(args: list[str], *, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    try:
        return subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            input=input,
            check=check,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH")
    except subprocess.CalledProcessError as e:
        raise GitError(f"git {' '.join(args)} failed: {e.stderr.strip()}")


def git_root() -> Path:
    """Return the root of the current Git repository."""
    try:
        result = _run(["rev-parse", "--show-toplevel"])
        return Path(result.stdout.strip())
    except GitError:
        raise NotAGitRepo("not a Git repository")


def whence_dir() -> Path:
    """Return the .git/whence directory path."""
    root = git_root()
    # Handle worktrees: .git might be a file pointing to the actual git dir
    git_path = root / ".git"
    if git_path.is_file():
        # .git is a gitdir link (worktree)
        content = git_path.read_text().strip()
        if content.startswith("gitdir: "):
            git_dir = Path(content[8:])
            if not git_dir.is_absolute():
                git_dir = root / git_dir
            return git_dir / "whence"
    return git_path / "whence"


def ensure_whence_initialized() -> Path:
    """Return whence_dir, raising WHENCENotInitialized if it doesn't exist."""
    d = whence_dir()
    if not (d / "config.json").exists():
        raise WHENCENotInitialized()
    return d


def rev_parse(ref: str) -> str:
    """Resolve a ref to a full SHA."""
    result = _run(["rev-parse", ref])
    return result.stdout.strip()


def current_branch() -> str | None:
    """Return the current branch name, or None if detached."""
    try:
        result = _run(["symbolic-ref", "--short", "HEAD"], check=True)
        return result.stdout.strip()
    except GitError:
        return None


def is_working_tree_clean() -> bool:
    """Check if the working tree is clean (no uncommitted changes)."""
    result = _run(["status", "--porcelain"], check=False)
    return result.stdout.strip() == ""


def notes_show(commit: str, ref: str = "refs/notes/whence") -> str | None:
    """Read the note content for a commit, or None if no note exists."""
    result = _run(["notes", "--ref", ref, "show", commit], check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def notes_add(commit: str, content: str, ref: str = "refs/notes/whence", force: bool = True) -> None:
    """Write a note on a commit. Uses --file=- to pass content via stdin."""
    args = ["notes", "--ref", ref, "add"]
    if force:
        args.append("-f")
    args.extend(["--file=-", commit])
    _run(args, input=content)


def notes_list(ref: str = "refs/notes/whence") -> list[tuple[str, str]]:
    """List all notes as (note_object_sha, annotated_commit_sha) pairs."""
    result = _run(["notes", "--ref", ref, "list"], check=False)
    if result.returncode != 0:
        return []
    pairs = []
    for line in result.stdout.strip().splitlines():
        if line.strip():
            parts = line.strip().split()
            if len(parts) == 2:
                pairs.append((parts[0], parts[1]))
    return pairs


def notes_remove(commit: str, ref: str = "refs/notes/whence") -> None:
    """Remove a note from a commit."""
    _run(["notes", "--ref", ref, "remove", commit], check=False)


def config_set(key: str, value: str) -> None:
    """Set a git config value."""
    _run(["config", key, value])


def config_get(key: str) -> str | None:
    """Get a git config value, or None if not set."""
    result = _run(["config", "--get", key], check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def config_get_all(key: str) -> list[str]:
    """Get all values for a multi-valued git config key."""
    result = _run(["config", "--get-all", key], check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def config_add(key: str, value: str) -> None:
    """Add a value to a multi-valued git config key."""
    _run(["config", "--add", key, value])


def log_range(revision_range: str) -> list[dict]:
    """Get commits in a range as a list of dicts.

    Returns: [{"sha": str, "short_sha": str, "message": str, "trailers": str}]
    """
    fmt = "%H%x00%h%x00%s%x00%(trailers:only,unfold)"
    result = _run(["log", f"--format={fmt}", revision_range], check=False)
    if result.returncode != 0:
        # Fallback: if the range uses ~N and we don't have enough commits,
        # try showing all commits instead
        if "~" in revision_range:
            result = _run(["log", f"--format={fmt}"], check=False)
            if result.returncode != 0:
                raise GitError(f"invalid revision range: {revision_range}")
        else:
            raise GitError(f"invalid revision range: {revision_range}")
    commits = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\x00")
        if len(parts) >= 3:
            commits.append({
                "sha": parts[0],
                "short_sha": parts[1],
                "message": parts[2],
                "trailers": parts[3] if len(parts) > 3 else "",
            })
    return commits


def diff_staged() -> str:
    """Get the staged diff."""
    result = _run(["diff", "--staged", "--no-color"])
    return result.stdout


def diff_working() -> str:
    """Get the working tree diff."""
    result = _run(["diff", "--no-color"])
    return result.stdout


def diff_names(commit: str) -> list[str]:
    """Get the list of files changed in a commit."""
    result = _run(["diff-tree", "--no-commit-id", "--name-only", "-r", commit], check=False)
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f.strip()]


def is_reachable(sha: str) -> bool:
    """Check if a SHA is reachable from any branch."""
    result = _run(["branch", "--contains", sha], check=False)
    return result.returncode == 0 and result.stdout.strip() != ""


def reflog(ref: str = "HEAD") -> list[dict]:
    """Parse reflog entries for a ref.

    Returns: [{"old_sha": str, "new_sha": str, "action": str, "message": str}]
    """
    # Use the raw reflog format
    result = _run(["reflog", "show", ref, "--format=%H%x00%gD%x00%gs"], check=False)
    if result.returncode != 0:
        return []
    entries = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\x00")
        if len(parts) >= 3:
            entries.append({
                "new_sha": parts[0],
                "ref": parts[1],
                "message": parts[2],
            })
    return entries


def push_ref(remote: str, ref: str) -> int:
    """Push a ref to a remote. Returns exit code."""
    result = _run(["push", remote, ref], check=False)
    return result.returncode


def fetch_ref(remote: str, src: str, dst: str) -> int:
    """Fetch a ref from a remote. Returns exit code."""
    result = _run(["fetch", remote, f"{src}:{dst}"], check=False)
    return result.returncode


def commit_message(commit: str) -> str:
    """Get the full commit message for a commit."""
    result = _run(["log", "-1", "--format=%B", commit], check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def commit_trailers(commit: str) -> str:
    """Get trailers from a commit message."""
    result = _run(["log", "-1", "--format=%(trailers:only,unfold)", commit], check=False)
    return result.stdout.strip() if result.returncode == 0 else ""
