# LLM Export Analytics

Tools for analyzing personal large language model (LLM) usage using official export data from ChatGPT and Claude.

This repository focuses on **aggregate behavior and long-horizon patterns**, not prompt content or model output inspection. All analysis is performed locally using platform-provided exports.

---

## Why this exists

Most discussions about LLM usage are anecdotal or impressionistic.  
This project treats LLM interaction as something that can be **measured, audited, and reproduced**.

The goals are to:
- Normalize different LLM export formats into a common schema
- Quantify conversation depth, activity patterns, and scale over time
- Preserve privacy by default
- Produce artifacts that hold up under long-term scrutiny

No raw prompts, responses, or private conversation data are committed to this repository.

---

## What’s in this repository
├── scripts/
│ ├── analyze_chatgpt.py # ChatGPT export analysis (primary conversation path)
│ ├── analyze_claude.py # Claude export analysis (text blocks only)
│ └── analyze_combined.py # Aggregate analysis across platforms
│
├── results/
│ └── usage_snapshot_2025-12-09.md
│
├── outputs/
│ └── .gitkeep
│
├── requirements.txt
├── .gitignore
└── README.md


### scripts/
Contains the analysis tools. Each script is designed to be run independently and produces normalized CSV outputs plus printed summary statistics.

### results/
Contains point-in-time, aggregate-only snapshots generated using the scripts in this repository.

### outputs/
Local output directory for generated CSVs. Contents are intentionally ignored by Git to avoid accidental data leakage.

---

## Design principles

- **Privacy first**  
  Message text is excluded by default and only written when explicitly requested for local analysis.

- **Reproducibility**  
  UTC is used for time bucketing to ensure consistent results across systems.

- **Explicit assumptions**  
  Platform-specific quirks (such as ChatGPT conversation trees or Claude content blocks) are handled intentionally and documented in code.

- **Separation of concerns**  
  Scripts generate normalized data; interpretation lives outside the tooling.

---

## How the analysis works (high level)

- **ChatGPT**
  - Uses the primary linear conversation path reconstructed from parent pointers
  - Ignores alternate branches and system messages
- **Claude**
  - Extracts text blocks only
  - Normalizes roles to match the ChatGPT schema
- **Combined**
  - Merges normalized outputs
  - Computes aggregate depth, activity, and scale metrics

Token counts are approximate and encoding-dependent.

---

## Results

A complete snapshot of aggregate usage metrics as of **2025-12-09** is available here:

- `results/usage_snapshot_2025-12-09.md`

This includes:
- Conversation counts and depth distributions
- Message, word, and token totals
- Temporal activity landmarks
- Cross-platform aggregates

Future snapshots can be added without modifying prior results.

---

## Scope and limitations

- Results depend on platform export formats and filtering choices
- ChatGPT analysis does not traverse full conversation trees
- Claude analysis includes text blocks only
- This repository is not intended for content analysis or behavioral inference

---

## License and data handling

This project contains **no platform data** and distributes **no generated content**.  
It is intended for inspection, reuse, and adaptation under standard open-source norms.

---

## Author note

This repository reflects a long-term interest in **human–AI collaboration as a measurable practice**, rather than a short-term experiment or growth artifact.
