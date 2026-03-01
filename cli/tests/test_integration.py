"""End-to-end integration tests: init -> record -> attach -> show -> verify."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from git_whence.main import main


class TestInitCommand:
    def test_init_creates_acp_dir(self, tmp_git_repo):
        result = main(["init"])
        assert result == 0
        acp_dir = tmp_git_repo / ".git" / "acp"
        assert acp_dir.exists()
        assert (acp_dir / "config.json").exists()
        assert (acp_dir / "queue.ndjson").exists()

    def test_init_config_defaults(self, tmp_git_repo):
        main(["init"])
        config = json.loads((tmp_git_repo / ".git" / "acp" / "config.json").read_text())
        assert config["spec_version"] == "0.1.0"
        assert config["default_redaction"] == "hash-response"

    def test_init_custom_redaction(self, tmp_git_repo):
        main(["init", "--redaction", "full"])
        config = json.loads((tmp_git_repo / ".git" / "acp" / "config.json").read_text())
        assert config["default_redaction"] == "full"

    def test_init_already_initialized(self, acp_initialized):
        result = main(["init"])
        assert result == 2  # Already initialized


class TestRecordCommand:
    def test_record_simple(self, acp_initialized):
        result = main(["record", "--prompt", "Test prompt", "--tool", "claude-code"])
        assert result == 0

        # Check queue has the event
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        content = queue_path.read_text().strip()
        assert content
        event = json.loads(content)
        assert event["prompt"] == "Test prompt"
        assert event["tool"] == "claude-code"
        assert event["event_id"].startswith("evt_")
        assert event["prompt_hash"].startswith("sha256:")

    def test_record_no_response(self, acp_initialized):
        result = main(["record", "--prompt", "Test", "--no-response"])
        assert result == 0
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        event = json.loads(queue_path.read_text().strip())
        assert event["response_captured"] is False

    def test_record_with_context(self, acp_initialized):
        result = main(["record", "--prompt", "Test", "--context"])
        assert result == 0
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        event = json.loads(queue_path.read_text().strip())
        assert "context" in event
        assert "git_base_sha" in event["context"]
        assert event["context"]["workspace_state"] in ("clean", "dirty")


class TestQueueCommand:
    def test_queue_count_empty(self, acp_initialized):
        result = main(["queue", "count"])
        assert result == 0

    def test_queue_count_after_record(self, acp_initialized):
        main(["record", "--prompt", "Event 1"])
        main(["record", "--prompt", "Event 2"])
        result = main(["queue", "count"])
        assert result == 0

    def test_queue_clear_requires_force(self, acp_initialized):
        main(["record", "--prompt", "Event 1"])
        result = main(["queue", "clear"])
        assert result == 1  # Requires --force

    def test_queue_clear_with_force(self, acp_initialized):
        main(["record", "--prompt", "Event 1"])
        result = main(["queue", "clear", "--force"])
        assert result == 0
        # Verify queue is empty
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        assert queue_path.read_text().strip() == ""


class TestAttachCommand:
    def test_attach_empty_queue(self, acp_initialized):
        result = main(["attach"])
        assert result == 1  # No events

    def test_attach_basic(self, acp_initialized):
        # Record an event
        main(["record", "--prompt", "Refactor the auth module", "--tool", "claude-code"])

        # Attach to HEAD
        result = main(["attach"])
        assert result == 0

        # Verify queue is now empty
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        assert queue_path.read_text().strip() == ""

        # Verify note exists
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=acp_initialized,
        ).stdout.strip()
        note = subprocess.run(
            ["git", "notes", "--ref=refs/notes/acp", "show", sha],
            capture_output=True, text=True, cwd=acp_initialized,
        )
        assert note.returncode == 0
        assert "ACP-Spec-Version: 0.1.0" in note.stdout
        assert "claude-code" in note.stdout

    def test_attach_dry_run(self, acp_initialized):
        main(["record", "--prompt", "Test", "--tool", "claude-code"])
        result = main(["attach", "--dry-run"])
        assert result == 0

        # Queue should NOT be cleared in dry-run
        queue_path = acp_initialized / ".git" / "acp" / "queue.ndjson"
        assert queue_path.read_text().strip() != ""

    def test_attach_hash_all_mode(self, acp_initialized):
        main(["record", "--prompt", "Secret prompt", "--tool", "claude-code"])
        result = main(["attach", "--redaction", "hash-all"])
        assert result == 0

        # Verify the trace doesn't contain prompt text
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=acp_initialized,
        ).stdout.strip()
        note = subprocess.run(
            ["git", "notes", "--ref=refs/notes/acp", "show", sha],
            capture_output=True, text=True, cwd=acp_initialized,
        ).stdout

        # Parse the JSON body from the envelope
        for line in note.split("\n"):
            line = line.strip()
            if line.startswith("{"):
                trace = json.loads(line)
                assert trace["redaction_mode"] == "hash-all"
                for event in trace["events"]:
                    assert "prompt" not in event
                    assert "prompt_hash" in event
                break


class TestShowCommand:
    def test_show_no_trace(self, acp_initialized):
        result = main(["show"])
        assert result == 1  # No trace

    def test_show_after_attach(self, acp_initialized):
        main(["record", "--prompt", "Build the widget", "--tool", "claude-code"])
        main(["attach"])
        result = main(["show"])
        assert result == 0

    def test_show_json_format(self, acp_initialized):
        main(["record", "--prompt", "Build the widget", "--tool", "claude-code"])
        main(["attach"])
        result = main(["show", "--format", "json"])
        assert result == 0

    def test_show_verify(self, acp_initialized):
        main(["record", "--prompt", "Build the widget", "--tool", "claude-code"])
        main(["attach"])
        result = main(["show", "--verify"])
        assert result == 0


class TestVerifyCommand:
    def test_verify_integrity_pass(self, acp_initialized):
        # Create a second commit so we have a valid parent for the range
        (acp_initialized / "test.txt").write_text("test\n")
        subprocess.run(["git", "add", "test.txt"], cwd=acp_initialized, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Add test file"], cwd=acp_initialized, capture_output=True, check=True)

        main(["record", "--prompt", "Test", "--tool", "claude-code"])
        main(["attach"])
        # Verify using HEAD range
        result = main(["verify", "HEAD~1..HEAD", "--policy", "integrity"])
        assert result == 0


class TestFullPipeline:
    def test_end_to_end(self, acp_initialized):
        """Full pipeline: record -> attach -> show -> verify."""
        # Create a second commit so we have a valid parent for the range
        (acp_initialized / "feature.py").write_text("# new feature\n")
        subprocess.run(["git", "add", "feature.py"], cwd=acp_initialized, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Add feature"], cwd=acp_initialized, capture_output=True, check=True)

        # Record multiple events
        main(["record", "--prompt", "Refactor auth module", "--tool", "claude-code"])
        main(["record", "--prompt", "Add unit tests", "--tool", "claude-code"])

        # Attach
        result = main(["attach"])
        assert result == 0

        # Show
        result = main(["show"])
        assert result == 0

        # Show with verification
        result = main(["show", "--verify"])
        assert result == 0

        # Verify integrity
        result = main(["verify", "HEAD~1..HEAD", "--policy", "integrity"])
        assert result == 0
