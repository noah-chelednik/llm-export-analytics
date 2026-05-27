# Deep Analysis Guide

A step by step guide to running the full deep analysis pipeline on your own ChatGPT and Claude conversation exports. By the end, you will have detailed data on which AI models you have used, what topics you discuss, how effective your prompts are, how much value you get per dollar, and how your usage compares to industry benchmarks.

Everything runs locally on your machine. Nothing is sent anywhere.

## 1. Prerequisites

**Python 3.10 or later** with pip installed.

**Install dependencies:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This installs `pandas` and `tiktoken`. Some deep analysis scripts also use `numpy`, which comes as a dependency of pandas.

**Your export data.** You need conversation exports from one or both platforms:

- **ChatGPT:** Go to Settings > Data Controls > Export Data. OpenAI will email you a download link. The export is a zip file containing one or more `conversations-NNN.json` shard files plus other data. Unzip it to a directory.
- **Claude:** Go to Settings > Account > Export Data. Anthropic will email you a download link. The export contains a `conversations.json` file (and optionally a `projects.json` file if you use Claude Projects). Unzip it to a directory.

**Run the basic scripts first.** The deep analysis scripts expect normalized CSV files as input. You need to run the basic normalization scripts with the `--include-content` flag before proceeding. This flag includes your full conversation text in the output CSVs, which the deep analysis scripts need for topic classification, prompt technique detection, and effectiveness analysis.

## 2. Step by Step Pipeline

### Step 1: Run basic normalization

If you have not already run the basic scripts, do that now. The `--include-content` flag is important because several downstream scripts need the actual message text.

```bash
# Claude
python scripts/analyze_claude.py \
  --input /path/to/claude/conversations.json \
  --out outputs --utc --include-content

# ChatGPT
python scripts/analyze_chatgpt.py \
  --input /path/to/chatgpt/conversations.json \
  --out outputs --utc --include-content
```

This produces two key files in `outputs/`:

- `chatgpt_messages_normalized.csv`
- `claude_messages_normalized.csv`

If you only use one platform, that is fine. Just skip the flags for the platform you do not use in the later steps.

### Step 2: ChatGPT metadata extraction

**What it does:** Reads the raw ChatGPT export shard files and extracts metadata that the basic normalization script does not capture. This includes which model version was used for each message (GPT-4, GPT-4o, o1, etc.), which tools were invoked (web search, code interpreter, DALL-E, etc.), how many conversations had branching or regeneration, and whether reasoning/thinking mode was active.

**Command:**

```bash
python scripts/deep_analysis/extract_chatgpt_metadata.py \
  --input-dir /path/to/chatgpt/export/ \
  --output outputs/chatgpt_metadata.json
```

The `--input-dir` should point to the directory containing your `conversations-*.json` shard files. If your export has a different naming pattern, you can use `--shard-pattern` to adjust (the default is `conversations-*.json`).

**What you get:** A JSON file containing:

- A complete model timeline showing when you first and last used each model version
- Monthly model distribution showing how your model usage shifted over time
- Tool and feature adoption data (web search, code interpreter, image generation, canvas, memory, and more)
- Branching and regeneration statistics
- Reasoning/thinking mode usage

If you only use Claude, skip this step. The later scripts will work without it.

### Step 3: Topic classification

**What it does:** Classifies every conversation from both platforms into topic categories (Software Engineering, AI/ML, Writing/Creative, Academic, and 13 other domains). It first tries to classify based on the conversation title using keyword matching. If the title is empty or has no keyword hits, it falls back to the first user message content. It also attributes conversations to specific projects if you provide a project configuration.

**Command:**

```bash
python scripts/deep_analysis/classify_and_link.py \
  --chatgpt-shard-dir /path/to/chatgpt/export/ \
  --claude-conv-path /path/to/claude/conversations.json \
  --chatgpt-csv outputs/chatgpt_messages_normalized.csv \
  --claude-csv outputs/claude_messages_normalized.csv \
  --output outputs/classifications_and_projects.json
```

If you also have a Claude projects.json from your export, add:

```bash
  --claude-projects-path /path/to/claude/projects.json
```

**What you get:** Per-conversation topic classifications, a topic distribution summary, project attribution with confidence levels (high, medium, low), and a validation report showing classification agreement rates.

**Optional: project attribution.** The script has a built-in set of project keywords that were designed for the original case study. If you want project attribution for your own projects, you have two options:

1. **Edit the script directly.** Open `scripts/deep_analysis/classify_and_link.py` and modify the `PROJECT_KEYWORDS` dictionary near the top of the file. Each project entry looks like this:

```python
"My Project Name": {
    "keywords": ["keyword1", "keyword2", "relevant phrase"],
    "platform": "both",  # or "chatgpt" or "claude"
},
```

2. **Skip project attribution.** If you do not define your own projects, the topic classification still works. You just will not get the project-level breakdown.

### Step 4: Prompt effectiveness analysis

