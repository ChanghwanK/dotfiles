#!/usr/bin/env python3
"""
Notion Task CLI (Read-only)

Usage:
  python3 notion-task.py dashboard [--week previous|current|next]
  python3 notion-task.py tasks [--week previous|current|next] [--month YYYY-MM] [--status in-progress|upcoming|all]
  python3 notion-task.py today
  python3 notion-task.py daily-progress
"""

import os
import sys
import json
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
    return monday.isoformat(), sunday.isoformat()


def get_month_range(month_str):
    """YYYY-MM 형식의 월 문자열로부터 해당 월의 첫날~마지막날 반환"""
    if len(month_str) != 7 or month_str[4] != "-":
        print(f"Error: Invalid month format '{month_str}'. Use YYYY-MM (e.g., 2026-03)", file=sys.stderr)
        sys.exit(1)
    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        if month < 1 or month > 12:
            raise ValueError("Month must be 1-12")
    except ValueError as e:
        print(f"Error: Invalid month format '{month_str}': {e}", file=sys.stderr)
        sys.exit(1)

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    return first_day.isoformat(), last_day.isoformat()


def query_tasks(token, start_date, end_date):
    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": start_date}},
                {"property": "Due Date", "date": {"on_or_before": end_date}},
            ]
        },
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)

    tasks = {"in_progress": [], "upcoming": [], "waiting": [], "completed": []}
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

        task = {
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": status,
            "due_date": due.get("start", ""),
            "category": category,
            "tags": tags,
        }

        if status == "진행 중":
            tasks["in_progress"].append(task)
        elif status in ("시작 전", ""):
            tasks["upcoming"].append(task)
        elif status == "대기":
            tasks["waiting"].append(task)
        elif status == "완료":
            tasks["completed"].append(task)

    return tasks


def query_all_in_progress(token):
    """진행 중인 모든 Task를 조회한다 (Due Date 유무 무관)."""
    body = {
        "filter": {"property": "상태", "status": {"equals": "진행 중"}},
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)

    tasks = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        name = rich_text_to_plain(props.get("이름", {}).get("title", []))
        priority_sel = props.get("Priority", {}).get("select")
        priority = priority_sel.get("name", "") if priority_sel else ""
        due = props.get("Due Date", {}).get("date") or {}
        category_sel = props.get("Category", {}).get("select")
        category = category_sel.get("name", "") if category_sel else ""
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]

        tasks.append({
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": "진행 중",
            "due_date": due.get("start", ""),
            "category": category,
            "tags": tags,
        })

    return tasks


