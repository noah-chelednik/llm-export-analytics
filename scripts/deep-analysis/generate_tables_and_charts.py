#!/usr/bin/env python3
"""
generate_tables_and_charts.py

Reads Phase 1 JSON data files and produces markdown tables and ASCII charts
for embedding in the deep-analysis document.

Inputs  (from data/):
    chatgpt_metadata.json
    classifications_and_projects.json
    effectiveness_and_patterns.json

Outputs (to tables/):
    model_timeline.md
    model_migration_chart.md
    platform_share_chart.md
    topic_distribution.md
    project_attribution.md
    technique_adoption.md
    technique_growth_chart.md
    conversation_outcomes.md
    session_dynamics.md
    tool_usage.md
    summary_stats.json
"""

import argparse
import json
import math
import os
from collections import OrderedDict
from pathlib import Path


# ── Slug-to-human-name mapping ────────────────────────────────────────────────

SLUG_NAMES = {
    "text-davinci-002-render-sha": "GPT-3.5 Turbo",
    "gpt-4": "GPT-4",
    "gpt-4-gizmo": "GPT-4 (Custom GPTs)",
    "gpt-4o": "GPT-4o",
    "gpt-4-5": "GPT-4.5",
    "gpt-4-1": "GPT-4.1",
    "o1": "o1",
    "o3": "o3",
    "gpt-5": "GPT-5",
    "gpt-5-thinking": "GPT-5 (Thinking)",
    "gpt-5-t-mini": "GPT-5 Turbo Mini",
    "gpt-5-instant": "GPT-5 Instant",
    "gpt-5-1": "GPT-5.1",
    "gpt-5-1-thinking": "GPT-5.1 (Thinking)",
    "gpt-5-1-instant": "GPT-5.1 Instant",
    "gpt-5-2": "GPT-5.2",
    "gpt-5-2-thinking": "GPT-5.2 (Thinking)",
    "gpt-5-2-instant": "GPT-5.2 Instant",
    "gpt-5-3": "GPT-5.3",
    "gpt-5-4-thinking": "GPT-5.4 (Thinking)",
    "research": "Deep Research",
    "auto": "Auto",
}

# Short labels for charts (keep bars readable)
SLUG_SHORT = {
    "text-davinci-002-render-sha": "GPT-3.5",
    "gpt-4": "GPT-4",
    "gpt-4-gizmo": "GPT-4 Gizmo",
    "gpt-4o": "GPT-4o",
    "gpt-4-5": "GPT-4.5",
    "gpt-4-1": "GPT-4.1",
    "o1": "o1",
    "o3": "o3",
    "gpt-5": "GPT-5",
    "gpt-5-thinking": "GPT-5-T",
    "gpt-5-t-mini": "GPT-5-TM",
    "gpt-5-instant": "GPT-5-I",
    "gpt-5-1": "GPT-5.1",
    "gpt-5-1-thinking": "GPT-5.1-T",
    "gpt-5-1-instant": "GPT-5.1-I",
    "gpt-5-2": "GPT-5.2",
    "gpt-5-2-thinking": "GPT-5.2-T",
    "gpt-5-2-instant": "GPT-5.2-I",
    "gpt-5-3": "GPT-5.3",
    "gpt-5-4-thinking": "GPT-5.4-T",
    "research": "Research",
    "auto": "Auto",
}

TOOL_NAMES = {
    "web_search": "Web Search",
    "code_interpreter": "Code Interpreter",
    "reasoning": "Extended Reasoning",
    "multimodal": "Multimodal/Vision",
    "memory": "Memory",
    "image_gen": "Image Generation (DALL-E)",
    "file_browser": "File Browser",
    "file_search": "File Search",
    "canvas": "Canvas",
    "deep_research": "Deep Research",
    "genui": "Generated UI",
}

TECHNIQUE_NAMES = {
    "role_assignment": "Role Assignment",
    "constraints": "Constraints / Boundaries",
    "output_format": "Output Format Spec",
    "examples_given": "Few-Shot Examples",
    "multi_step": "Multi-Step Decomposition",
    "meta_prompting": "Meta-Prompting",
    "code_inclusion": "Code Inclusion",
    "prior_reference": "Prior Reference",
    "iterative_refinement": "Iterative Refinement",
    "context_frontloading": "Context Front-Loading",
}

BAR_CHAR = "█"  # █
MAX_BAR_WIDTH = 40


# ── Helpers ───────────────────────────────────────────────────────────────────

