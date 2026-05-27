#!/usr/bin/env python3
"""classify_and_link.py -- Classify conversations by topic and link to known projects.

Reads ChatGPT shard files and Claude conversations/projects JSON, classifies each
conversation into 1-2 topic categories using a keyword taxonomy, and attributes
conversations to known projects with confidence levels.

Outputs a comprehensive JSON file with per-conversation classifications,
topic/project summaries, and a validation report.
"""

import argparse
import csv
import json
import os
import random
import re
from collections import Counter, defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Taxonomy: category -> list of keywords / phrases (all lowercase)
# ---------------------------------------------------------------------------
TOPIC_TAXONOMY = {
    "Software Engineering": [
        "code", "programming", "debug", "function", "class", "method", "api",
        "git", "compile", "refactor", "build", "deploy", "test", "error",
        "bug", "stack", "library", "framework", "module", "package",
        "repository", "commit", "branch", "merge", "pull request", "ide",
        "algorithm", "implementation",
        # expanded keywords
        "backend", "frontend", "react", "vue", "angular", "django", "flask",
        "fastapi", "REST", "GraphQL", "microservice", "CI/CD", "linting",
        "type checking", "dependency", "npm", "webpack", "vite", "typescript",
        "javascript", "python", "java", "rust", "golang", "database",
        "postgres", "mongodb", "redis", "container", "sql", "query",
        "sorting", "data structure", "generics", "component", "render",
        "normalization", "schema", "endpoint", "crud", "orm", "migration",
        "babel", "eslint", "prettier", "junit", "pytest",
        "unittest", "mocha", "jest", "cypress", "selenium", "swift",
        "kotlin", "csharp", "dotnet", "rails", "laravel", "spring",
        "express", "node", "deno", "bun", "regex", "parser", "compiler",
        "interpreter", "syntax", "variable", "loop", "recursion",
        "inheritance", "polymorphism", "interface", "generic", "async",
        "await", "callback", "promise", "observable", "middleware",
    ],
    "Systems/Hardware/DevOps": [
        "pc", "bios", "gpu", "ram", "nvme", "linux", "ubuntu", "boot",
        "overclock", "kernel", "driver", "cpu", "motherboard", "ssd",
        "hardware", "terminal", "shell", "bash", "docker", "server",
        "network", "dns", "ssh", "firewall",
        # expanded keywords
        "shell scripting", "command line", "CLI", "systemd", "nginx",
        "apache", "cron", "filesystem", "partition", "Raspberry Pi",
        "homelab", "virtualization", "VMware", "proxmox", "ansible",
        "terraform", "kubernetes", "k8s", "AWS", "azure", "GCP", "cloud",
        "devops", "pipeline", "load balancer", "reverse proxy", "ssl",
        "certificate", "monitoring", "logging", "grafana", "prometheus",
        "nagios", "uptime", "backup", "raid", "iptables", "subnet",
        "vlan", "dhcp", "tcp", "udp", "http", "ftp", "smtp",
    ],
    "AI/ML/LLM": [
        "ai", "llm", "model", "training", "neural", "machine learning",
        "gpt", "claude", "prompt", "fine-tune", "transformer", "embedding",
        "inference", "token", "dataset", "evaluation", "benchmark",
        "reinforcement", "diffusion", "hallucination", "alignment", "rag",
        "vector", "agent",
        # expanded keywords
        "deep learning", "neural network", "vector database", "retrieval augmented",
        "prompt injection", "chain of thought", "few-shot", "zero-shot",
        "semantic search", "attention mechanism", "RLHF", "CUDA",
        "quantization", "distillation", "vision model", "computer vision",
        "NLP", "natural language", "chatbot", "fine-tuning", "LoRA",
        "weights", "gradient", "backpropagation", "loss function",
        "classification", "regression", "clustering", "supervised",
        "unsupervised", "generative", "discriminative", "GAN", "VAE",
        "autoencoder", "convolutional", "recurrent", "LSTM", "GPT-4",
        "Gemini", "Llama", "Mistral", "Anthropic", "OpenAI",
    ],
    "Writing/Creative": [
        "poem", "story", "novel", "writing", "creative", "narrative",
        "essay", "article", "fiction", "prose", "poetry", "lyric",
        "screenplay", "dialogue", "character", "plot", "draft", "revision",
        "edit", "publish", "blog", "substack",
        # expanded keywords
        "brainstorm", "outline", "character development", "world building",
        "tone", "voice", "editing", "rewrite", "paraphrase", "summarize",
        "summary", "proofread", "copywriting", "content", "memoir",
        "short story", "flash fiction", "script", "stanza", "rhyme",
        "metaphor", "simile", "imagery", "theme", "genre", "prologue",
        "epilogue", "climax", "protagonist", "antagonist",
    ],
    "Academic/Coursework": [
        "exam", "assignment", "class", "homework", "course", "final",
        "rubric", "grade", "university", "student", "quiz", "study",
        "lecture", "textbook", "semester", "credit", "gpa", "degree", "thesis",
        # expanded keywords
        "paper", "research paper", "citation", "reference", "methodology",
        "abstract", "peer review", "dissertation", "undergraduate",
        "graduate", "professor", "curriculum", "syllabus", "academic",
        "scholarship", "enrollment", "transcript", "midterm",
    ],
    "Language/Linguistics": [
        "translate", "translation", "language", "vocabulary", "grammar",
        "conjugation", "declension", "etymology", "bilingual", "parallel",
        "corpus", "multilingual", "localization", "i18n",
        # expanded keywords
        "Spanish", "French", "German", "Chinese", "Japanese", "Korean",
        "Arabic", "Portuguese", "Italian", "Hindi", "Russian", "Hebrew",
        "Latin", "Greek", "Mandarin", "Cantonese", "dialect", "phonetics",
        "morphology", "syntax", "semantics", "pragmatics", "idiom",
        "proverb",
    ],
    "Research/Knowledge": [
        "research", "analysis", "history", "philosophy", "theory", "science",
        "study", "investigation", "survey", "literature review", "methodology",
        "hypothesis", "evidence", "synthesis", "bibliography",
        # expanded keywords
        "explain", "how does", "what is", "compare", "difference between",
        "pros and cons", "overview", "introduction to", "guide", "tutorial",
        "definition", "concept", "principle", "fundamentals", "basics",
    ],
    "Personal/Life": [
        "health", "skin", "hair", "diet", "moving", "dating", "identity",
        "name", "apartment", "relationship", "fitness", "wellness",
        "self-improvement", "lifestyle", "routine",
        # expanded keywords
        "advice", "help me", "recommend", "suggestion", "plan", "schedule",
        "organize", "morning routine", "habit", "goal setting", "motivation",
        "recipe", "cooking", "meal prep", "nutrition", "exercise", "yoga",
        "meditation", "sleep", "travel", "itinerary", "vacation", "trip",
        "packing", "hobby", "gardening", "pet", "parenting", "wedding",
        "vegetarian", "vegan", "gluten-free",
    ],
    "Career/Professional": [
        "resume", "job", "interview", "application", "career", "hire",
        "salary", "cover letter", "linkedin", "portfolio", "qualification",
        "professional", "employer", "recruitment",
        # expanded keywords
        "networking", "negotiation", "promotion", "freelance", "side hustle",
        "startup", "pitch", "business plan", "meeting", "presentation",
        "email draft", "internship", "onboarding", "performance review",
        "remote work", "coworker", "manager", "leadership",
    ],
    "Music/Audio": [
        "music", "song", "audio", "sound", "midi", "daw",
        "melody", "chord", "composition", "instrument", "synth", "mix",
        "master", "frequency", "beat", "tempo", "notation",
        # expanded keywords
        "playlist", "album", "genre", "lyrics", "recording", "producer",
        "DJ", "podcast", "voice over", "equalizer", "reverb", "delay",
        "compressor", "sample", "loop", "drum machine", "piano", "guitar",
    ],
    "Visual/Design": [
        "image", "design", "art", "logo", "brand", "aesthetic", "color",
        "layout", "typography", "illustration", "graphic", "mockup",
        "wireframe", "ui", "ux", "css", "style",
        # expanded keywords
        "Figma", "Photoshop", "Canva", "infographic", "presentation design",
        "slide deck", "banner", "icon", "animation", "sketch", "prototype",
        "responsive", "grid", "spacing", "palette", "contrast", "svg",
        "pixel", "resolution", "vector graphic",
    ],
    "Finance/Business": [
        "money", "budget", "salary", "investment", "business", "startup",
        "revenue", "profit", "market", "stock", "crypto", "tax",
        "accounting", "financial", "llc", "incorporation",
        # expanded keywords
        "pricing", "subscription", "SaaS", "revenue model", "cost analysis",
        "ROI", "invoice", "bookkeeping", "payment", "mortgage", "loan",
        "interest rate", "401k", "retirement", "dividend", "portfolio",
        "forex", "bitcoin", "ethereum", "defi", "nft",
    ],
    "Mythology/Philosophy": [
        "myth", "mythology", "god", "philosophy", "metaphysics", "ontology",
        "epistemology", "ethics", "existential", "archetype", "cosmology",
        "theological", "spiritual", "ritual",
    ],
    "Cryptography": [
        "cipher", "manuscript", "decode", "cryptography",
        "transcription", "codex", "enigma", "encryption", "steganography",
    ],
    "Gaming/Entertainment": [
        "game", "play", "rpg", "character sheet", "d&d", "dungeon", "quest",
        "total war", "strategy", "campaign", "mod",
        # expanded keywords
        "video game", "board game", "streaming", "Twitch", "YouTube",
        "movie", "TV show", "anime", "manga", "book recommendation",
        "Netflix", "console", "PlayStation", "Xbox", "Nintendo", "Steam",
        "indie game", "esports", "speedrun", "walkthrough",
    ],
    "Legal": [
        "law", "legal", "court", "statute", "regulation", "compliance",
        "contract", "litigation", "attorney", "lawyer", "case law",
        "precedent", "jurisdiction",
        # expanded keywords
        "terms of service", "privacy policy", "patent", "copyright",
        "trademark", "NDA", "liability", "insurance", "lease", "tenant",
        "landlord", "eviction", "arbitration", "mediation",
    ],
    "Military/Strategy": [
        "military", "strategy", "war", "battle", "defense", "intelligence",
        "operation", "tactical", "weapons", "geopolitical", "nato",
        # expanded keywords
        "geopolitics", "foreign policy", "diplomacy", "conflict", "security",
        "cyber", "surveillance", "sanctions", "treaty", "alliance",
    ],
}

