#!/usr/bin/env python3
"""
compute_poe.py
==============
Computes the Productive Output Efficiency (POE) metric -- the quality-adjusted
version of POD.

POE = (output_words x Q) / cost

Q is reported as a RANGE across 5 configurations (q_unit, q_high, q_mid,
q_low, q_floor), not a single value.

Inputs:
  - Normalized CSVs (chatgpt + claude)
  - pod_results.json        -- overall/monthly/per-platform output totals
  - dlod_results.json       -- project attribution & deliverable linkage
  - quality_params.json     -- 5 Q configurations with per-proxy weights
  - classifications_and_projects.json -- per-conversation project attribution
  - chatgpt_metadata.json   -- per-conversation branching data
  - cost_log.json            -- subscription cost log

Output:
  - poe_results.json

Methodology:
  1. Re-derive per-conversation outcomes from CSVs (same logic as
     analyze_effectiveness.py).
  2. For each conversation, compute per-Q-configuration quality weight.
  3. POE = sum(conversation_assistant_words x conversation_Q) / total_cost.
"""

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Same classification regex patterns used by analyze_effectiveness.py
# ---------------------------------------------------------------------------

CORRECTION_RE = re.compile(
    r"try again|that's not right|that'?s wrong|not what I|closer but|"
    r"almost|revise|redo|rewrite|fix that|incorrect",
    re.IGNORECASE,
)

POSITIVE_FEEDBACK_RE = re.compile(
    r"\bthank|thanks|perfect|exactly|great|awesome|that works|looks good|"
    r"well done|nice\b|excellent|got it",
    re.IGNORECASE,
)

