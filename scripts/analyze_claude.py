import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    import tiktoken
except ImportError:
    tiktoken = None


def parse_iso_z(s: Any, use_utc: bool = True) -> Optional[datetime]:
    """Parse timestamps like 2025-10-21T00:42:03.397014Z into datetime."""
    if not s or not isinstance(s, str):
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if use_utc:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
        return dt
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


def normalize_role(sender: Any) -> Optional[str]:
    """Claude uses sender=human or sender=assistant. Normalize to user/assistant."""
    if not sender:
        return None
    s = str(sender).lower()
    if s == "human":
        return "user"
    if s == "assistant":
        return "assistant"
    return s


def extract_text_from_blocks(msg_obj: Dict[str, Any]) -> str:
    """
    Claude message format:
      - content: list of blocks
      - text blocks have type="text" and text="..."
    Concatenate only text blocks in order, separated by newline.
    Fallback to msg_obj["text"] if content blocks missing.
    """
    if not msg_obj:
        return ""

    blocks = msg_obj.get("content", None)
    out_parts: List[str] = []

    if isinstance(blocks, list) and blocks:
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                t = clean_text(b.get("text", ""))
                if t:
                    out_parts.append(t)

    if out_parts:
        return "\n".join(out_parts).strip()

    return clean_text(msg_obj.get("text", ""))


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
        description="Extract and analyze Claude export data (text blocks only) into normalized message records."
    )
    parser.add_argument("--input", required=True, help="Path to Claude conversations.json export")
    parser.add_argument("--out", default="outputs", help="Output directory (default: outputs)")
    parser.add_argument("--utc", action="store_true", help="Force UTC for date bucketing (recommended)")
    parser.add_argument("--encoding", default="cl100k_base", help="tiktoken encoding name")
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Write raw message text to normalized CSV (not recommended for public sharing)",
    )

    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    token_count = get_token_counter(args.encoding)

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise SystemExit("Unexpected Claude export structure: expected a JSON list of conversations.")

    rows: List[Dict[str, Any]] = []

    for conv in data:
        if not isinstance(conv, dict):
            continue

        conv_id = conv.get("uuid")
        msgs = conv.get("chat_messages", [])

        if not conv_id or not isinstance(msgs, list) or not msgs:
            continue

        for m in msgs:
            if not isinstance(m, dict):
                continue

            role = normalize_role(m.get("sender"))
            if role not in ("user", "assistant"):
                continue

            created_dt = parse_iso_z(m.get("created_at"), use_utc=args.utc)
            if created_dt is None:
                continue

            text = clean_text(extract_text_from_blocks(m))
            if not text:
                continue

            row = {
                "platform": "claude",
                "conversation_id": conv_id,
                "message_id": m.get("uuid"),
                "role": role,
                "created": created_dt,
            }

            if args.include_content:
                row["content"] = text
                row["word_count"] = word_count(text)
                row["char_count"] = len(text)
                row["token_count"] = token_count(text)
            else:
                # Still allow combined analysis later if you want, but keep privacy-first default.
                # You can recompute counts later if you choose to export content.
                pass

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
    monthly_csv = out_dir / "claude_monthly_stats.csv"
    normalized_csv = out_dir / "claude_messages_normalized.csv"

    # Monthly stats
    msgs_per_month = df.groupby("month").size()
    convos_per_month = df.sort_values("created").drop_duplicates("conversation_id").groupby("month").size()
    summary_df = pd.DataFrame(
        {
            "messages_per_month": msgs_per_month,
            "conversations_started_per_month": convos_per_month,
        }
    )
    summary_df.to_csv(monthly_csv, index=True)

    # Normalized messages
    if args.include_content:
        df.to_csv(normalized_csv, index=False)
    else:
        # Write a privacy-minimized version without content
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

    # Activity landmarks
    msgs_per_day = df.groupby("date").size()
    most_active_day = msgs_per_day.idxmax()
    max_msgs_day = int(msgs_per_day.max())

    most_active_month = str(msgs_per_month.sort_values(ascending=False).index[0])
    most_active_month_msgs = int(msgs_per_month.sort_values(ascending=False).iloc[0])

    # Depth distribution
    depth = depth_distribution(convo_stats)

    print("Claude Export Analytics (Per-Message Timestamps, Text Blocks Only)")
    print("=" * 66)
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

    if args.include_content:
        # These require content-derived columns
        print()
        print("Word and token stats")
        print("-" * 66)
        print(f"Total user words IN: {int(user_msgs.get('word_count', pd.Series(dtype=int)).sum())}")
        print(f"Total assistant words OUT: {int(assistant_msgs.get('word_count', pd.Series(dtype=int)).sum())}")
        print(f"Total user tokens IN: {int(user_msgs.get('token_count', pd.Series(dtype=int)).sum())}")
        print(f"Total assistant tokens OUT: {int(assistant_msgs.get('token_count', pd.Series(dtype=int)).sum())}")
        print(f"Longest user message (words): {int(user_msgs.get('word_count', pd.Series(dtype=int)).max()) if len(user_msgs) else 0}")
        print(f"Longest assistant message (words): {int(assistant_msgs.get('word_count', pd.Series(dtype=int)).max()) if len(assistant_msgs) else 0}")

    print()
    print("Activity landmarks")
    print("-" * 66)
    print(f"Most active day: {most_active_day} ({max_msgs_day} messages)")
    print(f"Most active month: {most_active_month} ({most_active_month_msgs} messages)")

    print()
    print("Depth distribution (messages per conversation)")
    print("-" * 66)
    print(f"Under 10 messages: {depth['under_10'][0]} ({depth['under_10'][1]:.2f}%)")
    print(f"10 to 29 messages: {depth['between_10_29'][0]} ({depth['between_10_29'][1]:.2f}%)")
    print(f"30 to 99 messages: {depth['between_30_99'][0]} ({depth['between_30_99'][1]:.2f}%)")
    print(f"100+ messages: {depth['over_100'][0]} ({depth['over_100'][1]:.2f}%)")

    print()
    print(f"Monthly stats written to: {monthly_csv}")
    print(f"Normalized messages written to: {normalized_csv}")


if __name__ == "__main__":
    main()
