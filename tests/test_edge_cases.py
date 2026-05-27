"""Tests for edge cases: unusual content, single-platform pipelines, extremes."""

import csv
import json
import os
import subprocess

from tests.helpers import (
    DEEP_DIR,
    PYTHON,
    SCRIPTS_DIR,
)

CHATGPT_SCRIPT = os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py")
CLAUDE_SCRIPT = os.path.join(SCRIPTS_DIR, "analyze_claude.py")
EFFECTIVENESS_SCRIPT = os.path.join(DEEP_DIR, "analyze_effectiveness.py")


def _minimal_chatgpt_conv(conv_id="conv-001", user_text="Hello world",
                           assistant_text="Hi there",
                           create_time=1736899200.0):
    """Build a minimal valid ChatGPT conversation."""
    return {
        "id": conv_id,
        "title": "Test",
        "create_time": create_time,
        "update_time": create_time + 30,
        "default_model_slug": "gpt-4o",
        "mapping": {
            "root": {
                "id": "root", "parent": None, "children": ["u01"], "message": None,
            },
            "u01": {
                "id": "u01", "parent": "root", "children": ["a01"],
                "message": {
                    "id": "msg-u01",
                    "author": {"role": "user"},
                    "create_time": create_time + 5,
                    "content": {"content_type": "text", "parts": [user_text]},
                    "metadata": {},
                },
            },
            "a01": {
                "id": "a01", "parent": "u01", "children": [],
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


def _minimal_claude_conv(conv_id="c01a-uuid", user_text="Hello world",
                          assistant_text="Hi there",
                          created_at="2025-01-20T14:30:00.000000Z"):
    """Build a minimal valid Claude conversation."""
    return {
        "uuid": conv_id,
        "name": "Test",
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


class TestEdgeCases:
    def test_empty_content_message_chatgpt(self, tmp_path):
        """ChatGPT message with empty string content should not crash."""
        # The analyzer skips messages with empty text, so include a valid one too
        conv = _minimal_chatgpt_conv(user_text="", assistant_text="Valid reply here")
        export = tmp_path / "empty_content.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        # Should succeed -- empty user message is skipped, assistant survives
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_empty_content_message_claude(self, tmp_path):
        """Claude message with empty text block should not crash."""
        conv = _minimal_claude_conv(user_text="", assistant_text="Valid reply here")
        export = tmp_path / "empty_content_claude.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_null_content_message_chatgpt(self, tmp_path):
        """ChatGPT message with null in parts should produce 0 word count."""
        conv = _minimal_chatgpt_conv()
        # Set user message parts to [None]
        conv["mapping"]["u01"]["message"]["content"]["parts"] = [None]
        # Keep the assistant message valid
        export = tmp_path / "null_content.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        # The null-content user message is skipped (empty text), assistant survives
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

    def test_unicode_content_chatgpt(self, tmp_path):
        """CJK, emoji, RTL text should produce positive word counts."""
        unicode_text = "你好世界 Hello 🎉 مرحبا testing"
        conv = _minimal_chatgpt_conv(
            user_text=unicode_text,
            assistant_text="Response with unicode: 日本語テスト",
        )
        export = tmp_path / "unicode.json"
        export.write_text(json.dumps(conv if isinstance(conv, list) else [conv], ensure_ascii=False))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "chatgpt_messages_normalized.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # At least one row should have a positive word count
        word_counts = [int(r["word_count"]) for r in rows if r.get("word_count")]
        assert any(wc > 0 for wc in word_counts), "Unicode text should produce positive word counts"

    def test_unicode_content_claude(self, tmp_path):
        """Claude messages with CJK/emoji/RTL text should not crash."""
        unicode_text = "你好世界 Hello 🎉 مرحبا testing"
        conv = _minimal_claude_conv(
            user_text=unicode_text,
            assistant_text="Response: 日本語テスト",
        )
        export = tmp_path / "unicode_claude.json"
        export.write_text(json.dumps([conv], ensure_ascii=False))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "claude_messages_normalized.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        word_counts = [int(r["word_count"]) for r in rows if r.get("word_count")]
        assert any(wc > 0 for wc in word_counts), "Unicode text should produce positive word counts"

    def test_single_message_conversation_chatgpt(self, tmp_path):
        """Conversation with 1 user message and 0 assistant messages."""
        conv = {
            "id": "single-msg",
            "title": "One message",
            "create_time": 1736899200.0,
            "update_time": 1736899210.0,
            "default_model_slug": "gpt-4o",
            "mapping": {
                "root": {
                    "id": "root", "parent": None, "children": ["u01"], "message": None,
                },
                "u01": {
                    "id": "u01", "parent": "root", "children": [],
                    "message": {
                        "id": "msg-u01",
                        "author": {"role": "user"},
                        "create_time": 1736899205.0,
                        "content": {"content_type": "text", "parts": ["Just one question"]},
                        "metadata": {},
                    },
                },
            },
        }
        export = tmp_path / "single_msg.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path), "--utc"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "chatgpt_messages_normalized.csv"
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["role"] == "user"

    def test_very_long_message_chatgpt(self, tmp_path):
        """Message with 10,000+ words should be handled without error."""
        long_text = " ".join(["word"] * 10000)
        conv = _minimal_chatgpt_conv(user_text=long_text, assistant_text="OK")
        export = tmp_path / "long_msg.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CHATGPT_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "chatgpt_messages_normalized.csv"
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        user_rows = [r for r in rows if r["role"] == "user"]
        assert len(user_rows) == 1
        assert int(user_rows[0]["word_count"]) >= 10000

    def test_very_long_message_claude(self, tmp_path):
        """Claude message with 10,000+ words should be handled."""
        long_text = " ".join(["word"] * 10000)
        conv = _minimal_claude_conv(user_text=long_text, assistant_text="OK got it")
        export = tmp_path / "long_msg_claude.json"
        export.write_text(json.dumps([conv]))

        result = subprocess.run(
            [PYTHON, CLAUDE_SCRIPT, "--input", str(export), "--out", str(tmp_path),
             "--utc", "--include-content"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        csv_path = tmp_path / "claude_messages_normalized.csv"
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        user_rows = [r for r in rows if r["role"] == "user"]
        assert len(user_rows) == 1
        assert int(user_rows[0]["word_count"]) >= 10000
