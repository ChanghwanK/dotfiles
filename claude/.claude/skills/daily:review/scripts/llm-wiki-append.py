#!/usr/bin/env python3
"""LLM Wiki Raw 아카이브 스크립트 - 일일 핵심 기록을 LLM Wiki Raw 폴더에 append."""

import argparse
import json
import os
from datetime import date
from pathlib import Path

VAULT_PATH = Path("/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home")
LLM_WIKI_RAW_DIR = VAULT_PATH / "06. LLM-Wiki" / "raw"


def append_entry(entry_date: str, content: str) -> dict:
    try:
        LLM_WIKI_RAW_DIR.mkdir(parents=True, exist_ok=True)
        file_path = LLM_WIKI_RAW_DIR / f"{entry_date}.md"

        is_new = not file_path.exists()

        with open(file_path, "a", encoding="utf-8") as f:
            if is_new:
                f.write(f"# {entry_date} 핵심 기록\n")
            f.write("\n---\n\n")
            f.write(content.strip())
            f.write("\n")

        return {
            "success": True,
            "file": str(file_path),
            "created": is_new,
            "date": entry_date,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="LLM Wiki Raw 아카이브")
    parser.add_argument("--date", default=str(date.today()), help="날짜 (YYYY-MM-DD)")
    parser.add_argument("--content", required=True, help="기록할 마크다운 내용")
    args = parser.parse_args()

    result = append_entry(args.date, args.content)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
