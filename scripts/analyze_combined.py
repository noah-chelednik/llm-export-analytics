import argparse
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


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


def has_cols(df: pd.DataFrame, cols) -> bool:
    return all(c in df.columns for c in cols)


def safe_sum(df: pd.DataFrame, col: str) -> Optional[int]:
    if col not in df.columns:
        return None
    try:
        return int(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
    except Exception:
        return None


def safe_max(df: pd.DataFrame, col: str) -> Optional[int]:
    if col not in df.columns:
        return None
    try:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.dropna().empty:
            return None
        return int(s.max())
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Combine normalized ChatGPT + Claude CSVs and compute aggregate stats.")
    parser.add_argument("--chatgpt", required=True, help="Path to outputs/chatgpt_messages_normalized.csv")
    parser.add_argument("--claude", required=True, help="Path to outputs/claude_messages_normalized.csv")
    parser.add_argument("--utc", action="store_true", help="Parse created timestamps as UTC (recommended)")
    args = parser.parse_args()

    chatgpt_path = Path(args.chatgpt).expanduser().resolve()
    claude_path = Path(args.claude).expanduser().resolve()

    df1 = pd.read_csv(chatgpt_path)
    df2 = pd.read_csv(claude_path)

    df = pd.concat([df1, df2], ignore_index=True)

    # Parse created timestamps
    df["created"] = pd.to_datetime(df["created"], utc=args.utc, errors="coerce")
    df = df.dropna(subset=["created"])

    # Derived buckets (safe even in privacy-minimized CSVs)
    df["date"] = df["created"].dt.date
    df["month"] = df["created"].dt.to_period("M").astype(str)

    # Totals
    total_messages = int(len(df))
    user_msgs = df[df["role"] == "user"]
    assistant_msgs = df[df["role"] == "assistant"]

    user_msg_count = int(len(user_msgs))
    assistant_msg_count = int(len(assistant_msgs))

    total_convos = int(df["conversation_id"].nunique())
    unique_days = int(df["date"].nunique())

    date_min = df["created"].min().date()
    date_max = df["created"].max().date()

    # Conversation stats
    convo_sizes = df.groupby("conversation_id").size()
    avg_convo_length = float(convo_sizes.mean())
    median_convo_length = int(convo_sizes.median())
    max_convo_length = int(convo_sizes.max())
    min_convo_length = int(convo_sizes.min())

    # NOTE: Only print conversation_id if you explicitly want it public.
    # Keeping it suppressed by default.
    # longest_convo_id = convo_sizes.idxmax()

    # Depth buckets
    depth = depth_distribution(convo_sizes)

    # Most active day/month
    msgs_per_day = df.groupby("date").size()
    most_active_day = msgs_per_day.idxmax()
    most_active_day_msgs = int(msgs_per_day.loc[most_active_day])

    msgs_per_month = df.groupby("month").size().sort_values(ascending=False)
    most_active_month = str(msgs_per_month.index[0])
    most_active_month_msgs = int(msgs_per_month.iloc[0])

    # Optional: words/tokens/extremes only if columns exist
    has_counts = has_cols(df, ["word_count", "token_count"])
    user_total_words = safe_sum(user_msgs, "word_count")
    assistant_total_words = safe_sum(assistant_msgs, "word_count")
    user_total_tokens = safe_sum(user_msgs, "token_count")
    assistant_total_tokens = safe_sum(assistant_msgs, "token_count")

    longest_user_words = safe_max(user_msgs, "word_count")
    longest_assistant_words = safe_max(assistant_msgs, "word_count")

    print("COMBINED (ChatGPT + Claude) Export Analytics")
    print("=" * 52)
    print(f"Conversations: {total_convos}")
    print(f"Messages total: {total_messages}")
    print(f"User messages: {user_msg_count}")
    print(f"Assistant messages: {assistant_msg_count}")
    print(f"Active days: {unique_days}")
    print(f"Date range: {date_min} to {date_max}")

    if has_counts:
        print()
        print("Words and tokens")
        print("-" * 52)
        print(f"User words IN: {user_total_words}")
        print(f"Assistant words OUT: {assistant_total_words}")
        print(f"User tokens IN: {user_total_tokens}")
        print(f"Assistant tokens OUT: {assistant_total_tokens}")

    print()
    print("Conversation length landmarks")
    print("-" * 52)
    print(f"Average messages per conversation: {avg_convo_length:.2f}")
    print(f"Median messages per conversation: {median_convo_length}")
    print(f"Longest conversation: {max_convo_length} messages")
    print(f"Shortest conversation: {min_convo_length}")

    print()
    print("Depth distribution")
    print("-" * 52)
    print(f"Under 10 messages: {depth['under_10'][0]} ({depth['under_10'][1]:.2f}%)")
    print(f"10 to 29 messages: {depth['between_10_29'][0]} ({depth['between_10_29'][1]:.2f}%)")
    print(f"30 to 99 messages: {depth['between_30_99'][0]} ({depth['between_30_99'][1]:.2f}%)")
    print(f"100+ messages: {depth['over_100'][0]} ({depth['over_100'][1]:.2f}%)")

    print()
    print("Activity landmarks")
    print("-" * 52)
    print(f"Most active day: {most_active_day} ({most_active_day_msgs} messages)")
    print(f"Most active month: {most_active_month} ({most_active_month_msgs} messages)")

    if has_counts:
        print()
        print("Extremes")
        print("-" * 52)
        print(f"Longest user message: {longest_user_words} words")
        print(f"Longest assistant message: {longest_assistant_words} words")


if __name__ == "__main__":
    main()
