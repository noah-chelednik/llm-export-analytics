# LLM Export Analytics

**Reproducible measurement of long-horizon LLM practice.** This repository quantifies 33 months (August 2023 – April 2026) of complete, official ChatGPT and Claude exports — no sampling — and packages the analysis as open, privacy-first tools so anyone can run the same measurement on their own exports.

**Headline figures** (complete exports; every number is reproducible from the scripts here):

| Metric | Value |
|:---|:---|
| Conversations / messages | 2,398 / 71,427 |
| Active days | 883 (88% of the period) |
| Model output / words written | 12.98M / 2.06M words · 23.4M tokens |
| External validation | Top 1% of ChatGPT users by messages sent (OpenAI, 2025) |
| Documented in-chat practice | 3,737 hours (auditable) |
| Total LLM-assisted practice | 6,465 hours (conservative floor 5,101) |

**Start here:** the [one-page summary](docs/Prompting_One_Pager.pdf) is the 60-second read. Full methodology in the [practice-hours paper](LLM_Practice_Hours_Methodology.pdf), [usage analysis](docs/Deep_LLM_Usage_Analysis.pdf), and [cost-efficiency paper](docs/Productive_Output_Efficiency.pdf).

The tools turn raw export data into model-adoption timelines, topic breakdowns, prompt-technique tracking, and cost-efficiency analysis. Everything runs locally; no conversations, prompts, or PII are ever committed.

## Try it now

```bash
git clone https://github.com/noah-chelednik/llm-export-analytics.git
cd llm-export-analytics
./run_pipeline.sh --sample
```

This runs the full pipeline against included sample data so you can see what it produces before using your own exports.

## What you get

**Model adoption timeline** shows which AI models you used and when you switched (real output, abbreviated):
```
2024-05  █████████████████████████████ GPT-4o (73%)  ████████ GPT-4 (19%)  ███ GPT-3.5 (8%)
2025-08  ██████████████████████████ GPT-5 (66%)  ████████ GPT-4o (21%)  ████ GPT-5-T (11%)
2026-02  ██████████████████████████████████████ GPT-5.2-T (94%)  ██ GPT-5.2 (6%)
```

**Prompt technique tracking** measures how your prompting style evolves over time:

| Technique | Adoption Rate | First Appeared |
|:---|---:|:---|
| Constraint specification | 6.5% | 2023-08 |
| Context front-loading | 4.6% | 2024-02 |
| Code inclusion | 2.7% | 2023-10 |
| Multi-step instructions | 1.7% | 2023-11 |

**Cost efficiency** computes your Productive Output per Dollar (POD) from subscription costs and total output words. Also computes quality-adjusted POE with sensitivity analysis.

**Plus:** topic distribution, session dynamics, interaction style breakdown, conversation outcome classification, industry benchmark comparison, and more.

## Papers

Four documents, fastest first:

- **[Prompting_One_Pager.pdf](docs/Prompting_One_Pager.pdf)** : One-page summary — headline results and approach at a glance.

- **[LLM_Practice_Hours_Methodology.pdf](LLM_Practice_Hours_Methodology.pdf)** : Methodology for quantifying LLM practice hours from export data. Tiered claims with sensitivity analysis and stress testing.

- **[Deep_LLM_Usage_Analysis.pdf](docs/Deep_LLM_Usage_Analysis.pdf)** : Data-driven usage profile covering model adoption (21 model versions), domain portfolio, prompt engineering effectiveness, and interaction patterns.

- **[Productive_Output_Efficiency.pdf](docs/Productive_Output_Efficiency.pdf)** : A standardized methodology for measuring individual LLM cost efficiency. Defines Productive Output per Dollar (POD), Deliverable-Linked Output per Dollar (DLOD), and quality-adjusted Productive Output Efficiency (POE).

### What the scripts produce vs. what the papers are

These are two different things:

- **The scripts produce data**: normalized CSVs, JSON, and the Markdown summary tables and ASCII charts you see under [`examples/sample_output/`](examples/sample_output/). That is the raw, reproducible output anyone gets by running the pipeline on their own exports.
- **The papers are authored analyses.** The PDFs above were written by me (Noah T. G. Chelednik) on top of *my own* export output — the narrative, framing, sensitivity analysis, and conclusions are mine. The pipeline does not generate the PDFs; it generates the numbers they are built from. Every figure in the papers is reproducible from the scripts (see `examples/sample_output/` for what a run looks like, and `compute_hours.py` below for the practice-hours figures specifically).

In short: run the scripts and you get the same *kind* of data about yourself; the papers are what I made *with* that data.

For provenance, [`results/`](results/) holds my **own real, aggregate-only output** behind the papers — the actual snapshot, practice-hours, and summary tables the PDFs were written from (no message content; personal project names redacted). `examples/sample_output/` is the synthetic, runnable demo; `results/` is the real thing.

