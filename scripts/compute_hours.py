#!/usr/bin/env python3
"""
compute_hours.py
================
Computes documented LLM **practice hours** directly from the normalized
message CSVs produced by ``analyze_chatgpt.py`` / ``analyze_claude.py``.

This is the runnable implementation of the methodology described in
``LLM_Practice_Hours_Methodology_GIT.pdf``. The paper documents the model and
the reasoning; this script applies it to export data so the headline figures
are reproducible push-button rather than by hand.

Two tiers are reported:

  Tier 1 -- Documented In-Chat Interaction (fully auditable from exports):
            weighted reading + prompt composition + inter-exchange processing
            + per-day session overhead.

  Tier 2 -- Total LLM-Assisted Practice (Tier 1 + estimated offline work,
            scaled by conversation depth). The offline multipliers are
            estimates, not measurements -- see the methodology paper.

Each tier is reported with a baseline, a sensitivity range, and a stress-test
floor under deliberately pessimistic assumptions.

Inputs:
  --chatgpt   Path to chatgpt_messages_normalized.csv  (optional)
  --claude    Path to claude_messages_normalized.csv   (optional)
              At least one is required; if both are given they are combined.
  --output    Optional path to write the full result as JSON.

All constants below are taken verbatim from the methodology paper. Changing
them changes the model; they are exposed here precisely so the assumptions are
inspectable.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Methodology constants (see LLM_Practice_Hours_Methodology_GIT.pdf)
# ---------------------------------------------------------------------------

# Method 1 -- Weighted reading time. Reading speeds in words per minute, and
# the share of assistant output read at each depth.
READING_BASELINE = [
    # (label, share_of_content, words_per_minute)
    ("Skimmed / discarded", 0.20, 400),
    ("Casual reading",       0.35, 200),
    ("Analytical reading",   0.30, 125),
    ("Deep processing",      0.15, 80),
]
READING_STRESS = [
    ("Skimmed / discarded", 0.40, 400),
    ("Casual reading",       0.35, 200),
    ("Analytical reading",   0.20, 125),
    ("Deep processing",      0.05, 80),
]

# Method 2 -- Composition time (words per minute of prompt writing).
COMPOSE_WPM_BASELINE = 22
COMPOSE_WPM_STRESS = 30

# Method 3 -- Inter-exchange cognitive processing (minutes per user message).
PROCESS_MIN_BASELINE = 1.0
PROCESS_MIN_STRESS = 0.75

# Method 4 -- Session overhead (minutes per unique active day).
OVERHEAD_MIN_BASELINE = 12
OVERHEAD_MIN_STRESS = 8

# Tier 1 sensitivity band applied to the baseline.
TIER1_BAND = 0.15  # +/- 15%

# Tier 2 -- Offline work hours per conversation, by depth bucket.
#   bucket key -> (baseline_hours_per_conv, stress_hours_per_conv)
OFFLINE = {
    "under_10": (0.25, 0.125),
    "10_to_29": (1.0, 0.5),
    "30_to_99": (2.5, 1.25),
    "100_plus": (5.0, 2.5),
}
TIER2_UPPER_BAND = 0.15  # +15% upper estimate on the baseline


def _weighted_reading_hours(asst_words, split):
    """Sum over reading modes of (words * share / wpm), converted to hours."""
    minutes = sum(asst_words * share / wpm for _label, share, wpm in split)
    return minutes / 60.0


def load_messages(chatgpt_csv, claude_csv):
    """Load and concatenate the normalized message CSVs we were given."""
    frames = []
    cols = ["platform", "conversation_id", "role", "word_count", "date"]
    for path in (chatgpt_csv, claude_csv):
        if not path:
            continue
        df = pd.read_csv(
            path,
            usecols=cols,
            dtype={"conversation_id": str, "role": str},
        )
        frames.append(df)
    if not frames:
        raise SystemExit("error: provide at least one of --chatgpt / --claude")
    return pd.concat(frames, ignore_index=True)


def derive_inputs(df):
    """Pull the raw quantities the methodology consumes out of the messages."""
    asst = df[df.role == "assistant"]
    user = df[df.role == "user"]
    # Conversations are keyed per platform so ids never collide across them.
    sizes = df.groupby(["platform", "conversation_id"]).size()
    depth = {
        "under_10": int((sizes < 10).sum()),
        "10_to_29": int(((sizes >= 10) & (sizes <= 29)).sum()),
        "30_to_99": int(((sizes >= 30) & (sizes <= 99)).sum()),
        "100_plus": int((sizes >= 100).sum()),
    }
    return {
        "assistant_words": int(asst.word_count.sum()),
        "user_words": int(user.word_count.sum()),
        "user_messages": int(len(user)),  # exchanges
        "active_days": int(df["date"].nunique()),
        "conversations_with_messages": int(sizes.shape[0]),
        "depth": depth,
    }


def compute(inp):
    """Apply the methodology to the derived inputs. Returns a result dict."""
    aw = inp["assistant_words"]
    uw = inp["user_words"]
    ex = inp["user_messages"]
    days = inp["active_days"]
    depth = inp["depth"]

    # --- Tier 1 baseline ----------------------------------------------------
    m1 = _weighted_reading_hours(aw, READING_BASELINE)
    m2 = uw / COMPOSE_WPM_BASELINE / 60.0
    m3 = ex * PROCESS_MIN_BASELINE / 60.0
    m4 = days * OVERHEAD_MIN_BASELINE / 60.0
    tier1 = m1 + m2 + m3 + m4

    # --- Tier 1 stress floor ------------------------------------------------
    s1 = _weighted_reading_hours(aw, READING_STRESS)
    s2 = uw / COMPOSE_WPM_STRESS / 60.0
    s3 = ex * PROCESS_MIN_STRESS / 60.0
    s4 = days * OVERHEAD_MIN_STRESS / 60.0
    tier1_floor = s1 + s2 + s3 + s4

    # --- Offline work (Tier 2 addition) -------------------------------------
    offline_base = sum(depth[k] * OFFLINE[k][0] for k in OFFLINE)
    offline_stress = sum(depth[k] * OFFLINE[k][1] for k in OFFLINE)

    tier2 = tier1 + offline_base
    tier2_conservative = tier1 + offline_stress

    return {
        "tier1": {
            "method1_weighted_reading": m1,
            "method2_composition": m2,
            "method3_inter_exchange": m3,
            "method4_session_overhead": m4,
            "baseline": tier1,
            "conservative_minus_15pct": tier1 * (1 - TIER1_BAND),
            "upper_plus_15pct": tier1 * (1 + TIER1_BAND),
            "stress_floor": tier1_floor,
        },
        "offline": {"baseline": offline_base, "stress": offline_stress},
        "tier2": {
            "baseline": tier2,
            "conservative_floor": tier2_conservative,
            "upper_plus_15pct": tier2 * (1 + TIER2_UPPER_BAND),
        },
        "cross_checks": {
            "tier1_hours_per_active_day": tier1 / days if days else 0,
            "tier2_hours_per_active_day": tier2 / days if days else 0,
            "total_words_read_and_written": aw + uw,
            "words_per_hour_tier1": (aw + uw) / tier1 if tier1 else 0,
        },
    }


def _r(x):
    return f"{round(x):,}"


def render(inp, res):
    d = inp["depth"]
    t1 = res["tier1"]
    t2 = res["tier2"]
    off = res["offline"]
    cc = res["cross_checks"]
    lines = []
    lines.append("=" * 64)
    lines.append("  LLM PRACTICE HOURS")
    lines.append("=" * 64)
    lines.append("")
    lines.append("Data foundation (from exports):")
    lines.append(f"  Assistant words read     : {inp['assistant_words']:>12,}")
    lines.append(f"  User words written       : {inp['user_words']:>12,}")
    lines.append(f"  Exchanges (user msgs)    : {inp['user_messages']:>12,}")
    lines.append(f"  Unique active days       : {inp['active_days']:>12,}")
    lines.append(
        f"  Conversations (w/ msgs)  : {inp['conversations_with_messages']:>12,}"
    )
    lines.append(
        f"  Depth  <10/10-29/30-99/100+ : "
        f"{d['under_10']:,} / {d['10_to_29']:,} / {d['30_to_99']:,} / {d['100_plus']:,}"
    )
    lines.append("")
    lines.append("TIER 1 -- Documented In-Chat Interaction (auditable)")
    lines.append(f"  Method 1  Weighted reading      : {_r(t1['method1_weighted_reading']):>7} h")
    lines.append(f"  Method 2  Prompt composition    : {_r(t1['method2_composition']):>7} h")
    lines.append(f"  Method 3  Inter-exchange proc.  : {_r(t1['method3_inter_exchange']):>7} h")
    lines.append(f"  Method 4  Session overhead      : {_r(t1['method4_session_overhead']):>7} h")
    lines.append(f"  -> Baseline                     : {_r(t1['baseline']):>7} h")
    lines.append(
        f"     Range  {_r(t1['conservative_minus_15pct'])}"
        f" -- {_r(t1['upper_plus_15pct'])}"
        f"   (stress floor {_r(t1['stress_floor'])})"
    )
    lines.append("")
    lines.append("TIER 2 -- Total LLM-Assisted Practice (adds offline work)")
    lines.append(f"  Offline baseline / stress       : {_r(off['baseline'])} / {_r(off['stress'])} h")
    lines.append(f"  -> Baseline                     : {_r(t2['baseline']):>7} h")
    lines.append(f"     Conservative floor           : {_r(t2['conservative_floor']):>7} h")
    lines.append(f"     Upper (+15%)                 : {_r(t2['upper_plus_15pct']):>7} h")
    lines.append("")
    lines.append("Cross-checks:")
    lines.append(f"  Tier 1 hours / active day       : {cc['tier1_hours_per_active_day']:.2f}")
    lines.append(f"  Tier 2 hours / active day       : {cc['tier2_hours_per_active_day']:.2f}")
    lines.append(f"  Words / hour (Tier 1)           : {cc['words_per_hour_tier1']:,.0f}")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Compute LLM practice hours from normalized message CSVs."
    )
    parser.add_argument("--chatgpt", help="Path to chatgpt_messages_normalized.csv")
    parser.add_argument("--claude", help="Path to claude_messages_normalized.csv")
    parser.add_argument("--output", help="Optional path to write results as JSON")
    args = parser.parse_args()

    df = load_messages(args.chatgpt, args.claude)
    inp = derive_inputs(df)
    res = compute(inp)
    print(render(inp, res))

    if args.output:
        payload = {"inputs": inp, "results": res}
        Path(args.output).write_text(json.dumps(payload, indent=2))
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
