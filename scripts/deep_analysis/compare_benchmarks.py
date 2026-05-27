#!/usr/bin/env python3
"""
compare_benchmarks.py -- Compare user's POD/DLOD/POE metrics against
curated industry benchmarks.

Reads:
  - pod_results.json     (user's POD data)
  - dlod_results.json    (user's DLOD data)
  - benchmarks.json      (curated industry benchmarks)

Writes:
  - benchmark_comparison.json
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def load_json(path: Path) -> dict:
    """Read and parse a JSON file from the given path."""
    with open(path) as f:
        return json.load(f)


def compute_direct_comparisons(pod: dict, dlod: dict, bench: dict) -> list[dict]:
    """Compute metrics where user and industry data are directly comparable."""
    comparisons = []

    total_cost = pod["total_cost"]
    total_output_words = pod["overall"]["total_output_words"]

    # ── 1. Cost per deliverable ──
    deliverables_count = dlod["metadata"]["deliverables_count"]
    cost_per_deliverable = total_cost / deliverables_count if deliverables_count else 0

    # Per-project costs from dlod
    verified_projects = {
        k: v for k, v in dlod["per_project"].items() if v.get("verified")
    }
    verified_costs = [v["implied_cost"] for v in verified_projects.values()]
    avg_verified_cost = sum(verified_costs) / len(verified_costs) if verified_costs else 0

    comparisons.append({
        "metric": "Cost per deliverable",
        "industry": {
            "value": "$0.28/PR (low AI) to $89.32/PR (high AI)",
            "source": "Faros AI, March 2026 (22,000 developers)"
        },
        "user": {
            "value": (
                f"${cost_per_deliverable:.2f}/deliverable "
                f"(total ${total_cost:,.0f} / {deliverables_count} verified deliverables)"
            ),
            "cost_per_deliverable": round(cost_per_deliverable, 2),
            "avg_verified_project_cost": round(avg_verified_cost, 2),
            "per_project_detail": {
                k: {"implied_cost": v["implied_cost"], "output_words": v["output_words"]}
                for k, v in verified_projects.items()
            }
        },
        "ratio": (
            f"User cost per deliverable (${cost_per_deliverable:.2f}) vs industry low-AI ($0.28/PR) "
            f"and high-AI ($89.32/PR); deliverables are full projects, not PRs"
        ),
        "comparable": True,
        "note": (
            "Unit mismatch: industry measures cost per merged PR (a single code change); "
            "user measures cost per full deliverable (an entire published project). "
            "Deliverables encompass dozens to hundreds of PR-equivalent units of work. "
            "On a per-PR basis, the cost would be far lower."
        )
    })

    # ── 2. AI code generation share ──
    comparisons.append({
        "metric": "AI code generation share",
        "industry": {
            "value": "26.9% AI-authored (industry avg, Feb 2026); 46% (Copilot users)",
            "source": "Larridin / GitHub, 2026"
        },
        "user": {
            "value": "100% AI-generated through directed collaboration",
            "detail": "All code produced through LLM conversations with human direction"
        },
        "ratio": "User: 100% vs Industry: 26.9% = 3.72x; vs Copilot: 46% = 2.17x",
        "comparable": True,
        "note": (
            "Directly comparable on the metric of 'what share of code is AI-generated'. "
            "The directed-collaboration model is fundamentally different: 100% AI generation "
            "with human direction, not AI-assisted human coding."
        )
    })

    # ── 3. METR RCT speed impact ──
    # Derive output rate from actual data
    monthly = pod.get("monthly", {})
    months_sorted = sorted(monthly.keys())
    months_active = len(months_sorted) if months_sorted else 1
    words_per_month = total_output_words / months_active if months_active else 0
    # Approximate lines from words (rough heuristic: ~10 words per line of code/prose)
    words_per_line = 10
    lines_per_month = words_per_month / words_per_line
    lines_per_day = lines_per_month / 30 if lines_per_month else 0
    industry_lines_per_day = 125

    comparisons.append({
        "metric": "Speed impact of AI tools",
        "industry": {
            "value": "-19% (developers were 19% SLOWER with AI; believed they were 20% faster)",
            "source": "METR randomized controlled trial, July 2025"
        },
        "user": {
            "value": (
                f"~{lines_per_day:.0f} lines/day average "
                f"({total_output_words:,} output words over {months_active} months) "
                f"vs industry ~{industry_lines_per_day} lines/day "
                f"= {lines_per_day / industry_lines_per_day:.1f}x"
            ),
            "lines_per_day_estimate": round(lines_per_day, 0),
            "detail": f"{total_output_words:,} output words over {months_active} months of activity"
        },
        "ratio": (
            f"Industry: -19% (slower). "
            f"User: {lines_per_day / industry_lines_per_day:.1f}x output rate vs baseline"
        ),
        "comparable": True,
        "note": (
            "Methodological contrast. METR used an RCT; this data is observational. "
            "The directed-collaboration model (AI as primary generator, not assistant) "
            "may eliminate context-switching overhead captured in the METR RCT."
        )
    })

    # ── 4. Code churn contrast ──
    verified_count = len(verified_projects)
    comparisons.append({
        "metric": "Code churn / persistence",
        "industry": {
            "value": "861% increase in code churn under high AI adoption",
            "source": "Faros AI, March 2026"
        },
        "user": {
            "value": f"Code persists in production across {verified_count} verified deliverable(s)",
            "detail": "Code serves published/deployed deliverables rather than speculative generation"
        },
        "ratio": (
            "Industry: 861% churn increase (most AI code deleted). "
            "User: code persists in deployed projects"
        ),
        "comparable": True,
        "note": (
            "Both measure what happens to AI-generated code after creation. "
            "Industry data shows most AI code is throwaway; directed-collaboration "
            "code persists because it targets specific deliverables rather than "
            "speculative generation."
        )
    })

    return comparisons


def compute_contextual_comparisons(pod: dict, dlod: dict, bench: dict) -> list[dict]:
    """Compute metrics that provide context but are not directly comparable."""
    comparisons = []

    total_cost = pod["total_cost"]
    monthly = pod.get("monthly", {})
    months_active = len(monthly) if monthly else 1
    user_monthly = total_cost / months_active if months_active else 0

    verified_count = dlod["metadata"]["deliverables_count"]

    # ── 1. Enterprise spend context ──
    enterprise_annual = bench["enterprise_spend"]["value"]
    enterprise_monthly = bench["enterprise_spend"]["monthly"]
    user_as_pct_enterprise = (total_cost / enterprise_annual) * 100 if enterprise_annual else 0

    comparisons.append({
        "metric": "Total AI spend",
        "industry": {
            "value": f"${enterprise_annual:,.0f}/year = ${enterprise_monthly:,.0f}/month",
            "source": bench["enterprise_spend"]["source"]
        },
        "user": {
            "value": f"${total_cost:,.0f} total over {months_active} months = ${user_monthly:.0f}/month",
            "monthly_avg": round(user_monthly, 2),
            "as_pct_of_enterprise_annual": round(user_as_pct_enterprise, 2)
        },
        "ratio": (
            f"User total (${total_cost:,.0f}) over {months_active} months = "
            f"{user_as_pct_enterprise:.2f}% of one enterprise year (${enterprise_annual:,.0f})"
        ),
        "comparable": False,
        "note": (
            "NOT directly comparable. Enterprise spend covers automated pipelines, "
            "hundreds of users, and API-based infrastructure. Individual practitioner "
            "uses subscription plans. The difference reflects entirely different use "
            "patterns, not efficiency."
        )
    })

    # ── 2. Per-engineer cost ──
    per_eng_low = bench["per_engineer_token_cost"]["range_low"]
    per_eng_high = bench["per_engineer_token_cost"]["range_high"]
    ratio_low = per_eng_low / user_monthly if user_monthly else 0
    ratio_high = per_eng_high / user_monthly if user_monthly else 0

    comparisons.append({
        "metric": "Per-engineer monthly AI cost",
        "industry": {
            "value": f"${per_eng_low:,}-${per_eng_high:,}/month",
            "source": bench["per_engineer_token_cost"]["source"]
        },
        "user": {
            "value": f"${user_monthly:.0f}/month average",
            "monthly_avg": round(user_monthly, 2)
        },
        "ratio": f"Industry is {ratio_low:.0f}-{ratio_high:.0f}x more expensive per month",
        "comparable": False,
        "note": (
            "Comparable on cost INPUT (both measure what one person spends on AI tools), "
            "but NOT on cost OUTPUT. Industry per-engineer costs include API tokens for "
            "automated workflows; user cost is subscription-only."
        )
    })

    # ── 3. Copilot productivity ──
    comparisons.append({
        "metric": "Copilot productivity claim",
        "industry": {
            "value": "55% faster task completion at $19/month (Business tier)",
            "source": bench["copilot_speed"]["source"]
        },
        "user": {
            "value": (
                f"POD = {pod['overall']['pod_words']:.1f} words/dollar; "
                f"total output = {pod['overall']['total_output_words']:,} words"
            ),
            "pod_words": pod["overall"]["pod_words"]
        },
        "ratio": (
            "Cannot compute -- Copilot measures speed improvement (%), "
            "POD measures output-per-dollar (words/$). Different units."
        ),
        "comparable": False,
        "note": (
            "Copilot's 55% is a SPEED metric (same task, less time). POD is an OUTPUT "
            "metric (words produced per dollar). To make these comparable, we would need "
            "baseline output per Copilot user in words/month, which is not reported."
        )
    })

    # ── 4. HBS GPT-4 study ──
    comparisons.append({
        "metric": "HBS GPT-4 quality/speed study",
        "industry": {
            "value": "25.1% faster, 40% higher quality ratings",
            "source": bench["hbs_gpt4_study"]["source"]
        },
        "user": {
            "value": f"Quality measured by verified deliverables: {verified_count} verified deliverable(s)",
            "verified_deliverables": verified_count
        },
        "ratio": (
            "Cannot compute -- HBS measures % improvement on controlled tasks; "
            "quality here is measured by publication/deployment (binary: published or not)"
        ),
        "comparable": False,
        "note": (
            "Different quality metrics. HBS used blind ratings of consultant output "
            "on defined tasks. User quality is measured by real-world acceptance: "
            "published/deployed deliverables. Both suggest AI improves quality, but "
            "through incompatible measurement frameworks."
        )
    })

    # ── 5. AI code vulnerabilities ──
    comparisons.append({
        "metric": "AI code vulnerability rate",
        "industry": {
            "value": "2.74x more vulnerabilities in AI-generated code; 45% fail security tests",
            "source": bench["ai_code_vulnerabilities"]["source"]
        },
        "user": {
            "value": "No security audit data available",
        },
        "ratio": "Cannot compute -- no vulnerability data for user codebase",
        "comparable": False,
        "note": (
            "An important caveat for 100% AI-generated code claims. Industry data shows "
            "AI code has significantly more vulnerabilities. Without a security audit, "
            "this risk factor is unquantified."
        )
    })

    # ── 6. Nvidia VP quote (qualitative) ──
    comparisons.append({
        "metric": "Compute cost vs employee cost",
        "industry": {
            "value": bench["nvidia_vp_quote"]["quote"],
            "source": f"{bench['nvidia_vp_quote']['source']}, {bench['nvidia_vp_quote']['date']}"
        },
        "user": {
            "value": (
                f"AI compute cost: ${total_cost:,} over {months_active} months. "
                f"Solo practitioner -- compute cost is a fraction of equivalent labor cost."
            )
        },
        "ratio": (
            f"Directionally opposite: Nvidia's compute exceeds employee cost; "
            f"user's compute (${total_cost:,}) is negligible compared to equivalent labor"
        ),
        "comparable": False,
        "note": (
            "Qualitative contrast. At enterprise scale (Nvidia), AI compute dominates "
            "budgets. At individual practitioner scale, AI subscriptions are trivial. "
            "This highlights the scale-dependent economics of AI adoption."
        )
    })

    return comparisons


def compute_anti_efficiency_contrast(pod: dict, dlod: dict, bench: dict) -> dict:
    """Compute the tokenmaxxing anti-efficiency contrast."""
    # Tokenmaxxing efficiency ratio: 2x throughput at 10x cost = 0.2x
    tokenmaxxing_efficiency = 2.0 / 10.0  # 0.2x

    # User efficiency trend: compare early vs late periods
    monthly = pod["monthly"]
    months_sorted = sorted(monthly.keys())

    # Split into early (first 12 months) and late (last 12 months)
    n_early = min(12, len(months_sorted) // 2) or 1
    n_late = min(12, len(months_sorted) // 2) or 1
    early_months = months_sorted[:n_early]
    late_months = months_sorted[-n_late:]

    early_output = sum(monthly[m]["output_words"] for m in early_months)
    early_cost = sum(monthly[m]["cost"] for m in early_months)
    late_output = sum(monthly[m]["output_words"] for m in late_months)
    late_cost = sum(monthly[m]["cost"] for m in late_months)

    early_efficiency = early_output / early_cost if early_cost else 0
    late_efficiency = late_output / late_cost if late_cost else 0

    output_growth = late_output / early_output if early_output else 0
    cost_growth = late_cost / early_cost if early_cost else 0
    user_efficiency_ratio = output_growth / cost_growth if cost_growth else 0

    total_output_words = pod["overall"]["total_output_words"]
    verified_count = len([v for v in dlod["per_project"].values() if v.get("verified")])

    return {
        "tokenmaxxing": {
            "throughput_gain": "2x",
            "cost_increase": "10x",
            "efficiency_ratio": tokenmaxxing_efficiency,
            "interpretation": (
                "For every dollar spent, tokenmaxxing produces "
                "0.2x the output of the pre-AI baseline"
            ),
            "code_churn": "861% increase -- most AI-generated code is deleted",
            "source": "Faros AI, March 2026"
        },
        "user": {
            "early_period": {
                "months": f"{early_months[0]} to {early_months[-1]}",
                "total_output_words": early_output,
                "total_cost": early_cost,
                "words_per_dollar": round(early_efficiency, 1)
            },
            "late_period": {
                "months": f"{late_months[0]} to {late_months[-1]}",
                "total_output_words": late_output,
                "total_cost": late_cost,
                "words_per_dollar": round(late_efficiency, 1)
            },
            "output_growth_ratio": round(output_growth, 2),
            "cost_growth_ratio": round(cost_growth, 2),
            "efficiency_ratio": round(user_efficiency_ratio, 2),
            "interpretation": (
                f"Output grew {output_growth:.1f}x while cost grew "
                f"{cost_growth:.1f}x = {user_efficiency_ratio:.2f}x efficiency ratio"
            )
        },
        "contrast": {
            "tokenmaxxing_efficiency": tokenmaxxing_efficiency,
            "user_efficiency": round(user_efficiency_ratio, 2),
            "ratio": (
                f"User efficiency ratio ({user_efficiency_ratio:.2f}x) vs tokenmaxxing "
                f"(0.20x) = {user_efficiency_ratio / tokenmaxxing_efficiency:.1f}x better"
            ),
            "key_difference": (
                "Tokenmaxxing treats AI as a volume tool (generate more, delete more). "
                "Directed collaboration treats AI as a production tool (generate what is "
                "needed, keep what is produced)."
            )
        },
        "code_persistence": {
            "industry": "861% code churn -- most AI code deleted shortly after generation",
            "user": (
                f"{total_output_words:,} output words across {verified_count} "
                f"verified deliverable(s); code serves deployed deliverables"
            ),
            "interpretation": (
                "The anti-efficiency of tokenmaxxing is driven by waste: generating "
                "code that gets thrown away. The directed-collaboration model avoids "
                "this by targeting specific, pre-planned deliverables."
            )
        }
    }


def build_summary_table(direct: list[dict], contextual: list[dict], anti_eff: dict) -> list[dict]:
    """Build a flat summary table combining direct, contextual, and anti-efficiency rows."""
    table = []

    for comp in direct:
        industry_val = comp["industry"]["value"]
        user_val = comp["user"]["value"]
        table.append({
            "metric": comp["metric"],
            "industry": industry_val,
            "user": user_val,
            "comparable": True,
            "note": comp["note"]
        })

    for comp in contextual:
        industry_val = comp["industry"]["value"]
        user_val = comp["user"]["value"]
        table.append({
            "metric": comp["metric"],
            "industry": industry_val,
            "user": user_val,
            "comparable": False,
            "note": comp["note"]
        })

    # Anti-efficiency summary row
    table.append({
        "metric": "Efficiency ratio (output growth / cost growth)",
        "industry": "0.20x (tokenmaxxing: 2x throughput at 10x cost)",
        "user": f"{anti_eff['user']['efficiency_ratio']}x ({anti_eff['user']['interpretation']})",
        "comparable": True,
        "note": (
            "Both measure how efficiency scales with AI spending. Tokenmaxxing shows "
            "diminishing returns; directed collaboration shows whether output scales with cost."
        )
    })

    return table


def print_summary_table(table: list[dict]) -> None:
    """Print a formatted summary table to stdout."""
    print("=" * 120)
    print("BENCHMARK COMPARISON: User AI Practice vs Industry Data")
    print("=" * 120)
    print()

    # Direct comparisons
    print("DIRECT COMPARISONS (comparable=true)")
    print("-" * 120)
    direct = [r for r in table if r["comparable"]]
    for i, row in enumerate(direct, 1):
        print(f"\n  {i}. {row['metric']}")
        print(f"     Industry : {row['industry']}")
        print(f"     User     : {row['user']}")
        print(f"     Note     : {row['note']}")

    print()
    print()

    # Contextual comparisons
    print("CONTEXTUAL COMPARISONS (comparable=false, for context only)")
    print("-" * 120)
    contextual = [r for r in table if not r["comparable"]]
    for i, row in enumerate(contextual, 1):
        print(f"\n  {i}. {row['metric']}")
        print(f"     Industry : {row['industry']}")
        print(f"     User     : {row['user']}")
        print(f"     Note     : {row['note']}")

    print()
    print("=" * 120)


def main() -> None:
    """Compare user POD/DLOD metrics against curated industry benchmarks and write results."""
    parser = argparse.ArgumentParser(
        description="Compare user's POD/DLOD/POE metrics against industry benchmarks."
    )
    parser.add_argument(
        "--pod",
        required=True,
        help="Path to pod_results.json",
    )
    parser.add_argument(
        "--dlod",
        required=True,
        help="Path to dlod_results.json",
    )
    parser.add_argument(
        "--benchmarks",
        required=True,
        help="Path to benchmarks.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write benchmark_comparison.json",
    )
    args = parser.parse_args()

    # Load data
    pod = load_json(Path(args.pod))
    dlod = load_json(Path(args.dlod))
    bench = load_json(Path(args.benchmarks))

    # Compute comparisons
    direct = compute_direct_comparisons(pod, dlod, bench)
    contextual = compute_contextual_comparisons(pod, dlod, bench)
    anti_eff = compute_anti_efficiency_contrast(pod, dlod, bench)
    summary = build_summary_table(direct, contextual, anti_eff)

    # Build output
    result = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "pod_source": args.pod,
            "dlod_source": args.dlod,
            "benchmarks_source": args.benchmarks,
            "methodology_note": (
                "Comparisons are classified as 'direct' (comparable=true) only when "
                "both industry and user data measure the same unit or a closely analogous "
                "metric at the individual-practitioner level. All other comparisons are "
                "'contextual' (comparable=false) and are included for framing, not for "
                "ratio claims."
            )
        },
        "direct_comparisons": direct,
        "contextual_comparisons": contextual,
        "anti_efficiency_contrast": anti_eff,
        "summary_table": summary,
    }

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote benchmark comparison to {out_path}\n")

    # Print summary
    print_summary_table(summary)


if __name__ == "__main__":
    main()
