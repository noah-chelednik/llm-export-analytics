# Changelog

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
