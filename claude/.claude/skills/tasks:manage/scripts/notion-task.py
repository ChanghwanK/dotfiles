#!/usr/bin/env python3
"""
Notion Task CLI (Read + Write)

Usage:
  python3 notion-task.py dashboard [--week previous|current|next]
  python3 notion-task.py tasks [--week previous|current|next] [--month YYYY-MM] [--status in-progress|upcoming|all]
  python3 notion-task.py daily-progress
  python3 notion-task.py carry-over (--dry-run | --apply) [--page-ids id1,id2,...]
  python3 notion-task.py update-status --page-id <id> --status <시작 전|진행 중|완료|대기>
  python3 notion-task.py create-task --name "이름" --priority "P1 - Must Have" --due "YYYY-MM-DD" [--category "WORK"]
  python3 notion-task.py delete-task --page-id <id>
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


def query_in_progress_no_due(token):
    """진행 중이지만 Due Date가 없는 Task를 조회한다."""
    body = {
        "filter": {
            "and": [
                {"property": "상태", "status": {"equals": "진행 중"}},
                {"property": "Due Date", "date": {"is_empty": True}},
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
        category_sel = props.get("Category", {}).get("select")
        category = category_sel.get("name", "") if category_sel else ""
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]

        tasks.append({
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": "진행 중",
            "due_date": "",
            "category": category,
            "tags": tags,
        })

    return tasks


def query_tasks_flat(token, start_date, end_date):
    """query_tasks()와 동일하지만 버킷 분리 없이 flat list 반환"""
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
    in_progress_no_due = query_in_progress_no_due(token)
    daily_progress = query_daily_progress(token, monday, sunday)

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


def cmd_carry_over(args):
    token = get_token()
    prev_monday, prev_sunday = get_week_range("previous")
    current_monday, _ = get_week_range("current")

    all_tasks = query_tasks_flat(token, prev_monday, prev_sunday)
    targets = [t for t in all_tasks if t["status"] != "완료"]

    if args.page_ids:
        id_set = set(args.page_ids.split(","))
        targets = [t for t in targets if t["page_id"] in id_set]

    if args.dry_run:
        print(json.dumps({
            "mode": "dry-run",
            "previous_week": {"start": prev_monday, "end": prev_sunday},
            "carry_over_to": current_monday,
            "total_tasks": len(all_tasks),
            "targets": targets,
        }, ensure_ascii=False, indent=2))
        return

    updated = []
    for task in targets:
        notion_request(token, "PATCH", f"/pages/{task['page_id']}", {
            "properties": {
                "Due Date": {"date": {"start": current_monday}}
            }
        })
        updated.append(task)

    print(json.dumps({
        "mode": "apply",
        "carry_over_to": current_monday,
        "updated": updated,
    }, ensure_ascii=False, indent=2))


def cmd_update_status(args):
    token = get_token()
    notion_request(token, "PATCH", f"/pages/{args.page_id}", {
        "properties": {
            "상태": {"status": {"name": args.status}}
        }
    })
    print(json.dumps({"updated": args.page_id, "status": args.status}, ensure_ascii=False))


def cmd_create_task(args):
    token = get_token()
    properties = {
        "이름": {"title": [{"text": {"content": args.name}}]},
        "Priority": {"select": {"name": args.priority}},
    }
    if args.due:
        properties["Due Date"] = {"date": {"start": args.due}}
    if args.category:
        properties["Group"] = {"select": {"name": args.category}}
    resp = notion_request(token, "POST", "/pages", {
        "parent": {"database_id": TASK_DB_ID},
        "properties": properties,
    })
    print(json.dumps({"created": resp["id"], "name": args.name}, ensure_ascii=False))


def cmd_delete_task(args):
    token = get_token()
    notion_request(token, "PATCH", f"/pages/{args.page_id}", {
        "archived": True
    })
    print(json.dumps({"archived": args.page_id}, ensure_ascii=False))


def cmd_daily_progress(args):
    token = get_token()
    monday, sunday = get_week_range("current")
    progress = query_daily_progress(token, monday, sunday)
    print(json.dumps(progress, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Task CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # dashboard
    dash = subparsers.add_parser("dashboard", help="Unified view: Task + Daily Progress")
    dash.add_argument("--week", choices=["previous", "current", "next"], default="current")

    # tasks
    tasks_p = subparsers.add_parser("tasks", help="Task DB query")
    tasks_p.add_argument("--week", choices=["previous", "current", "next"], default="current")
    tasks_p.add_argument("--month", default=None, help="YYYY-MM format (overrides --week)")
    tasks_p.add_argument("--status", choices=["in-progress", "upcoming", "all"], default="all")

    # carry-over
    carry_p = subparsers.add_parser("carry-over", help="Carry over incomplete tasks from previous week")
    carry_mode = carry_p.add_mutually_exclusive_group(required=True)
    carry_mode.add_argument("--dry-run", action="store_true", help="Preview carry-over targets")
    carry_mode.add_argument("--apply", action="store_true", help="Apply carry-over (update Due Date)")
    carry_p.add_argument("--page-ids", default=None, help="Comma-separated page IDs for selective carry-over")

    # update-status
    us_p = subparsers.add_parser("update-status", help="Update task status")
    us_p.add_argument("--page-id", required=True, help="Notion page ID")
    us_p.add_argument("--status", required=True, help="Target status (시작 전|진행 중|완료|대기)")

    # create-task
    ct_p = subparsers.add_parser("create-task", help="Create a new task")
    ct_p.add_argument("--name", required=True, help="Task name")
    ct_p.add_argument("--priority", required=True, help="P1 - Must Have | P2 - Nice to Have")
    ct_p.add_argument("--due", default=None, help="Due date (YYYY-MM-DD)")
    ct_p.add_argument("--category", default=None, help="Category (WORK|MY)")

    # delete-task
    dt_p = subparsers.add_parser("delete-task", help="Archive (delete) a task")
    dt_p.add_argument("--page-id", required=True, help="Notion page ID")

    # daily-progress
    subparsers.add_parser("daily-progress", help="Daily DB this week progress")

    args = parser.parse_args()

    cmd_map = {
        "dashboard": cmd_dashboard,
        "tasks": cmd_tasks,
        "carry-over": cmd_carry_over,
        "update-status": cmd_update_status,
        "create-task": cmd_create_task,
        "delete-task": cmd_delete_task,
        "daily-progress": cmd_daily_progress,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
