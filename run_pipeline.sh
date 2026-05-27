#!/bin/bash
# ============================================================================
# run_pipeline.sh -- Run the full LLM Export Analytics pipeline
#
# Usage:
#   ./run_pipeline.sh [--sample]
#
#   --sample   Use the included synthetic sample data for a quick test run.
#              Without this flag, you will be prompted for paths to your own
#              ChatGPT and Claude export files.
# ============================================================================

set -e

# ── Color helpers (no-op if stdout is not a terminal) ────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    CYAN='\033[0;36m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' CYAN='' YELLOW='' RED='' BOLD='' NC=''
fi

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
step()  { echo -e "${GREEN}[STEP]${NC}  ${BOLD}$*${NC}"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Resolve project root (directory containing this script) ──────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  LLM Export Analytics Pipeline Runner${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""

# ── Parse arguments ──────────────────────────────────────────────────────────
USE_SAMPLE=false
for arg in "$@"; do
    case "$arg" in
        --sample) USE_SAMPLE=true ;;
        --help|-h)
            echo "Usage: $0 [--sample]"
            echo ""
            echo "  --sample   Use included synthetic sample data for a test run"
            echo "  --help     Show this help message"
            exit 0
            ;;
        *) warn "Unknown argument: $arg (ignored)" ;;
    esac
done

# ── Step 0: Check prerequisites ─────────────────────────────────────────────
step "0/8  Checking prerequisites..."

# Python 3
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null && python --version 2>&1 | grep -q "Python 3"; then
    PYTHON=python
else
    fail "Python 3 is required but not found. Please install Python 3.8+."
fi
info "Using $($PYTHON --version 2>&1)"

# pip
if ! $PYTHON -m pip --version &>/dev/null; then
    fail "pip is not available. Please install pip for Python 3."
fi

# ── Step 1: Set up virtual environment ───────────────────────────────────────
step "1/8  Setting up Python environment..."

VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtual environment in .venv/"
    $PYTHON -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "Virtual environment activated"

# Install requirements
info "Installing dependencies from requirements.txt..."
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

# numpy is needed by analyze_effectiveness.py but not listed in requirements.txt
pip install --quiet numpy

info "Dependencies installed"

# ── Step 2: Determine input paths ────────────────────────────────────────────
step "2/8  Configuring input data..."

OUTPUT_DIR="$SCRIPT_DIR/outputs"
DATA_DIR="$OUTPUT_DIR/deep_analysis-data"
TABLES_DIR="$OUTPUT_DIR/tables"

mkdir -p "$OUTPUT_DIR" "$DATA_DIR" "$TABLES_DIR"

if [ "$USE_SAMPLE" = true ]; then
    info "Using sample data from examples/"
    CHATGPT_INPUT="$SCRIPT_DIR/examples/sample_chatgpt_export.json"
    CLAUDE_INPUT="$SCRIPT_DIR/examples/sample_claude_export.json"

    if [ ! -f "$CHATGPT_INPUT" ]; then
        fail "Sample ChatGPT data not found at $CHATGPT_INPUT"
    fi
    if [ ! -f "$CLAUDE_INPUT" ]; then
        fail "Sample Claude data not found at $CLAUDE_INPUT"
    fi
else
    echo ""
    echo "Please provide paths to your export files."
    echo "(Leave blank to skip a platform.)"
    echo ""

    read -rp "  Path to ChatGPT conversations.json: " CHATGPT_INPUT
    read -rp "  Path to Claude conversations.json:  " CLAUDE_INPUT

    if [ -z "$CHATGPT_INPUT" ] && [ -z "$CLAUDE_INPUT" ]; then
        fail "At least one export file must be provided."
    fi

    # Validate paths
    if [ -n "$CHATGPT_INPUT" ] && [ ! -f "$CHATGPT_INPUT" ]; then
        fail "ChatGPT file not found: $CHATGPT_INPUT"
    fi
    if [ -n "$CLAUDE_INPUT" ] && [ ! -f "$CLAUDE_INPUT" ]; then
        fail "Claude file not found: $CLAUDE_INPUT"
    fi
fi

echo ""

# ── Step 3: Run basic analyzers ─────────────────────────────────────────────
step "3/8  Running basic analyzers (with --include-content)..."

CHATGPT_CSV=""
CLAUDE_CSV=""

if [ -n "$CHATGPT_INPUT" ]; then
    info "Analyzing ChatGPT export..."
    $PYTHON "$SCRIPT_DIR/scripts/analyze_chatgpt.py" \
        --input "$CHATGPT_INPUT" \
        --out "$OUTPUT_DIR" \
        --utc \
        --include-content
    CHATGPT_CSV="$OUTPUT_DIR/chatgpt_messages_normalized.csv"
    echo ""
