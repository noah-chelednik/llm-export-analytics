"""Shared constants and helper functions for the test suite."""

import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
DEEP_DIR = os.path.join(SCRIPTS_DIR, "deep-analysis")
EXAMPLES_DIR = os.path.join(REPO_ROOT, "examples")
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")

SAMPLE_CHATGPT = os.path.join(EXAMPLES_DIR, "sample_chatgpt_export.json")
SAMPLE_CLAUDE = os.path.join(EXAMPLES_DIR, "sample_claude_export.json")
EXAMPLE_PROJECTS = os.path.join(TEMPLATES_DIR, "example_projects.json")
QUALITY_PARAMS = os.path.join(TEMPLATES_DIR, "quality_params.json")
BENCHMARKS_JSON = os.path.join(TEMPLATES_DIR, "benchmarks.json")

PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_script(script_path, args, cwd=None, check=True):
    """Run a Python script as a subprocess and return the CompletedProcess."""
    cmd = [PYTHON, script_path] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or REPO_ROOT,
        timeout=60,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Script {os.path.basename(script_path)} failed "
            f"(rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout[-2000:]}\n"
            f"STDERR:\n{result.stderr[-2000:]}"
        )
    return result
