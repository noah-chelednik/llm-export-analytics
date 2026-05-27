"""Tests for graceful error handling across analyzer scripts."""

import csv
import json
import os
import subprocess

from tests.helpers import DEEP_DIR, PYTHON, SCRIPTS_DIR

CHATGPT_SCRIPT = os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py")
CLAUDE_SCRIPT = os.path.join(SCRIPTS_DIR, "analyze_claude.py")
POD_SCRIPT = os.path.join(DEEP_DIR, "compute_pod.py")


def _minimal_chatgpt_conv(conv_id="conv-001", title="Test chat",
                           user_text="Hello world", assistant_text="Hi there",
                           create_time=1736899200.0):
    """Build a minimal valid ChatGPT conversation dict."""
    return {
        "id": conv_id,
        "title": title,
        "create_time": create_time,
        "update_time": create_time + 30,
        "default_model_slug": "gpt-4o",
        "mapping": {
            "root": {
                "id": "root",
                "parent": None,
                "children": ["u01"],
                "message": None,
            },
            "u01": {
                "id": "u01",
                "parent": "root",
                "children": ["a01"],
                "message": {
                    "id": "msg-u01",
                    "author": {"role": "user"},
                    "create_time": create_time + 5,
                    "content": {"content_type": "text", "parts": [user_text]},
                    "metadata": {},
                },
            },
            "a01": {
                "id": "a01",
                "parent": "u01",
                "children": [],
                "message": {
                    "id": "msg-a01",
                    "author": {"role": "assistant"},
                    "create_time": create_time + 15,
                    "content": {"content_type": "text", "parts": [assistant_text]},
                    "metadata": {"model_slug": "gpt-4o"},
                },
            },
        },
    }


def _minimal_claude_conv(conv_id="c01a-uuid", name="Test claude",
                          user_text="Hello world", assistant_text="Hi there",
                          created_at="2025-01-20T14:30:00.000000Z"):
    """Build a minimal valid Claude conversation dict."""
    return {
        "uuid": conv_id,
        "name": name,
        "created_at": created_at,
        "updated_at": created_at,
        "chat_messages": [
            {
                "uuid": "m-u01",
                "sender": "human",
                "created_at": created_at,
                "content": [{"type": "text", "text": user_text}],
            },
            {
                "uuid": "m-a01",
                "sender": "assistant",
                "created_at": "2025-01-20T14:30:30.000000Z",
                "content": [{"type": "text", "text": assistant_text}],
            },
        ],
    }


class TestErrorHandling:
    def test_empty_chatgpt_export(self, tmp_path):
        """Empty JSON array should exit with SystemExit, not crash."""
        export = tmp_path / "empty.json"
        export.write_text("[]")
        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0  # should fail gracefully
        assert "Traceback" not in result.stderr  # no raw stacktrace

    def test_empty_claude_export(self, tmp_path):
        """Empty JSON array for Claude should exit gracefully, not crash."""
        export = tmp_path / "empty_claude.json"
        export.write_text("[]")
        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0  # should fail gracefully
        assert "Traceback" not in result.stderr  # no raw stacktrace

    def test_single_conversation_chatgpt(self, tmp_path):
        """Single conversation with 2 messages should produce valid output."""
        export = tmp_path / "single.json"
        export.write_text(json.dumps([_minimal_chatgpt_conv()]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc",
             "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "chatgpt_messages_normalized.csv"
        assert csv_path.exists()
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 2  # at least user + assistant

    def test_single_conversation_claude(self, tmp_path):
        """Single Claude conversation with 2 messages should produce valid output."""
        export = tmp_path / "single_claude.json"
        export.write_text(json.dumps([_minimal_claude_conv()]))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc",
             "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "claude_messages_normalized.csv"
        assert csv_path.exists()
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 2

    def test_conversation_missing_messages_chatgpt(self, tmp_path):
        """ChatGPT conversation with empty mapping should be skipped, not crash."""
        conv = {
            "id": "empty-conv",
            "title": "Empty",
            "create_time": 1736899200.0,
            "mapping": {},
        }
        # Include a valid conversation so the script has something to output
        valid = _minimal_chatgpt_conv(conv_id="valid-conv")
        export = tmp_path / "mixed.json"
        export.write_text(json.dumps([conv, valid]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_conversation_missing_messages_claude(self, tmp_path):
        """Claude conversation with no chat_messages should be skipped, not crash."""
        conv_empty = {
            "uuid": "empty-uuid",
            "name": "Empty",
            "created_at": "2025-01-20T14:30:00.000000Z",
            "chat_messages": [],
        }
        valid = _minimal_claude_conv(conv_id="valid-uuid")
        export = tmp_path / "mixed_claude.json"
        export.write_text(json.dumps([conv_empty, valid]))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_invalid_file_path_chatgpt(self, tmp_path):
        """Non-existent file should error with non-zero exit code."""
        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", "/nonexistent/path.json", "--out", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_invalid_file_path_claude(self, tmp_path):
        """Non-existent file for Claude should error with non-zero exit code."""
        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", "/nonexistent/path.json", "--out", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_malformed_timestamp_claude(self, tmp_path):
        """Message with invalid timestamp should be skipped, not crash."""
        conv = _minimal_claude_conv()
        # Corrupt the first message timestamp
        conv["chat_messages"][0]["created_at"] = "not-a-date"
        # The assistant message still has a valid timestamp so
        # there should be at least 1 valid message unless the text is also empty.
        # Actually, Claude analyzer skips messages with bad timestamps, so if
        # only the user message has a bad timestamp, only the assistant row survives.
        export = tmp_path / "bad_ts.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        # Should succeed (skipped bad message, processed the rest)
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_malformed_timestamp_chatgpt(self, tmp_path):
        """ChatGPT message with invalid create_time should be skipped, not crash."""
        conv = _minimal_chatgpt_conv()
        # Corrupt the user message timestamp
        conv["mapping"]["u01"]["message"]["create_time"] = "bad-ts"
        export = tmp_path / "bad_ts_chatgpt.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        # The assistant message still has a valid timestamp so should succeed
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"
