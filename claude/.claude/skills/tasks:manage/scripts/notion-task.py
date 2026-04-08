#!/usr/bin/env python3
"""
Notion Task CLI (Write + Query)

공유 라이브러리 스크립트 — tasks:capture, tasks:status, tasks:carry-over,
daily:start, daily:review 스킬에서 참조한다.

Usage:
  # 조회
  python3 notion-task.py search-tasks [--status all|active]
  python3 notion-task.py tasks [--week current|previous|next] [--month YYYY-MM] [--status in-progress|upcoming|all]

  # 생성
  python3 notion-task.py create-task --name "이름" --priority "P3 - Could Have" --category "WORK" [--due "YYYY-MM-DD"] [--description "설명"]

  # 상태 변경
  python3 notion-task.py update-status --page-id <id> --status "진행 중"

  # 삭제 (아카이브)
  python3 notion-task.py delete-task --page-id <id>

  # 이월
  python3 notion-task.py carry-over --dry-run
  python3 notion-task.py carry-over --apply [--page-ids id1,id2,...]
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse
from datetime import date, timedelta

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

VALID_STATUSES = {"시작 전", "진행 중", "완료", "대기"}
PRIORITY_OPTIONS = {
    "P1 - Must Have",
    "P2 - Should Have",
    "P3 - Could Have",
    "P4 - Won't Have",
}
CATEGORY_OPTIONS = {"WORK", "MY"}


# ─────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────

def get_token():
    token = NOTION_TOKEN
    if not token:
        _exit_error("NOTION_TOKEN environment variable not set")
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
        _exit_error(f"HTTP {e.code}: {err_body}")


def rich_text_to_plain(rich_text_list):
    return "".join(item.get("plain_text", "") for item in rich_text_list)


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
    if len(month_str) != 7 or month_str[4] != "-":
        _exit_error(f"Invalid month format '{month_str}'. Use YYYY-MM (e.g., 2026-03)")
    try:
        year, month = int(month_str[:4]), int(month_str[5:7])
        if month < 1 or month > 12:
            raise ValueError("Month must be 1-12")
    except ValueError as e:
        _exit_error(f"Invalid month format '{month_str}': {e}")

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    return first_day.isoformat(), last_day.isoformat()


def _exit_error(message):
    print(json.dumps({"success": False, "error": message}, ensure_ascii=False))
    sys.exit(1)


def _parse_page(page):
    props = page.get("properties", {})
    name = rich_text_to_plain(props.get("이름", {}).get("title", []))
    priority_sel = props.get("Priority", {}).get("select")
    priority = priority_sel.get("name", "") if priority_sel else ""
    status_obj = props.get("상태", {}).get("status")
    status = status_obj.get("name", "") if status_obj else ""
    due = props.get("Due Date", {}).get("date") or {}
    category_sel = props.get("Group", {}).get("select")
    category = category_sel.get("name", "") if category_sel else ""
    tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]
    return {
        "page_id": page["id"],
        "name": name,
        "priority": priority,
        "status": status,
        "due_date": due.get("start", ""),
        "category": category,
        "tags": tags,
    }


# ─────────────────────────────────────────────
# 조회
# ─────────────────────────────────────────────

def query_tasks_by_period(token, start_date, end_date):
    """Due Date 범위 기반 Task 조회. 상태별로 분류하여 반환."""
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
        task = _parse_page(page)
        status = task["status"]
        if status == "진행 중":
            tasks["in_progress"].append(task)
        elif status in ("시작 전", ""):
            tasks["upcoming"].append(task)
        elif status == "대기":
            tasks["waiting"].append(task)
        elif status == "완료":
            tasks["completed"].append(task)

    return tasks


def query_active_tasks(token):
    """완료 제외 모든 활성 Task 조회 (Due Date 유무 무관)."""
    body = {
        "filter": {
            "property": "상태",
            "status": {"does_not_equal": "완료"},
        },
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)
    return [_parse_page(page) for page in resp.get("results", [])]


def cmd_search_tasks(args):
    """Claude 매칭용: 활성 Task 전체 목록 반환."""
    token = get_token()
    status_filter = getattr(args, "status", "active")

    if status_filter == "all":
        body = {
            "sorts": [{"property": "Priority", "direction": "ascending"}],
        }
        resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)
        results = [_parse_page(page) for page in resp.get("results", [])]
    else:
        results = query_active_tasks(token)

    print(json.dumps({
        "results": results,
        "total": len(results),
    }, ensure_ascii=False, indent=2))


def cmd_tasks(args):
    """주간/월간 Task 조회."""
    token = get_token()
    month = getattr(args, "month", None)

    if month:
        start_date, end_date = get_month_range(month)
    else:
        week = getattr(args, "week", "current")
        start_date, end_date = get_week_range(week)

    status_filter = getattr(args, "status", "all")
    tasks = query_tasks_by_period(token, start_date, end_date)

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


# ─────────────────────────────────────────────
# 생성
# ─────────────────────────────────────────────

def cmd_create_task(args):
    """Notion Task DB에 새 Task 생성."""
    token = get_token()

    name = args.name.strip()
    if not name:
        _exit_error("--name is required and cannot be empty")

    priority = args.priority
    if priority not in PRIORITY_OPTIONS:
        _exit_error(f"Invalid priority '{priority}'. Valid: {sorted(PRIORITY_OPTIONS)}")

    category = args.category
    if category not in CATEGORY_OPTIONS:
        _exit_error(f"Invalid category '{category}'. Valid: {sorted(CATEGORY_OPTIONS)}")

    properties = {
        "이름": {
            "title": [{"text": {"content": name}}]
        },
        "Priority": {
            "select": {"name": priority}
        },
        "Group": {
            "select": {"name": category}
        },
        "상태": {
            "status": {"name": "시작 전"}
        },
    }

    if args.due:
        properties["Due Date"] = {"date": {"start": args.due}}

    if args.description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": args.description}}]
        }

    body = {
        "parent": {"database_id": TASK_DB_ID},
        "properties": properties,
    }

    result = notion_request(token, "POST", "/pages", body)
    print(json.dumps({
        "success": True,
        "page_id": result.get("id", ""),
        "name": name,
        "priority": priority,
        "category": category,
        "due_date": args.due or "",
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# 상태 변경
# ─────────────────────────────────────────────

def cmd_update_status(args):
    """Task 상태 변경."""
    token = get_token()

    if args.status not in VALID_STATUSES:
        _exit_error(f"Invalid status '{args.status}'. Valid: {sorted(VALID_STATUSES)}")

    body = {
        "properties": {
            "상태": {"status": {"name": args.status}}
        }
    }
    result = notion_request(token, "PATCH", f"/pages/{args.page_id}", body)

    props = result.get("properties", {})
    name_title = props.get("이름", {}).get("title", [])
    name = rich_text_to_plain(name_title)

    print(json.dumps({
        "success": True,
        "page_id": args.page_id,
        "name": name,
        "status": args.status,
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# 삭제 (아카이브)
# ─────────────────────────────────────────────

def cmd_delete_task(args):
    """Task 아카이브 (복구 가능한 삭제)."""
    token = get_token()

    # 삭제 전 Task 이름 조회
    page = notion_request(token, "GET", f"/pages/{args.page_id}")
    props = page.get("properties", {})
    name = rich_text_to_plain(props.get("이름", {}).get("title", []))

    body = {"archived": True}
    notion_request(token, "PATCH", f"/pages/{args.page_id}", body)

    print(json.dumps({
        "success": True,
        "page_id": args.page_id,
        "name": name,
        "archived": True,
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# 이월 (carry-over)
# ─────────────────────────────────────────────

def cmd_carry_over(args):
    """지난 주 미완료 Task를 이번 주 월요일로 이월."""
    token = get_token()

    prev_monday, prev_sunday = get_week_range("previous")
    curr_monday, _ = get_week_range("current")

    # 지난 주 미완료 Task 조회
    prev_tasks = query_tasks_by_period(token, prev_monday, prev_sunday)
    incomplete = prev_tasks["in_progress"] + prev_tasks["upcoming"] + prev_tasks["waiting"]

    if not incomplete:
        print(json.dumps({
            "success": True,
            "dry_run": args.dry_run,
            "message": "지난 주 미완료 항목이 없습니다.",
            "tasks": [],
            "target_date": curr_monday,
        }, ensure_ascii=False, indent=2))
        return

    # 선택적 이월: --page-ids 지정 시 해당 항목만
    if getattr(args, "page_ids", None):
        id_set = set(args.page_ids.split(","))
        incomplete = [t for t in incomplete if t["page_id"] in id_set]

    if args.dry_run:
        print(json.dumps({
            "success": True,
            "dry_run": True,
            "tasks": incomplete,
            "target_date": curr_monday,
            "count": len(incomplete),
        }, ensure_ascii=False, indent=2))
        return

    # apply: Due Date를 이번 주 월요일로 변경
    updated = []
    for task in incomplete:
        body = {
            "properties": {
                "Due Date": {"date": {"start": curr_monday}}
            }
        }
        notion_request(token, "PATCH", f"/pages/{task['page_id']}", body)
        updated.append({
            "page_id": task["page_id"],
            "name": task["name"],
            "old_due": task["due_date"],
            "new_due": curr_monday,
        })

    print(json.dumps({
        "success": True,
        "dry_run": False,
        "updated": updated,
        "count": len(updated),
        "target_date": curr_monday,
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Notion Task CLI (Write + Query) — tasks:manage 공유 스크립트"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search-tasks
    st = subparsers.add_parser("search-tasks", help="Claude 매칭용 활성 Task 목록 조회")
    st.add_argument("--status", choices=["active", "all"], default="active",
                    help="active: 완료 제외 (기본값), all: 전체")

    # tasks
    tasks_p = subparsers.add_parser("tasks", help="주간/월간 Task 조회")
    tasks_p.add_argument("--week", choices=["previous", "current", "next"], default="current")
    tasks_p.add_argument("--month", default=None, help="YYYY-MM (--week 대신 사용)")
    tasks_p.add_argument("--status", choices=["in-progress", "upcoming", "all"], default="all")

    # create-task
    ct = subparsers.add_parser("create-task", help="새 Task 생성")
    ct.add_argument("--name", required=True, help="Task 이름")
    ct.add_argument("--priority", required=True,
                    choices=sorted(PRIORITY_OPTIONS),
                    help="우선순위")
    ct.add_argument("--category", required=True, choices=["WORK", "MY"], help="카테고리")
    ct.add_argument("--due", default=None, help="마감일 (YYYY-MM-DD)")
    ct.add_argument("--description", default=None, help="부연 설명")

    # update-status
    us = subparsers.add_parser("update-status", help="Task 상태 변경")
    us.add_argument("--page-id", required=True, help="Notion page ID")
    us.add_argument("--status", required=True,
                    choices=sorted(VALID_STATUSES),
                    help="변경할 상태")

    # delete-task
    dt = subparsers.add_parser("delete-task", help="Task 아카이브 (복구 가능)")
    dt.add_argument("--page-id", required=True, help="Notion page ID")

    # carry-over
    co = subparsers.add_parser("carry-over", help="지난 주 미완료 Task 이월")
    co_group = co.add_mutually_exclusive_group(required=True)
    co_group.add_argument("--dry-run", action="store_true", help="이월 대상 미리보기")
    co_group.add_argument("--apply", action="store_true", help="실제 이월 실행")
    co.add_argument("--page-ids", default=None, help="선택 이월: page_id 콤마 구분")

    args = parser.parse_args()

    # carry-over의 dry_run 속성 정규화
    if args.command == "carry-over":
        args.dry_run = args.dry_run or not args.apply

    dispatch = {
        "search-tasks": cmd_search_tasks,
        "tasks": cmd_tasks,
        "create-task": cmd_create_task,
        "update-status": cmd_update_status,
        "delete-task": cmd_delete_task,
        "carry-over": cmd_carry_over,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