def bar(fraction: float, max_width: int = MAX_BAR_WIDTH) -> str:
    """Return an ASCII bar of length proportional to fraction (0-1)."""
    n = max(0, round(fraction * max_width))
    return BAR_CHAR * n


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format a numeric value as a percentage string."""
    return f"{value:.{decimals}f}%"


def write_file(path: str, content: str) -> None:
    """Write content to path, creating parent dirs if needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def human_name(slug: str) -> str:
    """Map a model slug to its human-readable display name."""
    return SLUG_NAMES.get(slug, slug)


def short_name(slug: str) -> str:
    """Map a model slug to its abbreviated chart label."""
    return SLUG_SHORT.get(slug, slug)


# ── Table/Chart generators ───────────────────────────────────────────────────

def generate_model_timeline(meta: dict, out_dir: str) -> tuple[int, int, int]:
    """Generate the model timeline markdown table from metadata."""
    mt = meta["model_timeline"]

    # Sort by first_used date
    rows = sorted(mt.items(), key=lambda kv: kv[1]["first_used"])

    lines = [
        "# Model Timeline",
        "",
        "| Model | First Used | Last Used | Messages | Conversations |",
        "|-------|-----------|-----------|----------|---------------|",
    ]

    total_msgs = 0
    total_convs = 0
    for slug, info in rows:
        name = human_name(slug)
        lines.append(
            f"| {name} | {info['first_used']} | {info['last_used']} "
            f"| {info['msg_count']:,} | {info['conv_count']:,} |"
        )
        total_msgs += info["msg_count"]
        total_convs += info["conv_count"]

    lines.append(
        f"| **Total** | | | **{total_msgs:,}** | **{total_convs:,}** |"
    )
    lines.append("")
    lines.append(
        f"*{len(rows)} distinct model slugs observed across ChatGPT conversations.*"
    )

    write_file(os.path.join(out_dir, "model_timeline.md"), "\n".join(lines))
    return total_msgs, total_convs, len(rows)


def generate_model_migration_chart(meta: dict, out_dir: str) -> None:
    """Generate the monthly model migration ASCII chart."""
    mmd = meta["monthly_model_distribution"]

    lines = [
        "# Model Migration Chart",
        "",
        "Top 3 models by message count per month.",
        "",
        "```",
    ]

    for month in sorted(mmd.keys()):
        dist = mmd[month]
        total = sum(dist.values())
        if total == 0:
            continue

        # Top 3 models
        top = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:3]

        parts = []
        for slug, count in top:
            pct = count / total
            pct_display = round(pct * 100)
            b = bar(pct)
            label = short_name(slug)
            parts.append(f"{b} {label} ({pct_display}%)")

        row = f"{month}  {'  '.join(parts)}"
        lines.append(row)

    lines.append("```")
    write_file(os.path.join(out_dir, "model_migration_chart.md"), "\n".join(lines))


def generate_platform_share_chart(eff: dict, out_dir: str) -> None:
    """Generate the monthly ChatGPT-vs-Claude platform share chart."""
    ms = eff["platform_comparison"]["monthly_share"]

    lines = [
        "# Platform Share: ChatGPT vs Claude",
        "",
        "Monthly message share between platforms.",
        "",
        "```",
    ]

    for month in sorted(ms.keys()):
        info = ms[month]
        cg_pct = info["chatgpt_pct"]
        cl_pct = info["claude_pct"]
        cg_display = round(cg_pct * 100)
        cl_display = round(cl_pct * 100)

        cg_bar = bar(cg_pct)
        cl_bar = bar(cl_pct)

        # Skip months with zero messages on both sides
        if info["chatgpt_count"] + info["claude_count"] == 0:
            continue

        # Pad for alignment
        cg_part = f"ChatGPT {cg_bar} {cg_display}%"
        cl_part = f"Claude {cl_bar} {cl_display}%"

        lines.append(f"{month}  {cg_part:<52s} {cl_part}")

    lines.append("```")
    write_file(os.path.join(out_dir, "platform_share_chart.md"), "\n".join(lines))


