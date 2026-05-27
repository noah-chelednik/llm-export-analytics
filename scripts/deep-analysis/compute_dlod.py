#!/usr/bin/env python3
"""
compute_dlod.py
===============
Computes the Deliverable-Linked Output per Dollar (DLOD) metric.

DLOD counts only assistant output words from conversations that can be
traced to a named deliverable, divided by total subscription cost.  It is
a more conservative cousin of POD (Productive Output per Dollar).

Inputs (defaults):
  - analysis/latest-run/chatgpt_messages_normalized.csv
  - analysis/latest-run/claude_messages_normalized.csv
  - analysis/deep-analysis/data/classifications_and_projects.json
  - analysis/deep-analysis/data/cost_log.json
  - analysis/deep-analysis/data/deliverable_inventory.json

Output:
  - analysis/deep-analysis/data/dlod_results.json
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def build_project_to_deliverable(deliverables: list[dict]) -> dict[str, list[str]]:
    """Build a project-name -> deliverable-names mapping from the inventory.

    Each deliverable entry may contain a ``"project_names"`` list that
    enumerates the project names (as used in classify_and_link output)
    which feed into that deliverable.  If ``"project_names"`` is absent,
    the deliverable's own ``"name"`` is treated as the project name.

    Returns {project_name: [deliverable_name, ...]}.
    """
    mapping: dict[str, list[str]] = defaultdict(list)
    for d in deliverables:
        d_name = d["name"]
        proj_names = d.get("project_names", [d_name])
        for pname in proj_names:
            mapping[pname].append(d_name)
    return dict(mapping)


def build_deliverable_to_projects(project_to_deliverable: dict[str, list[str]]) -> dict[str, set[str]]:
    """Reverse lookup: deliverable name -> set of project names."""
    reverse: dict[str, set[str]] = defaultdict(set)
    for proj, dels in project_to_deliverable.items():
        for d in dels:
            reverse[d].add(proj)
    return dict(reverse)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jsonify(obj: object) -> object:
    """Recursively convert numpy types to JSON-serialisable Python types."""
    if isinstance(obj, dict):
        return {str(k): jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(float(obj), 4)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(obj, 4)
    if isinstance(obj, np.ndarray):
        return jsonify(obj.tolist())
    return obj


def months_between(start: str, end: str) -> int:
    """Count calendar months between two YYYY-MM strings, inclusive."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    return (ey - sy) * 12 + (em - sm) + 1


