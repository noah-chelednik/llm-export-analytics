# Sample output

This directory is the **verbatim output of the pipeline run on the included
synthetic sample data** — i.e. what you get from:

```bash
./run_pipeline.sh --sample
```

Nothing here is real personal data. The inputs are the synthetic
`examples/sample_chatgpt_export.json` and `examples/sample_claude_export.json`,
so these files are safe to commit (the privacy rules in `.gitignore` that
normally exclude `*_normalized.csv` and `*_metadata.json` are deliberately
overridden for this folder only).

It exists so you can see exactly what the scripts produce **before** running
them on your own exports — and so the distinction between *tool output* and the
authored PDF papers is concrete. The papers in this repo are written by hand on
top of output like this; the pipeline generates the numbers, not the prose.

## What's here

| File | Produced by |
|:---|:---|
| `chatgpt_messages_normalized.csv`, `claude_messages_normalized.csv` | `analyze_chatgpt.py` / `analyze_claude.py` (with `--include-content`) |
| `chatgpt_monthly_stats.csv`, `claude_monthly_stats.csv` | basic analyzers |
| `practice_hours.txt`, `practice_hours.json` | `compute_hours.py` |
| `tables/*.md` | `generate_tables_and_charts.py` (model timeline, migration chart, topic distribution, technique adoption, session dynamics, tool usage, outcomes) |
| `tables/summary_stats.json` | `generate_tables_and_charts.py` |
| `deep_data/*.json` | `extract_chatgpt_metadata.py`, `classify_and_link.py`, `analyze_effectiveness.py` |

The bar charts under `tables/` (e.g. `model_migration_chart.md`) use block
characters; they render correctly in any monospace context and in the PDF
papers when built with a block-capable mono font (DejaVu Sans Mono).

> Note: figures here are tiny and not meaningful on their own — the sample
> data is a handful of synthetic conversations. They demonstrate format and
> reproducibility, not scale.
