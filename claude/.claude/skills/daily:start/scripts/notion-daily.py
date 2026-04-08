#!/usr/bin/env python3
"""
Notion Daily Work Log CLI
Usage:
  python3 notion-daily.py read --date today|yesterday|YYYY-MM-DD
  python3 notion-daily.py read-weekly
  python3 notion-daily.py update-todos --page-id PAGE_ID --content "내용"
  python3 notion-daily.py update-tomorrow --page-id PAGE_ID --content "내용"
  python3 notion-daily.py update-kpt --page-id PAGE_ID --content "내용"
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta
import argparse

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"


def get_token():
    return NOTION_TOKEN


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


def resolve_date(date_str):
    today = date.today()
    if date_str == "today":
        return today.isoformat()
    elif date_str == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    else:
        try:
            date.fromisoformat(date_str)
            return date_str
        except ValueError:
            print(f"Invalid date format: {date_str}. Use today/yesterday/YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)


def get_week_range():
    """이번 주 월~일 ISO 날짜 반환."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def rich_text_to_plain(rich_text_list):
    """Extract plain text from rich_text array."""
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def parse_todos_from_rich_text(rich_text_list):
    """
    Parse todos from a rich_text property.
    Each rich_text segment may contain multiple lines.
    Strikethrough annotation on the segment marks those lines as done.

    Returns list of: {"text": "- item text", "done": bool}
    """
    todos = []
    for segment in rich_text_list:
        text = segment.get("plain_text", "")
        done = segment.get("annotations", {}).get("strikethrough", False)
        # Split by newline — each non-empty line is a todo item
        lines = text.split("\n")
        for line in lines:
            if line.strip():
                todos.append({"text": line, "done": done})
    return todos


def parse_page_properties(page):
    """
    Parse page properties into structured sections.
    Property names: "Todo's", "Note", "내일 할 것들", "KPT"
    """
    props = page.get("properties", {})

    def get_rich_text_plain(prop_name):
        prop = props.get(prop_name, {})
        rt = prop.get("rich_text", [])
        return rich_text_to_plain(rt)

    todos_rich_text = props.get("Todo's", {}).get("rich_text", [])
    todos = parse_todos_from_rich_text(todos_rich_text)

    return {
        "todos": todos,
        "note": get_rich_text_plain("Note"),
        "tomorrow": get_rich_text_plain("내일 할 것들"),
        "kpt": get_rich_text_plain("KPT"),
    }


