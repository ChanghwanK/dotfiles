#!/usr/bin/env python3
"""
Notion Weekly CLI (Read-only): Daily DB 주간 요약

weekly:4l-review 전용. 2026-09-18 weekly:start 스킬을 제거하면서 이 스킬이 쓰던
weekly-daily-summary만 옮겨 왔다(Task DB 조회 명령은 소비자가 없어 삭제).

Usage:
  python3 notion-weekly.py weekly-daily-summary --week previous|current
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
from datetime import date, timedelta
import argparse

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DAILY_DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"


def get_token():
    token = NOTION_TOKEN
    if not token:
        print("Error: NOTION_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)
    return token


def notion_request(token, method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


# ── data source resolution (Notion-Version 2025-09-03) ────────
# 2025-09-03부터 쿼리는 database가 아니라 data source 단위다.
# 단일 data source DB를 전제로 db_id→ds_id를 1회 조회 후 프로세스 내 캐시한다.
_DS_CACHE = {}


def resolve_ds_id(token, db_id):
    """db_id → data source id (프로세스 내 캐시). 2025-09-03 쿼리/생성에 필요."""
    if db_id not in _DS_CACHE:
        db = notion_request(token, "GET", f"/databases/{db_id}")
        sources = db.get("data_sources", [])
        if not sources:
            raise RuntimeError(f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


def rich_text_to_plain(rich_text_list):
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def parse_todos_from_rich_text(rich_text_list):
    """strikethrough 어노테이션으로 완료 여부 판단."""
    todos = []
    for segment in rich_text_list:
        text = segment.get("plain_text", "")
        done = segment.get("annotations", {}).get("strikethrough", False)
        for line in text.split("\n"):
            if line.strip():
                todos.append({"text": line, "done": done})
    return todos


def get_week_range(week="current"):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if week == "previous":
        monday = monday - timedelta(days=7)
    elif week == "next":
        monday = monday + timedelta(days=7)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_week_number(d):
    """ISO week number 반환 (예: 2026-W10)."""
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def query_daily_pages_in_range(token, start_date, end_date):
    """Daily DB에서 날짜 범위 내 페이지 조회."""
    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": start_date.isoformat()}},
                {"property": "Due Date", "date": {"on_or_before": end_date.isoformat()}},
            ]
        },
        "sorts": [{"property": "Due Date", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, DAILY_DB_ID)}/query", body)
    return resp.get("results", [])


def parse_kpt(kpt_text):
    """KPT 텍스트를 Keep/Problem/Try 섹션으로 파싱."""
    kpt = {"keep": [], "problem": [], "try": []}
    if not kpt_text:
        return kpt

    current = None
    for line in kpt_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("k:") or lower.startswith("keep:") or lower == "k" or lower == "keep":
            current = "keep"
            rest = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
            if rest:
                kpt["keep"].append(rest)
        elif lower.startswith("p:") or lower.startswith("problem:") or lower == "p" or lower == "problem":
            current = "problem"
            rest = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
            if rest:
                kpt["problem"].append(rest)
        elif lower.startswith("t:") or lower.startswith("try:") or lower == "t" or lower == "try":
            current = "try"
            rest = stripped.split(":", 1)[-1].strip() if ":" in stripped else ""
            if rest:
                kpt["try"].append(rest)
        elif current and (stripped.startswith("- ") or stripped.startswith("* ")):
            kpt[current].append(stripped[2:])
        elif current:
            kpt[current].append(stripped)

    return kpt


def cmd_weekly_daily_summary(args):
    """
    Daily DB 기반 주간 일별 요약.
    월~금 Due Date 범위로 페이지 조회 → 날별 todos 완료율, KPT, Note 파싱.
    """
    token = get_token()
    week = getattr(args, "week", "previous")
    monday, sunday = get_week_range(week)
    week_label = get_week_number(monday)

    pages = query_daily_pages_in_range(token, monday, sunday)

    days = []
    total_done = 0
    total_todos = 0

    for page in pages:
        props = page.get("properties", {})
        name = rich_text_to_plain(props.get("Title", {}).get("title", []))
        due = props.get("Due Date", {}).get("date") or {}
        due_date = due.get("start", "")

        todos_rt = props.get("Todo's", {}).get("rich_text", [])
        todos = parse_todos_from_rich_text(todos_rt)
        done_count = sum(1 for t in todos if t["done"])
        total_count = len(todos)

        total_done += done_count
        total_todos += total_count

        note_rt = props.get("Note", {}).get("rich_text", [])
        note = rich_text_to_plain(note_rt)

        kpt_rt = props.get("KPT", {}).get("rich_text", [])
        kpt_text = rich_text_to_plain(kpt_rt)
        kpt = parse_kpt(kpt_text)

        days.append({
            "date": due_date,
            "name": name,
            "todos": {
                "items": todos,
                "done": done_count,
                "total": total_count,
                "rate": round(done_count / total_count, 2) if total_count > 0 else 0,
            },
            "note": note,
            "kpt": kpt,
        })

    week_rate = round(total_done / total_todos, 2) if total_todos > 0 else 0

    print(json.dumps({
        "week": week_label,
        "period": {"start": monday.isoformat(), "end": sunday.isoformat()},
        "summary": {
            "total_done": total_done,
            "total_todos": total_todos,
            "week_rate": week_rate,
            "days_recorded": len(days),
        },
        "days": days,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Weekly CLI (Read-only)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # weekly-daily-summary
    daily_sum = subparsers.add_parser(
        "weekly-daily-summary",
        help="Daily DB 기반 주간 일별 요약 (완료율, KPT, Note)"
    )
    daily_sum.add_argument(
        "--week",
        choices=["previous", "current"],
        default="previous",
        help="조회할 주 (기본: previous)"
    )

    args = parser.parse_args()

    if args.command == "weekly-daily-summary":
        cmd_weekly_daily_summary(args)


if __name__ == "__main__":
    main()
