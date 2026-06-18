#!/usr/bin/env python3
"""Add a todo item to today's Obsidian Daily Note Todos section."""

import sys
import os
from pathlib import Path
from datetime import datetime


DAILY_NOTE_BASE = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily"


def get_daily_note_path(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return DAILY_NOTE_BASE / f"{date_str}.md"


def add_todo(text, done=False, date_str=None):
    path = get_daily_note_path(date_str)
    if not path.exists():
        print(f"ERROR: Daily note not found: {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")

    if "## Todos" not in content:
        print("ERROR: ## Todos section not found in daily note", file=sys.stderr)
        sys.exit(1)

    marker = "- [x]" if done else "- [ ]"
    new_line = f"{marker} {text}"

    lines = content.split("\n")
    todos_start = None
    todos_end = None

    for i, line in enumerate(lines):
        if line.strip() == "## Todos":
            todos_start = i
        elif todos_start is not None and line.startswith("## ") and i > todos_start:
            todos_end = i
            break

    if todos_end is None:
        todos_end = len(lines)

    # Insert after last todo item in the section
    insert_at = todos_start + 1
    for i in range(todos_end - 1, todos_start, -1):
        if lines[i].strip().startswith("- "):
            insert_at = i + 1
            break

    lines.insert(insert_at, new_line)
    path.write_text("\n".join(lines), encoding="utf-8")

    status = "✅ 완료" if done else "⬜ 미완료"
    print(f"[task:add-todo] {status} 추가됨: {new_line}")
    print(f"파일: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Add todo to Obsidian Daily Note")
    parser.add_argument("text", help="Todo item text")
    parser.add_argument("--done", action="store_true", help="Mark as already completed [x]")
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    add_todo(args.text, done=args.done, date_str=args.date)


if __name__ == "__main__":
    main()