**What it does:** Analyzes your prompting patterns across both platforms. It detects 10 prompt techniques (role assignment, constraints, output format specifications, few-shot examples, multi-step decomposition, meta-prompting, code inclusion, prior reference, iterative refinement, and context front-loading). It classifies conversation outcomes as converged (positive feedback detected), frustrated (3+ corrections or explicit frustration), or standard completion. It also categorizes your interaction style (directive, interrogative, collaborative, feedback, informational) and usage modes (teaching, production, synthesis, debugging, exploration, mixed).

**Command:**

```bash
python scripts/deep_analysis/analyze_effectiveness.py \
  --chatgpt-csv outputs/chatgpt_messages_normalized.csv \
  --claude-csv outputs/claude_messages_normalized.csv \
  --output outputs/effectiveness_and_patterns.json
```

**What you learn:**

- Which prompt techniques you use most and how adoption has changed over time
- Your convergence rate (how often conversations end with positive signals vs frustration)
- Your correction density (how many times per conversation you ask the model to try again)
- Your efficiency ratio (how many words the model produces per word you type)
- How your interaction style differs between ChatGPT and Claude
- Whether your sessions tend to be sprints (under 30 minutes), working sessions, marathons, or multi-day conversations

### Step 5: Tables and charts

**What it does:** Reads the JSON outputs from Steps 2, 3, and 4 and generates formatted markdown tables and ASCII charts. These are useful for embedding in reports or just getting a quick visual overview.

**Command:**

```bash
python scripts/deep_analysis/generate_tables_and_charts.py \
  --data-dir outputs \
  --out-dir outputs/tables
```

The `--data-dir` should be the directory containing `chatgpt_metadata.json`, `classifications_and_projects.json`, and `effectiveness_and_patterns.json` from the previous steps.

**What you get:** 10 markdown files and a summary JSON:

- `model_timeline.md` and `model_migration_chart.md` showing your model usage history
- `platform_share_chart.md` showing ChatGPT vs Claude usage over time
- `topic_distribution.md` and `project_attribution.md` for your conversation domains
- `technique_adoption.md` and `technique_growth_chart.md` for prompting patterns
- `conversation_outcomes.md` and `session_dynamics.md` for interaction analysis
- `tool_usage.md` for ChatGPT tool/feature adoption
- `summary_stats.json` with all key numbers in one place

### Step 6 (optional): Cost efficiency (POD / DLOD / POE)

These scripts measure how much productive output you get per dollar of subscription cost. You need a cost log documenting your subscription history.

#### 6a. Create your cost log

Copy the template and fill in your actual subscription periods:

```bash
cp templates/cost_log_template.json my_cost_log.json
```

Edit `my_cost_log.json` to reflect your subscriptions. Each entry specifies a platform, plan name, monthly cost, and the start/end months:

```json
[
  {
    "platform": "chatgpt",
    "plan": "Plus",
    "monthly_cost": 20,
    "start": "2023-08",
    "end": "2026-04"
  },
  {
    "platform": "claude",
    "plan": "Pro",
    "monthly_cost": 20,
    "start": "2024-10",
    "end": "2026-04"
  }
]
```

If you upgraded plans partway through (e.g., from ChatGPT Plus at $20/month to Pro at $200/month), create separate entries for each period.

#### 6b. Compute POD (Productive Output per Dollar)

POD measures raw output volume per dollar: total assistant words divided by total cost.

```bash
python scripts/deep_analysis/compute_pod.py \
  --chatgpt-csv outputs/chatgpt_messages_normalized.csv \
  --claude-csv outputs/claude_messages_normalized.csv \
  --cost-log my_cost_log.json \
  --classifications outputs/classifications_and_projects.json \
  --output outputs/pod_results.json
```

**What you get:** Overall POD, per-platform POD, monthly POD trajectory, per-domain POD (using topic classifications from Step 3), leverage ratios (how many words the model produces per word you type), and a modality split estimating conversational vs agentic usage.

#### 6c. Compute DLOD (Deliverable-Linked Output per Dollar)

DLOD is a more conservative metric that only counts output from conversations linked to verified deliverables. This requires both a deliverable inventory and project attribution from Step 3.

Create a deliverable inventory from the template:

```bash
cp templates/deliverable_inventory_template.json my_deliverables.json
```

Edit it to list your actual deliverables with verification artifacts:

```json
[
  {
    "name": "My Web App",
    "type": "code",
    "description": "Full-stack web application",
    "verification": {
      "method": "repository",
      "artifact": "https://github.com/you/my-web-app"
    },
    "conversations_attributed": 0,
    "high_confidence": 0,
    "active_period": "2024-01 to 2024-06"
  }
]
```

Then run:

```bash
python scripts/deep_analysis/compute_dlod.py \
  --chatgpt-csv outputs/chatgpt_messages_normalized.csv \
  --claude-csv outputs/claude_messages_normalized.csv \
  --classifications outputs/classifications_and_projects.json \
  --cost-log my_cost_log.json \
  --deliverables my_deliverables.json \
  --output outputs/dlod_results.json
```

Note: DLOD requires that you have set up project attribution in Step 3. You will also need to edit the `PROJECT_TO_DELIVERABLE` mapping near the top of `compute_dlod.py` to connect your project names to your deliverable names.

#### 6d. Compute POE (Productive Output Efficiency)

