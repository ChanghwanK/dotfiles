#!/usr/bin/env python3
"""
Notion Schedule View CLI

Usage:
  python3 notion-schedule.py dashboard [--week current|next]
  python3 notion-schedule.py tasks [--week current|next] [--status in-progress|upcoming|all]
  python3 notion-schedule.py goals
  python3 notion-schedule.py daily-progress
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
GOAL_DB_ID = "2db64745-3170-8072-83da-ee01e505f003"
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
    if week == "next":
        monday = monday + timedelta(days=7)
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def query_tasks(token, monday, sunday):
    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": monday}},
                {"property": "Due Date", "date": {"on_or_before": sunday}},
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


def query_goals(token):
    body = {
        "filter": {
            "property": "Done",
            "checkbox": {"equals": False},
        },
        "sorts": [{"property": "Priority Level", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{GOAL_DB_ID}/query", body)

    goals = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        name = rich_text_to_plain(props.get("이름", {}).get("title", []))
        priority_sel = props.get("Priority Level", {}).get("select")
        priority = priority_sel.get("name", "") if priority_sel else ""
        type_sel = props.get("유형", {}).get("select")
        goal_type = type_sel.get("name", "") if type_sel else ""
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]
        desc_rt = props.get("Goal Description", {}).get("rich_text", [])
        description = rich_text_to_plain(desc_rt)

        goals.append({
            "name": name,
            "priority": priority,
            "type": goal_type,
            "tags": tags,
            "description": description[:100] if description else "",
        })

    return goals


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
    goals = query_goals(token)
    daily_progress = query_daily_progress(token, monday, sunday)

    output = {
        "week": {"start": monday, "end": sunday},
        "tasks": tasks,
        "goals": {"active": goals},
        "daily_progress": daily_progress,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_tasks(args):
    token = get_token()
    week = getattr(args, "week", "current")
    monday, sunday = get_week_range(week)
    status_filter = getattr(args, "status", "all")

    tasks = query_tasks(token, monday, sunday)

    if status_filter == "in-progress":
        result = tasks["in_progress"]
    elif status_filter == "upcoming":
        result = tasks["upcoming"]
    else:
        result = tasks

    print(json.dumps({
        "week": {"start": monday, "end": sunday},
        "tasks": result,
    }, ensure_ascii=False, indent=2))


def cmd_goals(args):
    token = get_token()
    goals = query_goals(token)
    print(json.dumps({"goals": goals}, ensure_ascii=False, indent=2))


def cmd_daily_progress(args):
    token = get_token()
    monday, sunday = get_week_range("current")
    progress = query_daily_progress(token, monday, sunday)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Schedule View CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # dashboard
    dash = subparsers.add_parser("dashboard", help="Unified view: Task + Goal + Daily")
    dash.add_argument("--week", choices=["current", "next"], default="current")

    # tasks
    tasks_p = subparsers.add_parser("tasks", help="Task DB query")
    tasks_p.add_argument("--week", choices=["current", "next"], default="current")
    tasks_p.add_argument("--status", choices=["in-progress", "upcoming", "all"], default="all")

    # goals
    subparsers.add_parser("goals", help="Active goals from Goal DB")

    # daily-progress
    subparsers.add_parser("daily-progress", help="Daily DB this week progress")

    args = parser.parse_args()

    if args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "tasks":
        cmd_tasks(args)
    elif args.command == "goals":
        cmd_goals(args)
    elif args.command == "daily-progress":
        cmd_daily_progress(args)


if __name__ == "__main__":
    main()
