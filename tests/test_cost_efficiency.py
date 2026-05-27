"""Tests for the POD / DLOD / POE / benchmark-comparison pipeline."""

import json
import os
import shutil

import pytest

from tests.helpers import (
    DEEP_DIR,
    SAMPLE_CHATGPT,
    SAMPLE_CLAUDE,
    TEMPLATES_DIR,
    run_script,
)


def _create_cost_log(path):
    """Write a minimal but valid cost_log.json covering the sample data dates."""
    cost_log = [
        {
            "platform": "chatgpt",
            "plan": "Plus",
            "monthly_cost": 20,
            "start": "2025-01",
            "end": "2025-12",
        },
        {
            "platform": "claude",
            "plan": "Pro",
            "monthly_cost": 20,
            "start": "2025-01",
            "end": "2025-12",
        },
    ]
    with open(path, "w") as f:
        json.dump(cost_log, f, indent=2)


def _create_classifications(path, chatgpt_csv, claude_csv, tmp_path):
    """Run classify_and_link.py to produce a classifications JSON."""
    shard_dir = str(tmp_path / "shards")
    os.makedirs(shard_dir, exist_ok=True)
    shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

    run_script(
        os.path.join(DEEP_DIR, "classify_and_link.py"),
        [
            "--chatgpt-shard-dir", shard_dir,
            "--num-shards", "1",
            "--claude-conv-path", SAMPLE_CLAUDE,
            "--chatgpt-csv", chatgpt_csv,
            "--claude-csv", claude_csv,
            "--output", path,
        ],
    )


def _create_chatgpt_metadata(path, tmp_path):
    """Run extract_chatgpt_metadata.py to produce metadata JSON."""
    shard_dir = str(tmp_path / "meta_shards")
    os.makedirs(shard_dir, exist_ok=True)
    shutil.copy(SAMPLE_CHATGPT, os.path.join(shard_dir, "conversations-000.json"))

    run_script(
        os.path.join(DEEP_DIR, "extract_chatgpt_metadata.py"),
        [
            "--input-dir", shard_dir,
            "--output", path,
            "--shard-pattern", "conversations-*.json",
        ],
    )


# ---------------------------------------------------------------------------
# compute_pod.py
# ---------------------------------------------------------------------------

class TestComputePOD:
    @pytest.fixture(scope="class")
    def pod_result(self, tmp_path_factory, content_analysis_outputs):
        """Run compute_pod.py once and return (output_path, parsed JSON)."""
        tmp_path = tmp_path_factory.mktemp("pod")

        cost_log_path = str(tmp_path / "cost_log.json")
        _create_cost_log(cost_log_path)

        classifications_path = str(tmp_path / "classifications.json")
        _create_classifications(
            classifications_path,
            content_analysis_outputs["chatgpt_csv"],
            content_analysis_outputs["claude_csv"],
            tmp_path,
        )

        output_path = str(tmp_path / "pod_results.json")

        run_script(
            os.path.join(DEEP_DIR, "compute_pod.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--cost-log", cost_log_path,
                "--classifications", classifications_path,
                "--output", output_path,
            ],
        )

        with open(output_path) as f:
            data = json.load(f)
        return output_path, data

    def test_compute_pod(self, pod_result):
        """POD output exists and overall.pod_words > 0."""
        _, data = pod_result
        assert "overall" in data
        assert data["overall"]["pod_words"] > 0

    def test_compute_pod_monthly(self, pod_result):
        """Monthly breakdown exists and has at least one month."""
        _, data = pod_result
        assert "monthly" in data
        assert len(data["monthly"]) > 0


# ---------------------------------------------------------------------------
# compute_poe.py
# ---------------------------------------------------------------------------