# Pre-compiled regex patterns for structural pattern detection
_RE_CODE_FENCE = re.compile(r'```')
_RE_FILE_PATH = re.compile(r'/[a-zA-Z]+/[a-zA-Z]')
_RE_URL = re.compile(r'https?://')

# Compile regex patterns for each category (word-boundary matching)
def _compile_patterns(taxonomy: dict[str, list[str]]) -> dict[str, list[tuple[str, re.Pattern]]]:
    """Pre-compile regex patterns for efficient matching."""
    compiled = {}
    for cat, keywords in taxonomy.items():
        # Sort keywords by length descending so multi-word phrases match first
        sorted_kws = sorted(keywords, key=len, reverse=True)
        patterns = []
        for kw in sorted_kws:
            # Use word boundaries; escape special regex chars
            pat = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
            patterns.append((kw, pat))
        compiled[cat] = patterns
    return compiled

CATEGORY_PATTERNS = _compile_patterns(TOPIC_TAXONOMY)


def load_project_keywords(config_path: str) -> dict:
    """Load project keyword definitions from a JSON config file."""
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"  [WARN] Could not load project config from {config_path}: {exc}")
        return {}


def _compile_project_patterns(proj_map: dict) -> dict[str, dict]:
    """Compile regex patterns for project keyword matching."""
    compiled = {}
    for proj, info in proj_map.items():
        sorted_kws = sorted(info["keywords"], key=len, reverse=True)
        patterns = []
        for kw in sorted_kws:
            pat = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
            patterns.append((kw, pat))
        compiled[proj] = {
            "patterns": patterns,
            "platform": info.get("platform", "both"),
            "name_pattern": re.compile(
                r'\b' + re.escape(proj.split("/")[0].strip().split("(")[0].strip()) + r'\b',
                re.IGNORECASE,
            ),
        }
    return compiled