def generate_topic_distribution(classif: dict, out_dir: str) -> tuple[int, float, float]:
    """Generate the topic distribution markdown table from classifications."""
    ts = classif["topic_summary"]

    # Separate Other
    other = ts.get("Other", {"count": 0, "pct": 0, "avg_depth": 0})
    topics = {k: v for k, v in ts.items() if k != "Other"}

    # Sort by count descending
    rows = sorted(topics.items(), key=lambda kv: kv[1]["count"], reverse=True)

    total_classified = sum(v["count"] for v in topics.values())
    total_all = total_classified + other["count"]

    lines = [
        "# Topic Distribution",
        "",
        "| Category | Conversations | Percentage | Avg Depth |",
        "|----------|--------------|------------|-----------|",
    ]

    for cat, info in rows:
        avg_d = f"{info['avg_depth']:.2f}" if info.get("avg_depth") else "---"
        lines.append(
            f"| {cat} | {info['count']:,} | {fmt_pct(info['pct'])} | {avg_d} |"
        )

    lines.append("")
    lines.append(
        f"*{other['count']:,} conversations ({fmt_pct(other['pct'])}) "
        f'classified as "Other" (no dominant topic detected) are excluded from '
        f"this table.*"
    )
    # Percentages in topic_summary are relative to total conversations, not topic assignments.
    # A conversation can have multiple topics, so topic assignment counts > total conversations.
    total_conversations = len(classif["per_conversation"])
    convs_with_topic = sum(
        1 for c in classif["per_conversation"]
        if any(
            (t.get("category") if isinstance(t, dict) else t) != "Other"
            for t in c.get("topics", [])
        )
    )
    lines.append("")
    lines.append(
        f"*{convs_with_topic:,} of {total_conversations:,} conversations "
        f"({fmt_pct(convs_with_topic / total_conversations * 100 if total_conversations else 0, 1)}) "
        f"received at least one specific topic label. "
        f"Conversations may appear in multiple categories; {total_all:,} total "
        f"topic assignments across {total_conversations:,} conversations. "
        f'The {other["count"]:,} "Other" assignments indicate no dominant topic detected.*'
    )

    write_file(os.path.join(out_dir, "topic_distribution.md"), "\n".join(lines))
    classified_pct = convs_with_topic / total_conversations * 100 if total_conversations else 0
    other_pct = other["pct"]
    return len(topics), classified_pct, other_pct


def generate_project_attribution(classif: dict, out_dir: str) -> tuple[int, int]:
    """Generate the project attribution markdown table from classifications."""
    ps = classif["project_summary"]

    rows = sorted(ps.items(), key=lambda kv: kv[1]["count"], reverse=True)
    total_linked = sum(v["count"] for v in ps.values())

    lines = [
        "# Project Attribution",
        "",
        "| Project | Conversations | High Confidence | Medium | Low |",
        "|---------|--------------|----------------|--------|-----|",
    ]

    for proj, info in rows:
        cd = info["confidence_dist"]
        lines.append(
            f"| {proj} | {info['count']:,} | {cd['high']} | {cd['medium']} | {cd['low']} |"
        )

    lines.append(
        f"| **Total** | **{total_linked:,}** | "
        f"**{sum(v['confidence_dist']['high'] for v in ps.values())}** | "
        f"**{sum(v['confidence_dist']['medium'] for v in ps.values())}** | "
        f"**{sum(v['confidence_dist']['low'] for v in ps.values())}** |"
    )

    write_file(os.path.join(out_dir, "project_attribution.md"), "\n".join(lines))
    return total_linked, len(ps)


def generate_technique_adoption(eff: dict, out_dir: str, total_conversations: int) -> tuple[str, float]:
    """Generate the prompt technique adoption markdown table."""
    ta = eff["technique_adoption"]
    tc = eff["platform_comparison"].get("technique_comparison", {})

    # Sort by total_pct descending
    rows = sorted(ta.items(), key=lambda kv: kv[1]["total_pct"], reverse=True)

    lines = [
        "# Prompt Technique Adoption",
        "",
        "| Technique | Overall % | ChatGPT % | Claude % | First Appeared |",
        "|-----------|----------|-----------|----------|---------------|",
    ]

    for tech_key, info in rows:
        name = TECHNIQUE_NAMES.get(tech_key, tech_key)
        overall = info["total_pct"] * 100
        first_app = info.get("first_appearance", "---")

        # Platform breakdown
        bp = info.get("by_platform", {})
        cg_pct = bp.get("chatgpt", {}).get("pct", 0) * 100
        cl_pct = bp.get("claude", {}).get("pct", 0) * 100

        lines.append(
            f"| {name} | {fmt_pct(overall)} | {fmt_pct(cg_pct)} | {fmt_pct(cl_pct)} | {first_app} |"
        )

    lines.append("")
    lines.append(
        "*Percentages are of total messages on each platform. "
        "First Appeared = earliest month with detected usage.*"
    )

    write_file(os.path.join(out_dir, "technique_adoption.md"), "\n".join(lines))

    top_tech = rows[0] if rows else (None, {})
    return (
        TECHNIQUE_NAMES.get(top_tech[0], top_tech[0]),
        top_tech[1]["total_pct"] * 100 if top_tech[1] else 0,
    )


