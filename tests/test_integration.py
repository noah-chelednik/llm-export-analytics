"""Integration tests: full pipeline execution and output validation."""

import csv
import json
import os
import shutil

from tests.helpers import (
    DEEP_DIR,
    SAMPLE_CHATGPT,
    SAMPLE_CLAUDE,
    SCRIPTS_DIR,
    run_script,
)


class TestIntegration:
    def test_full_pipeline_produces_all_outputs(self, tmp_path):
        """Running the full pipeline produces all expected output files."""
        out_dir = str(tmp_path / "pipeline_out")
        data_dir = str(tmp_path / "data")
        os.makedirs(out_dir)
        os.makedirs(data_dir)

        # --- Step 1: Run basic analyzers with --include-content ---
        run_script(
            os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py"),
            ["--input", SAMPLE_CHATGPT, "--out", out_dir, "--utc", "--include-content"],
        )
        run_script(
            os.path.join(SCRIPTS_DIR, "analyze_claude.py"),
            ["--input", SAMPLE_CLAUDE, "--out", out_dir, "--utc", "--include-content"],
        )

        chatgpt_csv = os.path.join(out_dir, "chatgpt_messages_normalized.csv")
        claude_csv = os.path.join(out_dir, "claude_messages_normalized.csv")
        chatgpt_monthly = os.path.join(out_dir, "chatgpt_monthly_stats.csv")
        claude_monthly = os.path.join(out_dir, "claude_monthly_stats.csv")

        assert os.path.isfile(chatgpt_csv), "ChatGPT CSV not produced"
        assert os.path.isfile(claude_csv), "Claude CSV not produced"
        assert os.path.isfile(chatgpt_monthly), "ChatGPT monthly stats not produced"
        assert os.path.isfile(claude_monthly), "Claude monthly stats not produced"

        # Verify CSVs have rows
        for csv_path in (chatgpt_csv, claude_csv):
            with open(csv_path, newline="") as f:
                row_count = sum(1 for _ in csv.DictReader(f))
            assert row_count > 0, f"CSV {csv_path} has no data rows"

        # --- Step 2: Extract ChatGPT metadata ---
        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        metadata_path = os.path.join(data_dir, "chatgpt_metadata.json")
        run_script(
            os.path.join(DEEP_DIR, "extract_chatgpt_metadata.py"),
            ["--input-dir", shard_dir, "--output", metadata_path,
             "--shard-pattern", "conversations-*.json"],
        )
        assert os.path.isfile(metadata_path)

        # --- Step 3: Classify and link ---
        classifications_path = os.path.join(data_dir, "classifications_and_projects.json")
        run_script(
            os.path.join(DEEP_DIR, "classify_and_link.py"),
            [
                "--chatgpt-shard-dir", shard_dir,
                "--num-shards", "1",
                "--claude-conv-path", SAMPLE_CLAUDE,
                "--chatgpt-csv", chatgpt_csv,
                "--claude-csv", claude_csv,
                "--output", classifications_path,
            ],
        )
        assert os.path.isfile(classifications_path)

        # --- Step 4: Effectiveness analysis ---
        effectiveness_path = os.path.join(data_dir, "effectiveness_and_patterns.json")
        run_script(
            os.path.join(DEEP_DIR, "analyze_effectiveness.py"),
            [
                "--chatgpt-csv", chatgpt_csv,
                "--claude-csv", claude_csv,
                "--output", effectiveness_path,
            ],
        )
        assert os.path.isfile(effectiveness_path)

        # --- Step 5: Tables and charts ---
        tables_dir = str(tmp_path / "tables")
        os.makedirs(tables_dir)
        run_script(
            os.path.join(DEEP_DIR, "generate_tables_and_charts.py"),
            ["--data-dir", data_dir, "--out-dir", tables_dir],
        )
        md_files = [f for f in os.listdir(tables_dir) if f.endswith(".md")]
        assert len(md_files) > 0, "No .md files produced by generate_tables_and_charts"

    def test_all_json_outputs_parseable(self, tmp_path):
        """Every JSON file produced by the pipeline is valid JSON."""
        out_dir = str(tmp_path / "json_test_out")
        data_dir = str(tmp_path / "json_test_data")
        os.makedirs(out_dir)
        os.makedirs(data_dir)

        # Run analyzers
        run_script(
            os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py"),
            ["--input", SAMPLE_CHATGPT, "--out", out_dir, "--utc", "--include-content"],
        )
        run_script(
            os.path.join(SCRIPTS_DIR, "analyze_claude.py"),
            ["--input", SAMPLE_CLAUDE, "--out", out_dir, "--utc", "--include-content"],
        )

        chatgpt_csv = os.path.join(out_dir, "chatgpt_messages_normalized.csv")
        claude_csv = os.path.join(out_dir, "claude_messages_normalized.csv")

        # Shards for metadata extraction
        shard_dir = str(tmp_path / "shards")
        os.makedirs(shard_dir)
        shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

        # Generate JSON outputs
        json_outputs = []

        # Metadata
        meta_path = os.path.join(data_dir, "chatgpt_metadata.json")
        run_script(
            os.path.join(DEEP_DIR, "extract_chatgpt_metadata.py"),
            ["--input-dir", shard_dir, "--output", meta_path,
             "--shard-pattern", "conversations-*.json"],
        )
        json_outputs.append(meta_path)

        # Classifications
        class_path = os.path.join(data_dir, "classifications_and_projects.json")
        run_script(
            os.path.join(DEEP_DIR, "classify_and_link.py"),
            [
                "--chatgpt-shard-dir", shard_dir,
                "--num-shards", "1",
                "--claude-conv-path", SAMPLE_CLAUDE,
                "--chatgpt-csv", chatgpt_csv,
                "--claude-csv", claude_csv,
                "--output", class_path,
            ],
        )
        json_outputs.append(class_path)

        # Effectiveness
        eff_path = os.path.join(data_dir, "effectiveness_and_patterns.json")
        run_script(
            os.path.join(DEEP_DIR, "analyze_effectiveness.py"),
            [
                "--chatgpt-csv", chatgpt_csv,
                "--claude-csv", claude_csv,
                "--output", eff_path,
            ],
        )
        json_outputs.append(eff_path)

        # Verify every JSON output is parseable
        for jpath in json_outputs:
            assert os.path.isfile(jpath), f"JSON output not found: {jpath}"
            with open(jpath) as f:
                data = json.load(f)
            assert isinstance(data, (dict, list)), (
                f"{jpath} did not parse to a dict or list"
            )
