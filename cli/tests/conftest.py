"""Shared fixtures for git-whence tests."""

import os
import subprocess

import pytest


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temporary Git repo with one initial commit.

    Yields the repo path. Sets cwd to the repo for the test duration.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    old_cwd = os.getcwd()
    os.chdir(repo)

    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)

    # Create initial commit
    (repo / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True, check=True)

    yield repo

    os.chdir(old_cwd)


@pytest.fixture
def whence_initialized(tmp_git_repo):
    """A git repo with WHENCE already initialized."""
    from git_whence.main import main
    result = main(["init"])
    assert result == 0
    return tmp_git_repo
