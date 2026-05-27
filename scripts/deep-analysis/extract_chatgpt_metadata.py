#!/usr/bin/env python3
"""Extract rich metadata from ChatGPT conversation export shards.

Reads 19 individual JSON shard files, extracts per-conversation metadata
that existing analysis scripts ignore (model slugs, tool/feature usage,
branching/regeneration, finish details, reasoning status, etc.), computes
aggregations, and writes a single JSON output.

Usage:
    python extract_chatgpt_metadata.py                    # defaults
    python extract_chatgpt_metadata.py --input-dir DIR    # custom input
    python extract_chatgpt_metadata.py --output FILE      # custom output
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_INPUT_DIR = (
    "/mnt/ai_workspace/Remembrancer/exports/"
    "61b85573cfbec86e6fc397dbfdca42f8117fe4ece43591c30e851c2fc1090356-"
    "2026-04-22-00-23-34-a5d95132b6894c289964b70e79488ade"
)
DEFAULT_OUTPUT = (
    "/mnt/ai_workspace/Remembrancer/analysis/deep-analysis/data/"
    "chatgpt_metadata.json"
)

# ── Tool / feature detection via recipient values ───────────────────────────

TOOL_RECIPIENT_MAP: dict[str, str] = {
    "web":                          "web_search",
    "web.search":                   "web_search",
    "web.run":                      "web_search",
    "web.python":                   "web_search",
    "browser":                      "web_search",
    "python":                       "code_interpreter",
    "container.exec":               "code_interpreter",
    "dalle.text2im":                "image_gen",
    "canmore.create_textdoc":       "canvas",
    "canmore.update_textdoc":       "canvas",
    "bio":                          "memory",
    "myfiles_browser":              "file_browser",
    "file_search.msearch":          "file_search",
    "file_search.mclick":           "file_search",
    "genui.run":                    "genui",
    "genui.search":                 "genui",
    "research_kickoff_tool.start_research_task": "deep_research",
}

# Content types that indicate tool/feature usage beyond plain text
CONTENT_TYPE_TOOL_MAP: dict[str, str] = {
    "code":                     "code_interpreter",
    "execution_output":         "code_interpreter",
    "tether_browsing_display":  "web_search",
    "tether_quote":             "web_search",
    "multimodal_text":          "multimodal",
    "thoughts":                 "reasoning",
    "reasoning_recap":          "reasoning",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def epoch_to_month(ts: float | None) -> str | None:
    """Convert a Unix epoch float to 'YYYY-MM', or None."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")
    except (OSError, ValueError, OverflowError):
        return None


