#!/usr/bin/env python3
"""
analyze_effectiveness.py
========================
Analyzes prompt engineering effectiveness, interaction patterns, and
platform comparison from normalized conversation CSVs.

Inputs (defaults):
  - analysis/latest-run/chatgpt_messages_normalized.csv
  - analysis/latest-run/claude_messages_normalized.csv

Output:
  - analysis/deep_analysis/data/effectiveness_and_patterns.json
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
# Constants: technique regex patterns (compiled once)
# ---------------------------------------------------------------------------

TECHNIQUE_PATTERNS: dict[str, re.Pattern] = {
    "role_assignment": re.compile(
        r"you are a|act as|pretend you|imagine you|your role is|as a .{2,20} expert",
        re.IGNORECASE,
    ),
    "constraints": re.compile(
        r"\b(?:must|should not|do not|don't|never|always|ensure|make sure|"
        r"limit to|at most|at least|no more than|only include|exclude|avoid)\b",
        re.IGNORECASE,
    ),
    "output_format": re.compile(
        r"format as|return as|in json|as json|in a table|bullet point|"
        r"numbered list|step by step|step-by-step|in markdown|as csv|"
        r"as a list|provide a table",
        re.IGNORECASE,
    ),
    "examples_given": re.compile(
        r"for example|e\.g\.|such as|like this:|here's an example|"
        r"here is an example",
        re.IGNORECASE,
    ),
    "multi_step": re.compile(
        r"\b1\.\s|first,?\s.*second|step 1|step one|\ba\)\s|\bi\)\s",
        re.IGNORECASE,
    ),
    "meta_prompting": re.compile(
        r"think step by step|chain of thought|let's think|think carefully|"
        r"reason through|before you answer|think about this",
        re.IGNORECASE,
    ),
    "code_inclusion": re.compile(
        r"```|\bdef\s+\w|\bclass\s+\w|\bfunction\s+\w|\bimport\s+\w|\b#include\b",
        re.IGNORECASE,
    ),
    "prior_reference": re.compile(
        r"as we discussed|as you mentioned|earlier you|building on|"
        r"continuing from|as I said|going back to",
        re.IGNORECASE,
    ),
    "iterative_refinement": re.compile(
        r"try again|that's not right|that'?s wrong|not what I|closer but|"
        r"almost|revise|redo|rewrite|fix that|incorrect",
        re.IGNORECASE,
    ),
}

# examples_given also fires on code fences with example data
CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")

# context_frontloading is word_count > 200 — handled in column logic

# Interaction style patterns
IMPERATIVE_VERBS = re.compile(
    r"^(?:write|create|make|build|generate|add|remove|fix|change|update|"
    r"implement|design|explain)\b",
    re.IGNORECASE,
)
QUESTION_STARTERS = re.compile(
    r"^(?:what|how|why|when|where|which|can|could|would|is|are|do|does|will|should)\b",
    re.IGNORECASE,
)
COLLABORATIVE_RE = re.compile(
    r"\blet's\b|\blet us\b|\bwe could\b|\bwe should\b|\bhow about\b|"
    r"\bwhat if we\b|\bshall we\b|\btogether\b",
    re.IGNORECASE,
)
POSITIVE_FEEDBACK_RE = re.compile(
    r"\bthank|thanks|perfect|exactly|great|awesome|that works|looks good|"
    r"well done|nice\b|excellent|got it",
    re.IGNORECASE,
)
CORRECTION_RE = TECHNIQUE_PATTERNS["iterative_refinement"]

# Convergence patterns
FRUSTRATED_RE = re.compile(
    r"never mind|forget it|this isn't working|useless|doesn't work|give up",
    re.IGNORECASE,
)

# Usage-mode patterns
TEACHING_RE = re.compile(
    r"explain|why|how does|teach|help me understand|what is|what are",
    re.IGNORECASE,
)
PRODUCTION_RE = re.compile(
    r"write|create|generate|build|make|draft|produce",
    re.IGNORECASE,
)
SYNTHESIS_RE = re.compile(
    r"compare|contrast|combine|synthesize|relationship between|"
    r"similarities|differences|integrate",
    re.IGNORECASE,
)
DEBUG_CODE_RE = re.compile(r"```")
DEBUG_FIX_RE = re.compile(
    r"fix|error|bug|crash|doesn't work|not working|issue|debug|traceback|exception",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_float(v):
    """Convert numpy/pandas numeric to plain float, handling NaN."""
    if isinstance(v, (float, np.floating)):
        if np.isnan(v) or np.isinf(v):
            return None
        return float(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    return v


def jsonify(obj):
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


def quarter_label(month_str: str) -> str:
    """Convert 'YYYY-MM' to 'YYYY-Q1' etc."""
    y, m = month_str.split("-")
    q = (int(m) - 1) // 3 + 1
    return f"{y}-Q{q}"


# ---------------------------------------------------------------------------
# Part 1: Technique detection on user messages
# ---------------------------------------------------------------------------

def detect_techniques(df_user: pd.DataFrame) -> pd.DataFrame:
    """Add boolean columns for each prompt technique."""
    print("[Part 1] Detecting prompt techniques across user messages ...")
    t0 = time.time()

    content = df_user["content"].fillna("")

    for tech_name, pattern in TECHNIQUE_PATTERNS.items():
        df_user[tech_name] = content.str.contains(pattern, na=False)

    # examples_given: also fires if there are code fences (even without the textual markers)
    has_code_fences = content.str.contains(CODE_FENCE_RE, na=False)
    df_user["examples_given"] = df_user["examples_given"] | has_code_fences

    # context_frontloading: word_count > 200
    df_user["context_frontloading"] = df_user["word_count"] > 200

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")
    return df_user


def compute_technique_stats(df_user: pd.DataFrame) -> dict:
    """Aggregate technique stats: overall, monthly, per-platform, first appearance."""
    techniques = list(TECHNIQUE_PATTERNS.keys()) + ["context_frontloading"]
    total_msgs = len(df_user)
    months = sorted(df_user["month"].dropna().unique())

    result = {}
    for tech in techniques:
        total_count = int(df_user[tech].sum())
        total_pct = round(total_count / total_msgs, 6) if total_msgs else 0.0

        # Monthly
        monthly = {}
        first_appearance = None
        for m in months:
            mask = df_user["month"] == m
            n = int(mask.sum())
            c = int(df_user.loc[mask, tech].sum())
            pct = round(c / n, 6) if n else 0.0
            monthly[m] = {"count": c, "pct": pct}
            if first_appearance is None and n > 0 and pct > 0.01:
                first_appearance = m

        # Per-platform
        by_platform = {}
        for plat in ("chatgpt", "claude"):
            mask = df_user["platform"] == plat
            n = int(mask.sum())
            c = int(df_user.loc[mask, tech].sum())
            by_platform[plat] = {
                "count": c,
                "pct": round(c / n, 6) if n else 0.0,
            }

        result[tech] = {
            "total_count": total_count,
            "total_pct": total_pct,
            "monthly": monthly,
            "by_platform": by_platform,
            "first_appearance": first_appearance,
        }

    return result


# ---------------------------------------------------------------------------
# Part 2: Conversation outcome metrics
# ---------------------------------------------------------------------------

def classify_interaction_style(content: str) -> str:
    """Classify a single user message into an interaction style."""
    if not content:
        return "informational"
    stripped = content.strip()
    if COLLABORATIVE_RE.search(content):
        return "collaborative"
    if POSITIVE_FEEDBACK_RE.search(content) or CORRECTION_RE.search(content):
        return "feedback"
    if IMPERATIVE_VERBS.match(stripped):
        return "directive"
    if "?" in content or QUESTION_STARTERS.match(stripped):
        return "interrogative"
    return "informational"


def compute_conversation_outcomes(df: pd.DataFrame, df_user: pd.DataFrame) -> dict:
    """Part 2: conversation-level outcome metrics."""
    print("[Part 2] Computing conversation outcome metrics ...")
    t0 = time.time()

    # Ensure created is parsed
    df = df.copy()
    df["created_dt"] = pd.to_datetime(df["created"], utc=True, errors="coerce")

    # Group by conversation
    conv_groups = df.groupby("conversation_id")

    convergence_counts: Counter[str] = Counter()
    convergence_monthly: dict[str, Counter] = defaultdict(Counter)
    correction_counts: list[int] = []
    correction_monthly: dict[str, list] = defaultdict(list)
    efficiency_ratios: list[float] = []
    efficiency_monthly: dict[str, list] = defaultdict(list)
    efficiency_platform: dict[str, list] = defaultdict(list)
    iteration_depth_vals: list[float] = []
    session_types: Counter[str] = Counter()
    session_types_platform: dict[str, Counter] = defaultdict(Counter)

    n_convs = 0
    for _conv_id, grp in conv_groups:
        n_convs += 1
        grp = grp.sort_values("created_dt")
        total_msgs = len(grp)
        user_msgs = grp[grp["role"] == "user"]
        asst_msgs = grp[grp["role"] == "assistant"]
        platform = grp["platform"].iloc[0]
        conv_month = grp["month"].iloc[0]

        # ---- Convergence classification (5+ messages only) ----
        if total_msgs >= 5:
            user_contents = user_msgs["content"].fillna("").tolist()
            # Count correction messages
            n_corrections = sum(
                1 for c in user_contents if CORRECTION_RE.search(c)
            )
            last_role = grp["role"].iloc[-1]
            last_user_content = user_contents[-1] if user_contents else ""

            if n_corrections >= 3 or FRUSTRATED_RE.search(last_user_content):
                label = "frustrated"
            elif POSITIVE_FEEDBACK_RE.search(last_user_content):
                label = "converged"
            elif last_role == "assistant":
                label = "abandoned"
            else:
                label = "neutral"

            convergence_counts[label] += 1
            convergence_monthly[conv_month][label] += 1

        # ---- Correction density ----
        user_contents_all = user_msgs["content"].fillna("").tolist()
        n_corr = sum(1 for c in user_contents_all if CORRECTION_RE.search(c))
        correction_counts.append(n_corr)
        correction_monthly[conv_month].append(n_corr)

        # ---- Efficiency ratio ----
        user_wc = user_msgs["word_count"].sum()
        asst_wc = asst_msgs["word_count"].sum()
        if user_wc > 0:
            ratio = asst_wc / user_wc
            efficiency_ratios.append(ratio)
            efficiency_monthly[conv_month].append(ratio)
            efficiency_platform[platform].append(ratio)

        # ---- Iteration depth to resolution ----
        if n_corr > 0 and total_msgs > 1:
            # Find position of last correction
            last_corr_pos = 0
            for i, (_, row) in enumerate(grp.iterrows()):
                if row["role"] == "user" and isinstance(row["content"], str):
                    if CORRECTION_RE.search(row["content"]):
                        last_corr_pos = i
            depth = last_corr_pos / (total_msgs - 1)
            iteration_depth_vals.append(depth)

        # ---- Session timing ----
        if len(grp) >= 2:
            times = grp["created_dt"].dropna()
            if len(times) >= 2:
                span = (times.max() - times.min()).total_seconds()
                if span > 86400:
                    stype = "multi_day"
                elif span > 7200:
                    stype = "marathon"
                elif span > 1800:
                    stype = "working"
                else:
                    stype = "sprint"
                session_types[stype] += 1
                session_types_platform[platform][stype] += 1

    # Aggregate monthly convergence as percentages
    convergence_monthly_pct = {}
    for m in sorted(convergence_monthly.keys()):
        cnt = convergence_monthly[m]
        total = sum(cnt.values())
        if total > 0:
            convergence_monthly_pct[m] = {
                k: round(v / total, 6) for k, v in cnt.items()
            }
        else:
            convergence_monthly_pct[m] = {}

    # Aggregate monthly corrections
    corr_monthly_agg = {}
    for m in sorted(correction_monthly.keys()):
        vals = correction_monthly[m]
        corr_monthly_agg[m] = round(np.mean(vals), 6) if vals else 0.0

    # Aggregate efficiency
    eff_monthly_agg = {}
    for m in sorted(efficiency_monthly.keys()):
        vals = efficiency_monthly[m]
        if vals:
            eff_monthly_agg[m] = {
                "median": round(float(np.median(vals)), 6),
                "mean": round(float(np.mean(vals)), 6),
            }

    # Efficiency by platform
    eff_by_platform: dict[str, dict[str, float | None]] = {}
    for plat in ("chatgpt", "claude"):
        vals = efficiency_platform.get(plat, [])
        if vals:
            eff_by_platform[plat] = {
                "median": round(float(np.median(vals)), 6),
                "mean": round(float(np.mean(vals)), 6),
            }
        else:
            eff_by_platform[plat] = {"median": None, "mean": None}

    elapsed = time.time() - t0
    print(f"  Processed {n_convs} conversations in {elapsed:.1f}s")

    return {
        "convergence_distribution": dict(convergence_counts),
        "convergence_monthly": convergence_monthly_pct,
        "correction_density": {
            "overall_mean": round(float(np.mean(correction_counts)), 6) if correction_counts else 0.0,
            "monthly": corr_monthly_agg,
        },
        "efficiency_ratio": {
            "overall_median": round(float(np.median(efficiency_ratios)), 6) if efficiency_ratios else 0.0,
            "overall_mean": round(float(np.mean(efficiency_ratios)), 6) if efficiency_ratios else 0.0,
            "monthly": eff_monthly_agg,
            "by_platform": eff_by_platform,
        },
        "iteration_depth": {
            "mean_last_correction_position": (
                round(float(np.mean(iteration_depth_vals)), 6)
                if iteration_depth_vals else 0.0
            ),
        },
        "session_types": dict(session_types),
        "session_types_by_platform": {
            plat: dict(session_types_platform.get(plat, {}))
            for plat in ("chatgpt", "claude")
        },
    }


# ---------------------------------------------------------------------------
# Part 3: Interaction style analysis
# ---------------------------------------------------------------------------

def compute_interaction_styles(df_user: pd.DataFrame) -> dict:
    """Part 3: classify interaction styles and usage modes."""
    print("[Part 3] Classifying interaction styles ...")
    t0 = time.time()

    df_user = df_user.copy()
    df_user["interaction_style"] = df_user["content"].fillna("").apply(
        classify_interaction_style
    )

    total = len(df_user)
    styles = ["directive", "interrogative", "collaborative", "feedback", "informational"]

    # Overall distribution
    overall_counts = df_user["interaction_style"].value_counts()
    overall = {s: round(int(overall_counts.get(s, 0)) / total, 6) for s in styles}

    # By platform
    by_platform = {}
    for plat in ("chatgpt", "claude"):
        mask = df_user["platform"] == plat
        n = int(mask.sum())
        if n == 0:
            by_platform[plat] = {s: 0.0 for s in styles}
            continue
        pc = df_user.loc[mask, "interaction_style"].value_counts()
        by_platform[plat] = {s: round(int(pc.get(s, 0)) / n, 6) for s in styles}

    # Quarterly
    df_user["quarter"] = df_user["month"].apply(
        lambda x: quarter_label(x) if isinstance(x, str) else None
    )
    quarterly = {}
    for q in sorted(df_user["quarter"].dropna().unique()):
        mask = df_user["quarter"] == q
        n = int(mask.sum())
        if n == 0:
            continue
        qc = df_user.loc[mask, "interaction_style"].value_counts()
        quarterly[q] = {s: round(int(qc.get(s, 0)) / n, 6) for s in styles}

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")

    return {
        "overall": overall,
        "by_platform": by_platform,
        "quarterly": quarterly,
        "_style_column": df_user["interaction_style"],  # pass through for usage modes
        "_df_user": df_user,
    }


def compute_usage_modes(df_all: pd.DataFrame, df_user: pd.DataFrame) -> dict:
    """Classify each conversation into a usage mode."""
    print("[Part 3b] Classifying usage modes per conversation ...")
    t0 = time.time()

    mode_counts: Counter[str] = Counter()
    conv_groups = df_user.groupby("conversation_id")

    for _conv_id, grp in conv_groups:
        contents = grp["content"].fillna("").tolist()
        n = len(contents)
        if n == 0:
            mode_counts["mixed"] += 1
            continue

        avg_wc = grp["word_count"].mean()

        # Check each mode
        n_teaching = sum(
            1 for c in contents if TEACHING_RE.search(c) and ("?" in c or QUESTION_STARTERS.match(c.strip()))
        )
        n_production = sum(1 for c in contents if PRODUCTION_RE.search(c) and IMPERATIVE_VERBS.match(c.strip()))
        n_synthesis = sum(1 for c in contents if SYNTHESIS_RE.search(c))
        n_debug = sum(1 for c in contents if DEBUG_CODE_RE.search(c) and DEBUG_FIX_RE.search(c))
        n_questions = sum(1 for c in contents if "?" in c)

        teaching_frac = n_teaching / n
        production_frac = n_production / n
        synthesis_frac = n_synthesis / n
        debug_frac = n_debug / n
        question_frac = n_questions / n

        if teaching_frac > 0.4:
            mode_counts["teaching"] += 1
        elif production_frac > 0.4:
            mode_counts["production"] += 1
        elif synthesis_frac > 0.15:  # synthesis is rarer, lower threshold
            mode_counts["synthesis"] += 1
        elif debug_frac > 0.3:
            mode_counts["debugging"] += 1
        elif avg_wc < 20 and question_frac > 0.5:
            mode_counts["exploration"] += 1
        else:
            mode_counts["mixed"] += 1

    elapsed = time.time() - t0
    print(f"  Classified {sum(mode_counts.values())} conversations in {elapsed:.1f}s")
    return dict(mode_counts)


# ---------------------------------------------------------------------------
# Part 4: Platform comparison
# ---------------------------------------------------------------------------

def compute_platform_comparison(
    df: pd.DataFrame,
    df_user: pd.DataFrame,
    technique_stats: dict,
    outcome_stats: dict,
) -> dict:
    """Part 4: per-platform breakdowns and monthly share."""
    print("[Part 4] Computing platform comparison ...")
    t0 = time.time()

    months = sorted(df["month"].dropna().unique())

    # Monthly platform share
    monthly_share = {}
    for m in months:
        mask = df["month"] == m
        total = int(mask.sum())
        if total == 0:
            continue
        chatgpt_n = int((df.loc[mask, "platform"] == "chatgpt").sum())
        claude_n = int((df.loc[mask, "platform"] == "claude").sum())
        monthly_share[m] = {
            "chatgpt_pct": round(chatgpt_n / total, 6),
            "claude_pct": round(claude_n / total, 6),
            "chatgpt_count": chatgpt_n,
            "claude_count": claude_n,
        }

    # Technique comparison (already in technique_stats.by_platform)
    technique_comparison = {}
    for tech, stats in technique_stats.items():
        technique_comparison[tech] = stats["by_platform"]

    # Outcome comparison by platform — compute convergence per platform
    outcome_by_platform = {}
    for plat in ("chatgpt", "claude"):
        plat_df = df[df["platform"] == plat]
        conv_groups = plat_df.groupby("conversation_id")
        conv_counts: Counter[str] = Counter()
        corr_list = []
        for _conv_id, grp in conv_groups:
            grp = grp.sort_values("created")
            total_msgs = len(grp)
            user_msgs = grp[grp["role"] == "user"]
            user_contents = user_msgs["content"].fillna("").tolist()
            n_corr = sum(1 for c in user_contents if CORRECTION_RE.search(c))
            corr_list.append(n_corr)

            if total_msgs >= 5:
                last_role = grp["role"].iloc[-1]
                last_user = user_contents[-1] if user_contents else ""
                if n_corr >= 3 or FRUSTRATED_RE.search(last_user):
                    conv_counts["frustrated"] += 1
                elif POSITIVE_FEEDBACK_RE.search(last_user):
                    conv_counts["converged"] += 1
                elif last_role == "assistant":
                    conv_counts["abandoned"] += 1
                else:
                    conv_counts["neutral"] += 1

        total_classified = sum(conv_counts.values())
        outcome_by_platform[plat] = {
            "convergence": {
                k: round(v / total_classified, 6) if total_classified else 0.0
                for k, v in conv_counts.items()
            },
            "correction_density_mean": round(float(np.mean(corr_list)), 6) if corr_list else 0.0,
            "total_conversations": len(conv_groups),
        }

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")

    return {
        "monthly_share": monthly_share,
        "technique_comparison": technique_comparison,
        "outcome_comparison": outcome_by_platform,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze prompt engineering effectiveness, interaction patterns, "
                    "and platform comparison from normalized conversation CSVs."
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
        "--output",
        default="effectiveness_and_patterns.json",
        help="Path for output JSON",
    )
    args = parser.parse_args()

    overall_t0 = time.time()

    # ---- Load data ----
    print("=" * 70)
    print("PROMPT EFFECTIVENESS & INTERACTION PATTERN ANALYSIS")
    print("=" * 70)

    print(f"\nLoading ChatGPT CSV: {args.chatgpt_csv}")
    df_chatgpt = pd.read_csv(args.chatgpt_csv, low_memory=False)
    print(f"  Rows: {len(df_chatgpt):,}")

    print(f"Loading Claude CSV: {args.claude_csv}")
    df_claude = pd.read_csv(args.claude_csv, low_memory=False)
    print(f"  Rows: {len(df_claude):,}")

    # Concat
    df = pd.concat([df_chatgpt, df_claude], ignore_index=True)
    print(f"\nCombined: {len(df):,} messages")

    # Parse datetime
    df["created_dt"] = pd.to_datetime(df["created"], utc=True, errors="coerce")

    # Drop rows with null content
    null_content = df["content"].isna().sum()
    print(f"Messages with null content: {null_content:,} (will be skipped where needed)")
    df_valid = df[df["content"].notna()].copy()

    # Separate user messages
    df_user = df_valid[df_valid["role"] == "user"].copy()
    print(f"User messages (non-null content): {len(df_user):,}")
    print(f"Assistant messages (non-null content): {len(df_valid[df_valid['role'] == 'assistant']):,}")
    print(f"Unique conversations: {df['conversation_id'].nunique():,}")

    # Platform breakdown
    for plat in ("chatgpt", "claude"):
        n = (df_user["platform"] == plat).sum()
        print(f"  {plat} user messages: {n:,}")

    print()

    # ==== PART 1: Technique Detection ====
    df_user = detect_techniques(df_user)
    technique_stats = compute_technique_stats(df_user)

    print("\n--- Technique Adoption Summary ---")
    for tech, stats in sorted(technique_stats.items(), key=lambda x: -x[1]["total_count"]):
        print(
            f"  {tech:25s}: {stats['total_count']:6,} ({stats['total_pct']*100:5.1f}%)  "
            f"chatgpt={stats['by_platform']['chatgpt']['pct']*100:5.1f}%  "
            f"claude={stats['by_platform']['claude']['pct']*100:5.1f}%  "
            f"first={stats['first_appearance']}"
        )

    # ==== PART 2: Conversation Outcomes ====
    outcome_stats = compute_conversation_outcomes(df, df_user)

    print("\n--- Conversation Outcome Summary ---")
    conv_dist = outcome_stats["convergence_distribution"]
    total_classified = sum(conv_dist.values())
    for label, count in sorted(conv_dist.items(), key=lambda x: -x[1]):
        pct = count / total_classified * 100 if total_classified else 0
        print(f"  {label:12s}: {count:6,} ({pct:5.1f}%)")

    print(f"\n  Correction density (mean per conv): {outcome_stats['correction_density']['overall_mean']:.3f}")
    print(f"  Efficiency ratio (median):          {outcome_stats['efficiency_ratio']['overall_median']:.3f}")
    print(f"  Efficiency ratio (mean):            {outcome_stats['efficiency_ratio']['overall_mean']:.3f}")
    iter_depth = outcome_stats['iteration_depth']['mean_last_correction_position']
    print(f"  Iteration depth (mean):             {iter_depth:.3f}")

    print("\n  Session types:")
    for stype, count in sorted(outcome_stats["session_types"].items(), key=lambda x: -x[1]):
        print(f"    {stype:10s}: {count:6,}")

    # ==== PART 3: Interaction Styles ====
    style_result = compute_interaction_styles(df_user)
    usage_modes = compute_usage_modes(df, df_user)

    print("\n--- Interaction Style Summary ---")
    for style, frac in sorted(style_result["overall"].items(), key=lambda x: -x[1]):
        print(f"  {style:15s}: {frac*100:5.1f}%")

    print("\n--- Usage Mode Summary ---")
    total_convs = sum(usage_modes.values())
    for mode, count in sorted(usage_modes.items(), key=lambda x: -x[1]):
        pct = count / total_convs * 100 if total_convs else 0
        print(f"  {mode:15s}: {count:6,} ({pct:5.1f}%)")

    # ==== PART 4: Platform Comparison ====
    platform_comparison = compute_platform_comparison(
        df, df_user, technique_stats, outcome_stats
    )

    print("\n--- Platform Outcome Comparison ---")
    for plat in ("chatgpt", "claude"):
        info = platform_comparison["outcome_comparison"].get(plat, {})
        print(f"  {plat}:")
        print(f"    Conversations: {info.get('total_conversations', 0):,}")
        print(f"    Correction density: {info.get('correction_density_mean', 0):.3f}")
        conv = info.get("convergence", {})
        for k, v in sorted(conv.items(), key=lambda x: -x[1]):
            print(f"    {k:12s}: {v*100:5.1f}%")

    eff_plat = outcome_stats["efficiency_ratio"].get("by_platform", {})
    print("\n--- Efficiency Ratio by Platform ---")
    for plat in ("chatgpt", "claude"):
        info = eff_plat.get(plat, {})
        med = info.get("median")
        mn = info.get("mean")
        print(f"  {plat}: median={med}, mean={mn}")

    # ==== Build final output ====
    # Clean up style_result (remove internal columns)
    interaction_style_output = {
        "overall": style_result["overall"],
        "by_platform": style_result["by_platform"],
        "quarterly": style_result["quarterly"],
    }

    output = {
        "technique_adoption": technique_stats,
        "conversation_outcomes": outcome_stats,
        "interaction_style": interaction_style_output,
        "usage_modes": usage_modes,
        "platform_comparison": platform_comparison,
    }

    # Write JSON
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
