#!/usr/bin/env python3
"""
오늘 작업한 Claude 세션들의 transcript를 읽어
주요 작업 내용을 추출하는 스크립트.

사용법:
  python3 extract-work.py [--date YYYY-MM-DD]

출력: JSON
  {
    "date": "2026-02-26",
    "sessions": [
      {
        "project": "riiid-kubernetes",
        "file": "...",
        "user_messages": ["메시지1", "메시지2"]
      }
    ],
    "summary": ["작업 요약1", "작업 요약2"]
  }
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import date, datetime

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# 필터링할 짧거나 무의미한 패턴
SKIP_PATTERNS = [
    "y", "n", "yes", "no", "ok", "ㅇㅇ", "응", "네", "아니",
]

# system reminder 태그 포함 메시지 스킵
SKIP_SUBSTRINGS = [
    "<system-reminder>",
    "<command-message>",
    "<local-command-",
    "Base directory for this skill",
    "UserPromptSubmit hook",
    "SessionStart",
    "[Request interrupted",
    "Caveat: The messages below",
]

# 프로젝트 디렉토리명 → 사람이 읽을 수 있는 이름
def parse_project_name(dir_name: str) -> str:
    # -Users-changhwan-workspace-riiid-kubernetes → riiid-kubernetes
    # -Users-changhwan--claude → .claude (home)
    name = dir_name
    for prefix in [
        "-Users-changhwan-workspace-",
        "-Users-changhwan--",
        "-Users-changhwan-",
    ]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name or dir_name


def is_meaningful_message(text: str) -> bool:
    """의미 있는 사용자 메시지인지 판별"""
    stripped = text.strip()

    if len(stripped) < 5:
        return False

    if stripped.lower() in SKIP_PATTERNS:
        return False

    for sub in SKIP_SUBSTRINGS:
        if sub in stripped:
            return False

    return True


def extract_user_messages(jsonl_path: Path) -> list[str]:
    """JSONL transcript에서 user 메시지 추출"""
    messages = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "user":
                    continue

                msg = entry.get("message", {})
                content = msg.get("content", "")

                texts = []
                if isinstance(content, str):
                    texts = [content]
                elif isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            texts.append(c.get("text", ""))

                for text in texts:
                    if is_meaningful_message(text):
                        # 너무 긴 메시지는 앞부분만
                        messages.append(text[:300].strip())
    except Exception as e:
        sys.stderr.write(f"warn: failed to read {jsonl_path}: {e}\n")
    return messages


def get_file_date(path: Path) -> date:
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).date()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="today",
                        help="날짜 (today 또는 YYYY-MM-DD)")
    args = parser.parse_args()

    if args.date == "today":
        target_date = date.today()
    else:
        target_date = date.fromisoformat(args.date)

    sessions = []

    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        # mem-observer, subagents 제외
        dir_name = project_dir.name
        if "mem-observer" in dir_name:
            continue

        project_name = parse_project_name(dir_name)

        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            # 오늘 수정된 파일만
            if get_file_date(jsonl_file) != target_date:
                continue

            messages = extract_user_messages(jsonl_file)
            if messages:
                sessions.append({
                    "project": project_name,
                    "file": str(jsonl_file),
                    "user_messages": messages,
                })

    result = {
        "date": target_date.isoformat(),
        "sessions": sessions,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