fi

if [ -n "$CLAUDE_INPUT" ]; then
    info "Analyzing Claude export..."
    $PYTHON "$SCRIPT_DIR/scripts/analyze_claude.py" \
        --input "$CLAUDE_INPUT" \
        --out "$OUTPUT_DIR" \
        --utc \
        --include-content
    CLAUDE_CSV="$OUTPUT_DIR/claude_messages_normalized.csv"
    echo ""
fi

# Run combined analysis if both platforms are present
if [ -f "$OUTPUT_DIR/chatgpt_messages_normalized.csv" ] && [ -f "$OUTPUT_DIR/claude_messages_normalized.csv" ]; then
    info "Running combined cross-platform analysis..."
    $PYTHON "$SCRIPT_DIR/scripts/analyze_combined.py" \
        --chatgpt "$OUTPUT_DIR/chatgpt_messages_normalized.csv" \
        --claude "$OUTPUT_DIR/claude_messages_normalized.csv" \
        --utc
    echo ""
fi

# ── Step 4: Extract ChatGPT metadata ────────────────────────────────────────
step "4/8  Extracting ChatGPT metadata..."

METADATA_OUTPUT="$DATA_DIR/chatgpt_metadata.json"

if [ -n "$CHATGPT_INPUT" ]; then
    # extract_chatgpt_metadata.py expects a directory with shard files.
    # For a single export file, we create a temp directory with a symlink
    # and use --shard-pattern to match it.
    SHARD_DIR=$(mktemp -d)
    SHARD_BASENAME="$(basename "$CHATGPT_INPUT")"
    ln -sf "$(realpath "$CHATGPT_INPUT")" "$SHARD_DIR/$SHARD_BASENAME"

    $PYTHON "$SCRIPT_DIR/scripts/deep_analysis/extract_chatgpt_metadata.py" \
        --input-dir "$SHARD_DIR" \
        --shard-pattern "$SHARD_BASENAME" \
        --output "$METADATA_OUTPUT"

    rm -rf "$SHARD_DIR"
    echo ""
else
    warn "No ChatGPT input provided; creating minimal metadata placeholder."
    # Create a minimal metadata file so downstream scripts don't fail
    cat > "$METADATA_OUTPUT" <<'ENDJSON'
{
  "per_conversation": [],
  "model_timeline": {},
  "monthly_model_distribution": {},
  "tool_usage": {},
  "custom_gpt_stats": {
    "total_custom_gpt_conversations": 0,
    "unique_template_count": 0,
    "template_ids": []
  },
  "branching_stats": {
    "conversations_with_branches": 0,
    "total_branch_points": 0,
    "distribution": {}
  },
  "finish_details": {"counts": {}, "total": 0},
  "reasoning_stats": {"conversations_with_reasoning": 0}
}
ENDJSON
fi

# ── Step 5: Classify topics ─────────────────────────────────────────────────
step "5/8  Classifying conversations by topic..."

CLASSIFY_OUTPUT="$DATA_DIR/classifications_and_projects.json"

# classify_and_link.py expects a shard directory (conversations-NNN.json)
# for ChatGPT and a conversations.json path for Claude.
# We create temp dirs/files as needed to bridge the format gap.

# Prepare ChatGPT shard directory
SHARD_DIR=$(mktemp -d)
if [ -n "$CHATGPT_INPUT" ]; then
    ln -sf "$(realpath "$CHATGPT_INPUT")" "$SHARD_DIR/conversations-000.json"
else
    echo '[]' > "$SHARD_DIR/conversations-000.json"
fi

# Prepare Claude conversations path
if [ -n "$CLAUDE_INPUT" ]; then
    CLAUDE_CONV_PATH="$CLAUDE_INPUT"
else
    CLAUDE_CONV_PATH=$(mktemp --suffix=.json)
    echo '[]' > "$CLAUDE_CONV_PATH"
fi

# Prepare CSV paths (create empty CSVs for missing platforms)
CL_CHATGPT_CSV="$CHATGPT_CSV"
CL_CLAUDE_CSV="$CLAUDE_CSV"

if [ -z "$CL_CHATGPT_CSV" ]; then
    CL_CHATGPT_CSV=$(mktemp --suffix=.csv)
    echo 'platform,conversation_id,message_id,role,created,content,word_count,char_count,token_count,date,hour,month' > "$CL_CHATGPT_CSV"
