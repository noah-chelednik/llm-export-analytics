import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import tiktoken
except ImportError:
    tiktoken = None


def to_dt(ts: Any, use_utc: bool = True) -> Optional[datetime]:
    """Convert epoch seconds to datetime."""
    if ts is None:
        return None
    try:
        ts_f = float(ts)
        if use_utc:
            return datetime.fromtimestamp(ts_f, tz=timezone.utc)
        # local timezone naive datetime (not recommended for reproducibility)
        return datetime.fromtimestamp(ts_f)
    except Exception:
        return None


def clean_text(s: Any) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return s.strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def get_token_counter(encoding_name: str = "cl100k_base"):
    """
    Token counting is optional.
    If tiktoken is not installed, return a dummy counter.
    """
    if tiktoken is None:
        return lambda _text: 0

    enc = tiktoken.get_encoding(encoding_name)

    def count_tokens(text: str) -> int:
        try:
            return len(enc.encode(text))
        except Exception:
            return 0

    return count_tokens


def extract_text_from_message(message_obj: Dict[str, Any]) -> str:
    """
    ChatGPT export message content often looks like:
      {'content': {'parts': [...]}}
    Some parts may be dicts/lists; stringify them.
    """
    if not message_obj:
        return ""

    content = message_obj.get("content", {})
    parts = content.get("parts", None)

    if not parts:
        return ""

    out_parts: List[str] = []
    for p in parts:
        if p is None:
            continue
        if isinstance(p, str):
            out_parts.append(p)
        else:
            out_parts.append(str(p))

    return "\n".join(out_parts).strip()


def get_role(message_obj: Dict[str, Any]) -> Optional[str]:
    author = (message_obj or {}).get("author", {})
    role = author.get("role", None)
    return role


def reconstruct_main_path(mapping: Dict[str, Any], current_node_id: Optional[str] = None) -> List[str]:
    """
    Reconstruct the primary linear conversation path using parent pointers.

    Strategy:
    - If current_node_id exists and is valid, start there.
    - Else choose the leaf node with the latest create_time as the endpoint.
    - Walk parent links back to root.
    - Reverse to get chronological order.
    """
    if not mapping:
        return []

    def node_create_time(node: Dict[str, Any]) -> Optional[float]:
        msg = node.get("message") if node else None
        if not msg:
            return None
        return msg.get("create_time")

    if not current_node_id or current_node_id not in mapping:
        leaf_ids: List[str] = []
        for node_id, node in mapping.items():
            if not node:
                continue
            children = node.get("children", [])
            if not children:
                leaf_ids.append(node_id)

        candidates = leaf_ids if leaf_ids else list(mapping.keys())

        best_id = None
        best_time = None
        for cid in candidates:
            ct = node_create_time(mapping.get(cid))
            if ct is None:
                continue
            if best_time is None or ct > best_time:
                best_time = ct
                best_id = cid

        current_node_id = best_id if best_id else candidates[0]

    path: List[str] = []
    seen = set()
    nid = current_node_id
    while nid and nid in mapping and nid not in seen:
        seen.add(nid)
        path.append(nid)
        nid = mapping[nid].get("parent")

    path.reverse()
    return path