POE is the quality-adjusted version of POD. Instead of treating all output words equally, it applies quality weights based on conversation outcomes (frustrated conversations are discounted, converged ones get full credit), project attribution (linked conversations count more), and branching (regenerated responses are discounted).

POE is reported as a range across five configurations from optimistic to maximum skepticism. The configurations are defined in `templates/quality_params.json`.

```bash
python scripts/deep_analysis/compute_poe.py \
  --chatgpt-csv outputs/chatgpt_messages_normalized.csv \
  --claude-csv outputs/claude_messages_normalized.csv \
  --pod-results outputs/pod_results.json \
  --quality-params templates/quality_params.json \
  --classifications outputs/classifications_and_projects.json \
  --chatgpt-metadata outputs/chatgpt_metadata.json \
  --cost-log my_cost_log.json \
  --output outputs/poe_results.json
```

### Step 7 (optional): Industry benchmarks

Compare your POD and DLOD metrics against curated industry benchmark data. This requires that you have already computed POD (Step 6b) and DLOD (Step 6c).

```bash
python scripts/deep_analysis/compare_benchmarks.py \
  --pod outputs/pod_results.json \
  --dlod outputs/dlod_results.json \
  --benchmarks templates/benchmarks.json \
  --output outputs/benchmark_comparison.json
```

The benchmark data in `templates/benchmarks.json` includes enterprise AI spending data, GitHub Copilot metrics, the METR developer speed study, Faros AI tokenmaxxing data, and other published sources with full citations.

## 3. What You Will Learn About Yourself

Running this pipeline gives you a data-driven picture of how you actually use AI tools, as opposed to how you think you use them.

**Which AI models have I used and when did I switch?** The model timeline shows every model version you have used, when you first tried it, and how your usage shifted month to month. You might discover you stuck with GPT-4 longer than you realized, or that you adopted new models faster than you thought.

**What topics do I use AI for most?** The topic distribution reveals your actual usage portfolio. Many people assume they mostly use AI for coding, then discover that writing, research, or other domains make up a significant share.

**Am I getting better at prompting over time?** The technique adoption trends show whether you are using more sophisticated prompt techniques as you gain experience. The convergence rate tells you how often your conversations end successfully vs in frustration. A declining correction density over time is a concrete signal of improving skill.

**How cost-efficient is my AI usage?** POD gives you a raw output-per-dollar number. DLOD tells you how much of that output is tied to real deliverables (vs exploratory or throwaway conversations). POE adjusts for quality, giving you a defensible range.

**How does my usage compare to industry benchmarks?** The benchmark comparison puts your metrics in context against published research from METR, Faros AI, GitHub, and others. This is useful for understanding where individual practitioner usage fits relative to enterprise patterns.

## 4. Customization

### Adding your own topic categories

Open `scripts/deep_analysis/classify_and_link.py` and find the `TOPIC_TAXONOMY` dictionary near the top. Each category is a key mapping to a list of keywords. To add a new category:

```python
TOPIC_TAXONOMY = {
    # ... existing categories ...
    "Robotics": [
        "robot", "actuator", "servo", "ros", "sensor fusion",
        "kinematics", "control system", "lidar", "slam",
    ],
}
```

Keywords are matched using word boundaries, so "robot" will match "robotics" and "robot arm" but not "probiotic". Multi-word phrases work too. The classifier picks the top 1 or 2 categories by keyword hit count.

### Creating a project configuration

Edit the `PROJECT_KEYWORDS` dictionary in the same file. Each project needs a name, a list of keywords that appear in conversation titles or first messages, and a platform scope:

```python
PROJECT_KEYWORDS = {
    # ... existing projects ...
    "My Side Project": {
        "keywords": ["side project", "my-app", "flutter", "firebase"],
        "platform": "both",
    },
}
```

The classifier assigns confidence levels: "high" if the project name itself appears in the conversation title, "medium" if 2+ keywords match, and "low" if only 1 keyword matches.

### Adjusting quality parameters for POE

The quality weight configurations live in `templates/quality_params.json`. Each configuration sets weights for different quality signals:

- `frustrated_discount`: how much to discount output from frustrated conversations (0.0 = discard entirely, 1.0 = full credit)
- `standard_weight`: weight for conversations with no clear positive or negative outcome signal
- `converged_weight`: weight for conversations where the user gave positive feedback
- `deliverable_linked_bonus`: multiplier for conversations linked to a project (typically 1.0)
- `unlinked_discount`: weight for conversations with no project link
- `branched_discount`: weight for conversations with regeneration/branching

You can modify existing configurations or add new ones. The script will compute POE for every configuration defined under `configurations`, giving you a range rather than a single number.

## 5. Privacy

The `--include-content` flag causes the normalized CSVs to contain your full conversation text. This includes everything you typed and everything the AI responded with.

**Do not commit these files to version control.** The `.gitignore` in this repo already excludes the `outputs/` directory, but double check before pushing anything.

**Do not share these files.** They contain your complete conversation history in plain text.

**All analysis runs locally.** None of these scripts connect to the internet or send data anywhere. The only network activity happens during `pip install` when you set up dependencies. After that, everything is purely local file processing.
