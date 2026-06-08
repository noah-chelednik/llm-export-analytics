# results/ — the real aggregate output behind the papers

This folder holds **my own real, aggregate-only output** from running the
pipeline on my complete ChatGPT and Claude exports (the 2026-05-26 run). These
are the actual numbers the PDF papers were written from — provenance, not a
demo.

Everything here is **aggregate-only**: counts, distributions, monthly rollups,
and the practice-hours computation. **No message content, prompts, or
conversation text is included** — that raw data stays on my machine, per the
privacy contract the papers describe (see the repo `.gitignore`). For a
*runnable* example of what the tools emit, see
[`examples/sample_output/`](../examples/sample_output/), which uses synthetic
data instead.

## Contents

| File | What it is |
|:---|:---|
| `usage_snapshot_2026-05-26.md` | Current point-in-time aggregate snapshot (conversations, messages, words, tokens, active days). |
| `usage_snapshot_2025-12-09.md` | Prior snapshot, for comparison. |
| `practice_hours.txt` / `.json` | Output of `compute_hours.py` on the real exports — the Tier 1 / Tier 2 figures used in the methodology paper (Tier 1 baseline 3,737 h; Tier 2 baseline 6,465 h; conservative floor 5,101 h). |
| `tables/` | The real summary tables and ASCII charts the *Deep LLM Usage Analysis* paper is built from (model timeline, model-migration chart, topic distribution, technique adoption/growth, session dynamics, tool usage, conversation outcomes, platform share, project attribution). |

## Redaction

Two tables name projects. Personal project codenames are replaced with neutral
labels (e.g. "Personal project A"); genuinely public portfolio projects (VCAT,
The Muser, this repo, and the published papers) are
kept. The one classical-language topic label is generalized to
"Domain-Specific Processing." These match the redactions in the published PDF
papers exactly, so the artifacts agree.

The figures here are real and large; the sample-output figures are tiny and
synthetic. Same tools, two purposes: this folder proves the papers' numbers;
`examples/sample_output/` shows a stranger what a run looks like.