def depth_distribution(convo_sizes: pd.Series) -> Dict[str, Any]:
    total = int(convo_sizes.shape[0])

    under_10 = int((convo_sizes < 10).sum())
    between_10_29 = int(((convo_sizes >= 10) & (convo_sizes <= 29)).sum())
    between_30_99 = int(((convo_sizes >= 30) & (convo_sizes <= 99)).sum())
    over_100 = int((convo_sizes >= 100).sum())

    def pct(x: int) -> float:
        return (x / total * 100) if total else 0.0

    return {
        "total_conversations": total,
        "under_10": (under_10, pct(under_10)),
        "between_10_29": (between_10_29, pct(between_10_29)),
        "between_30_99": (between_30_99, pct(between_30_99)),
        "over_100": (over_100, pct(over_100)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract and analyze ChatGPT export data (primary path) into normalized message records."
    )
    parser.add_argument("--input", required=True, help="Path to ChatGPT conversations.json export")
    parser.add_argument("--out", default="outputs", help="Output directory (default: outputs)")
    parser.add_argument("--utc", action="store_true", help="Force UTC for date bucketing (recommended)")
    parser.add_argument("--encoding", default="cl100k_base", help="tiktoken encoding name")
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Write raw message text + counts to normalized CSV (not recommended for public sharing)",
    )

    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    token_count = get_token_counter(args.encoding)

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise SystemExit("Unexpected ChatGPT export structure: expected a JSON list of conversations.")

    rows: List[Dict[str, Any]] = []

    for conv in data:
        if not isinstance(conv, dict):
            continue

        conv_id = conv.get("id")
        mapping = conv.get("mapping", {})
        current_node = conv.get("current_node")

        if not conv_id or not isinstance(mapping, dict) or not mapping:
            continue

        path_ids = reconstruct_main_path(mapping, current_node)

        for node_id in path_ids:
            node = mapping.get(node_id)
            if not node:
                continue
            msg = node.get("message")
            if not msg or not isinstance(msg, dict):
                continue

            role = get_role(msg)
            if role not in ("user", "assistant"):
                continue

            created_dt = to_dt(msg.get("create_time"), use_utc=args.utc)
            if created_dt is None:
                continue

            text = clean_text(extract_text_from_message(msg))
            if not text:
                continue

            row: Dict[str, Any] = {
                "platform": "chatgpt",
                "conversation_id": conv_id,
                "message_id": msg.get("id", node_id),
                "role": role,
                "created": created_dt,
            }

            if args.include_content:
                row["content"] = text
                row["word_count"] = word_count(text)
                row["char_count"] = len(text)
                row["token_count"] = token_count(text)

            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No valid messages were extracted. Check the JSON path and export structure.")

    # Derived fields
    df["created"] = pd.to_datetime(df["created"], utc=args.utc, errors="coerce")
    df = df.dropna(subset=["created"])
    df["date"] = df["created"].dt.date
    df["hour"] = df["created"].dt.hour
    df["month"] = df["created"].dt.to_period("M").astype(str)

    # Write outputs
    monthly_csv = out_dir / "chatgpt_monthly_stats.csv"
    normalized_csv = out_dir / "chatgpt_messages_normalized.csv"

    msgs_per_month = df.groupby("month").size()
    convos_per_month = df.sort_values("created").drop_duplicates("conversation_id").groupby("month").size()
    summary_df = pd.DataFrame(
        {
            "messages_per_month": msgs_per_month,
            "conversations_started_per_month": convos_per_month,
        }
    )
    summary_df.to_csv(monthly_csv, index=True)

    if args.include_content:
        df.to_csv(normalized_csv, index=False)
    else:
        cols = ["platform", "conversation_id", "message_id", "role", "created", "date", "hour", "month"]
        df[cols].to_csv(normalized_csv, index=False)

    # Core metrics
    convo_stats = df.groupby("conversation_id").size()

    total_convos = int(convo_stats.count())
    total_messages = int(df.shape[0])

    user_msgs = df[df["role"] == "user"]
    assistant_msgs = df[df["role"] == "assistant"]

    unique_days = int(df["date"].nunique())

    avg_convo_length = float(convo_stats.mean())
    median_convo_length = int(convo_stats.median())
    max_convo_length = int(convo_stats.max())
    min_convo_length = int(convo_stats.min())

    deep_dives_10 = int((convo_stats >= 10).sum())
    deep_dives_20 = int((convo_stats >= 20).sum())
    deep_dives_30 = int((convo_stats >= 30).sum())

    # Activity landmarks
    msgs_per_day = df.groupby("date").size()
    most_active_day = msgs_per_day.idxmax()
    max_msgs_day = int(msgs_per_day.max())

    most_active_month = str(msgs_per_month.sort_values(ascending=False).index[0])
    most_active_month_msgs = int(msgs_per_month.sort_values(ascending=False).iloc[0])

    # Depth distribution
    depth = depth_distribution(convo_stats)

    print("ChatGPT Export Analytics (Primary Path, Per-Message Timestamps)")
    print("=" * 62)
    print(f"Total conversations: {total_convos}")
    print(f"Total messages: {total_messages}")
    print(f"Messages by user: {int(len(user_msgs))}, by assistant: {int(len(assistant_msgs))}")
    print(f"Date range: {df['created'].min().date()} to {df['created'].max().date()}")
    print(f"Unique days active: {unique_days}")

    print()
    print(f"Average conversation length: {avg_convo_length:.2f} messages")
    print(f"Median conversation length: {median_convo_length} messages")
    print(f"Max conversation length: {max_convo_length} messages")
    print(f"Min conversation length: {min_convo_length} messages")
    print(f"Conversations with 10+ messages: {deep_dives_10}")
    print(f"Conversations with 20+ messages: {deep_dives_20}")
    print(f"Conversations with 30+ messages: {deep_dives_30}")

    if args.include_content:
        print()
        print("Word and token stats")
        print("-" * 62)
        print(f"Total user words IN: {int(user_msgs['word_count'].sum())}")
        print(f"Total assistant words OUT: {int(assistant_msgs['word_count'].sum())}")
        print(f"Avg user words/message: {float(user_msgs['word_count'].mean()):.1f}" if len(user_msgs) else "Avg user words/message: 0.0")
        print(
            f"Avg assistant words/message: {float(assistant_msgs['word_count'].mean()):.1f}"
            if len(assistant_msgs)
            else "Avg assistant words/message: 0.0"
        )
        print(f"Total user tokens IN: {int(user_msgs['token_count'].sum())}")
        print(f"Total assistant tokens OUT: {int(assistant_msgs['token_count'].sum())}")
        print(f"Avg user tokens/message: {float(user_msgs['token_count'].mean()):.1f}" if len(user_msgs) else "Avg user tokens/message: 0.0")
        print(
            f"Avg assistant tokens/message: {float(assistant_msgs['token_count'].mean()):.1f}"
            if len(assistant_msgs)
            else "Avg assistant tokens/message: 0.0"
        )

        # Vocabulary (content required)
        all_words = " ".join(df["content"].astype(str)).lower()
        toks = re.findall(r"\b\w+\b", all_words)
        vocab_size = len(set(toks))
        most_common_words = Counter(toks).most_common(15)

        print()
        print(f"Vocabulary size (unique words, rough): {vocab_size}")
        print(f"Most common words: {most_common_words}")
        print(f"Most active hour ({'UTC' if args.utc else 'local'}): {int(df['hour'].value_counts().idxmax())}:00")
        print(f"Most active day: {most_active_day} ({max_msgs_day} messages)")
        print(f"Most active month: {most_active_month} ({most_active_month_msgs} messages)")
        print(f"Longest user message (words): {int(user_msgs['word_count'].max()) if len(user_msgs) else 0}")
        print(f"Longest assistant message (words): {int(assistant_msgs['word_count'].max()) if len(assistant_msgs) else 0}")

    print()
    print("Depth distribution (messages per conversation)")
    print("-" * 62)
    print(f"Under 10 messages: {depth['under_10'][0]} ({depth['under_10'][1]:.2f}%)")
    print(f"10 to 29 messages: {depth['between_10_29'][0]} ({depth['between_10_29'][1]:.2f}%)")
    print(f"30 to 99 messages: {depth['between_30_99'][0]} ({depth['between_30_99'][1]:.2f}%)")
    print(f"100+ messages: {depth['over_100'][0]} ({depth['over_100'][1]:.2f}%)")

    print()
    print(f"Monthly stats written to: {monthly_csv}")
    print(f"Normalized messages written to: {normalized_csv}")


if __name__ == "__main__":
    main()