class TestComputePOE:
    @pytest.fixture(scope="class")
    def poe_result(self, tmp_path_factory, content_analysis_outputs):
        """Run compute_poe.py once and return (output_path, parsed JSON)."""
        tmp_path = tmp_path_factory.mktemp("poe")

        cost_log_path = str(tmp_path / "cost_log.json")
        _create_cost_log(cost_log_path)

        classifications_path = str(tmp_path / "classifications.json")
        _create_classifications(
            classifications_path,
            content_analysis_outputs["chatgpt_csv"],
            content_analysis_outputs["claude_csv"],
            tmp_path,
        )

        chatgpt_meta_path = str(tmp_path / "chatgpt_metadata.json")
        _create_chatgpt_metadata(chatgpt_meta_path, tmp_path)

        pod_output_path = str(tmp_path / "pod_results.json")
        run_script(
            os.path.join(DEEP_DIR, "compute_pod.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--cost-log", cost_log_path,
                "--classifications", classifications_path,
                "--output", pod_output_path,
            ],
        )

        poe_output_path = str(tmp_path / "poe_results.json")
        quality_params = os.path.join(TEMPLATES_DIR, "quality_params.json")

        run_script(
            os.path.join(DEEP_DIR, "compute_poe.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--pod-results", pod_output_path,
                "--quality-params", quality_params,
                "--classifications", classifications_path,
                "--chatgpt-metadata", chatgpt_meta_path,
                "--cost-log", cost_log_path,
                "--output", poe_output_path,
            ],
        )

        with open(poe_output_path) as f:
            data = json.load(f)
        return poe_output_path, data

    def test_compute_poe(self, poe_result):
        """POE output has poe_range with all 5 configs."""
        _, data = poe_result
        assert "poe_range" in data
        expected_configs = {"q_unit", "q_high", "q_mid", "q_low", "q_floor"}
        assert set(data["poe_range"].keys()) == expected_configs

    def test_poe_ordering(self, poe_result):
        """q_unit >= q_high >= q_mid >= q_low >= q_floor."""
        _, data = poe_result
        pr = data["poe_range"]
        vals = {k: v["poe_words"] for k, v in pr.items()}
        assert vals["q_unit"] >= vals["q_high"], (
            f"q_unit ({vals['q_unit']}) < q_high ({vals['q_high']})"
        )
        assert vals["q_high"] >= vals["q_mid"], (
            f"q_high ({vals['q_high']}) < q_mid ({vals['q_mid']})"
        )
        assert vals["q_mid"] >= vals["q_low"], (
            f"q_mid ({vals['q_mid']}) < q_low ({vals['q_low']})"
        )
        assert vals["q_low"] >= vals["q_floor"], (
            f"q_low ({vals['q_low']}) < q_floor ({vals['q_floor']})"
        )


# ---------------------------------------------------------------------------
# compare_benchmarks.py
# ---------------------------------------------------------------------------

class TestBenchmarkComparison:
    def test_benchmark_comparison(self, tmp_path, content_analysis_outputs):
        """compare_benchmarks.py produces JSON with direct_comparisons and summary_table."""
        cost_log_path = str(tmp_path / "cost_log.json")
        _create_cost_log(cost_log_path)

        classifications_path = str(tmp_path / "classifications.json")
        _create_classifications(
            classifications_path,
            content_analysis_outputs["chatgpt_csv"],
            content_analysis_outputs["claude_csv"],
            tmp_path,
        )

        chatgpt_meta_path = str(tmp_path / "chatgpt_metadata.json")
        _create_chatgpt_metadata(chatgpt_meta_path, tmp_path)

        # POD
        pod_path = str(tmp_path / "pod_results.json")
        run_script(
            os.path.join(DEEP_DIR, "compute_pod.py"),
            [
                "--chatgpt-csv", content_analysis_outputs["chatgpt_csv"],
                "--claude-csv", content_analysis_outputs["claude_csv"],
                "--cost-log", cost_log_path,
                "--classifications", classifications_path,
                "--output", pod_path,
            ],
        )

        # DLOD (run without --deliverables; script exits 0 with a message)
        # We need a real DLOD result for compare_benchmarks.
        # compute_dlod exits 0 when no deliverables are provided, but
        # compare_benchmarks requires a valid dlod_results.json.
        # So we create a minimal placeholder.
        dlod_path = str(tmp_path / "dlod_results.json")
        dlod_stub = {
            "metadata": {
                "deliverables_count": 1,
            },
            "overall": {
                "dlod_words": 0,
                "total_output_words": 0,
                "deliverable_linked_words": 0,
                "coverage_rate": 0,
            },
            "per_project": {
                "test_project": {
                    "verified": True,
                    "implied_cost": 10.0,
                    "output_words": 500,
                },
            },
            "per_deliverable": [],
            "monthly": {},
        }
        with open(dlod_path, "w") as f:
            json.dump(dlod_stub, f, indent=2)

        benchmarks = os.path.join(TEMPLATES_DIR, "benchmarks.json")
        output_path = str(tmp_path / "benchmark_comparison.json")

        run_script(
            os.path.join(DEEP_DIR, "compare_benchmarks.py"),
            [
                "--pod", pod_path,
                "--dlod", dlod_path,
                "--benchmarks", benchmarks,
                "--output", output_path,
            ],
        )

        assert os.path.isfile(output_path)
        with open(output_path) as f:
            data = json.load(f)

        assert "direct_comparisons" in data
        assert "summary_table" in data
