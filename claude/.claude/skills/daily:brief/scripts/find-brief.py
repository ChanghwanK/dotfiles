#!/usr/bin/env python3
"""daily:start 브리핑 JSON에서 하루 시작 Artifact 주소를 찾는다(읽기 전용).

usage: find-brief.py [--date YYYY-MM-DD]
  --date 생략 시 오늘(Asia/Seoul).
출력(JSON):
  성공 {"success": true, "date", "artifact_url", "title", "path"}
  실패 {"success": false, "date", "error", "latest"}  latest: 그 날짜 이전 가장 최근 브리핑 날짜 또는 null
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BRIEF_DIR = Path.home() / ".claude" / "tmp" / "daily-start"
KST = timezone(timedelta(hours=9))
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def latest_before(date: str):
    """date 이전(당일 포함 안 함) 브리핑 중 artifact_url이 있는 가장 최근 날짜."""
    dates = sorted(p.stem for p in BRIEF_DIR.glob("*.json") if DATE_RE.match(p.stem) and p.stem < date)
    for d in reversed(dates):
        try:
            if json.loads((BRIEF_DIR / f"{d}.json").read_text(encoding="utf-8")).get("artifact_url"):
                return d
        except (OSError, ValueError):
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="하루 시작 Artifact 주소 찾기")
    parser.add_argument("--date", help="YYYY-MM-DD (기본: 오늘, Asia/Seoul)")
    args = parser.parse_args()

    date = args.date or datetime.now(KST).strftime("%Y-%m-%d")
    if not DATE_RE.match(date):
        print(json.dumps({"success": False, "date": date, "error": "날짜는 YYYY-MM-DD 형식이어야 합니다", "latest": None},
                         ensure_ascii=False))
        return 1

    path = BRIEF_DIR / f"{date}.json"
    if not path.exists():
        print(json.dumps({"success": False, "date": date, "error": f"{date} 브리핑 JSON이 없습니다",
                          "latest": latest_before(date)}, ensure_ascii=False))
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(json.dumps({"success": False, "date": date, "error": f"브리핑 JSON을 읽지 못했습니다: {e}",
                          "latest": latest_before(date)}, ensure_ascii=False))
        return 1

    url = data.get("artifact_url")
    if not url or not str(url).startswith("https://claude.ai/"):
        print(json.dumps({"success": False, "date": date, "error": f"{date} 브리핑에 artifact_url이 없습니다(게시 전에 멈춤)",
                          "latest": latest_before(date)}, ensure_ascii=False))
        return 1

    print(json.dumps({"success": True, "date": date, "artifact_url": url, "title": data.get("title"),
                      "path": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
