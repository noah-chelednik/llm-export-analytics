#!/usr/bin/env python3
"""
compute_pod.py — Productive Output per Dollar (POD) metric computation.

POD = total assistant output words (or tokens) / total subscription cost.

Reads normalized message CSVs, subscription cost log, and topic classifications
to produce overall, per-platform, monthly, per-domain, and modality-split POD
metrics.
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Some message content fields are very large (e.g. pasted documents)
csv.field_size_limit(sys.maxsize)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def months_in_range(start_str: str, end_str: str) -> list[str]:
    """Return list of 'YYYY-MM' strings from start to end inclusive."""
    start = datetime.strptime(start_str, "%Y-%m")
    end = datetime.strptime(end_str, "%Y-%m")
    months = []
    cur = start
    while cur <= end:
        months.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def safe_int(val: object, default: int = 0) -> int:
    """Parse an int from a CSV field, returning default on failure."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_float(val: object, default: float = 0.0) -> float:
    """Parse a float from a CSV field, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def looks_agentic(content: str, word_count: int, msg_count_in_conv: int) -> bool:
    """Heuristic: does a message look like it came from an agentic/code session?"""
    if not content:
        return False
    # File-path patterns
    path_pattern = re.compile(r'(/mnt/|/home/|/usr/|/tmp/|/var/|/etc/|C:\\|\.py\b|\.ts\b|\.js\b|\.json\b)')
    path_hits = len(path_pattern.findall(content))
    # Code fences
    fence_count = content.count("```")
    # High density of code indicators
    if path_hits >= 3 or fence_count >= 4:
        return True
    if msg_count_in_conv >= 50 and (path_hits >= 1 or fence_count >= 2):
        return True
    return False


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_messages(csv_path: str, platform_label: str) -> list[dict]:
    """Load a normalized messages CSV. Returns list of row dicts."""
    print(f"  Loading {platform_label} messages from {csv_path} ...")
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["_platform"] = platform_label
            rows.append(row)
    print(f"    -> {len(rows):,} rows")
    return rows


def load_cost_log(path: str) -> list[dict]:
    """Load the subscription cost log from a JSON file."""
    print(f"  Loading cost log from {path} ...")
    with open(path, "r") as f:
        data = json.load(f)
    print(f"    -> {len(data)} subscription entries")
    return data


def load_classifications(path: str) -> dict:
    """Returns mapping of conversation_id -> list of category strings."""
    print(f"  Loading classifications from {path} ...")
    with open(path, "r") as f:
        data = json.load(f)
    conv_topics = {}
    for entry in data.get("per_conversation", []):
        cid = entry["conversation_id"]
        cats = [t["category"] for t in entry.get("topics", [])]
        conv_topics[cid] = cats if cats else ["Uncategorized"]
    print(f"    -> {len(conv_topics):,} conversations classified")
    return conv_topics


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def compute_costs(cost_log: list[dict]) -> dict:
    """Compute total cost and per-platform per-month cost allocation."""
    # Build month -> [(platform, monthly_cost)] mapping
    month_subs = defaultdict(list)
    detail = []

    for entry in cost_log:
        m_list = months_in_range(entry["start"], entry["end"])
        total = entry["monthly_cost"] * len(m_list)
        detail.append({**entry, "months_count": len(m_list), "total": total})
        for m in m_list:
            month_subs[m].append((entry["platform"], entry["monthly_cost"]))

    # Per-month cost (simple: just sum all subscriptions active that month)
    per_month = {}
    for m in sorted(month_subs.keys()):
        per_month[m] = {}
        for platform, cost in month_subs[m]:
            per_month[m][platform] = per_month[m].get(platform, 0) + cost

    total_cost = sum(cost for m in per_month.values() for cost in m.values())
    per_platform_total = defaultdict(float)
    for m_costs in per_month.values():
        for plat, cost in m_costs.items():
            per_platform_total[plat] += cost

    return {
        "total_cost": total_cost,
        "per_month": per_month,
        "per_platform_total": dict(per_platform_total),
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_pod(
    chatgpt_csv: str,
    claude_csv: str,
    cost_log_path: str,
    classifications_path: str,
    output_path: str,
) -> dict:
    """Compute overall, per-platform, monthly, and per-domain POD metrics."""
    print("=" * 60)
    print("POD (Productive Output per Dollar) Computation")
    print("=" * 60)

    # ---- Load data ----
    print("\n[1/6] Loading data...")
    chatgpt_msgs = load_messages(chatgpt_csv, "chatgpt")
    claude_msgs = load_messages(claude_csv, "claude")
    cost_log = load_cost_log(cost_log_path)
    conv_topics = load_classifications(classifications_path)

    all_msgs = chatgpt_msgs + claude_msgs

    # ---- Cost computation ----
    print("\n[2/6] Computing costs...")
    costs = compute_costs(cost_log)
    total_cost = costs["total_cost"]
    print(f"  Total subscription cost: ${total_cost:,.0f}")
    for plat, plat_cost in costs["per_platform_total"].items():
        print(f"    {plat}: ${plat_cost:,.0f}")

    # ---- Aggregate message stats ----
    print("\n[3/6] Aggregating message statistics...")

    # Overall and per-platform
    stats = {
        "overall": {"assistant": defaultdict(int), "user": defaultdict(int)},
        "chatgpt": {"assistant": defaultdict(int), "user": defaultdict(int)},
        "claude": {"assistant": defaultdict(int), "user": defaultdict(int)},
    }

    # Monthly stats: month -> platform -> role -> {words, tokens, chars, count}
    monthly = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    # Per-conversation stats (for domain and modality)
    conv_stats = defaultdict(lambda: {
        "platform": None,
        "assistant_words": 0, "assistant_tokens": 0,
        "user_words": 0, "user_tokens": 0,
        "msg_count": 0,
        "months": set(),
        "agentic_signals": 0,
        "total_signals_checked": 0,
    })

    for row in all_msgs:
        platform = row.get("_platform", row.get("platform", "unknown"))
        role = row.get("role", "")
        wc = safe_int(row.get("word_count"))
        tc = safe_int(row.get("token_count"))
        cc = safe_int(row.get("char_count"))
        month = row.get("month", "")
        cid = row.get("conversation_id", "")
        content = row.get("content", "") or ""

        if role in ("assistant", "user"):
            bucket = "assistant" if role == "assistant" else "user"
            stats["overall"][bucket]["words"] += wc
            stats["overall"][bucket]["tokens"] += tc
            stats["overall"][bucket]["chars"] += cc
            stats["overall"][bucket]["count"] += 1

            stats[platform][bucket]["words"] += wc
            stats[platform][bucket]["tokens"] += tc
            stats[platform][bucket]["chars"] += cc
            stats[platform][bucket]["count"] += 1

            if month:
                monthly[month][platform][bucket]["words"] += wc
                monthly[month][platform][bucket]["tokens"] += tc
                monthly[month][platform][bucket]["count"] += 1

            # Conversation-level tracking
            if cid:
                cs = conv_stats[cid]
                cs["platform"] = platform
                cs["msg_count"] += 1
                if month:
                    cs["months"].add(month)
                if bucket == "assistant":
                    cs["assistant_words"] += wc
                    cs["assistant_tokens"] += tc
                    # Agentic heuristic (only check assistant messages)
                    cs["total_signals_checked"] += 1
                    if looks_agentic(content, wc, 0):  # msg_count checked later
                        cs["agentic_signals"] += 1
                else:
                    cs["user_words"] += wc
                    cs["user_tokens"] += tc

    # ---- Overall POD ----
    print("\n[4/6] Computing POD metrics...")

    total_out_words = stats["overall"]["assistant"]["words"]
    total_out_tokens = stats["overall"]["assistant"]["tokens"]
    total_in_words = stats["overall"]["user"]["words"]
    total_in_tokens = stats["overall"]["user"]["tokens"]

    pod_words = total_out_words / total_cost if total_cost else 0
    pod_tokens = total_out_tokens / total_cost if total_cost else 0
    leverage = total_out_words / total_in_words if total_in_words else 0

    print(f"  Overall POD (words):  {pod_words:,.1f} words/$")
    print(f"  Overall POD (tokens): {pod_tokens:,.1f} tokens/$")
    print(f"  Leverage ratio:       {leverage:.2f}x")
    print(f"  Total output words:   {total_out_words:,}")
    print(f"  Total output tokens:  {total_out_tokens:,}")
    print(f"  Total input words:    {total_in_words:,}")
    print(f"  Total input tokens:   {total_in_tokens:,}")

    overall = {
        "pod_words": round(pod_words, 1),
        "pod_tokens": round(pod_tokens, 1),
        "total_output_words": total_out_words,
        "total_output_tokens": total_out_tokens,
        "total_input_words": total_in_words,
        "total_input_tokens": total_in_tokens,
        "leverage_ratio": round(leverage, 2),
    }

    # ---- Per-platform POD ----
    per_platform = {}
    for plat in ("chatgpt", "claude"):
        plat_cost = costs["per_platform_total"].get(plat, 0)
        plat_out_w = stats[plat]["assistant"]["words"]
        plat_out_t = stats[plat]["assistant"]["tokens"]
        plat_in_w = stats[plat]["user"]["words"]
        plat_in_t = stats[plat]["user"]["tokens"]
        plat_pod_w = plat_out_w / plat_cost if plat_cost else 0
        plat_pod_t = plat_out_t / plat_cost if plat_cost else 0
        plat_lev = plat_out_w / plat_in_w if plat_in_w else 0

        per_platform[plat] = {
            "pod_words": round(plat_pod_w, 1),
            "pod_tokens": round(plat_pod_t, 1),
            "cost_allocated": plat_cost,
            "output_words": plat_out_w,
            "output_tokens": plat_out_t,
            "input_words": plat_in_w,
            "input_tokens": plat_in_t,
            "leverage_ratio": round(plat_lev, 2),
            "assistant_messages": stats[plat]["assistant"]["count"],
            "user_messages": stats[plat]["user"]["count"],
        }
        print(f"\n  {plat.upper()}:")
        print(f"    Cost: ${plat_cost:,.0f}  |  POD(w): {plat_pod_w:,.1f}  |  POD(t): {plat_pod_t:,.1f}  |  Leverage: {plat_lev:.2f}x")

    # ---- Monthly POD ----
    print("\n[5/6] Computing monthly POD...")
    monthly_results = {}
    for m in sorted(monthly.keys()):
        m_cost = sum(costs["per_month"].get(m, {}).values())
        m_out_w = sum(monthly[m][p]["assistant"]["words"] for p in monthly[m])
        m_out_t = sum(monthly[m][p]["assistant"]["tokens"] for p in monthly[m])
        m_in_w = sum(monthly[m][p]["user"]["words"] for p in monthly[m])
        m_in_t = sum(monthly[m][p]["user"]["tokens"] for p in monthly[m])
        m_asst_count = sum(monthly[m][p]["assistant"]["count"] for p in monthly[m])
        m_user_count = sum(monthly[m][p]["user"]["count"] for p in monthly[m])
        m_pod_w = m_out_w / m_cost if m_cost else 0
        m_pod_t = m_out_t / m_cost if m_cost else 0
        m_lev = m_out_w / m_in_w if m_in_w else 0

        monthly_results[m] = {
            "pod_words": round(m_pod_w, 1),
            "pod_tokens": round(m_pod_t, 1),
            "cost": m_cost,
            "output_words": m_out_w,
            "output_tokens": m_out_t,
            "input_words": m_in_w,
            "input_tokens": m_in_t,
            "leverage_ratio": round(m_lev, 2),
            "assistant_messages": m_asst_count,
            "user_messages": m_user_count,
            "platforms_active": list(costs["per_month"].get(m, {}).keys()),
        }

    # Print a compact trajectory
    print(f"  {'Month':<10} {'Cost':>7} {'Out Words':>12} {'POD(w)':>10} {'Leverage':>10}")
    print(f"  {'-'*10} {'-'*7} {'-'*12} {'-'*10} {'-'*10}")
    for m in sorted(monthly_results.keys()):
        r = monthly_results[m]
        print(f"  {m:<10} ${r['cost']:>5,.0f} {r['output_words']:>12,} {r['pod_words']:>10,.1f} {r['leverage_ratio']:>10.2f}x")

    # ---- Per-domain POD ----
    print("\n[6/6] Computing per-domain POD...")

    # Aggregate per domain
    domain_stats = defaultdict(lambda: {
        "output_words": 0, "output_tokens": 0,
        "input_words": 0, "input_tokens": 0,
        "conversations": 0, "messages": 0,
        "months": set(),
    })

    classified_count = 0
    unclassified_count = 0

    for cid, cs in conv_stats.items():
        cats = conv_topics.get(cid, ["Uncategorized"])
        if cats == ["Uncategorized"]:
            unclassified_count += 1
        else:
            classified_count += 1

        # Distribute conversation stats equally among its categories
        weight = 1.0 / len(cats) if cats else 1.0
        for cat in cats:
            ds = domain_stats[cat]
            ds["output_words"] += int(cs["assistant_words"] * weight)
            ds["output_tokens"] += int(cs["assistant_tokens"] * weight)
            ds["input_words"] += int(cs["user_words"] * weight)
            ds["input_tokens"] += int(cs["user_tokens"] * weight)
            ds["conversations"] += 1  # count full, not weighted
            ds["messages"] += cs["msg_count"]
            ds["months"].update(cs["months"])

    # Compute per-domain POD using proportional cost allocation
    total_domain_out_words = sum(ds["output_words"] for ds in domain_stats.values())

    per_domain = {}
    for cat in sorted(domain_stats.keys()):
        ds = domain_stats[cat]
        # Allocate cost proportional to output words
        cost_share = (ds["output_words"] / total_domain_out_words * total_cost) if total_domain_out_words else 0
        pod_w = ds["output_words"] / cost_share if cost_share else 0
        pod_t = ds["output_tokens"] / cost_share if cost_share else 0
        lev = ds["output_words"] / ds["input_words"] if ds["input_words"] else 0

        per_domain[cat] = {
            "pod_words": round(pod_w, 1),
            "pod_tokens": round(pod_t, 1),
            "output_words": ds["output_words"],
            "output_tokens": ds["output_tokens"],
            "input_words": ds["input_words"],
            "input_tokens": ds["input_tokens"],
            "conversations": ds["conversations"],
            "messages": ds["messages"],
            "cost_allocated": round(cost_share, 2),
            "share_of_output": round(ds["output_words"] / total_domain_out_words * 100, 2) if total_domain_out_words else 0,
            "leverage_ratio": round(lev, 2),
        }

    print(f"  Classified: {classified_count:,}  |  Unclassified: {unclassified_count:,}")
    print(f"\n  {'Category':<28} {'Out Words':>12} {'Cost':>9} {'POD(w)':>10} {'Convs':>7} {'Leverage':>10}")
    print(f"  {'-'*28} {'-'*12} {'-'*9} {'-'*10} {'-'*7} {'-'*10}")
    for cat in sorted(per_domain.keys(), key=lambda c: per_domain[c]["output_words"], reverse=True):
        d = per_domain[cat]
        print(f"  {cat:<28} {d['output_words']:>12,} ${d['cost_allocated']:>7,.0f} {d['pod_words']:>10,.1f} {d['conversations']:>7,} {d['leverage_ratio']:>10.2f}x")

    # ---- Modality split (conversational vs agentic) ----
    print("\n  Computing modality split (estimated from CSV patterns)...")

    # Refine agentic classification at conversation level
    agentic_words = 0
    agentic_tokens = 0
    agentic_in_words = 0
    agentic_in_tokens = 0
    agentic_convs = 0

    conv_words = 0
    conv_tokens = 0
    conv_in_words = 0
    conv_in_tokens = 0
    conv_convs = 0

    for cid, cs in conv_stats.items():
        # Determine if conversation is likely agentic
        is_agentic = False

        # Strong signal: Claude from Dec 2025+ with high message count
        if cs["platform"] == "claude":
            conv_months = cs["months"]
            has_late_months = any(m >= "2025-12" for m in conv_months)
            if has_late_months and cs["msg_count"] >= 50:
                is_agentic = True

        # Content-based signal: majority of assistant messages look agentic
        if cs["total_signals_checked"] > 0:
            agentic_ratio = cs["agentic_signals"] / cs["total_signals_checked"]
            if agentic_ratio >= 0.3 and cs["msg_count"] >= 10:
                is_agentic = True

        if is_agentic:
            agentic_words += cs["assistant_words"]
            agentic_tokens += cs["assistant_tokens"]
            agentic_in_words += cs["user_words"]
            agentic_in_tokens += cs["user_tokens"]
            agentic_convs += 1
        else:
            conv_words += cs["assistant_words"]
            conv_tokens += cs["assistant_tokens"]
            conv_in_words += cs["user_words"]
            conv_in_tokens += cs["user_tokens"]
            conv_convs += 1

    # For cost allocation in modality, use proportional split
    total_modality_out = agentic_words + conv_words
    agentic_cost_share = (agentic_words / total_modality_out * total_cost) if total_modality_out else 0
    conv_cost_share = (conv_words / total_modality_out * total_cost) if total_modality_out else 0

    modality_split = {
        "method": "estimated from CSV patterns (file paths, code fences, message count, date heuristics)",
        "note": "Modality classification is a heuristic estimate, not a measured value. "
                "True agentic sessions (Claude Code / tool_use) cannot be reliably identified from normalized CSVs alone.",
        "conversational": {
            "pod_words": round(conv_words / conv_cost_share, 1) if conv_cost_share else 0,
            "pod_tokens": round(conv_tokens / conv_cost_share, 1) if conv_cost_share else 0,
            "output_words": conv_words,
            "output_tokens": conv_tokens,
            "input_words": conv_in_words,
            "input_tokens": conv_in_tokens,
            "cost_allocated": round(conv_cost_share, 2),
            "conversations": conv_convs,
            "leverage_ratio": round(conv_words / conv_in_words, 2) if conv_in_words else 0,
        },
        "agentic_estimated": {
            "pod_words": round(agentic_words / agentic_cost_share, 1) if agentic_cost_share else 0,
            "pod_tokens": round(agentic_tokens / agentic_cost_share, 1) if agentic_cost_share else 0,
            "output_words": agentic_words,
            "output_tokens": agentic_tokens,
            "input_words": agentic_in_words,
            "input_tokens": agentic_in_tokens,
            "cost_allocated": round(agentic_cost_share, 2),
            "conversations": agentic_convs,
            "leverage_ratio": round(agentic_words / agentic_in_words, 2) if agentic_in_words else 0,
        },
    }

    print(f"    Conversational: {conv_convs:,} convs, {conv_words:,} output words")
    print(f"    Agentic (est.): {agentic_convs:,} convs, {agentic_words:,} output words")

    # ---- Build cost breakdown for output ----
    cost_breakdown = {
        "subscriptions": costs["detail"],
        "per_platform_total": costs["per_platform_total"],
        "per_month": {m: dict(v) for m, v in costs["per_month"].items()},
    }

    # ---- Assemble final results ----
    results = {
        "total_cost": total_cost,
        "cost_breakdown": cost_breakdown,
        "overall": overall,
        "per_platform": per_platform,
        "monthly": monthly_results,
        "per_domain": per_domain,
        "modality_split": modality_split,
    }

    # ---- Write output ----
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n{'=' * 60}")
    print(f"Results written to {output_path}")
    print(f"{'=' * 60}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the POD computation pipeline."""
    base = "/mnt/ai_workspace/Remembrancer"

    parser = argparse.ArgumentParser(
        description="Compute Productive Output per Dollar (POD) metric."
    )
    parser.add_argument(
        "--chatgpt-csv",
        default=f"{base}/analysis/latest-run/chatgpt_messages_normalized.csv",
        help="Path to ChatGPT normalized messages CSV",
    )
    parser.add_argument(
        "--claude-csv",
        default=f"{base}/analysis/latest-run/claude_messages_normalized.csv",
        help="Path to Claude normalized messages CSV",
    )
    parser.add_argument(
        "--cost-log",
        default=f"{base}/analysis/deep-analysis/data/cost_log.json",
        help="Path to subscription cost log JSON",
    )
    parser.add_argument(
        "--classifications",
        default=f"{base}/analysis/deep-analysis/data/classifications_and_projects.json",
        help="Path to conversation classifications JSON",
    )
    parser.add_argument(
        "--output",
        default=f"{base}/analysis/deep-analysis/data/pod_results.json",
        help="Path to write POD results JSON",
    )

    args = parser.parse_args()

    compute_pod(
        chatgpt_csv=args.chatgpt_csv,
        claude_csv=args.claude_csv,
        cost_log_path=args.cost_log,
        classifications_path=args.classifications,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