FRUSTRATED_RE = re.compile(
    r"never mind|forget it|this isn't working|useless|doesn't work|give up",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jsonify(obj):
    """Recursively convert numpy types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {str(k): jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(float(obj), 6)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return round(obj, 6)
    if isinstance(obj, np.ndarray):
        return jsonify(obj.tolist())
    return obj


def month_range(start: str, end: str) -> list[str]:
    """Generate YYYY-MM strings from start to end inclusive."""
    months = []
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


# ---------------------------------------------------------------------------
# Per-conversation outcome classification (mirrors analyze_effectiveness.py)
# ---------------------------------------------------------------------------

def classify_conversations(df: pd.DataFrame) -> dict[str, dict]:
    """
    Classify each conversation into an outcome label and compute
    per-conversation assistant word counts.

    Returns dict keyed by conversation_id with:
      - outcome: str ("frustrated", "converged", "abandoned", "neutral", "short")
      - assistant_words: int
      - platform: str
      - month: str
    """
    print("  Classifying conversation outcomes ...")
    t0 = time.time()

    df = df.copy()
    df["created_dt"] = pd.to_datetime(df["created"], utc=True, errors="coerce")

    results: dict[str, dict] = {}  # type: ignore[type-arg]
    conv_groups = df.groupby("conversation_id")

    for conv_id, grp in conv_groups:
        grp = grp.sort_values("created_dt")
        total_msgs = len(grp)
        user_msgs = grp[grp["role"] == "user"]
        asst_msgs = grp[grp["role"] == "assistant"]
        platform = grp["platform"].iloc[0]
        conv_month = grp["month"].iloc[0] if "month" in grp.columns else None

        assistant_words = int(asst_msgs["word_count"].sum())

        if total_msgs < 5:
            outcome = "short"
        else:
            user_contents = user_msgs["content"].fillna("").tolist()
            n_corrections = sum(
                1 for c in user_contents if CORRECTION_RE.search(c)
            )
            last_role = grp["role"].iloc[-1]
            last_user_content = user_contents[-1] if user_contents else ""

            if n_corrections >= 3 or FRUSTRATED_RE.search(last_user_content):
                outcome = "frustrated"
            elif POSITIVE_FEEDBACK_RE.search(last_user_content):
                outcome = "converged"
            elif last_role == "assistant":
                outcome = "abandoned"
            else:
                outcome = "neutral"

        results[str(conv_id)] = {
            "outcome": outcome,
            "assistant_words": assistant_words,
            "platform": platform,
            "month": conv_month,
        }

    elapsed = time.time() - t0
    print(f"  Classified {len(results)} conversations in {elapsed:.1f}s")
    return results


# ---------------------------------------------------------------------------
# POE computation
# ---------------------------------------------------------------------------

def compute_poe(
    conv_data: dict[str, dict],
    attribution_set: set[str],
    branched_set: set[str],
    q_configs: dict[str, dict],
    total_cost: float,
    per_month_cost: dict[str, float],
    total_output_words: int,
) -> dict:
    """
    Compute POE across all Q configurations.

    Parameters
    ----------
    conv_data : per-conversation dict from classify_conversations
    attribution_set : set of conversation_ids that have project attribution
    branched_set : set of conversation_ids that have branches (ChatGPT only)
    q_configs : dict of config_name -> weight params
    total_cost : total dollar cost
    per_month_cost : dict of YYYY-MM -> cost
    total_output_words : raw total assistant output words

    Returns
    -------
    dict with poe_range, stress_test, per_conversation_summary, monthly_poe_q_mid
    """
    config_names = ["q_unit", "q_high", "q_mid", "q_low", "q_floor"]

    # ---- Per-conversation quality weights ----
    # For each config, compute weighted output
    weighted_output_by_config: dict[str, float] = {c: 0.0 for c in config_names}
    # For monthly breakdown at q_mid
    monthly_weighted_output: dict[str, float] = defaultdict(float)
    monthly_raw_output: dict[str, float] = defaultdict(float)

    # Summary counters
    outcome_dist: Counter[str] = Counter()
    attributed_count = 0
    branched_count = 0
    total_conversations = len(conv_data)

    for conv_id, info in conv_data.items():
        outcome = info["outcome"]
        asst_words = info["assistant_words"]
        platform = info["platform"]
        month = info["month"]

        outcome_dist[outcome] += 1
        has_attribution = conv_id in attribution_set
        has_branches = conv_id in branched_set

        if has_attribution:
            attributed_count += 1
        if has_branches:
            branched_count += 1

        if month:
            monthly_raw_output[month] += asst_words

        for cfg_name in config_names:
            cfg = q_configs[cfg_name]

            # Step 1: base weight from outcome
            if outcome == "frustrated":
                base = cfg["frustrated_discount"]
            elif outcome == "converged":
                base = cfg["converged_weight"]
            else:
                # abandoned, neutral, short all use standard_weight
                base = cfg["standard_weight"]

            # Step 2: deliverable linkage modifier
            if has_attribution:
                linkage = cfg["deliverable_linked_bonus"]
            else:
                linkage = cfg["unlinked_discount"]

            # Step 3: branching modifier (ChatGPT only)
            if has_branches and platform == "chatgpt":
                branch_mod = cfg["branched_discount"]
            else:
                branch_mod = 1.0

            conv_q = base * linkage * branch_mod
            weighted = asst_words * conv_q

            weighted_output_by_config[cfg_name] += weighted

            if cfg_name == "q_mid" and month:
                monthly_weighted_output[month] += weighted

    # ---- Compute POE for each config ----
    raw_pod = total_output_words / total_cost if total_cost > 0 else 0.0

    poe_range = {}
    for cfg_name in config_names:
        w_out = weighted_output_by_config[cfg_name]
        poe_val = w_out / total_cost if total_cost > 0 else 0.0
        effective_q = w_out / total_output_words if total_output_words > 0 else 0.0
        ratio = poe_val / raw_pod if raw_pod > 0 else 0.0

        poe_range[cfg_name] = {
            "poe_words": round(poe_val, 1),
            "effective_q": round(effective_q, 4),
            "ratio_to_pod": round(ratio, 4),
        }

    # ---- Stress test: q_floor + hardware amortization ----
    hardware_cost = 50.0 * 33  # $50/month * 33 months
    cost_with_hardware = total_cost + hardware_cost
    w_floor = weighted_output_by_config["q_floor"]
    poe_floor_hw = w_floor / cost_with_hardware if cost_with_hardware > 0 else 0.0

    stress_test = {
        "cost_with_hardware": cost_with_hardware,
        "poe_words_q_floor": round(poe_floor_hw, 1),
        "note": "Minimum defensible POE under maximum skepticism",
    }

    # ---- Per-conversation summary ----
    per_conversation_summary = {
        "total_conversations": total_conversations,
        "outcome_distribution": dict(outcome_dist),
        "attributed_count": attributed_count,
        "branched_count": branched_count,
    }

    # ---- Monthly POE at q_mid ----
    # Compute per-month cost from per_month_cost
    monthly_poe_q_mid = {}
    for month in sorted(set(list(monthly_weighted_output.keys()) + list(monthly_raw_output.keys()))):
        m_cost = per_month_cost.get(month, 0)
        m_weighted = monthly_weighted_output.get(month, 0.0)
        m_raw = monthly_raw_output.get(month, 0.0)
        poe_m = m_weighted / m_cost if m_cost > 0 else 0.0
        monthly_poe_q_mid[month] = {
            "poe_words": round(poe_m, 1),
            "output_words": round(m_raw, 0),
            "weighted_output": round(m_weighted, 1),
            "cost": m_cost,
        }

    return {
        "poe_range": poe_range,
        "stress_test": stress_test,
        "per_conversation_summary": per_conversation_summary,
        "monthly_poe_q_mid": monthly_poe_q_mid,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute Productive Output Efficiency (POE) -- "
                    "the quality-adjusted version of POD."
    )
    parser.add_argument(
        "--chatgpt-csv",
        default="chatgpt_messages_normalized.csv",
        help="Path to ChatGPT normalized messages CSV",
    )
    parser.add_argument(
        "--claude-csv",
        default="claude_messages_normalized.csv",
        help="Path to Claude normalized messages CSV",
    )
    parser.add_argument(
        "--pod-results",
        default="pod_results.json",
        help="Path to pod_results.json",
    )
    parser.add_argument(
        "--quality-params",
        default="quality_params.json",
        help="Path to quality_params.json with Q configurations",
    )
    parser.add_argument(
        "--classifications",
        default="classifications_and_projects.json",
        help="Path to classifications_and_projects.json",
    )
    parser.add_argument(
        "--chatgpt-metadata",
        default="chatgpt_metadata.json",
        help="Path to chatgpt_metadata.json",
    )
    parser.add_argument(
        "--cost-log",
        default="cost_log.json",
        help="Path to cost_log.json",
    )
    parser.add_argument(
        "--output",
        default="poe_results.json",
        help="Path for output JSON",
    )
    args = parser.parse_args()

    overall_t0 = time.time()

    print("=" * 70)
    print("PRODUCTIVE OUTPUT EFFICIENCY (POE) COMPUTATION")
    print("=" * 70)

    # ---- Load CSVs ----
    print(f"\nLoading ChatGPT CSV: {args.chatgpt_csv}")
    df_chatgpt = pd.read_csv(args.chatgpt_csv, low_memory=False)
    print(f"  Rows: {len(df_chatgpt):,}")

    print(f"Loading Claude CSV: {args.claude_csv}")
    df_claude = pd.read_csv(args.claude_csv, low_memory=False)
    print(f"  Rows: {len(df_claude):,}")

    df = pd.concat([df_chatgpt, df_claude], ignore_index=True)
    print(f"Combined: {len(df):,} messages")
    print(f"Unique conversations: {df['conversation_id'].nunique():,}")

    # ---- Load supporting data ----
    print(f"\nLoading POD results: {args.pod_results}")
    with open(args.pod_results) as f:
        pod_data = json.load(f)

    print(f"Loading quality params: {args.quality_params}")
    with open(args.quality_params) as f:
        qp = json.load(f)
    q_configs = qp["configurations"]

    print(f"Loading classifications: {args.classifications}")
    with open(args.classifications) as f:
        classifications = json.load(f)

    print(f"Loading ChatGPT metadata: {args.chatgpt_metadata}")
    with open(args.chatgpt_metadata) as f:
        chatgpt_meta = json.load(f)

    print(f"Loading cost log: {args.cost_log}")
    with open(args.cost_log) as f:
        json.load(f)  # validate JSON but data not directly used

    # ---- Extract reference values ----
    total_cost = pod_data["total_cost"]
    total_output_words = pod_data["overall"]["total_output_words"]
    raw_pod_words = pod_data["overall"]["pod_words"]
    hardware_cost = 50 * 33  # $50/month * 33 months

    # Per-month cost from pod_results
    per_month_cost = {}
    for month_str, month_data in pod_data["cost_breakdown"]["per_month"].items():
        per_month_cost[month_str] = sum(month_data.values())

    print(f"\n  Total cost: ${total_cost}")
    print(f"  Total output words: {total_output_words:,}")
    print(f"  Raw POD (words/$): {raw_pod_words:.1f}")
    print(f"  Hardware amortization: ${hardware_cost}")
    print(f"  Cost with hardware: ${total_cost + hardware_cost}")

    # ---- Build attribution set ----
    attribution_set = set()
    per_conv_list = classifications.get("per_conversation", [])
    for entry in per_conv_list:
        if entry.get("project") is not None:
            attribution_set.add(entry["conversation_id"])
    print(f"\n  Conversations with project attribution: {len(attribution_set)}")

    # ---- Build branched set ----
    branched_set = set()
    for conv in chatgpt_meta.get("per_conversation", []):
        if conv.get("branch_points", 0) > 0:
            branched_set.add(conv["conversation_id"])
    print(f"  Conversations with branches (ChatGPT): {len(branched_set)}")

    # ---- Classify conversations ----
    print()
    conv_data = classify_conversations(df)

    # ---- Compute POE ----
    print("\n  Computing POE across Q configurations ...")
    result = compute_poe(
        conv_data=conv_data,
        attribution_set=attribution_set,
        branched_set=branched_set,
        q_configs=q_configs,
        total_cost=total_cost,
        per_month_cost=per_month_cost,
        total_output_words=total_output_words,
    )

    # ---- Build output ----
    output = {
        "total_cost": total_cost,
        "total_cost_with_hardware": total_cost + hardware_cost,
        "raw_pod_words": raw_pod_words,
        "poe_range": result["poe_range"],
        "stress_test": result["stress_test"],
        "per_conversation_summary": result["per_conversation_summary"],
        "monthly_poe_q_mid": result["monthly_poe_q_mid"],
    }

    # ---- Print sensitivity table ----
    print("\n" + "=" * 70)
    print("POE SENSITIVITY TABLE")
    print("=" * 70)
    print(f"{'Config':<12s} {'Label':<35s} {'POE (w/$)':<12s} {'Eff. Q':<10s} {'Ratio to POD':<12s}")
    print("-" * 81)

    config_order = ["q_unit", "q_high", "q_mid", "q_low", "q_floor"]
    for cfg_name in config_order:
        label = q_configs[cfg_name].get("label", cfg_name)
        pr = result["poe_range"][cfg_name]
        print(
            f"{cfg_name:<12s} {label:<35s} {pr['poe_words']:<12.1f} "
            f"{pr['effective_q']:<10.4f} {pr['ratio_to_pod']:<12.4f}"
        )

    print(f"\nRaw POD (no quality adjustment): {raw_pod_words:.1f} words/$")

    # ---- Print stress test ----
    print("\n" + "-" * 70)
    print("STRESS TEST: q_floor + hardware amortization")
    print("-" * 70)
    st = result["stress_test"]
    print(f"  Cost with hardware: ${st['cost_with_hardware']:.0f}")
    print(f"  POE (q_floor, with hardware): {st['poe_words_q_floor']:.1f} words/$")
    print(f"  {st['note']}")

    # ---- Print per-conversation summary ----
    pcs = result["per_conversation_summary"]
    print("\n" + "-" * 70)
    print("PER-CONVERSATION SUMMARY")
    print("-" * 70)
    print(f"  Total conversations: {pcs['total_conversations']}")
    print("  Outcome distribution:")
    for label, count in sorted(pcs["outcome_distribution"].items(), key=lambda x: -x[1]):
        pct = count / pcs["total_conversations"] * 100
        print(f"    {label:<12s}: {count:>5d} ({pct:5.1f}%)")
    print(f"  Attributed to a project: {pcs['attributed_count']}")
    print(f"  With branches (ChatGPT): {pcs['branched_count']}")

    # ---- Print monthly POE trend (q_mid) ----
    print("\n" + "-" * 70)
    print("MONTHLY POE TREND (q_mid)")
    print("-" * 70)
    print(f"{'Month':<10s} {'Cost':<8s} {'Raw Words':<14s} {'Wtd Words':<14s} {'POE (w/$)':<12s}")
    print("-" * 58)
    for month in sorted(result["monthly_poe_q_mid"].keys()):
        m = result["monthly_poe_q_mid"][month]
        print(
            f"{month:<10s} ${m['cost']:<7.0f} {m['output_words']:<14,.0f} "
            f"{m['weighted_output']:<14,.1f} {m['poe_words']:<12.1f}"
        )

    # ---- Write output ----
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(jsonify(output), f, indent=2, default=str)

    elapsed = time.time() - overall_t0
    print(f"\n{'=' * 70}")
    print(f"Output written to: {output_path}")
    print(f"Total elapsed: {elapsed:.1f}s")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
