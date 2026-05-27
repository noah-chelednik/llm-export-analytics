"""Privacy tests: default output should not contain conversation content."""

import csv
import json
import os

import pytest


class TestPrivacy:
    def test_default_csv_has_no_content(self, basic_analysis_outputs):
        """Without --include-content, content/word_count/token_count columns are absent."""
        for key in ("chatgpt_csv", "claude_csv"):
            with open(basic_analysis_outputs[key], newline="") as f:
                reader = csv.DictReader(f)
                fields = set(reader.fieldnames or [])

            for col in ("content", "word_count", "token_count"):
                assert col not in fields, (
                    f"Column '{col}' should not be in default CSV "
                    f"({os.path.basename(basic_analysis_outputs[key])})"
                )

    def test_no_raw_text_in_default_output(self, basic_analysis_outputs, sample_chatgpt_path, sample_claude_path):
        """No conversation text from sample data appears in any default output file."""
        # Collect a set of sample phrases from the raw exports
        phrases = set()
        with open(sample_chatgpt_path) as f:
            chatgpt_data = json.load(f)
        for conv in chatgpt_data[:5]:
            mapping = conv.get("mapping", {})
            for node in mapping.values():
                msg = (node or {}).get("message")
                if not msg:
                    continue
                content = msg.get("content", {})
                parts = content.get("parts", [])
                for part in parts:
                    if isinstance(part, str) and len(part) > 30:
                        # Take a distinctive substring
                        phrases.add(part[10:40])

        with open(sample_claude_path) as f:
            claude_data = json.load(f)
        for conv in claude_data[:5]:
            for m in conv.get("chat_messages", []):
                for block in m.get("content", []):
                    text = block.get("text", "")
                    if len(text) > 30:
                        phrases.add(text[10:40])

        # Now scan all default output files
        out_dir = basic_analysis_outputs["out_dir"]
        for fname in os.listdir(out_dir):
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "r", errors="replace") as f:
                file_content = f.read()
            for phrase in phrases:
                assert phrase not in file_content, (
                    f"Found raw text snippet in default output file {fname}: "
                    f"'{phrase[:50]}...'"
                )
