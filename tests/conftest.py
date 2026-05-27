"""Shared fixtures for LLM Export Analytics test suite."""

import os

import pytest

from tests.helpers import (
    BENCHMARKS_JSON,
    EXAMPLE_PROJECTS,
    QUALITY_PARAMS,
    SAMPLE_CHATGPT,
    SAMPLE_CLAUDE,
    SCRIPTS_DIR,
    run_script,
)

# ---------------------------------------------------------------------------
# Fixtures -- sample data paths
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_chatgpt_path():
    return SAMPLE_CHATGPT


@pytest.fixture(scope="session")
def sample_claude_path():
    return SAMPLE_CLAUDE


@pytest.fixture(scope="session")
def example_projects_path():
    return EXAMPLE_PROJECTS


@pytest.fixture(scope="session")
def quality_params_path():
    return QUALITY_PARAMS


@pytest.fixture(scope="session")
def benchmarks_path():
    return BENCHMARKS_JSON


# ---------------------------------------------------------------------------
# Fixture -- run basic analyzers once, return CSV paths
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def basic_analysis_outputs(tmp_path_factory):
    """Run both analyzers (without --include-content) once and return
    a dict with paths to the resulting CSVs.
    """
    out_dir = str(tmp_path_factory.mktemp("basic_outputs"))

    # Run ChatGPT analyzer
    run_script(
        os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py"),
        ["--input", SAMPLE_CHATGPT, "--out", out_dir, "--utc"],
    )

    # Run Claude analyzer
    run_script(
        os.path.join(SCRIPTS_DIR, "analyze_claude.py"),
        ["--input", SAMPLE_CLAUDE, "--out", out_dir, "--utc"],
    )

    return {
        "out_dir": out_dir,
        "chatgpt_csv": os.path.join(out_dir, "chatgpt_messages_normalized.csv"),
        "chatgpt_monthly": os.path.join(out_dir, "chatgpt_monthly_stats.csv"),
        "claude_csv": os.path.join(out_dir, "claude_messages_normalized.csv"),
        "claude_monthly": os.path.join(out_dir, "claude_monthly_stats.csv"),
    }


@pytest.fixture(scope="session")
def content_analysis_outputs(tmp_path_factory):
    """Run both analyzers WITH --include-content for tests that need
    word_count / token_count / content columns.
    """
    out_dir = str(tmp_path_factory.mktemp("content_outputs"))

    run_script(
        os.path.join(SCRIPTS_DIR, "analyze_chatgpt.py"),
        ["--input", SAMPLE_CHATGPT, "--out", out_dir, "--utc", "--include-content"],
    )

    run_script(
        os.path.join(SCRIPTS_DIR, "analyze_claude.py"),
        ["--input", SAMPLE_CLAUDE, "--out", out_dir, "--utc", "--include-content"],
    )

    return {
        "out_dir": out_dir,
        "chatgpt_csv": os.path.join(out_dir, "chatgpt_messages_normalized.csv"),
        "claude_csv": os.path.join(out_dir, "claude_messages_normalized.csv"),
    }