def cmd_read(args):
    token = get_token()
    target_date = resolve_date(args.date)

    DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"

    # Query DB for the page with matching Due Date
    body = {
        "filter": {
            "property": "Due Date",
            "date": {
                "equals": target_date
            }
        }
    }
    resp = notion_request(token, "POST", f"/databases/{DB_ID}/query", body)
    results = resp.get("results", [])

    if not results:
        print(json.dumps({
            "page_id": None,
            "date": target_date,
            "todos": [],
            "note": "",
            "tomorrow": "",
            "kpt": "",
            "error": f"No page found for date {target_date}"
        }, ensure_ascii=False, indent=2))
        return

    page = results[0]
    page_id = page["id"]
    parsed = parse_page_properties(page)

    output = {
        "page_id": page_id,
        "date": target_date,
        "todos": parsed["todos"],
        "note": parsed["note"],
        "tomorrow": parsed["tomorrow"],
        "kpt": parsed["kpt"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def get_two_week_range():
    """이번 주 월요일 ~ 다음 주 일요일 ISO 날짜 반환."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    next_sunday = monday + timedelta(days=13)
    return monday.isoformat(), next_sunday.isoformat()


def cmd_read_weekly(args):
    """이번 주 + 다음 주 Task DB 항목 조회 (P1 우선).
    level 필드:
      - 'weekly_project': due_end 있음 + status 진행 중 (주간 프로젝트 목표)
      - 'daily': 그 외 일반 Task
    """
    token = get_token()
    monday, sunday = get_week_range()
    _, next_sunday = get_two_week_range()

    body = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"on_or_after": monday}},
                {"property": "Due Date", "date": {"on_or_before": next_sunday}},
            ]
        },
        "sorts": [{"property": "Priority", "direction": "ascending"}]
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
        tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]
        due_end = due.get("end", "")
        level = "weekly_project" if (due_end and status == "진행 중") else "daily"
        tasks.append({
            "page_id": page["id"],
            "name": name,
            "priority": priority,
            "status": status,
            "due_start": due.get("start", ""),
            "due_end": due_end,
            "tags": tags,
            "level": level,
        })

    print(json.dumps({
        "week_start": monday,
        "week_end": sunday,
        "next_week_end": next_sunday,
        "tasks": tasks
    }, ensure_ascii=False, indent=2))


def build_nested_blocks(content):
    """
    Parse content lines into nested Notion bulleted_list_item blocks.
    Top-level: lines starting with '- ' (no leading spaces)
    Children:  lines starting with '  - ' (2+ leading spaces)
    """
    blocks = []
    current_top = None

    for line in content.split("\n"):
        if not line.strip():
            continue

        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if not stripped.startswith("- "):
            continue

        text = stripped[2:]
        block = {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": text}}]
            }
        }

        if indent == 0:
            blocks.append(block)
            current_top = block
        else:
            if current_top is not None:
                current_top["bulleted_list_item"].setdefault("children", []).append(block)
            else:
                blocks.append(block)

    return blocks


def cmd_create(args):
    """
    Create a new daily page in the database if one doesn't exist for the given date.
    """
    token = get_token()
    target_date = resolve_date(args.date)

    DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"

    # Check if page already exists
    check_body = {
        "filter": {
            "property": "Due Date",
            "date": {"equals": target_date}
        }
    }
    check_resp = notion_request(token, "POST", f"/databases/{DB_ID}/query", check_body)
    if check_resp.get("results"):
        page = check_resp["results"][0]
        print(json.dumps({
            "created": False,
            "page_id": page["id"],
            "date": target_date,
            "message": "Page already exists"
        }, ensure_ascii=False, indent=2))
        return

    # Create new page
    title = args.title or f"@{target_date} 업무 일지"
    body = {
        "parent": {"database_id": DB_ID},
        "properties": {
            "이름": {
                "title": [{"type": "text", "text": {"content": title}}]
            },
            "Due Date": {
                "date": {"start": target_date}
            },
        }
    }

    resp = notion_request(token, "POST", "/pages", body)
    print(json.dumps({
        "created": True,
        "page_id": resp["id"],
        "date": target_date,
        "title": title
    }, ensure_ascii=False, indent=2))


def cmd_update_todos(args):
    """
    Replace the Todo's rich_text property on the given page.
    """
    cmd_update_property(args, "Todo's")


def cmd_update_property(args, prop_name):
    """
    Replace content of a rich_text property on the given page.
    """
    token = get_token()
    page_id = args.page_id
    content = args.content.replace("\\n", "\n")

    new_segments = []
    lines = content.split("\n")
    for line in lines:
        segment_text = line + "\n"
        new_segments.append({
            "type": "text",
            "text": {"content": segment_text},
            "annotations": {"strikethrough": False}
        })

    if not new_segments:
        print(json.dumps({"success": False, "error": "No content to add"}))
        return

    resp = notion_request(token, "PATCH", f"/pages/{page_id}", {
        "properties": {
            prop_name: {
                "rich_text": new_segments
            }
        }
    })

    print(json.dumps({
        "success": True,
        "property": prop_name,
        "segments_written": len(new_segments)
    }, ensure_ascii=False, indent=2))


def cmd_update_tomorrow(args):
    cmd_update_property(args, "내일 할 것들")


def cmd_update_kpt(args):
    cmd_update_property(args, "KPT")


def main():
    parser = argparse.ArgumentParser(description="Notion Daily Work Log CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # read command
    read_parser = subparsers.add_parser("read", help="Read daily work log")
    read_parser.add_argument("--date", required=True,
                             help="Date to read: today, yesterday, or YYYY-MM-DD")

    # update-todos command
    update_parser = subparsers.add_parser("update-todos", help="Append todos to a page")
    update_parser.add_argument("--page-id", required=True, help="Notion page ID")
    update_parser.add_argument("--content", required=True, help="Content to append (newline-separated)")

    # create command
    create_parser = subparsers.add_parser("create", help="Create a new daily page")
    create_parser.add_argument("--date", required=True,
                               help="Date for the new page: today, yesterday, or YYYY-MM-DD")
    create_parser.add_argument("--title", required=False,
                               help="Page title (default: @YYYY-MM-DD 업무 일지)")

    # update-tomorrow command
    tomorrow_parser = subparsers.add_parser("update-tomorrow", help="Replace 내일 할 것들 property")
    tomorrow_parser.add_argument("--page-id", required=True, help="Notion page ID")
    tomorrow_parser.add_argument("--content", required=True, help="Content to write (newline-separated)")

    # update-kpt command
    kpt_parser = subparsers.add_parser("update-kpt", help="Replace KPT property")
    kpt_parser.add_argument("--page-id", required=True, help="Notion page ID")
    kpt_parser.add_argument("--content", required=True, help="KPT content to write")

    # read-weekly command
    subparsers.add_parser("read-weekly", help="Read this week's tasks from Task DB")

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "update-todos":
        cmd_update_todos(args)
    elif args.command == "update-tomorrow":
        cmd_update_tomorrow(args)
    elif args.command == "update-kpt":
        cmd_update_kpt(args)
    elif args.command == "read-weekly":
        cmd_read_weekly(args)


if __name__ == "__main__":
    main()