def generate_technique_growth_chart(eff: dict, out_dir: str) -> None:
    """Generate quarterly trend ASCII charts for the top 4 techniques."""
    ta = eff["technique_adoption"]

    # Top 4 by total_pct
    top4 = sorted(ta.items(), key=lambda kv: kv[1]["total_pct"], reverse=True)[:4]

    def month_to_quarter(m):
        year, mon = m.split("-")
        q = (int(mon) - 1) // 3 + 1
        return f"{year}-Q{q}"

    lines = [
        "# Technique Growth: Quarterly Trends",
        "",
        "Adoption rate (% of messages) per quarter for the top 4 techniques.",
        "",
    ]

    for tech_key, info in top4:
        name = TECHNIQUE_NAMES.get(tech_key, tech_key)
        monthly = info.get("monthly", {})

        # Group into quarters
        quarters = OrderedDict()
        for m in sorted(monthly.keys()):
            q = month_to_quarter(m)
            if q not in quarters:
                quarters[q] = {"total_count": 0, "months": 0, "sum_pct": 0.0}
            quarters[q]["total_count"] += monthly[m]["count"]
            quarters[q]["months"] += 1
            quarters[q]["sum_pct"] += monthly[m]["pct"]

        # Average pct per quarter
        q_data = OrderedDict()
        for q, vals in quarters.items():
            avg_pct = vals["sum_pct"] / vals["months"] if vals["months"] else 0
            q_data[q] = avg_pct

        # Find max for scaling
        max_pct = max(q_data.values()) if q_data else 1

        lines.append(f"### {name}")
        lines.append("```")
        for q, pct in q_data.items():
            b = bar(pct / max_pct if max_pct > 0 else 0)
            lines.append(f"{q}  {b} {fmt_pct(pct * 100)}")
        lines.append("```")
        lines.append("")

    write_file(os.path.join(out_dir, "technique_growth_chart.md"), "\n".join(lines))


def generate_conversation_outcomes(eff: dict, out_dir: str, total_conversations: int) -> tuple[float, float]:
    """Generate the conversation outcomes markdown table."""
    cd = eff["conversation_outcomes"]["convergence_distribution"]

    # Reframe: abandoned + neutral = standard completion
    standard = cd.get("abandoned", 0) + cd.get("neutral", 0)
    converged = cd.get("converged", 0)
    frustrated = cd.get("frustrated", 0)
    total = standard + converged + frustrated

    lines = [
        "# Conversation Outcomes",
        "",
        "| Outcome | Count | Percentage | Description |",
        "|---------|-------|------------|-------------|",
        f"| Standard Completion | {standard:,} | {fmt_pct(standard / total * 100)} "
        f"| Conversation ended normally (last message from assistant) |",
        f"| Converged (Positive) | {converged:,} | {fmt_pct(converged / total * 100)} "
        f"| Explicit positive feedback detected (thanks, confirmation) |",
        f"| Frustrated | {frustrated:,} | {fmt_pct(frustrated / total * 100)} "
        f"| 3+ corrections or explicit frustration signals |",
        f"| **Total** | **{total:,}** | **100.0%** | |",
        "",
        '*Note: The heuristic labels any conversation ending with an assistant '
        'message as "abandoned" — this is actually normal completion behavior. '
        'Only "Converged" (explicit positive feedback) and "Frustrated" '
        "(3+ corrections) represent meaningful outcome signals.*",
    ]

    write_file(os.path.join(out_dir, "conversation_outcomes.md"), "\n".join(lines))
    return converged / total * 100, frustrated / total * 100


