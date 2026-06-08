# Changelog

## v2.5.0 (June 2026)

### Changed
- README restructured for a fast read: a "what this is + headline figures" block now leads, above setup instructions, and the one-page summary is surfaced as the start-here document.
- Replaced the illustrative model-adoption example in the README, which showed model versions in months before they were released, with real rows from `results/tables/model_migration_chart.md`.
- Naming standardized to **Technomirrorism** (was "Technomirism" in the POE paper §9).
- Softened "the first standardized methodology" to "a standardized methodology" in the POE paper and README.
- Author name standardized to **Noah T. G. Chelednik** in the README.
- Renamed `LLM_Practice_Hours_Methodology_GIT.pdf` to `LLM_Practice_Hours_Methodology.pdf` (updated all references).
- Rebuilt the POE PDF.

## v2.4.0 (June 2026)

### Fixed (privacy) / Changed
- POE deliverable inventory (§6.3): removed the personal philosophy-paper entry and genericized deliverables that are not public artifacts (freelance articles, academic coursework). Only genuinely public artifacts are named (VCAT, The Muser, this repo, the published papers). The same genericization is applied to the Deep paper's project-attribution table and `results/`.
- Prompting one-pager: removed the "did not write a single line of the code by hand" claim.
- Author name standardized to **Noah T. G. Chelednik** across all papers (no full middle names).
- All four paper PDFs regenerated.

## v2.3.0 (June 2026)

### Added
- `results/` now carries the **real aggregate output behind the papers**: `practice_hours.txt`/`.json` (real `compute_hours.py` output) and `results/tables/` (the real summary tables and charts the Deep paper is built from), alongside the existing snapshots. Aggregate-only — no message content. `examples/sample_output/` remains the synthetic runnable demo.

### Fixed (privacy)
- Scrubbed personal project codenames (e.g. Aurora Build, Operation *, My DNA, The Remembrancer, Technomirrorism, The Great War) from the *Deep LLM Usage Analysis* paper's project-attribution table — they were inadvertently exposed in the published PDF. Replaced with neutral labels; genuinely public portfolio projects (VCAT, The Muser, How-To Geek, coursework, domain pipeline) retained. The `results/` table uses the same redactions, so all artifacts agree.

## v2.2.0 (June 2026)

### Added
- `scripts/compute_hours.py` — runnable implementation of the practice-hours methodology (Tier 1 / Tier 2 with sensitivity ranges) directly from the normalized CSVs. The headline hour figures are now reproducible push-button instead of by hand. Wired into `run_pipeline.sh` (also writes `practice_hours.json`/`.txt`).
- `examples/sample_output/` — the verbatim output of `run_pipeline.sh --sample` (CSVs, JSON, summary tables, ASCII charts, practice-hours), so the raw tool output is visible alongside the authored papers. A scoped `.gitignore` exception allows these synthetic files only.
- README section distinguishing what the scripts produce (data) from what the papers are (authored analyses built on that data).

### Changed
- Typography overhaul of all four PDF papers: readable serif body (Noto Serif), block-capable monospace (DejaVu Sans Mono) so the ASCII bar charts render as solid bars instead of missing glyphs, microtype justification, and roomier spacing. No figures changed — presentation only.

## v2.1.0 (June 2026)

- Methodology paper refreshed to Revision 3: incorporates the complete ChatGPT export through April 2026 (19 JSON shards), replacing the held-over December 2025 ChatGPT figures from the April revision. Both platforms now current through April 2026.
- Combined corpus updated to 2,398 conversations / 71,427 messages / 23,392,755 tokens (from 2,180 / 65,400 / 20,583,230).
- Practice-hour figures recomputed on the refreshed data (constants and formulas unchanged): Tier 1 baseline 3,737 h (was 3,264), Tier 2 baseline 6,465 h (was 5,755), Tier 2 conservative floor 5,101 h (was 4,509). The "5,000+" claim is now satisfied by the conservative floor.

## v2.0.0 (May 2026)

Major expansion: deep analysis pipeline, cost efficiency methodology, config-driven architecture.

### Added
- 8 deep analysis scripts covering model metadata, topic classification, prompt effectiveness, cost efficiency (POD/DLOD/POE), and industry benchmarks
- Productive Output Efficiency (POE) methodology paper defining the first standardized individual LLM cost efficiency metric
- Deep LLM Usage Analysis paper covering model adoption, domain portfolio, prompt engineering effectiveness, and interaction patterns
- One-page prompting summary document
- Getting started guide for the full analysis pipeline
- Synthetic sample data for immediate testing
- Pipeline run script (`run_pipeline.sh --sample`)
- Config-driven project attribution (user provides their own project keywords)
- Cost log and deliverable inventory templates
- Industry benchmark data with citations (Faros AI tokenmaxxing data, METR RCT, GitHub Copilot, enterprise spend)
- Quality parameter configurations for POE sensitivity analysis
- Updated usage snapshot (May 2026)

### Changed
- All deep analysis scripts are now fully config-driven with zero hardcoded personal data
- README expanded with example output, quickstart, and sample data instructions
- Requirements unchanged (pandas, tiktoken)

## v1.1.0 (April 2026)

- Updated methodology paper (April 2026 revision with refreshed Claude data)

## v1.0.0 (December 2025)

Initial release.

- ChatGPT export analyzer with primary path reconstruction
- Claude export analyzer with text block extraction
- Combined cross-platform analyzer
- LLM Practice Hours Methodology paper
- Usage snapshot (December 2025)
- Privacy-first design: no content in output by default