# ---------------------------------------------------------------------------
# Classification functions
# ---------------------------------------------------------------------------

def score_text(text: str, patterns_dict: dict[str, list[tuple[str, re.Pattern]]]) -> dict[str, int]:  # type: ignore[type-arg]
    """Score a text against all categories and return per-category hit counts."""
    scores: dict[str, int] = {}
    if not text:
        return scores
    for cat, patterns in patterns_dict.items():
        score = 0
        for _kw, pat in patterns:
            if pat.search(text):
                score += 1
        if score > 0:
            scores[cat] = score
    return scores


def apply_structural_bonuses(scores: dict[str, int | float], text: str) -> dict[str, float]:
    """Apply bonus points for structural patterns detected in text.

    These act as tiebreakers -- applied after keyword scoring, before
    final category selection.

    - Code fences (triple backticks): +1 to Software Engineering
    - File paths (/foo/bar): +1 to Systems/Hardware/DevOps
    - URLs (http/https): +0.5 to Research/Knowledge
    """
    if not text:
        return {k: float(v) for k, v in scores.items()}

    boosted: dict[str, float] = {k: float(v) for k, v in scores.items()}

    if _RE_CODE_FENCE.search(text):
        boosted["Software Engineering"] = boosted.get("Software Engineering", 0) + 1

    if _RE_FILE_PATH.search(text):
        boosted["Systems/Hardware/DevOps"] = boosted.get("Systems/Hardware/DevOps", 0) + 1

    if _RE_URL.search(text):
        boosted["Research/Knowledge"] = boosted.get("Research/Knowledge", 0) + 0.5

    return boosted