def query_daily_progress(token, monday, sunday):
    today_str = date.today().isoformat()
    end = min(sunday, today_str)

    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": monday}},
                {"property": "Due Date", "date": {"on_or_before": end}},
            ]
        },
        "sorts": [{"property": "Due Date", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{DAILY_DB_ID}/query", body)

    days = []
    total_done = 0
    total_todos = 0

    for page in resp.get("results", []):
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

        days.append({
            "date": due_date,
            "name": name,
            "total": total_count,
            "done": done_count,
            "rate": round(done_count / total_count, 2) if total_count > 0 else 0,
        })

    week_rate = round(total_done / total_todos, 2) if total_todos > 0 else 0
    return {"days": days, "week_rate": week_rate}


def cmd_dashboard(args):
    token = get_token()
    week = getattr(args, "week", "current")
    monday, sunday = get_week_range(week)

    tasks = query_tasks(token, monday, sunday)
    all_in_progress = query_all_in_progress(token)
    daily_progress = query_daily_progress(token, monday, sunday)

    # 이번 주 Due Date 범위에 이미 포함된 진행 중 Task의 page_id 수집
    existing_ids = {t["page_id"] for t in tasks["in_progress"]}

    # Due Date가 없는 진행 중 Task 분리
    in_progress_no_due = []
    for t in all_in_progress:
        if t["page_id"] in existing_ids:
            continue
        if not t["due_date"]:
            in_progress_no_due.append(t)
        else:
            # Due Date가 이번 주 범위 밖이지만 진행 중인 Task → 이번 주에 포함
            tasks["in_progress"].append(t)
            existing_ids.add(t["page_id"])

    output = {
        "week": {"start": monday, "end": sunday},
        "tasks": tasks,
        "in_progress_no_due": in_progress_no_due,
        "daily_progress": daily_progress,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_tasks(args):
    token = get_token()
    month = getattr(args, "month", None)

    if month:
        start_date, end_date = get_month_range(month)
    else:
        week = getattr(args, "week", "current")
        start_date, end_date = get_week_range(week)

    status_filter = getattr(args, "status", "all")
    tasks = query_tasks(token, start_date, end_date)

    if status_filter == "in-progress":
        result = tasks["in_progress"]
    elif status_filter == "upcoming":
        result = tasks["upcoming"]
    else:
        result = tasks

    print(json.dumps({
        "period": {"start": start_date, "end": end_date},
        "tasks": result,
    }, ensure_ascii=False, indent=2))


OBSIDIAN_DAILY_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily"
)


def parse_obsidian_daily(file_path):
    """Obsidian daily note 파일을 파싱하여 구조화된 데이터를 반환한다."""
    import re

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 섹션별 분리
    sections = {}
    current_section = None
    current_lines = []
    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = current_lines
            current_section = line[3:].strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)
    if current_section:
        sections[current_section] = current_lines

    def parse_todo_line(line):
        """Todo 라인을 파싱하여 dict 반환. 서브항목(탭 시작)은 None 반환."""
        stripped = line.strip()
        if not stripped.startswith("- ["):
            return None
        done = stripped.startswith("- [x]")
        text = stripped[5:].strip()

        # 날짜 추출
        due_match = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", text)
        due_date = due_match.group(1) if due_match else ""

        # 우선순위 추출
        high_priority = "⏫" in text

        # 메타데이터 제거하여 클린 텍스트 생성
        clean = text
        clean = re.sub(r"🛫\s*\d{4}-\d{2}-\d{2}\s*", "", clean)
        clean = re.sub(r"📅\s*\d{4}-\d{2}-\d{2}\s*", "", clean)
        clean = re.sub(r"✅\s*\d{4}-\d{2}-\d{2}", "", clean)
        clean = re.sub(r"[⏫🔼🔽⏬]", "", clean)
        clean = clean.strip()

        return {
            "text": clean,
            "done": done,
            "due_date": due_date,
            "high_priority": high_priority,
        }

    # Top 3 파싱
    top3 = []
    for line in sections.get("Top 3 오늘의 목표", []):
        todo = parse_todo_line(line)
        if todo and not line.startswith("\t"):
            top3.append(todo)

    # Todos 파싱 (최상위 항목만)
    todos = []
    for line in sections.get("Todos", []):
        if line.startswith("\t") or line.startswith("    "):
            continue
        todo = parse_todo_line(line)
        if todo:
            todos.append(todo)

    done_count = sum(1 for t in todos if t["done"])
    total_count = len(todos)

    return {
        "top3": top3,
        "todos": todos,
        "progress": {
            "done": done_count,
            "total": total_count,
            "rate": round(done_count / total_count, 2) if total_count > 0 else 0,
        },
    }


def cmd_today(args):
    """오늘 기준 경량 브리핑 — Obsidian daily note에서 데이터를 가져온다."""
    today_str = date.today().isoformat()
    daily_file = os.path.join(OBSIDIAN_DAILY_DIR, f"{today_str}.md")

    if not os.path.exists(daily_file):
        print(json.dumps({"error": f"Daily note not found: {daily_file}"}, ensure_ascii=False))
        sys.exit(1)

    parsed = parse_obsidian_daily(daily_file)

    output = {
        "date": today_str,
        "source": "obsidian",
        "top3": parsed["top3"],
        "todos": {
            "in_progress": [t for t in parsed["todos"] if not t["done"]],
            "completed": [t for t in parsed["todos"] if t["done"]],
        },
        "progress": parsed["progress"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_daily_progress(args):
    token = get_token()
    monday, sunday = get_week_range("current")
    progress = query_daily_progress(token, monday, sunday)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Task CLI (Read-only)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # dashboard
    dash = subparsers.add_parser("dashboard", help="Unified view: Task + Daily Progress")
    dash.add_argument("--week", choices=["previous", "current", "next"], default="current")

    # tasks
    tasks_p = subparsers.add_parser("tasks", help="Task DB query")
    tasks_p.add_argument("--week", choices=["previous", "current", "next"], default="current")
    tasks_p.add_argument("--month", default=None, help="YYYY-MM format (overrides --week)")
    tasks_p.add_argument("--status", choices=["in-progress", "upcoming", "all"], default="all")

    # today
    subparsers.add_parser("today", help="Today's lightweight briefing")

    # daily-progress
    subparsers.add_parser("daily-progress", help="Daily DB this week progress")

    args = parser.parse_args()

    if args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "tasks":
        cmd_tasks(args)
    elif args.command == "today":
        cmd_today(args)
    elif args.command == "daily-progress":
        cmd_daily_progress(args)


if __name__ == "__main__":
    main()
