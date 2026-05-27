"""Tests for the topic classifier and project attribution logic."""

import json
import os
import shutil
import sys

from tests.helpers import (
    DEEP_DIR,
    SAMPLE_CHATGPT,
    SAMPLE_CLAUDE,
    run_script,
)

# Import classifier functions directly for unit-style tests
sys.path.insert(0, DEEP_DIR)
from classify_and_link import (
    CATEGORY_PATTERNS,
    classify_topics,
    score_text,
)


class TestClassifier:
    def test_clear_technical_title_gets_category(self):
        """A clearly technical title should not be classified as Other."""
        title = "Python sorting algorithm implementation"
        topics = classify_topics(title, method="title")
        assert len(topics) > 0, "Technical title should get at least one category"
        categories = [t["category"] for t in topics]
        assert "Other" not in categories, (
            f"Title '{title}' was classified as Other; expected a real category"
        )
        # Should match Software Engineering
        assert "Software Engineering" in categories

    def test_ai_related_title(self):
        """An AI-related title should match AI/ML/LLM category."""
        title = "Fine-tune a transformer model for inference"
        topics = classify_topics(title, method="title")
        categories = [t["category"] for t in topics]
        assert "AI/ML/LLM" in categories

    def test_ambiguous_title_returns_empty(self):
        """A truly ambiguous title with no keywords returns empty list."""
        title = "Help"
        topics = classify_topics(title, method="title")
        # "Help" doesn't match any keywords, so classify_topics returns []
        assert topics == [], f"Ambiguous title 'Help' should return empty: {topics}"

    def test_multi_category_returns_at_most_two(self):
        """Title matching multiple categories returns at most 2."""
        # This title has keywords across several categories
        title = "Write a poem about programming algorithms and neural networks"
        topics = classify_topics(title, method="title")
        assert 1 <= len(topics) <= 2, (
            f"Expected 1-2 topic categories, got {len(topics)}: {topics}"
        )

    def test_score_text_returns_per_category_counts(self):
        """score_text returns a dict of category -> hit count."""
        text = "debug the python function error in this module"
        scores = score_text(text, CATEGORY_PATTERNS)
        assert isinstance(scores, dict)
        # Should have hits in Software Engineering
        assert "Software Engineering" in scores
        assert scores["Software Engineering"] >= 1

    def test_score_text_empty_returns_empty(self):
        """score_text on empty string returns empty dict."""
        scores = score_text("", CATEGORY_PATTERNS)
        assert scores == {}

    def test_project_config_produces_attribution(self, tmp_path, content_analysis_outputs):
        """Projects config with matching keywords produces non-null attribution."""
        # Create a projects config that matches something in the sample data
        projects = {
            "React Debug Project": {
                "keywords": ["react", "component", "debug", "rendering"],
                "platform": "both",
            },
        }
        projects_path = str(tmp_path / "test_projects.json")
        with open(projects_path, "w") as f:
            json.dump(projects, f)

        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir, exist_ok=True)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        output_path = str(tmp_path / "classifications.json")

        run_script(
            os.path.join(DEEP_DIR, "classify_and_link.py"),
            [
                "--chatgpt-shard-dir", shard_dir,
                "--num-shards", "1",
                "--claude-conv-path", SAMPLE_CLAUDE,
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--output", output_path,
                "--projects", projects_path,
            ],
        )

        with open(output_path) as f:
            data = json.load(f)

        # At least one conversation should be attributed to the project
        attributed = [
            e for e in data["per_conversation"]
            if e.get("project") is not None
        ]
        assert len(attributed) > 0, (
            "Expected at least one conversation attributed to 'React Debug Project'"
        )

    def test_empty_project_config_no_error(self, tmp_path, content_analysis_outputs):
        """Empty projects config ({}) should work without errors."""
        projects_path = str(tmp_path / "empty_projects.json")
        with open(projects_path, "w") as f:
            json.dump({}, f)

        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir, exist_ok=True)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        output_path = str(tmp_path / "classifications.json")

        run_script(
            os.path.join(DEEP_DIR, "classify_and_link.py"),
            [
                "--chatgpt-shard-dir", shard_dir,
                "--num-shards", "1",
                "--claude-conv-path", SAMPLE_CLAUDE,
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--output", output_path,
                "--projects", projects_path,
            ],
        )

        with open(output_path) as f:
            data = json.load(f)

        assert "per_conversation" in data
        assert len(data["per_conversation"]) > 0
