# LLM Export Analytics

Privacy-first tools for analyzing personal LLM usage using official export data from ChatGPT and Claude.

This repository focuses on aggregate patterns over time (depth, activity, totals), not content analysis. By default, it does not write prompts or model outputs into generated datasets.

The accompanying methodology paper is included in this repository:

- LLM_Practice_Hours_Methodology_GIT.pdf

---

## What this repo does

- Normalizes ChatGPT and Claude exports into a shared schema
- Produces reproducible, audit-friendly metrics:
  - conversation counts and length distributions
  - depth buckets (under 10, 10–29, 30–99, 100+)
  - activity over time (days and months)
  - optional word and token counts when explicitly enabled
- Keeps outputs local and untracked to avoid accidental data leakage

---

## Repository layout

```
scripts/
  analyze_chatgpt.py     # ChatGPT export analysis (primary path reconstruction)
  analyze_claude.py      # Claude export analysis (text blocks only)
  analyze_combined.py    # Combined aggregate analysis across platforms

results/
  usage_snapshot_2025-12-09.md   # Point-in-time aggregate snapshot

outputs/
  .gitkeep                # Output folder placeholder (contents ignored)

requirements.txt
.gitignore
LLM_Practice_Hours_Methodology_GIT.pdf
README.md
```

---

## Quick start

### Install dependencies

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the per-platform analyzers

Claude:
```
python scripts/analyze_claude.py \
  --input /path/to/claude/conversations.json \
  --out outputs \
  --utc
```

ChatGPT:
```
python scripts/analyze_chatgpt.py \
  --input /path/to/chatgpt/conversations.json \
  --out outputs \
  --utc
```

### Run the combined analyzer

```
python scripts/analyze_combined.py \
  --chatgpt outputs/chatgpt_messages_normalized.csv \
  --claude outputs/claude_messages_normalized.csv \
  --utc
```

---

## Privacy model

By default, the scripts generate privacy-minimized CSVs containing timestamps, ids, roles, and derived date buckets only.

If you explicitly want local-only content and counting features, pass:

```
--include-content
```

Do not share or commit generated CSVs when content output is enabled.

---

## How the extraction works

**ChatGPT**
- Reconstructs the primary linear conversation path
- Starts from the current node when available
- Otherwise selects the newest leaf by timestamp
- Walks parent pointers back to root
- Excludes non-user and non-assistant roles

**Claude**
- Extracts text blocks only
- Normalizes roles to match the ChatGPT schema
- Excludes empty or non-text messages

**Combined**
- Merges normalized outputs
- Computes aggregate depth, activity, and scale metrics
- Includes word and token statistics only when present

Token counts are approximate and encoding-dependent.

---

## Results snapshot

A point-in-time snapshot of aggregate usage metrics as of **2025-12-09** is available here:

- results/usage_snapshot_2025-12-09.md

Additional snapshots can be added without modifying prior results.

---

## Limitations

- Results depend on platform export formats and filtering choices
- ChatGPT analysis does not traverse full conversation trees
- Claude analysis includes text blocks only
- This repository is not intended for content analysis or behavioral inference

---

## Data handling and intent

This repository contains no platform export files and distributes no generated conversation data.

It exists to make long-horizon LLM usage measurable, reproducible, and inspectable without turning private conversations into a dataset.
