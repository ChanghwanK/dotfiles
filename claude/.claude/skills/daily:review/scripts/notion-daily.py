#!/usr/bin/env python3
"""
Notion Daily Work Log CLI
Usage:
  python3 notion-daily.py read --date today|yesterday|YYYY-MM-DD
  python3 notion-daily.py update-todos --page-id PAGE_ID --content "내용"
  python3 notion-daily.py update-tomorrow --page-id PAGE_ID --content "내용"
  python3 notion-daily.py update-kpt --page-id PAGE_ID --content "내용"
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta
import argparse

def get_token():
    import os
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("Error: NOTION_TOKEN environment variable is not set", file=sys.stderr)
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


def cmd_update_todos(args):
    """
    Append content to the Todo's property of the given page.
    Reads current value, appends new lines, and PATCHes the page.
    """
    token = get_token()
    page_id = args.page_id
    content = args.content.replace("\\n", "\n")

    # Fetch current page to get existing Todo's value
    page = notion_request(token, "GET", f"/pages/{page_id}")
    existing_rt = page.get("properties", {}).get("Todo's", {}).get("rich_text", [])

    # Build new rich_text segments from content
    new_segments = []
    lines = content.split("\n")
    for line in lines:
        if line:  # include non-empty lines (including lines with just spaces)
            new_segments.append({
                "type": "text",
                "text": {"content": line + "\n"},
                "annotations": {
                    "strikethrough": False
                }
            })

    if not new_segments:
        print(json.dumps({"success": False, "error": "No content to add"}))
        return

    # Append to existing rich_text
    updated_rt = existing_rt + new_segments

    # PATCH the page property
    resp = notion_request(token, "PATCH", f"/pages/{page_id}", {
        "properties": {
            "Todo's": {
                "rich_text": updated_rt
            }
        }
    })

    print(json.dumps({
        "success": True,
        "segments_added": len(new_segments),
        "total_segments": len(updated_rt)
    }, ensure_ascii=False, indent=2))


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

    # update-tomorrow command
    tomorrow_parser = subparsers.add_parser("update-tomorrow", help="Replace 내일 할 것들 property")
    tomorrow_parser.add_argument("--page-id", required=True, help="Notion page ID")
    tomorrow_parser.add_argument("--content", required=True, help="Content to write (newline-separated)")

    # update-kpt command
    kpt_parser = subparsers.add_parser("update-kpt", help="Replace KPT property")
    kpt_parser.add_argument("--page-id", required=True, help="Notion page ID")
    kpt_parser.add_argument("--content", required=True, help="KPT content to write")

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args)
    elif args.command == "update-todos":
        cmd_update_todos(args)
    elif args.command == "update-tomorrow":
        cmd_update_tomorrow(args)
    elif args.command == "update-kpt":
        cmd_update_kpt(args)


if __name__ == "__main__":
    main()
