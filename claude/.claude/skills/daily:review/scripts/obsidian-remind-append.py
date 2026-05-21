#!/usr/bin/env python3
"""Append remind entries to Obsidian Daily Note's 리마인드 section.

Usage:
    python3 obsidian-remind-append.py --date YYYY-MM-DD \\
        --items '[{"title": "...", "detail": "..."}, ...]'

Each entry is inserted at the top of ## 리마인드 section in this format:
    - [YYYY-MM-DD] {title}
      {detail}
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime


DAILY_NOTE_BASE = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily"


def get_daily_note_path(date_str):
    return DAILY_NOTE_BASE / f"{date_str}.md"


def append_remind(entries, date_str):
    path = get_daily_note_path(date_str)
    if not path.exists():
        print(json.dumps({"success": False, "error": f"Daily note not found: {path}"}))
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    if "## 리마인드" not in content:
        print(json.dumps({"success": False, "error": "## 리마인드 section not found"}))
        sys.exit(1)

    # Build new lines to insert (most recent first — inserted at top of section)
    new_lines = []
    for e in entries:
        title = e.get("title", "").strip()
        detail = e.get("detail", "").strip()
        if not title:
            continue
        new_lines.append(f"- [{date_str}] {title}")
        if detail:
            new_lines.append(f"  {detail}")

    if not new_lines:
        print(json.dumps({"success": True, "added": 0, "message": "No entries to add"}))
        return

    lines = content.split("\n")
    remind_start = None
    remind_end = None

    for i, line in enumerate(lines):
        if line.strip() == "## 리마인드":
            remind_start = i
        elif remind_start is not None and line.startswith("## ") and i > remind_start:
            remind_end = i
            break

    if remind_start is None:
        print(json.dumps({"success": False, "error": "## 리마인드 section not found in file"}))
        sys.exit(1)

    if remind_end is None:
        remind_end = len(lines)

    # Remove placeholder "-" lines in section (empty state)
    placeholder_indices = [
        i for i in range(remind_start + 1, remind_end)
        if lines[i].strip() == "-"
    ]
    for idx in reversed(placeholder_indices):
        del lines[idx]
    remind_end -= len(placeholder_indices)

    # Insert new entries right after the ## 리마인드 header
    insert_at = remind_start + 1
    for line in reversed(new_lines):
        lines.insert(insert_at, line)

    path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "success": True,
        "added": len([e for e in entries if e.get("title", "").strip()]),
        "file": str(path),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Append remind entries to Obsidian Daily Note")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--items", required=True, help="JSON array of {title, detail} objects")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    try:
        entries = json.loads(args.items)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    if not isinstance(entries, list):
        print(json.dumps({"success": False, "error": "--items must be a JSON array"}))
        sys.exit(1)

    append_remind(entries, date_str)


if __name__ == "__main__":
    main()
