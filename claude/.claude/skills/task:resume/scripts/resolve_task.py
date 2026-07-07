#!/usr/bin/env python3
"""
Notion Task 링크 -> page_id 파싱 + Task DB 속성 조회.

task:resume 스킬 전용. Task DB(2da64745-3170-8072-80bd-fb05cf592929) 페이지의
이름/상태/우선순위/마감일을 조회해 작업 재개 컨텍스트를 만든다.
상태 변경(update-status)은 tasks:manage/scripts/notion-task.py를 그대로 호출한다
(같은 로직을 여기서 다시 구현하지 않는다 — Done 체크박스 동기화, started_at
backfill 등 update-status 안 로직이 이미 있음).

Usage:
  python3 resolve_task.py resolve --url "https://www.notion.so/Task-이름-2da64745...
"
"""

import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.error

TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

UUID_TAIL_RE = re.compile(
    r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


def _exit_error(message):
    print(json.dumps({"success": False, "error": message}, ensure_ascii=False))
    sys.exit(1)


def get_token():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        _exit_error("NOTION_TOKEN environment variable not set")
    return token


def notion_request(token, method, path):
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2025-09-03",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"message": body}
        _exit_error(f"Notion API {e.code}: {parsed.get('message', body)}")


def extract_page_id(raw):
    """URL(제목 슬러그+쿼리스트링 포함) 또는 순수 page_id 문자열에서 dashed UUID를 뽑는다."""
    raw = raw.strip().split("?")[0].split("#")[0]
    segment = raw.rstrip("/").split("/")[-1]
    m = UUID_TAIL_RE.search(segment)
    hex_id = (m.group(1) if m else segment).replace("-", "")
    if len(hex_id) != 32 or not re.fullmatch(r"[0-9a-fA-F]{32}", hex_id):
        return None
    return f"{hex_id[0:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:32]}"


def rich_text_to_plain(rich_text_list):
    return "".join(rt.get("plain_text", "") for rt in (rich_text_list or []))


def cmd_resolve(args):
    page_id = extract_page_id(args.url)
    if not page_id:
        _exit_error(f"'{args.url}'에서 Notion page_id를 추출하지 못했습니다.")

    token = get_token()
    page = notion_request(token, "GET", f"/pages/{page_id}")
    if page.get("object") == "error":
        _exit_error(page.get("message", "page 조회 실패"))

    props = page.get("properties", {})
    parent = page.get("parent", {})
    # API 버전 2025-09-03부터 database_id(컨테이너)와 data_source_id(테이블)가
    # 분리되어 서로 다른 UUID를 가진다. TASK_DB_ID는 database_id 기준이므로
    # 두 필드 모두 확인해야 data_source_id만 있는 응답에서 false negative가 안 난다.
    is_task_db = TASK_DB_ID in (parent.get("database_id") or "") or TASK_DB_ID in (parent.get("data_source_id") or "")

    name = rich_text_to_plain(props.get("이름", {}).get("title", []))
    status = (props.get("상태", {}).get("status") or {}).get("name")
    priority = (props.get("Priority", {}).get("select") or {}).get("name")
    due = (props.get("Due Date", {}).get("date") or {}).get("start")
    category = (props.get("Category", {}).get("select") or {}).get("name")
    roi = (props.get("ROI", {}).get("select") or {}).get("name")

    print(json.dumps({
        "success": True,
        "page_id": page_id,
        "is_task_db": is_task_db,
        "name": name,
        "status": status,
        "priority": priority,
        "due_date": due,
        "category": category,
        "roi": roi,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Task 링크 파싱 + 속성 조회")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rs = subparsers.add_parser("resolve", help="링크에서 page_id 추출 + Task 속성 조회")
    rs.add_argument("--url", required=True, help="Notion 페이지 URL 또는 page_id")
    rs.set_defaults(func=cmd_resolve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