def classify_topics(text: str, method: str = "title",
                    structural_text: str = "") -> list[dict]:
    """Return the top 1-2 topic categories for the given text.

    Args:
        text: The text to score keywords against.
        method: Label for the classification method used.
        structural_text: Optional additional text to scan for structural
            patterns (code fences, file paths, URLs). If empty, ``text``
            is used for structural detection as well.
    """
    raw_scores = score_text(text, CATEGORY_PATTERNS)
    scores: dict[str, int | float] = dict(raw_scores)

    # Apply structural pattern bonuses as tiebreakers
    scan_text = structural_text or text
    boosted = apply_structural_bonuses(scores, scan_text)

    # Filter to only categories with positive scores
    positive = {k: v for k, v in boosted.items() if v > 0}
    if not positive:
        return []

    ranked = sorted(positive.items(), key=lambda x: x[1], reverse=True)
    result = [{"category": ranked[0][0], "score": ranked[0][1], "method": method}]
    if len(ranked) > 1 and ranked[1][1] >= 1:
        result.append({"category": ranked[1][0], "score": ranked[1][1], "method": method})
    return result


def classify_project(title: str, first_msg: str, platform: str, project_patterns: dict) -> dict | None:
    """Attribute a conversation to a project based on keyword matching."""
    if not project_patterns:
        return None
    title_lower = (title or "").lower()
    first_msg_lower = (first_msg or "").lower()
    combined = title_lower + " " + first_msg_lower

    best_project = None
    best_confidence = None
    best_match_count = 0

    for proj, info in project_patterns.items():
        # Platform check
        plat = info["platform"]
        if plat != "both" and plat != platform:
            continue

        # Check for exact project name in title -> high confidence
        if info["name_pattern"].search(title_lower):
            match_count = sum(1 for _, p in info["patterns"] if p.search(combined))
            if best_confidence != "high" or match_count > best_match_count:
                best_project = proj
                best_confidence = "high"
                best_match_count = match_count
            continue

        # Count keyword matches in combined text
        match_count = sum(1 for _, p in info["patterns"] if p.search(combined))
        if match_count >= 2:
            if best_confidence not in ("high",) or match_count > best_match_count:
                if best_confidence == "high":
                    continue
                if match_count > best_match_count or best_confidence is None:
                    best_project = proj
                    best_confidence = "medium"
                    best_match_count = match_count
        elif match_count == 1:
            if best_confidence is None:
                best_project = proj
                best_confidence = "low"
                best_match_count = match_count

    if best_project:
        return {"name": best_project, "confidence": best_confidence}
    return None