def compute_total_cost(cost_log: list[dict]) -> float:
    """Sum total subscription cost across all cost-log entries."""
    total = 0.0
    for entry in cost_log:
        n_months = months_between(entry["start"], entry["end"])
        total += n_months * entry["monthly_cost"]
    return total


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def main() -> None:
    """Compute DLOD metrics from message CSVs, classifications, and deliverable inventory."""
    parser = argparse.ArgumentParser(
        description="Compute Deliverable-Linked Output per Dollar (DLOD)."
    )
    parser.add_argument(
        "--chatgpt-csv",
        default="/mnt/ai_workspace/Remembrancer/analysis/latest-run/chatgpt_messages_normalized.csv",
        help="Path to ChatGPT normalized messages CSV",
    )
    parser.add_argument(
        "--claude-csv",
        default="/mnt/ai_workspace/Remembrancer/analysis/latest-run/claude_messages_normalized.csv",
        help="Path to Claude normalized messages CSV",
    )
    parser.add_argument(
        "--classifications",
        default="/mnt/ai_workspace/Remembrancer/analysis/deep-analysis/data/classifications_and_projects.json",
        help="Path to classifications_and_projects.json",
    )
    parser.add_argument(
        "--cost-log",
        default="/mnt/ai_workspace/Remembrancer/analysis/deep-analysis/data/cost_log.json",
        help="Path to cost_log.json",
    )
    parser.add_argument(
        "--deliverables",
        default=None,
        help="Path to deliverable_inventory.json. If not provided, DLOD "
             "computation is skipped. Create one from "
             "templates/deliverable_inventory_template.json",
    )
    parser.add_argument(
        "--output",
        default="/mnt/ai_workspace/Remembrancer/analysis/deep-analysis/data/dlod_results.json",
        help="Path for output JSON",
    )
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 70)
    print("DELIVERABLE-LINKED OUTPUT PER DOLLAR (DLOD)")
    print("=" * 70)

    if args.deliverables is None:
        print("\nNo deliverable inventory provided.")
        print("Create one from templates/deliverable_inventory_template.json")
        print("and pass it via --deliverables <path>")
        sys.exit(0)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    print("\n[1] Loading data ...")

    print(f"  ChatGPT CSV: {args.chatgpt_csv}")
    df_chatgpt = pd.read_csv(args.chatgpt_csv, low_memory=False)
    print(f"    Rows: {len(df_chatgpt):,}")

    print(f"  Claude CSV:  {args.claude_csv}")
    df_claude = pd.read_csv(args.claude_csv, low_memory=False)
    print(f"    Rows: {len(df_claude):,}")

    df = pd.concat([df_chatgpt, df_claude], ignore_index=True)
    print(f"  Combined:    {len(df):,} messages")

    print(f"  Classifications: {args.classifications}")
    with open(args.classifications) as f:
        classifications = json.load(f)

    print(f"  Cost log:    {args.cost_log}")
    with open(args.cost_log) as f:
        cost_log = json.load(f)

    print(f"  Deliverables: {args.deliverables}")
    with open(args.deliverables) as f:
        deliverables = json.load(f)

    # Build project-to-deliverable mapping dynamically from inventory
    PROJECT_TO_DELIVERABLE = build_project_to_deliverable(deliverables)
    print(f"  Project-to-deliverable mappings: {len(PROJECT_TO_DELIVERABLE)}")

    # ------------------------------------------------------------------
    # 2. Compute total cost
    # ------------------------------------------------------------------
    print("\n[2] Computing total cost ...")
    total_cost = compute_total_cost(cost_log)
    print(f"  Total subscription cost: ${total_cost:,.0f}")

    # ------------------------------------------------------------------
    # 3. Build conversation-level attribution lookup
    # ------------------------------------------------------------------
    print("\n[3] Building attribution lookup ...")

    # Map conversation_id -> {project_name, confidence}
    conv_attribution: dict[str, dict] = {}
    for entry in classifications["per_conversation"]:
        if entry.get("project") and entry["project"].get("name"):
            conv_attribution[entry["conversation_id"]] = {
                "project": entry["project"]["name"],
                "confidence": entry["project"].get("confidence", "low"),
            }

    print(f"  Conversations with project attribution: {len(conv_attribution):,}")

    # Build set of verified deliverable names
    deliverable_names = {d["name"] for d in deliverables}
    print(f"  Verified deliverables: {len(deliverable_names)}")

    # Determine which project names map to a verified deliverable
    verified_projects = set()
    for proj, dels in PROJECT_TO_DELIVERABLE.items():
        if any(d in deliverable_names for d in dels):
            verified_projects.add(proj)

    # Projects in classifications that have NO deliverable mapping
    all_attributed_projects = set(v["project"] for v in conv_attribution.values())
    unmapped_projects = all_attributed_projects - set(PROJECT_TO_DELIVERABLE.keys())
    if unmapped_projects:
        print(f"  WARNING: {len(unmapped_projects)} project(s) have no deliverable mapping:")
        for p in sorted(unmapped_projects):
            count = sum(1 for v in conv_attribution.values() if v["project"] == p)
            print(f"    - {p} ({count} conversations)")

    # ------------------------------------------------------------------
    # 4. Filter messages and join with attribution
    # ------------------------------------------------------------------
    print("\n[4] Joining messages with attribution ...")

    # Only assistant messages matter for output word counting
    df_assistant = df[df["role"] == "assistant"].copy()
    total_assistant_msgs = len(df_assistant)
    total_output_words = int(df_assistant["word_count"].sum())
    total_output_tokens = int(df_assistant["token_count"].sum())
    total_conversations = df["conversation_id"].nunique()

    print(f"  Total assistant messages: {total_assistant_msgs:,}")
    print(f"  Total output words: {total_output_words:,}")
    print(f"  Total conversations: {total_conversations:,}")

    # Add attribution to assistant messages
    df_assistant["project"] = df_assistant["conversation_id"].map(
        lambda cid: conv_attribution.get(cid, {}).get("project")
    )
    df_assistant["confidence"] = df_assistant["conversation_id"].map(
        lambda cid: conv_attribution.get(cid, {}).get("confidence")
    )
    df_assistant["has_deliverable_link"] = df_assistant["project"].map(
        lambda p: p in PROJECT_TO_DELIVERABLE if p else False
    )

    df_attributed = df_assistant[df_assistant["project"].notna()].copy()
    df_deliverable_linked = df_attributed[df_attributed["has_deliverable_link"]].copy()

    print(f"  Messages with any project attribution: {len(df_attributed):,}")
    print(f"  Messages linked to a verified deliverable: {len(df_deliverable_linked):,}")

    # ------------------------------------------------------------------
    # 5. DLOD by confidence threshold
    # ------------------------------------------------------------------
    print("\n[5] Computing DLOD by confidence threshold ...")

    confidence_levels = {"high": 1, "medium": 2, "low": 3}

    def compute_threshold(df_src: pd.DataFrame, allowed_confidences: set[str]) -> dict:
        mask = df_src["confidence"].isin(allowed_confidences)
        subset = df_src[mask]
        words = int(subset["word_count"].sum())
        tokens = int(subset["token_count"].sum())
        convs = subset["conversation_id"].nunique()
        dlod_w = round(words / total_cost, 4) if total_cost > 0 else 0.0
        dlod_t = round(tokens / total_cost, 4) if total_cost > 0 else 0.0
        return {
            "dlod_words": dlod_w,
            "dlod_tokens": dlod_t,
            "output_words": words,
            "output_tokens": tokens,
            "conversations": int(convs),
        }

    dlod_high = compute_threshold(df_deliverable_linked, {"high"})
    dlod_high_medium = compute_threshold(df_deliverable_linked, {"high", "medium"})
    dlod_all = compute_threshold(df_deliverable_linked, {"high", "medium", "low"})

    dlod_by_threshold = {
        "high_only": dlod_high,
        "high_medium": dlod_high_medium,
        "all_attributed": dlod_all,
    }

    for label, vals in dlod_by_threshold.items():
        print(f"  {label:20s}: DLOD = {vals['dlod_words']:.2f} words/$  "
              f"({vals['output_words']:,} words, {vals['conversations']} convs)")

    # ------------------------------------------------------------------
    # 6. Per-project output
    # ------------------------------------------------------------------
    print("\n[6] Computing per-project output ...")

    per_project: dict[str, dict] = {}

    # Group by project name (using the classification project name)
    for project_name in sorted(all_attributed_projects):
        proj_mask = df_attributed["project"] == project_name
        proj_data = df_attributed[proj_mask]

        words = int(proj_data["word_count"].sum())
        tokens = int(proj_data["token_count"].sum())
        convs = int(proj_data["conversation_id"].nunique())

        # Confidence distribution
        conf_dist = {}
        for conf in ("high", "medium", "low"):
            conf_dist[conf] = int((proj_data["confidence"] == conf).sum())
        # Deduplicate to conversation level for confidence dist
        conf_dist_convs = {}
        for conf in ("high", "medium", "low"):
            conf_mask = (proj_data["confidence"] == conf)
            conf_dist_convs[conf] = int(proj_data.loc[conf_mask, "conversation_id"].nunique())

        # Implied cost (proportional to output word share of total)
        word_share = words / total_output_words if total_output_words > 0 else 0.0
        implied_cost = round(word_share * total_cost, 2)

        # Is this project linked to a verified deliverable?
        verified = project_name in verified_projects

        per_project[project_name] = {
            "output_words": words,
            "output_tokens": tokens,
            "conversations": convs,
            "confidence_dist": conf_dist_convs,
            "implied_cost": implied_cost,
            "verified": verified,
        }

        status = "VERIFIED" if verified else "unverified"
        print(f"  {project_name:35s}: {words:>8,} words, {convs:>3} convs, "
              f"${implied_cost:>7,.2f} implied  [{status}]")

    # ------------------------------------------------------------------
    # 7. Attribution coverage
    # ------------------------------------------------------------------
    print("\n[7] Computing attribution coverage ...")

    convs_attributed = len(set(
        entry["conversation_id"]
        for entry in classifications["per_conversation"]
        if entry.get("project") and entry["project"].get("name")
    ))

    attributed_output_words = int(df_attributed["word_count"].sum())

    coverage = {
        "conversations_attributed": convs_attributed,
        "conversations_total": total_conversations,
        "coverage_pct": round(convs_attributed / total_conversations * 100, 2)
            if total_conversations > 0 else 0.0,
        "output_words_attributed": attributed_output_words,
        "output_words_total": total_output_words,
        "output_coverage_pct": round(attributed_output_words / total_output_words * 100, 2)
            if total_output_words > 0 else 0.0,
    }

    print(f"  Conversations attributed: {coverage['conversations_attributed']:,} / "
          f"{coverage['conversations_total']:,} "
          f"({coverage['coverage_pct']:.1f}%)")
    print(f"  Output words attributed:  {coverage['output_words_attributed']:,} / "
          f"{coverage['output_words_total']:,} "
          f"({coverage['output_coverage_pct']:.1f}%)")

    # ------------------------------------------------------------------
    # 8. Comparison to POD
    # ------------------------------------------------------------------
    print("\n[8] Computing DLOD-to-POD ratio ...")

    # POD uses ALL assistant output words, regardless of attribution
    pod_words = round(total_output_words / total_cost, 4) if total_cost > 0 else 0.0
    print(f"  POD (all output): {pod_words:.2f} words/$")

    dlod_to_pod = {}
    for label in ("high_only", "high_medium", "all_attributed"):
        dlod_val = dlod_by_threshold[label]["dlod_words"]
        ratio = round(dlod_val / pod_words, 4) if pod_words > 0 else 0.0
        dlod_to_pod[label] = ratio
        print(f"  DLOD/POD ({label:20s}): {ratio:.4f}  "
              f"({ratio * 100:.2f}% of total output is deliverable-linked)")

    # ------------------------------------------------------------------
    # 9. Assemble and write output
    # ------------------------------------------------------------------
    print("\n[9] Writing output ...")

    output = {
        "total_cost": total_cost,
        "pod_words_per_dollar": pod_words,
        "attribution_coverage": coverage,
        "dlod_by_threshold": dlod_by_threshold,
        "per_project": per_project,
        "dlod_to_pod_ratio": dlod_to_pod,
        "unmapped_projects": sorted(unmapped_projects) if unmapped_projects else [],
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_messages": len(df),
            "total_assistant_messages": total_assistant_msgs,
            "deliverables_count": len(deliverables),
            "project_to_deliverable_map": {
                k: v for k, v in PROJECT_TO_DELIVERABLE.items()
            },
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(jsonify(output), f, indent=2, default=str)

    elapsed = time.time() - t0
    print(f"  Written to: {output_path}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("DLOD SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total cost:              ${total_cost:,.0f}")
    print(f"  POD (all output):        {pod_words:.2f} words/$")
    print(f"  DLOD (high only):        {dlod_high['dlod_words']:.2f} words/$  "
          f"({dlod_to_pod['high_only'] * 100:.1f}% of POD)")
    print(f"  DLOD (high+medium):      {dlod_high_medium['dlod_words']:.2f} words/$  "
          f"({dlod_to_pod['high_medium'] * 100:.1f}% of POD)")
    print(f"  DLOD (all attributed):   {dlod_all['dlod_words']:.2f} words/$  "
          f"({dlod_to_pod['all_attributed'] * 100:.1f}% of POD)")
    print(f"  Attribution coverage:    {coverage['coverage_pct']:.1f}% of conversations, "
          f"{coverage['output_coverage_pct']:.1f}% of output words")
    print(f"  Verified projects:       {len(verified_projects)} / "
          f"{len(all_attributed_projects)}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
