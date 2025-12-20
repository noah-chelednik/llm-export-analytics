# LLM Usage Snapshot (2025-12-09)

This document records a point-in-time snapshot of personal large language model (LLM) usage derived from official ChatGPT and Claude export files, analyzed using the scripts in this repository.

All figures are aggregate-only. No message content, prompts, or conversation identifiers are included.

---

## ChatGPT

**Export method:** Primary conversation path, per-message timestamps  
**Date range:** 2023-08-08 to 2025-12-09

### Overview
- Total conversations: **1,652**
- Total messages: **44,388**
- Messages by user / assistant: **21,889 / 22,499**
- Unique days active: **754**

### Conversation depth
- Average length: **26.87 messages**
- Median length: **8 messages**
- Max length: **872 messages**
- Min length: **1 message**
- Conversations with 10+ messages: **750**
- Conversations with 20+ messages: **448**
- Conversations with 30+ messages: **341**

### Words and tokens
- User words IN: **976,915**
- Assistant words OUT: **8,059,425**
- Avg user words / message: **44.6**
- Avg assistant words / message: **358.2**
- User tokens IN: **1,438,714**
- Assistant tokens OUT: **12,778,653**
- Avg user tokens / message: **65.7**
- Avg assistant tokens / message: **568.0**

### Language and activity
- Vocabulary size (approx.): **81,997 unique words**
- Most active hour (UTC): **00:00**
- Most active day: **2025-06-03** (494 messages)
- Most active month: **2025-04** (4,203 messages)

### Extremes
- Longest user message: **11,453 words**
- Longest assistant message: **4,592 words**

### Depth distribution (messages per conversation)
- Under 10 messages: **902** (54.60%)
- 10–29 messages: **409** (24.76%)
- 30–99 messages: **258** (15.62%)
- 100+ messages: **83** (5.02%)

---

## Claude

**Export method:** Per-message timestamps, text blocks only  
**Date range:** 2024-03-05 to 2025-12-07

### Overview
- Total conversations: **231**
- Total messages: **6,140**
- Messages by user / assistant: **3,069 / 3,071**
- Unique days active: **189**

### Conversation depth
- Average length: **26.58 messages**
- Median length: **12 messages**
- Max length: **275 messages**
- Min length: **1 message**

### Words and tokens
- User words IN: **173,842**
- Assistant words OUT: **1,221,757**
- User tokens IN: **238,728**
- Assistant tokens OUT: **1,701,255**
- Longest user message: **10,587 words**
- Longest assistant message: **6,179 words**

### Activity landmarks
- Most active day: **2024-07-25** (183 messages)
- Most active month: **2024-07** (790 messages)

### Depth distribution (messages per conversation)
- Under 10 messages: **95** (41.13%)
- 10–29 messages: **69** (29.87%)
- 30–99 messages: **54** (23.38%)
- 100+ messages: **13** (5.63%)

---

## Combined (ChatGPT + Claude)

**Date range:** 2023-08-08 to 2025-12-09

### Overview
- Total conversations: **1,883**
- Total messages: **50,525**
- User messages: **24,955**
- Assistant messages: **25,570**
- Active days: **761**

### Words and tokens
- User words IN: **1,150,690**
- Assistant words OUT: **9,281,182**
- User tokens IN: **1,677,358**
- Assistant tokens OUT: **14,479,908**

### Conversation depth
- Average length: **26.83 messages**
- Median length: **8 messages**
- Longest conversation: **872 messages**
- Shortest conversation: **1 message**

### Depth distribution
- Under 10 messages: **997** (52.95%)
- 10–29 messages: **478** (25.39%)
- 30–99 messages: **312** (16.57%)
- 100+ messages: **96** (5.10%)

### Activity landmarks
- Most active day: **2025-03-30** (513 messages)
- Most active month: **2025-04** (4,484 messages)

### Extremes
- Longest user message: **11,453 words**
- Longest assistant message: **6,179 words**

---

## Notes

- Results depend on export format and filtering choices (primary path vs. full tree, text blocks only).
- All timestamps are bucketed using UTC for reproducibility.
- Raw exports and normalized CSVs are intentionally excluded from version control.