def is_empty_title(title: str | None) -> bool:
    """Check if a title is empty, null, or a generic placeholder."""
    if not title:
        return True
    t = title.strip().lower()
    return t in ("", "new chat", "new conversation", "untitled")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_chatgpt_conversations(shard_dir: str, num_shards: int = 19) -> list[dict]:
    """Load conversation id and title from all ChatGPT shard files."""
    convos = []
    for i in range(num_shards):
        path = os.path.join(shard_dir, f"conversations-{i:03d}.json")
        if not os.path.exists(path):
            print(f"  [WARN] Shard not found: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for c in data:
            convos.append({
                "conversation_id": c["id"],
                "platform": "chatgpt",
                "title": c.get("title"),
            })
    return convos


def load_claude_conversations(conv_path: str) -> list[dict]:
    """Load conversation uuid and name from Claude conversations JSON."""
    print(f"  Loading Claude conversations from {conv_path} ...")
    convos = []
    with open(conv_path, encoding="utf-8") as f:
        data = json.load(f)
    for c in data:
        convos.append({
            "conversation_id": c["uuid"],
            "platform": "claude",
            "title": c.get("name"),
        })
    print(f"  Loaded {len(convos)} Claude conversations.")
    return convos


def load_conversation_content(csv_path: str, platform: str) -> dict[str, dict]:
    """Load expanded conversation content per conversation from a normalized CSV.

    Returns a dict mapping conversation_id -> {
        "first_user": str (up to 2000 chars of first user message),
        "first_assistant": str (up to 1000 chars of first assistant message),
        "mid_message": str (message at the midpoint, for long conversations),
        "msg_count": int (total messages in conversation),
    }
    """
    # Increase CSV field size limit to handle large message content
    csv.field_size_limit(10 * 1024 * 1024)  # 10 MB

    # First pass: collect all messages per conversation (ordered by CSV row)
    convo_messages: dict[str, list[dict]] = defaultdict(list)
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["conversation_id"]
            convo_messages[cid].append({
                "role": row["role"],
                "content": row.get("content", "") or "",
            })

    # Second pass: extract the fields we need
    result = {}
    for cid, messages in convo_messages.items():
        first_user = ""
        first_assistant = ""
        mid_message = ""
        msg_count = len(messages)

        for msg in messages:
            if not first_user and msg["role"] == "user":
                first_user = msg["content"][:2000]
            elif not first_assistant and msg["role"] == "assistant":
                first_assistant = msg["content"][:1000]
            if first_user and first_assistant:
                break

        # Sample mid-conversation message for long conversations
        if msg_count >= 10:
            mid_idx = msg_count // 2
            mid_message = messages[mid_idx]["content"][:1000]

        result[cid] = {
            "first_user": first_user,
            "first_assistant": first_assistant,
            "mid_message": mid_message,
            "msg_count": msg_count,
        }

    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> None:
    """Classify all conversations by topic and optionally attribute them to projects."""
    parser = argparse.ArgumentParser(
        description="Classify conversations by topic and link to projects."
    )
    parser.add_argument(
        "--chatgpt-shard-dir",
        default="exports/"
                "61b85573cfbec86e6fc397dbfdca42f8117fe4ece43591c30e851c2fc1090356-"
                "2026-04-22-00-23-34-a5d95132b6894c289964b70e79488ade",
        help="Directory containing ChatGPT conversation shard files",
    )
    parser.add_argument(
        "--num-shards", type=int, default=19,
        help="Number of ChatGPT shard files (default: 19)",
    )
    parser.add_argument(
        "--claude-conv-path",
        default="exports/2026-04-21-claude/"
                "data-f8e36cd0-8ae1-4565-bbc6-da7cdab23edb-1776813907-"
                "9aaf3227-batch-0000/conversations.json",
        help="Path to Claude conversations.json",
    )
    parser.add_argument(
        "--claude-projects-path",
        default="exports/2026-04-21-claude/"
                "data-f8e36cd0-8ae1-4565-bbc6-da7cdab23edb-1776813907-"
                "9aaf3227-batch-0000/projects.json",
        help="Path to Claude projects.json",
    )
    parser.add_argument(
        "--chatgpt-csv",
        default=""
                "chatgpt_messages_normalized.csv",
        help="Path to ChatGPT normalized messages CSV",
    )
    parser.add_argument(
        "--claude-csv",
        default=""
                "claude_messages_normalized.csv",
        help="Path to Claude normalized messages CSV",
    )
    parser.add_argument(
        "--output",
        default=""
                "classifications_and_projects.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--projects",
        default=None,
        help="Path to a JSON config file defining project keywords for "
             "project attribution. If not provided, project attribution is "
             "skipped (only topic classification is performed). "
             "See templates/example_projects.json for the expected format.",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for validation sampling",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("classify_and_link.py -- Topic Classification & Project Attribution")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Load project keywords config (if provided)
    # -----------------------------------------------------------------------
    project_keywords = {}
    project_patterns = {}
    if args.projects:
        print(f"\n  Loading project keywords from {args.projects} ...")
        project_keywords = load_project_keywords(args.projects)
        if project_keywords:
            project_patterns = _compile_project_patterns(project_keywords)
            print(f"  Loaded {len(project_keywords)} project definitions.")
        else:
            print("  No project definitions loaded; project attribution disabled.")
    else:
        print("\n  No --projects config provided; project attribution will be skipped.")
        print("  (See templates/example_projects.json for the expected format.)")

    # -----------------------------------------------------------------------
    # Step 1: Load conversation metadata
    # -----------------------------------------------------------------------
    print("\n[1/6] Loading conversation metadata ...")
    chatgpt_convos = load_chatgpt_conversations(
        args.chatgpt_shard_dir, args.num_shards
    )
    print(f"  ChatGPT conversations: {len(chatgpt_convos)}")

    claude_convos = load_claude_conversations(args.claude_conv_path)
    print(f"  Claude conversations:  {len(claude_convos)}")

    all_convos = chatgpt_convos + claude_convos
    print(f"  Total conversations:   {len(all_convos)}")

    # -----------------------------------------------------------------------
    # Step 2: Load conversation content from CSVs (for fallback + validation)
    # -----------------------------------------------------------------------
    print("\n[2/6] Loading conversation content from normalized CSVs ...")
    chatgpt_content = load_conversation_content(args.chatgpt_csv, "chatgpt")
    print(f"  ChatGPT conversations with content: {len(chatgpt_content)}")
    claude_content = load_conversation_content(args.claude_csv, "claude")
    print(f"  Claude conversations with content:  {len(claude_content)}")

    # Merge into single lookup
    conversation_content = {**chatgpt_content, **claude_content}
    print(f"  Total conversations with content:   {len(conversation_content)}")

    # Build a backward-compatible first_messages lookup for project attribution
    first_messages = {
        cid: info["first_user"]
        for cid, info in conversation_content.items()
    }

    # -----------------------------------------------------------------------
    # Step 3: Classify every conversation
    # -----------------------------------------------------------------------
    print("\n[3/6] Classifying conversations ...")
    results = []
    title_only_count = 0
    content_fallback_count = 0
    no_class_count = 0

    for convo in all_convos:
        cid = convo["conversation_id"]
        title = convo["title"]
        platform = convo["platform"]
        convo_info = conversation_content.get(cid, {})
        first_user = convo_info.get("first_user", "")
        first_assistant = convo_info.get("first_assistant", "")
        mid_message = convo_info.get("mid_message", "")

        # Build the deep content text for classification:
        # - first 2000 chars of first user message
        # - first 1000 chars of first assistant message
        # - mid-conversation message for long conversations (10+ messages)
        content_parts = [first_user, first_assistant]
        if mid_message:
            content_parts.append(mid_message)
        deep_content = " ".join(p for p in content_parts if p)

        # Structural text for pattern detection (code fences, paths, URLs)
        structural_text = deep_content

        # Topic classification
        if is_empty_title(title):
            # Fallback to content
            topics = classify_topics(deep_content, method="content",
                                     structural_text=structural_text)
            if topics:
                content_fallback_count += 1
            else:
                topics = [{"category": "Other", "score": 0, "method": "content"}]
                no_class_count += 1
        else:
            topics = classify_topics(title, method="title",
                                     structural_text=structural_text)
            if not topics:
                # Title had no keyword matches; try deeper content
                topics = classify_topics(deep_content, method="content",
                                         structural_text=structural_text)
                if topics:
                    content_fallback_count += 1
                else:
                    topics = [{"category": "Other", "score": 0, "method": "title"}]
                    no_class_count += 1
            else:
                title_only_count += 1

        # Project attribution (uses first user message for backward compat)
        first_msg = first_user
        project = classify_project(title, first_msg, platform, project_patterns)

        results.append({
            "conversation_id": cid,
            "platform": platform,
            "title": title,
            "topics": topics,
            "project": project,
        })

    print(f"  Title-classified:     {title_only_count}")
    print(f"  Content-fallback:     {content_fallback_count}")
    print(f"  Unclassifiable:       {no_class_count}")

    # -----------------------------------------------------------------------
    # Step 4: Topic summary
    # -----------------------------------------------------------------------
    print("\n[4/6] Computing topic summary ...")
    topic_counts: Counter[str] = Counter()
    topic_scores = defaultdict(list)
    total = len(results)

    for r in results:
        for t in r["topics"]:
            cat = t["category"]
            topic_counts[cat] += 1
            topic_scores[cat].append(t["score"])

    topic_summary = {}
    for cat in sorted(TOPIC_TAXONOMY.keys()):
        cnt = topic_counts.get(cat, 0)
        scores = topic_scores.get(cat, [])
        avg = sum(scores) / len(scores) if scores else 0.0
        topic_summary[cat] = {
            "count": cnt,
            "pct": round(cnt / total * 100, 2) if total else 0,
            "avg_depth": round(avg, 2),
        }
    # Add "Other"
    other_cnt = topic_counts.get("Other", 0)
    other_scores = topic_scores.get("Other", [])
    topic_summary["Other"] = {
        "count": other_cnt,
        "pct": round(other_cnt / total * 100, 2) if total else 0,
        "avg_depth": round(
            sum(other_scores) / len(other_scores) if other_scores else 0, 2
        ),
    }

    print(f"  {'Category':<30} {'Count':>6} {'Pct':>7} {'AvgDepth':>9}")
    print(f"  {'-'*30} {'-'*6} {'-'*7} {'-'*9}")
    for cat, s in sorted(topic_summary.items(), key=lambda x: -x[1]["count"]):
        print(f"  {cat:<30} {s['count']:>6} {s['pct']:>6.1f}% {s['avg_depth']:>8.2f}")

    # -----------------------------------------------------------------------
    # Step 5: Project summary
    # -----------------------------------------------------------------------
    print("\n[5/6] Computing project summary ...")
    project_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "confidence_dist": {"high": 0, "medium": 0, "low": 0}}
    )

    linked_count = 0
    for r in results:
        if r["project"]:
            pname = r["project"]["name"]
            conf = r["project"]["confidence"]
            project_summary[pname]["count"] += 1
            project_summary[pname]["confidence_dist"][conf] += 1
            linked_count += 1

    project_summary = dict(project_summary)  # type: ignore[assignment]  # convert from defaultdict

    print(f"  Linked conversations: {linked_count} / {total} ({linked_count/total*100:.1f}%)")
    print(f"  {'Project':<30} {'Count':>6} {'High':>5} {'Med':>5} {'Low':>5}")
    print(f"  {'-'*30} {'-'*6} {'-'*5} {'-'*5} {'-'*5}")
    for pname, ps in sorted(project_summary.items(), key=lambda x: -x[1]["count"]):
        cd = ps["confidence_dist"]
        print(f"  {pname:<30} {ps['count']:>6} {cd['high']:>5} {cd['medium']:>5} {cd['low']:>5}")

    # -----------------------------------------------------------------------
    # Step 6: Validation -- stratified 10% sample
    # -----------------------------------------------------------------------
    print("\n[6/6] Running validation (10% stratified sample) ...")
    random.seed(args.seed)

    # Group conversations by their primary topic
    by_category = defaultdict(list)
    for r in results:
        primary = r["topics"][0]["category"]
        by_category[primary].append(r)

    sample = []
    for _cat, members in by_category.items():
        n = max(1, len(members) // 10)
        sample.extend(random.sample(members, min(n, len(members))))

    print(f"  Sample size: {len(sample)} conversations")

    # For each sample conversation, classify with BOTH title AND first message
    # Compare to the original (title-only or content-only) result
    per_cat_agree: dict[str, dict[str, int]] = defaultdict(lambda: {"agree": 0, "total": 0})

    for r in sample:
        cid = r["conversation_id"]
        title = r["title"] or ""
        first_msg = first_messages.get(cid, "")
        combined_text = (title + " " + first_msg).strip()

        # Combined classification
        combined_topics = classify_topics(combined_text, method="combined")
        if not combined_topics:
            combined_topics = [{"category": "Other", "score": 0, "method": "combined"}]

        original_primary = r["topics"][0]["category"]
        combined_primary = combined_topics[0]["category"]

        per_cat_agree[original_primary]["total"] += 1
        if original_primary == combined_primary:
            per_cat_agree[original_primary]["agree"] += 1

    # Compute agreement rates
    per_category_agreement: dict[str, float] = {}
    flagged_categories: list[str] = []
    total_agree = 0
    total_checked = 0

    for cat in sorted(per_cat_agree.keys()):
        info = per_cat_agree[cat]
        rate = info["agree"] / info["total"] if info["total"] else 0
        per_category_agreement[cat] = round(rate, 4)
        total_agree += info["agree"]
        total_checked += info["total"]
        if rate < 0.75:
            flagged_categories.append(cat)

    overall_agreement = round(
        total_agree / total_checked if total_checked else 0, 4
    )

    validation: dict[str, Any] = {
        "per_category_agreement": per_category_agreement,
        "overall_agreement": overall_agreement,
        "flagged_categories": flagged_categories,
    }

    print(f"\n  {'Category':<30} {'Agreement':>10} {'n':>5} {'Flag':>5}")
    print(f"  {'-'*30} {'-'*10} {'-'*5} {'-'*5}")
    for cat in sorted(per_category_agreement.keys()):
        rate = per_category_agreement[cat]
        n = per_cat_agree[cat]["total"]
        flag = " !!!" if cat in flagged_categories else ""
        print(f"  {cat:<30} {rate:>9.1%} {n:>5}{flag}")
    print(f"\n  Overall agreement: {overall_agreement:.1%}")
    if flagged_categories:
        print(f"  FLAGGED (<75% agreement): {', '.join(flagged_categories)}")
    else:
        print("  No categories flagged.")

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------
    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output = {
        "per_conversation": results,
        "topic_summary": topic_summary,
        "project_summary": project_summary,
        "validation": validation,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"Output written to: {output_path}")
    file_size = os.path.getsize(output_path)
    print(f"File size: {file_size / 1024:.1f} KB")
    print(f"Total conversations classified: {len(results)}")
    print(f"  - ChatGPT: {sum(1 for r in results if r['platform'] == 'chatgpt')}")
    print(f"  - Claude:  {sum(1 for r in results if r['platform'] == 'claude')}")
    print(f"  - Linked to projects: {linked_count}")
    print(f"  - Topic 'Other' (unclassified): {topic_counts.get('Other', 0)}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