fi
if [ -z "$CL_CLAUDE_CSV" ]; then
    CL_CLAUDE_CSV=$(mktemp --suffix=.csv)
    echo 'platform,conversation_id,message_id,role,created,content,word_count,char_count,token_count,date,hour,month' > "$CL_CLAUDE_CSV"
fi

$PYTHON "$SCRIPT_DIR/scripts/deep_analysis/classify_and_link.py" \
    --chatgpt-shard-dir "$SHARD_DIR" \
    --num-shards 1 \
    --claude-conv-path "$CLAUDE_CONV_PATH" \
    --chatgpt-csv "$CL_CHATGPT_CSV" \
    --claude-csv "$CL_CLAUDE_CSV" \
    --output "$CLASSIFY_OUTPUT"

# Clean up temp files
rm -rf "$SHARD_DIR"
[ -z "$CLAUDE_INPUT" ] && rm -f "$CLAUDE_CONV_PATH"
[ -z "$CHATGPT_CSV" ] && rm -f "$CL_CHATGPT_CSV"
[ -z "$CLAUDE_CSV" ] && rm -f "$CL_CLAUDE_CSV"

echo ""

# ── Step 6: Analyze effectiveness ───────────────────────────────────────────
step "6/8  Analyzing prompt effectiveness and interaction patterns..."

EFFECTIVENESS_OUTPUT="$DATA_DIR/effectiveness_and_patterns.json"

# Build CSV args (create empty CSVs for missing platforms)
EFF_CHATGPT_CSV="$CHATGPT_CSV"
EFF_CLAUDE_CSV="$CLAUDE_CSV"

if [ -z "$EFF_CHATGPT_CSV" ]; then
    EFF_CHATGPT_CSV=$(mktemp --suffix=.csv)
    echo 'platform,conversation_id,message_id,role,created,content,word_count,char_count,token_count,date,hour,month' > "$EFF_CHATGPT_CSV"
fi
if [ -z "$EFF_CLAUDE_CSV" ]; then
    EFF_CLAUDE_CSV=$(mktemp --suffix=.csv)
    echo 'platform,conversation_id,message_id,role,created,content,word_count,char_count,token_count,date,hour,month' > "$EFF_CLAUDE_CSV"
fi

$PYTHON "$SCRIPT_DIR/scripts/deep_analysis/analyze_effectiveness.py" \
    --chatgpt-csv "$EFF_CHATGPT_CSV" \
    --claude-csv "$EFF_CLAUDE_CSV" \
    --output "$EFFECTIVENESS_OUTPUT"

# Clean up temp CSVs
[ -z "$CHATGPT_CSV" ] && rm -f "$EFF_CHATGPT_CSV"
[ -z "$CLAUDE_CSV" ] && rm -f "$EFF_CLAUDE_CSV"

echo ""

# ── Step 7: Generate tables and charts ──────────────────────────────────────
step "7/8  Generating summary tables and charts..."

$PYTHON "$SCRIPT_DIR/scripts/deep_analysis/generate_tables_and_charts.py" \
    --data-dir "$DATA_DIR" \
    --out-dir "$TABLES_DIR"

echo ""

# ── Step 8: Summary ─────────────────────────────────────────────────────────
step "8/8  Done!"

echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${GREEN}  Pipeline complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "Results are in:"
echo ""

echo "  Basic analysis CSVs:"
if [ -n "$CHATGPT_CSV" ] && [ -f "$CHATGPT_CSV" ]; then
    echo "    $OUTPUT_DIR/chatgpt_messages_normalized.csv"
    echo "    $OUTPUT_DIR/chatgpt_monthly_stats.csv"
fi
if [ -n "$CLAUDE_CSV" ] && [ -f "$CLAUDE_CSV" ]; then
    echo "    $OUTPUT_DIR/claude_messages_normalized.csv"
    echo "    $OUTPUT_DIR/claude_monthly_stats.csv"
fi

echo ""
echo "  Deep analysis data (JSON):"
echo "    $DATA_DIR/chatgpt_metadata.json"
echo "    $DATA_DIR/classifications_and_projects.json"
echo "    $DATA_DIR/effectiveness_and_patterns.json"

echo ""
echo "  Tables and charts (Markdown + JSON):"
for f in "$TABLES_DIR"/*; do
    [ -f "$f" ] && echo "    $f"
done

echo ""
echo "Next steps:"
echo "  1. Review the .md files in $TABLES_DIR for formatted summaries."
echo "  2. To add project attribution, create a projects config file"
echo "     (see templates/example_projects.json) and re-run classify_and_link.py"
echo "     with the --projects flag."
echo "  3. See docs/DEEP_ANALYSIS_GUIDE.md for the full methodology walkthrough."
echo ""