def epoch_to_iso(ts: float | None) -> str | None:
    """Convert a Unix epoch float to ISO-8601 date string, or None."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, ValueError, OverflowError):
        return None


# ── Per-conversation extraction ─────────────────────────────────────────────

def extract_conversation(conv: dict[str, Any]) -> dict[str, Any]:
    """Return a metadata dict for one conversation object."""

    cid = conv.get("id") or conv.get("conversation_id", "")
    title = conv.get("title", "")
    create_time = conv.get("create_time")
    update_time = conv.get("update_time")
    default_model = conv.get("default_model_slug")
    gizmo_type = conv.get("gizmo_type")
    template_id = conv.get("conversation_template_id")
    is_archived = conv.get("is_archived")
    is_starred = conv.get("is_starred")

    mapping = conv.get("mapping", {})

    # Counters
    model_counter: Counter[str] = Counter()
    finish_counter: Counter[str] = Counter()
    tools_detected: set[str] = set()
    branch_points = 0
    total_nodes = len(mapping)
    assistant_msg_count = 0
    user_msg_count = 0
    system_msg_count = 0
    tool_msg_count = 0
    has_reasoning = False
    thinking_efforts: list[str] = []
    reasoning_statuses: list[str] = []

    for node in mapping.values():
        # Branching: node with more than one child
        children = node.get("children", [])
        if len(children) > 1:
            branch_points += 1

        msg = node.get("message")
        if msg is None:
            continue

        author = msg.get("author") or {}
        role = author.get("role", "")
        meta = msg.get("metadata") or {}
        content = msg.get("content") or {}
        recipient = msg.get("recipient")

        # Count messages by role
        if role == "assistant":
            assistant_msg_count += 1

            # Model slug (per-message)
            ms = meta.get("model_slug")
            if ms:
                model_counter[ms] += 1

            # Finish details
            fd = meta.get("finish_details")
            if fd and isinstance(fd, dict):
                finish_counter[fd.get("type", "unknown")] += 1

            # Reasoning / thinking
            rs = meta.get("reasoning_status")
            if rs:
                has_reasoning = True
                reasoning_statuses.append(rs)
            te = meta.get("thinking_effort")
            if te is not None:
                has_reasoning = True
                thinking_efforts.append(str(te))

        elif role == "user":
            user_msg_count += 1
        elif role == "system":
            system_msg_count += 1
        elif role == "tool":
            tool_msg_count += 1

        # Tool detection via recipient
        if recipient and recipient != "all" and recipient != "assistant":
            tool_name = TOOL_RECIPIENT_MAP.get(recipient)
            if tool_name:
                tools_detected.add(tool_name)
            else:
                # Unknown/custom action — record raw recipient prefix
                tools_detected.add(f"other:{recipient.split('.')[0]}")

        # Tool detection via content_type
        ct = content.get("content_type")
        if ct and ct != "text" and ct != "system_error":
            mapped = CONTENT_TYPE_TOOL_MAP.get(ct)
            if mapped:
                tools_detected.add(mapped)

        # Tool detection via metadata keys
        if meta.get("search_result_groups") or meta.get("search_queries"):
            tools_detected.add("web_search")
        if meta.get("image_results") or meta.get("image_gen_multi_stream"):
            tools_detected.add("image_gen")
        if meta.get("invoked_plugin"):
            plugin_info = meta["invoked_plugin"]
            if isinstance(plugin_info, dict):
                tools_detected.add(f"plugin:{plugin_info.get('namespace', 'unknown')}")
            else:
                tools_detected.add("plugin:unknown")

    month = epoch_to_month(create_time)

    return {
        "conversation_id": cid,
        "title": title,
        "create_time": create_time,
        "create_date": epoch_to_iso(create_time),
        "create_month": month,
        "update_time": update_time,
        "default_model_slug": default_model,
        "model_slugs_used": dict(model_counter),
        "gizmo_type": gizmo_type,
        "conversation_template_id": template_id,
        "is_archived": is_archived,
        "is_starred": is_starred,
        "total_nodes": total_nodes,
        "assistant_msg_count": assistant_msg_count,
        "user_msg_count": user_msg_count,
        "system_msg_count": system_msg_count,
        "tool_msg_count": tool_msg_count,
        "tools_detected": sorted(tools_detected),
        "branch_points": branch_points,
        "finish_details": dict(finish_counter),
        "has_reasoning": has_reasoning,
        "thinking_efforts": thinking_efforts if thinking_efforts else None,
        "reasoning_statuses": sorted(set(reasoning_statuses)) if reasoning_statuses else None,
    }


# ── Aggregation ─────────────────────────────────────────────────────────────

def compute_aggregations(
    per_conv: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute cross-conversation aggregate statistics."""

    # 1. Model timeline
    model_first: dict[str, float] = {}
    model_last: dict[str, float] = {}
    model_msg_count: Counter[str] = Counter()
    model_conv_set: dict[str, set[str]] = defaultdict(set)

    # 2. Monthly model distribution
    monthly_model: dict[str, Counter[str]] = defaultdict(Counter)

    # 3. Tool usage
    tool_conv_count: Counter[str] = Counter()
    tool_monthly: dict[str, Counter[str]] = defaultdict(Counter)

    # 4. Custom GPT
    custom_gpt_count = 0
    template_ids: set[str] = set()

    # 5. Branching
    convs_with_branches = 0
    total_branch_points = 0
    branch_distribution: Counter[int] = Counter()

    # 6. Finish details
    global_finish: Counter[str] = Counter()

    # 7. Reasoning
    reasoning_conv_count = 0

    for c in per_conv:
        cid = c["conversation_id"]
        month = c.get("create_month")
        ct = c.get("create_time")

        # Models
        for slug, count in c.get("model_slugs_used", {}).items():
            model_msg_count[slug] += count
            model_conv_set[slug].add(cid)
            if ct is not None:
                if slug not in model_first or ct < model_first[slug]:
                    model_first[slug] = ct
                if slug not in model_last or ct > model_last[slug]:
                    model_last[slug] = ct
            if month:
                monthly_model[month][slug] += count

        # Tools
        for tool in c.get("tools_detected", []):
            tool_conv_count[tool] += 1
            if month:
                tool_monthly[tool][month] += 1

        # Custom GPTs
        if c.get("gizmo_type") == "gpt" and c.get("conversation_template_id"):
            custom_gpt_count += 1
            template_ids.add(c["conversation_template_id"])

        # Branching
        bp = c.get("branch_points", 0)
        if bp > 0:
            convs_with_branches += 1
            total_branch_points += bp
            branch_distribution[bp] += 1

        # Finish details
        for ft, cnt in c.get("finish_details", {}).items():
            global_finish[ft] += cnt

        # Reasoning
        if c.get("has_reasoning"):
            reasoning_conv_count += 1

    # Build model_timeline dict
    model_timeline: dict[str, dict[str, Any]] = {}
    for slug in sorted(model_msg_count):
        model_timeline[slug] = {
            "first_used": epoch_to_iso(model_first.get(slug)),
            "last_used": epoch_to_iso(model_last.get(slug)),
            "msg_count": model_msg_count[slug],
            "conv_count": len(model_conv_set[slug]),
        }

    # Build monthly_model_distribution (sorted by month)
    monthly_model_dist: dict[str, dict[str, int]] = {
        m: dict(monthly_model[m].most_common())
        for m in sorted(monthly_model)
    }

    # Build tool_usage
    tool_usage: dict[str, dict[str, Any]] = {}
    for tool in sorted(tool_conv_count, key=lambda t: -tool_conv_count[t]):
        monthly = {m: tool_monthly[tool][m] for m in sorted(tool_monthly[tool])}
        tool_usage[tool] = {
            "conv_count": tool_conv_count[tool],
            "monthly": monthly,
        }

    # Custom GPT stats
    custom_gpt_stats = {
        "total_custom_gpt_conversations": custom_gpt_count,
        "unique_template_count": len(template_ids),
        "template_ids": sorted(template_ids),
    }

    # Branching stats
    branching_stats: dict[str, Any] = {
        "conversations_with_branches": convs_with_branches,
        "total_branch_points": total_branch_points,
        "distribution": {
            str(k): v
            for k, v in sorted(branch_distribution.items())
        },
    }

    # Finish details summary
    total_finish = sum(global_finish.values())
    finish_details: dict[str, Any] = {
        "counts": dict(global_finish.most_common()),
        "total": total_finish,
    }
    if total_finish > 0:
        finish_details["percentages"] = {
            ft: round(100.0 * cnt / total_finish, 2)
            for ft, cnt in global_finish.most_common()
        }

    # Reasoning stats
    reasoning_stats: dict[str, Any] = {
        "conversations_with_reasoning": reasoning_conv_count,
    }

    return {
        "model_timeline": model_timeline,
        "monthly_model_distribution": monthly_model_dist,
        "tool_usage": tool_usage,
        "custom_gpt_stats": custom_gpt_stats,
        "branching_stats": branching_stats,
        "finish_details": finish_details,
        "reasoning_stats": reasoning_stats,
    }


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract rich metadata from ChatGPT conversation export shards.",
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Directory containing conversations-NNN.json shard files.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Path for the output JSON file.",
    )
    parser.add_argument(
        "--shard-pattern",
        default="conversations-*.json",
        help="Glob pattern for shard files within --input-dir.",
    )
    args = parser.parse_args()

    shard_files = sorted(glob.glob(os.path.join(args.input_dir, args.shard_pattern)))
    if not shard_files:
        print(f"ERROR: No files matching '{args.shard_pattern}' in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(shard_files)} shard file(s) in {args.input_dir}")

    per_conversation: list[dict[str, Any]] = []
    total_convs = 0

    for i, fp in enumerate(shard_files):
        fname = os.path.basename(fp)
        print(f"  [{i + 1:>2}/{len(shard_files)}] Processing {fname} ...", end="", flush=True)
        with open(fp, "r", encoding="utf-8") as fh:
            shard: list[dict[str, Any]] = json.load(fh)

        count = 0
        for conv in shard:
            per_conversation.append(extract_conversation(conv))
            count += 1

        total_convs += count
        print(f" {count} conversations")

    print(f"\nTotal conversations processed: {total_convs}")
    print("Computing aggregations ...")

    aggregations = compute_aggregations(per_conversation)

    output = {
        "per_conversation": per_conversation,
        **aggregations,
    }

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"\nWrote {args.output} ({size_mb:.1f} MB)")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    mt = aggregations["model_timeline"]
    print(f"\nModel slugs seen: {len(mt)}")
    for slug, info in mt.items():
        print(
            f"  {slug:30s}  msgs={info['msg_count']:>5d}  "
            f"convs={info['conv_count']:>5d}  "
            f"first={info['first_used']}  last={info['last_used']}"
        )

    tu = aggregations["tool_usage"]
    print(f"\nTool/feature types detected: {len(tu)}")
    for tool, info in tu.items():
        print(f"  {tool:30s}  convs={info['conv_count']:>5d}")

    cg = aggregations["custom_gpt_stats"]
    print(
        f"\nCustom GPTs: {cg['total_custom_gpt_conversations']} conversations, "
        f"{cg['unique_template_count']} unique templates"
    )

    bs = aggregations["branching_stats"]
    print(
        f"\nBranching: {bs['conversations_with_branches']} conversations, "
        f"{bs['total_branch_points']} total branch points"
    )

    fd = aggregations["finish_details"]
    print(f"\nFinish details (total={fd['total']}):")
    for ft, pct in fd.get("percentages", {}).items():
        print(f"  {ft:20s}  {pct:>6.2f}%  ({fd['counts'][ft]})")

    rs = aggregations["reasoning_stats"]
    print(f"\nConversations with reasoning: {rs['conversations_with_reasoning']}")


if __name__ == "__main__":
    main()