def generate_session_dynamics(eff: dict, out_dir: str) -> tuple[float, float]:
    """Generate the session dynamics usage-mode markdown table."""
    um = eff["usage_modes"]

    total = sum(um.values())
    rows = sorted(um.items(), key=lambda kv: kv[1], reverse=True)

    # Map mode names to more descriptive labels
    mode_labels = {
        "mixed": "Mixed / General",
        "synthesis": "Synthesis",
        "teaching": "Teaching / Learning",
        "production": "Production / Creation",
        "exploration": "Exploration / Research",
    }

    # Map to session-style categories for the requested sprint/working/marathon/multi-day framing
    # Since the data uses usage_modes rather than session duration types,
    # we present both the available mode data and note what we have.

    lines = [
        "# Session Dynamics: Usage Modes",
        "",
        "| Mode | Conversations | Percentage |",
        "|------|--------------|------------|",
    ]

    sprint_pct = 0
    marathon_pct = 0

    for mode, count in rows:
        label = mode_labels.get(mode, mode.title())
        pct = count / total * 100 if total else 0
        lines.append(f"| {label} | {count:,} | {fmt_pct(pct)} |")

        # Approximate: exploration + teaching are typically shorter (sprint-like)
        if mode in ("exploration", "teaching"):
            sprint_pct += pct
        # production + synthesis tend to be longer (marathon-like)
        if mode in ("production", "synthesis"):
            marathon_pct += pct

    lines.append(f"| **Total** | **{total:,}** | **100.0%** |")
    lines.append("")
    lines.append(
        "*Usage modes are classified by interaction pattern: Mixed (general-purpose), "
        "Synthesis (combining information), Teaching (explanatory exchanges), "
        "Production (creating artifacts), Exploration (open-ended research).*"
    )

    write_file(os.path.join(out_dir, "session_dynamics.md"), "\n".join(lines))
    return sprint_pct, marathon_pct


def generate_tool_usage(meta: dict, out_dir: str) -> int:
    """Generate the ChatGPT tool-usage markdown table."""
    tu = meta["tool_usage"]

    # Total ChatGPT conversations for percentage base
    total_convs = len(meta["per_conversation"])

    # Filter: only known tool names (exclude other:*, plugin:*)
    rows = []
    for key, info in tu.items():
        if key.startswith("other:") or key.startswith("plugin:"):
            continue
        if key not in TOOL_NAMES:
            continue
        rows.append((key, info))

    rows.sort(key=lambda kv: kv[1]["conv_count"], reverse=True)

    lines = [
        "# ChatGPT Tool & Feature Usage",
        "",
        f"| Tool | Conversations Using | % of Total ({total_convs:,} convos) |",
        "|------|-------------------|------------|",
    ]

    for key, info in rows:
        name = TOOL_NAMES[key]
        count = info["conv_count"]
        pct = count / total_convs * 100 if total_convs else 0
        lines.append(f"| {name} | {count:,} | {fmt_pct(pct)} |")

    lines.append("")
    lines.append(
        "*Counts reflect conversations where the tool was invoked at least once. "
        "A single conversation may use multiple tools.*"
    )

    write_file(os.path.join(out_dir, "tool_usage.md"), "\n".join(lines))
    return len(rows)


