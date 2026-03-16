#!/usr/bin/env python3
"""
Notion Weekly CLI (Read-only)

Usage:
  python3 notion-weekly.py weekly-daily-summary --week previous|current
  python3 notion-weekly.py weekly-review
  python3 notion-weekly.py quarterly-goals [--quarter Q1-2026]
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
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"
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
        "Notion-Version": "2022-06-28",
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


def query_tasks_in_range(token, start_date, end_date):
    """Task DB에서 Due Date 범위 내 항목 조회."""
    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": start_date.isoformat()}},
                {"property": "Due Date", "date": {"on_or_before": end_date.isoformat()}},
            ]
        },
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)

    tasks = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        name = rich_text_to_plain(props.get("이름", {}).get("title", []))
        priority_sel = props.get("Priority", {}).get("select")
        priority = priority_sel.get("name", "") if priority_sel else ""
        status_obj = props.get("상태", {}).get("status")
        status = status_obj.get("name", "") if status_obj else ""
        due = props.get("Due Date", {}).get("date") or {}
        category_sel = props.get("Category", {}).get("select")
        category = category_sel.get("name", "") if category_sel else ""
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]

        tasks.append({
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": status,
            "due_date": due.get("start", ""),
            "category": category,
            "tags": tags,
        })
    return tasks


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
    resp = notion_request(token, "POST", f"/databases/{DAILY_DB_ID}/query", body)
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
        name = rich_text_to_plain(props.get("이름", {}).get("title", []))
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


def cmd_weekly_review(args):
    """
    지난 주 Task 완료 통계.
    previous week 쿼리 + current week 쿼리 → 완료/미완료/이월 분류.
    이월 = 지난 주 미완료 중 이번 주에 Due Date가 없는 항목 (또는 이번 주에 동일 항목이 없는 것).
    """
    token = get_token()
    prev_monday, prev_sunday = get_week_range("previous")
    curr_monday, curr_sunday = get_week_range("current")

    prev_tasks = query_tasks_in_range(token, prev_monday, prev_sunday)
    curr_tasks = query_tasks_in_range(token, curr_monday, curr_sunday)

    # 이번 주 Task 이름 집합 (이월 감지용)
    curr_task_names = {t["name"] for t in curr_tasks}

    completed = []
    incomplete_carried = []
    incomplete_dropped = []

    for t in prev_tasks:
        if t["status"] == "완료":
            completed.append(t)
        else:
            # 이번 주에 동일 이름이 있으면 이월된 것
            if t["name"] in curr_task_names:
                incomplete_carried.append(t)
            else:
                incomplete_dropped.append(t)

    total = len(prev_tasks)
    completed_count = len(completed)
    completion_rate = round(completed_count / total, 2) if total > 0 else 0

    prev_week_label = get_week_number(prev_monday)
    curr_week_label = get_week_number(curr_monday)

    print(json.dumps({
        "previous_week": prev_week_label,
        "current_week": curr_week_label,
        "stats": {
            "total": total,
            "completed": completed_count,
            "incomplete": total - completed_count,
            "carried_over": len(incomplete_carried),
            "dropped": len(incomplete_dropped),
            "completion_rate": completion_rate,
        },
        "completed_tasks": completed,
        "incomplete_carried": incomplete_carried,
        "incomplete_dropped": incomplete_dropped,
        "current_week_tasks": curr_tasks,
    }, ensure_ascii=False, indent=2))


def infer_current_quarter():
    """현재 날짜 기반으로 분기 Tag 자동 추론 (예: Q1-2026)."""
    today = date.today()
    year = today.year
    month = today.month
    quarter = (month - 1) // 3 + 1
    return f"Q{quarter}-{year}"


def cmd_quarterly_goals(args):
    """
    분기 목표 Task 조회.
    Task DB에서 Tag multi_select 필터로 Q{N}-{YYYY} 패턴 검색.
    """
    token = get_token()

    quarter = getattr(args, "quarter", None)
    if not quarter:
        quarter = infer_current_quarter()

    # Tag 필터 — multi_select contains
    body = {
        "filter": {
            "property": "Tag",
            "multi_select": {"contains": quarter},
        },
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)

    tasks = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        name = rich_text_to_plain(props.get("이름", {}).get("title", []))
        priority_sel = props.get("Priority", {}).get("select")
        priority = priority_sel.get("name", "") if priority_sel else ""
        status_obj = props.get("상태", {}).get("status")
        status = status_obj.get("name", "") if status_obj else ""
        due = props.get("Due Date", {}).get("date") or {}
        category_sel = props.get("Category", {}).get("select")
        category = category_sel.get("name", "") if category_sel else ""
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]

        tasks.append({
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": status,
            "due_date": due.get("start", ""),
            "category": category,
            "tags": tags,
        })

    # 상태별 분류
    by_status = {
        "in_progress": [t for t in tasks if t["status"] == "진행 중"],
        "upcoming": [t for t in tasks if t["status"] in ("시작 전", "")],
        "waiting": [t for t in tasks if t["status"] == "대기"],
        "completed": [t for t in tasks if t["status"] == "완료"],
    }

    print(json.dumps({
        "quarter": quarter,
        "total": len(tasks),
        "by_status": {
            "in_progress": len(by_status["in_progress"]),
            "upcoming": len(by_status["upcoming"]),
            "waiting": len(by_status["waiting"]),
            "completed": len(by_status["completed"]),
        },
        "tasks": by_status,
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

    # weekly-review
    subparsers.add_parser(
        "weekly-review",
        help="지난 주 Task 완료 통계 + 이번 주 Task 현황"
    )

    # quarterly-goals
    qgoals = subparsers.add_parser(
        "quarterly-goals",
        help="분기 목표 Task 조회 (Tag 필터)"
    )
    qgoals.add_argument(
        "--quarter",
        default=None,
        help="조회할 분기 Tag (예: Q1-2026). 미지정 시 현재 분기 자동 추론"
    )

    args = parser.parse_args()

    if args.command == "weekly-daily-summary":
        cmd_weekly_daily_summary(args)
    elif args.command == "weekly-review":
        cmd_weekly_review(args)
    elif args.command == "quarterly-goals":
        cmd_quarterly_goals(args)


if __name__ == "__main__":
    main()
