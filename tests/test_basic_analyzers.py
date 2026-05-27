"""Tests for the three basic analyzer scripts (ChatGPT, Claude, combined)."""

import csv
import os

from tests.helpers import SCRIPTS_DIR, run_script

# ---------------------------------------------------------------------------
# ChatGPT analyzer
# ---------------------------------------------------------------------------

class TestChatGPTAnalyzer:
    def test_chatgpt_analyzer_runs(self, basic_analysis_outputs):
        """analyze_chatgpt.py produces a normalized CSV and monthly stats CSV."""
        assert os.path.isfile(basic_analysis_outputs["chatgpt_csv"])
        assert os.path.isfile(basic_analysis_outputs["chatgpt_monthly"])

    def test_chatgpt_csv_schema(self, basic_analysis_outputs):
        """Default CSV has the expected 8 columns."""
        expected = {
            "platform", "conversation_id", "message_id",
            "role", "created", "date", "hour", "month",
        }
        with open(basic_analysis_outputs["chatgpt_csv"], newline="") as f:
            reader = csv.DictReader(f)
            actual = set(reader.fieldnames or [])
        assert expected == actual, f"Column mismatch: extra={actual - expected}, missing={expected - actual}"

    def test_chatgpt_message_counts_positive(self, basic_analysis_outputs):
        """CSV has at least one row of data."""
        with open(basic_analysis_outputs["chatgpt_csv"], newline="") as f:
            row_count = sum(1 for _ in csv.DictReader(f))
        assert row_count > 0

    def test_chatgpt_csv_has_content_when_requested(self, content_analysis_outputs):
        """With --include-content, word_count and token_count columns appear."""
        with open(content_analysis_outputs["chatgpt_csv"], newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
        assert "word_count" in fields
        assert "token_count" in fields
        assert "content" in fields


# ---------------------------------------------------------------------------
# Claude analyzer
# ---------------------------------------------------------------------------

class TestClaudeAnalyzer:
    def test_claude_analyzer_runs(self, basic_analysis_outputs):
        """analyze_claude.py produces a normalized CSV and monthly stats CSV."""
        assert os.path.isfile(basic_analysis_outputs["claude_csv"])
        assert os.path.isfile(basic_analysis_outputs["claude_monthly"])

    def test_claude_csv_schema(self, basic_analysis_outputs):
        """Default CSV has the expected 8 columns."""
        expected = {
            "platform", "conversation_id", "message_id",
            "role", "created", "date", "hour", "month",
        }
        with open(basic_analysis_outputs["claude_csv"], newline="") as f:
            reader = csv.DictReader(f)
            actual = set(reader.fieldnames or [])
        assert expected == actual, f"Column mismatch: extra={actual - expected}, missing={expected - actual}"

    def test_claude_message_counts_positive(self, basic_analysis_outputs):
        """CSV has at least one row."""
        with open(basic_analysis_outputs["claude_csv"], newline="") as f:
            row_count = sum(1 for _ in csv.DictReader(f))
        assert row_count > 0

    def test_claude_csv_has_content_when_requested(self, content_analysis_outputs):
        """With --include-content, word_count and token_count columns appear."""
        with open(content_analysis_outputs["claude_csv"], newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
        assert "word_count" in fields
        assert "token_count" in fields
        assert "content" in fields


# ---------------------------------------------------------------------------
# Combined analyzer
# ---------------------------------------------------------------------------

class TestCombinedAnalyzer:
    def test_combined_analyzer_runs(self, basic_analysis_outputs):
        """analyze_combined.py runs and prints aggregate output."""
        result = run_script(
            os.path.join(SCRIPTS_DIR, "analyze_combined.py"),
            [
                "--chatgpt", basic_analysis_outputs["chatgpt_csv"],
                "--claude", basic_analysis_outputs["claude_csv"],
                "--utc",
            ],
        )
        # The script prints stats to stdout; make sure something appeared
        assert len(result.stdout) > 0
        # It should mention "Total messages" or similar
        lower = result.stdout.lower()
        assert "total" in lower or "messages" in lower or "platform" in lower