## Repository layout

```
scripts/
  analyze_chatgpt.py              # ChatGPT export normalization and basic stats
  analyze_claude.py               # Claude export normalization and basic stats
  analyze_combined.py             # Combined cross-platform analysis
  compute_hours.py                # Practice-hours model (Tier 1 / Tier 2) from CSVs

scripts/deep_analysis/
  extract_chatgpt_metadata.py     # Model versions, tools, branching, reasoning
  classify_and_link.py            # Topic classification + project attribution
  analyze_effectiveness.py        # Prompt techniques, outcomes, interaction patterns
  generate_tables_and_charts.py   # Formatted tables and ASCII charts
  compute_pod.py                  # Productive Output per Dollar
  compute_dlod.py                 # Deliverable-Linked Output per Dollar
  compute_poe.py                  # Quality-adjusted POE with sensitivity analysis
  compare_benchmarks.py           # Industry benchmark comparison

examples/
  sample_chatgpt_export.json      # Synthetic sample data for testing
  sample_claude_export.json       # Synthetic sample data for testing
  sample_output/                  # Verbatim output of `run_pipeline.sh --sample`

templates/
  example_projects.json           # Example project config (customize for your projects)
  cost_log_template.json          # Template for subscription cost tracking
  deliverable_inventory_template.json  # Template for verified deliverables
  quality_params.json             # Q coefficient configurations for POE
  benchmarks.json                 # Curated industry benchmark data with citations

docs/
  DEEP_ANALYSIS_GUIDE.md          # Step-by-step guide to the full pipeline
  Deep_LLM_Usage_Analysis.pdf
  Productive_Output_Efficiency.pdf
  Prompting_One_Pager.pdf

results/                          # My real aggregate output behind the papers
  usage_snapshot_2025-12-09.md    # Historical snapshot
  usage_snapshot_2026-05-26.md    # Current snapshot
  practice_hours.txt / .json      # Real compute_hours.py output (Tier 1 / Tier 2)
  tables/                         # Real summary tables + charts the Deep paper is built from
```

## Quick start with your own data

### 1. Get your exports

**ChatGPT:** Settings > Data controls > Export data. You'll receive a ZIP containing `conversations.json` (or multiple shards).

**Claude:** Settings > Account > Export data. You'll receive a ZIP containing `conversations.json`.

### 2. Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Basic analysis

```bash
python scripts/analyze_chatgpt.py --input /path/to/conversations.json --out outputs --utc
python scripts/analyze_claude.py --input /path/to/conversations.json --out outputs --utc
python scripts/analyze_combined.py \
  --chatgpt outputs/chatgpt_messages_normalized.csv \
  --claude outputs/claude_messages_normalized.csv --utc
```

To reproduce the practice-hours figures from the methodology paper (run the
basic analyzers with `--include-content` first so word counts are available):

```bash
python scripts/compute_hours.py \
  --chatgpt outputs/chatgpt_messages_normalized.csv \
  --claude outputs/claude_messages_normalized.csv
```

This prints the Tier 1 (auditable in-chat) and Tier 2 (with offline work)
hour estimates with their sensitivity ranges, applying the constants
documented in `LLM_Practice_Hours_Methodology.pdf`.

### 4. Deep analysis

Run the basic scripts with `--include-content` first, then see the [Deep Analysis Guide](docs/DEEP_ANALYSIS_GUIDE.md) for the full pipeline: model tracking, topic classification, prompt effectiveness, cost efficiency, and industry benchmarks.

## Privacy

All processing is local. No network calls. No telemetry.

By default, scripts produce privacy-minimized CSVs (timestamps, IDs, roles only). Content analysis requires the explicit `--include-content` flag. Never commit or share CSVs generated with content enabled.

## How the extraction works

**ChatGPT:** Reconstructs the primary conversation path from the mapping tree. Walks parent pointers from the current node back to root. Extracts per-message model metadata, tool usage, branching, and reasoning information.

**Claude:** Extracts text blocks from content arrays. Normalizes roles to match the shared schema. Supports both web/app and Claude Code CLI sessions.

**Deep analysis:** Adds topic classification via keyword taxonomy with content fallback, optional project attribution from user-provided config, prompt technique detection (10 techniques tracked), conversation outcome classification, interaction style analysis, and cost efficiency computation.

## Limitations

- Results depend on platform export formats which may change
- ChatGPT analysis reconstructs primary path only, not full conversation trees
- Topic classification uses keyword matching (expect 40-50% "Other" for casual conversation titles)
- Project attribution requires user-provided config and represents a lower bound
- Cost metrics are designed for subscription pricing, not API pricing
- Token counts are approximate and encoding-dependent

## License

This repository contains no platform export files and distributes no conversation data. It exists to make long-horizon LLM usage measurable, reproducible, and inspectable without turning private conversations into a dataset.
