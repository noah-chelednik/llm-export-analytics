"""Tests for deep_analysis scripts."""

import json
import os
import shutil

from tests.helpers import (
    DEEP_DIR,
    SAMPLE_CHATGPT,
    SAMPLE_CLAUDE,
    run_script,
)

# ---------------------------------------------------------------------------
# extract_chatgpt_metadata.py
# ---------------------------------------------------------------------------

class TestExtractChatGPTMetadata:
    def test_chatgpt_metadata_extraction(self, tmp_path):
        """Run extract_chatgpt_metadata.py on sample data and verify JSON keys."""
        # The script expects a *directory* of shard files named conversations-NNN.json.
        # Create a shard directory with the sample data as conversations-000.json.
        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        output_path = str(tmp_path / "chatgpt_metadata.json")

        run_script(
            os.path.join(DEEP_DIR, "extract_chatgpt_metadata.py"),
            [
                "--input-dir", shard_dir,
                "--output", output_path,
                "--shard-pattern", "conversations-*.json",
            ],
        )

        assert os.path.isfile(output_path)
        with open(output_path) as f:
            data = json.load(f)

        # Top-level keys
        assert "per_conversation" in data
        assert "model_timeline" in data
        assert "tool_usage" in data
        assert isinstance(data["per_conversation"], list)
        assert len(data["per_conversation"]) > 0


# ---------------------------------------------------------------------------
# classify_and_link.py
# ---------------------------------------------------------------------------

class TestTopicClassification:
    def _prepare_classify_args(self, tmp_path, content_outputs, projects=None):
        """Build common args for classify_and_link.py.

        The script expects ChatGPT shard files in a directory.
        We create a shard dir with sample data as conversations-000.json.
        """
        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir, exist_ok=True)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        output_path = str(tmp_path / "classifications.json")

        args = [
            "--chatgpt-shard-dir", shard_dir,
            "--num-shards", "1",
            "--claude-conv-path", SAMPLE_CLAUDE,
            "--chatgpt-csv", content_outputs["chatgpt_csv"],
            "--claude-csv", content_outputs["claude_csv"],
            "--output", output_path,
        ]
        if projects:
            args += ["--projects", projects]

        return args, output_path

    def test_topic_classification(self, tmp_path, content_analysis_outputs):
        """Topic-only run produces per_conversation array and topic_summary."""
        args, output_path = self._prepare_classify_args(
            tmp_path, content_analysis_outputs,
        )

        run_script(os.path.join(DEEP_DIR, "classify_and_link.py"), args)

        assert os.path.isfile(output_path)
        with open(output_path) as f:
            data = json.load(f)

        assert "per_conversation" in data
        assert isinstance(data["per_conversation"], list)
        assert len(data["per_conversation"]) > 0
        assert "topic_summary" in data

    def test_topic_classification_with_projects(
        self, tmp_path, content_analysis_outputs, example_projects_path,
    ):
        """With --projects, project attribution appears in per_conversation."""
        args, output_path = self._prepare_classify_args(
            tmp_path, content_analysis_outputs, projects=example_projects_path,
        )

        run_script(os.path.join(DEEP_DIR, "classify_and_link.py"), args)

        with open(output_path) as f:
            data = json.load(f)

        assert "per_conversation" in data
        assert len(data["per_conversation"]) > 0

        # At least some conversations should have a "project" key
        # (may be null if no keywords match, but the key should exist)
        has_project_key = any(
            "project" in entry
            for entry in data["per_conversation"]
        )
        assert has_project_key, "No entries have a 'project' key with --projects"


# ---------------------------------------------------------------------------
# analyze_effectiveness.py
# ---------------------------------------------------------------------------

class TestEffectivenessAnalysis:
    def test_effectiveness_analysis(self, tmp_path, content_analysis_outputs):
        """Run analyze_effectiveness.py on content CSVs, verify output keys."""
        output_path = str(tmp_path / "effectiveness.json")

        run_script(
            os.path.join(DEEP_DIR, "analyze_effectiveness.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--output", output_path,
            ],
        )

        assert os.path.isfile(output_path)
        with open(output_path) as f:
            data = json.load(f)

        assert "technique_adoption" in data
        assert "conversation_outcomes" in data
        assert "interaction_style" in data


# ---------------------------------------------------------------------------
# generate_tables_and_charts.py
# ---------------------------------------------------------------------------

class TestTablesGeneration:
    def test_tables_generation(self, tmp_path, content_analysis_outputs):
        """Run generate_tables_and_charts.py and verify .md files are created."""
        # This script needs chatgpt_metadata.json, classifications_and_projects.json,
        # and effectiveness_and_patterns.json in a data directory.
        # We first run the upstream scripts to produce those files.
        data_dir = str(tmp_path / "data")
        out_dir = str(tmp_path / "tables")
        os.makedirs(data_dir)
        os.makedirs(out_dir)

        # 1. Generate chatgpt_metadata.json
        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        run_script(
            os.path.join(DEEP_DIR, "extract_chatgpt_metadata.py"),
            [
                "--input-dir", shard_dir,
                "--output", os.path.join(data_dir, "chatgpt_metadata.json"),
                "--shard-pattern", "conversations-*.json",
            ],
        )

        # 2. Generate classifications_and_projects.json
        run_script(
            os.path.join(DEEP_DIR, "classify_and_link.py"),
            [
                "--chatgpt-shard-dir", shard_dir,
                "--num-shards", "1",
                "--claude-conv-path", SAMPLE_CLAUDE,
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--output", os.path.join(data_dir, "classifications_and_projects.json"),
            ],
        )

        # 3. Generate effectiveness_and_patterns.json
        run_script(
            os.path.join(DEEP_DIR, "analyze_effectiveness.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--output", os.path.join(data_dir, "effectiveness_and_patterns.json"),
            ],
        )

        # 4. Now run generate_tables_and_charts
        run_script(
            os.path.join(DEEP_DIR, "generate_tables_and_charts.py"),
            ["--data-dir", data_dir, "--out-dir", out_dir],
        )

        # Verify at least one .md file was created
        md_files = [f for f in os.listdir(out_dir) if f.endswith(".md")]
        assert len(md_files) > 0, f"No .md files found in {out_dir}; contents: {os.listdir(out_dir)}"