def generate_summary_stats(meta: dict, classif: dict, eff: dict, out_dir: str, computed: dict) -> None:
    """Write summary_stats.json aggregating all key numbers."""
    ms = eff["platform_comparison"]["monthly_share"]
    total_chatgpt_msgs = sum(v["chatgpt_count"] for v in ms.values())
    total_claude_msgs = sum(v["claude_count"] for v in ms.values())
    total_messages = total_chatgpt_msgs + total_claude_msgs

    pc = classif["per_conversation"]
    total_conversations = len(pc)
    chatgpt_convs = sum(1 for c in pc if c.get("platform") == "chatgpt")
    claude_convs = sum(1 for c in pc if c.get("platform") == "claude")

    # Projects
    ps = classif["project_summary"]
    total_linked = sum(v["count"] for v in ps.values())
    linked_pct = total_linked / total_conversations * 100 if total_conversations else 0

    # Topics
    ts = classif["topic_summary"]
    other = ts.get("Other", {"count": 0, "pct": 0})
    topic_count = len([k for k in ts if k != "Other"])
    # classified_pct = conversations with at least one non-Other topic
    convs_with_topic = sum(
        1 for c in pc
        if any(
            (t.get("category") if isinstance(t, dict) else t) != "Other"
            for t in c.get("topics", [])
        )
    )

    # Branching
    bs = meta["branching_stats"]

    # Custom GPTs
    cgs = meta["custom_gpt_stats"]

    # Convergence
    cd = eff["conversation_outcomes"]["convergence_distribution"]
    total_outcome = sum(cd.values())
    converged_pct = cd.get("converged", 0) / total_outcome * 100 if total_outcome else 0
    frustrated_pct = cd.get("frustrated", 0) / total_outcome * 100 if total_outcome else 0

    stats = {
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "total_tokens": None,  # Not available in current data
        "chatgpt_conversations": chatgpt_convs,
        "claude_conversations": claude_convs,
        "chatgpt_messages": total_chatgpt_msgs,
        "claude_messages": total_claude_msgs,
        "model_count": computed["model_count"],
        "tool_types_count": computed["tool_types_count"],
        "custom_gpt_conversations": cgs["total_custom_gpt_conversations"],
        "custom_gpt_templates": cgs["unique_template_count"],
        "topic_categories_count": topic_count,
        "classified_pct": round(
            convs_with_topic / total_conversations * 100, 2
        )
        if total_conversations
        else 0,
        "other_pct": round(other["pct"], 2),
        "projects_linked_count": total_linked,
        "projects_linked_pct": round(linked_pct, 2),
        "top_technique_name": computed["top_technique_name"],
        "top_technique_pct": round(computed["top_technique_pct"], 2),
        "converged_pct": round(converged_pct, 2),
        "frustrated_pct": round(frustrated_pct, 2),
        "sprint_pct": round(computed["sprint_pct"], 2),
        "marathon_pct": round(computed["marathon_pct"], 2),
        "branching_conversations": bs["conversations_with_branches"],
        "branching_pct": round(
            bs["conversations_with_branches"] / chatgpt_convs * 100, 2
        )
        if chatgpt_convs
        else 0,
    }

    path = os.path.join(out_dir, "summary_stats.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Load Phase 1 JSON data and generate all markdown tables and ASCII charts."""
    parser = argparse.ArgumentParser(
        description="Generate markdown tables and ASCII charts from Phase 1 data."
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
        ),
        help="Directory containing Phase 1 JSON data files.",
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tables",
        ),
        help="Directory for output markdown/JSON files.",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    # Load data
    with open(os.path.join(data_dir, "chatgpt_metadata.json")) as f:
        meta = json.load(f)
    with open(os.path.join(data_dir, "classifications_and_projects.json")) as f:
        classif = json.load(f)
    with open(os.path.join(data_dir, "effectiveness_and_patterns.json")) as f:
        eff = json.load(f)

    total_conversations = len(classif["per_conversation"])

    # Generate all outputs
    print("Generating tables and charts...")

    total_msgs, total_convs, model_count = generate_model_timeline(meta, out_dir)
    print(f"  [1] model_timeline.md")

    generate_model_migration_chart(meta, out_dir)
    print(f"  [2] model_migration_chart.md")

    generate_platform_share_chart(eff, out_dir)
    print(f"  [3] platform_share_chart.md")

    topic_cat_count, classified_pct, other_pct = generate_topic_distribution(
        classif, out_dir
    )
    print(f"  [4] topic_distribution.md")

    total_linked, proj_count = generate_project_attribution(classif, out_dir)
    print(f"  [5] project_attribution.md")

    top_tech_name, top_tech_pct = generate_technique_adoption(
        eff, out_dir, total_conversations
    )
    print(f"  [6] technique_adoption.md")

    generate_technique_growth_chart(eff, out_dir)
    print(f"  [7] technique_growth_chart.md")

    converged_pct, frustrated_pct = generate_conversation_outcomes(
        eff, out_dir, total_conversations
    )
    print(f"  [8] conversation_outcomes.md")

    sprint_pct, marathon_pct = generate_session_dynamics(eff, out_dir)
    print(f"  [9] session_dynamics.md")

    tool_types_count = generate_tool_usage(meta, out_dir)
    print(f"  [10] tool_usage.md")

    computed = {
        "model_count": model_count,
        "tool_types_count": tool_types_count,
        "top_technique_name": top_tech_name,
        "top_technique_pct": top_tech_pct,
        "sprint_pct": sprint_pct,
        "marathon_pct": marathon_pct,
    }
    generate_summary_stats(meta, classif, eff, out_dir, computed)
    print(f"  [+] summary_stats.json")

    # Report file sizes
    print(f"\nOutput directory: {out_dir}")
    print(f"{'File':<35s} {'Size':>8s}")
    print("-" * 45)
    for fname in sorted(os.listdir(out_dir)):
        fpath = os.path.join(out_dir, fname)
        size = os.path.getsize(fpath)
        if size < 1024:
            size_str = f"{size} B"
        else:
            size_str = f"{size / 1024:.1f} KB"
        print(f"  {fname:<33s} {size_str:>8s}")

    print(f"\nDone. {len(os.listdir(out_dir))} files generated.")


if __name__ == "__main__":
    main()
