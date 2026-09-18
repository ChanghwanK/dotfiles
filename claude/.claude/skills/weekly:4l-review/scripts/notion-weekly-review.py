#!/usr/bin/env python3
"""
Notion 주간 4L 리뷰 CLI (Query + Write)

대상 DB: 개인 노션 "주간 리뷰" (title-only, 본문에 4L H2 섹션을 담는다)
4L = Liked / Learned / Lacked / Longed for

Usage:
  python3 notion-weekly-review.py find-existing --week current|previous
  python3 notion-weekly-review.py create --week current|previous \
    --liked "항목1\n항목2" --learned "항목1" --lacked "항목1" --longed-for "항목1"
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
try:
    from notion_text import sanitize_body
except Exception:  # backstop은 쓰기 경로를 절대 깨지 않는다
    def sanitize_body(text):
        return text

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
REVIEW_DB_ID = "27664745-3170-8097-bb54-e1962a8242ff"


def _exit_error(msg):
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False, indent=2))
    sys.exit(1)


def get_token():
    if not NOTION_TOKEN:
        _exit_error("NOTION_TOKEN environment variable not set")
    return NOTION_TOKEN


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
        _exit_error(f"HTTP {e.code}: {e.read().decode()}")


_DS_CACHE = {}


def resolve_ds_id(token, db_id):
    """db_id → data source id (프로세스 내 캐시)."""
    if db_id not in _DS_CACHE:
        db = notion_request(token, "GET", f"/databases/{db_id}")
        sources = db.get("data_sources", [])
        if not sources:
            _exit_error(f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


def get_week_range(week="current"):
    """대상 주의 월요일/금요일 반환 (근무일 기준, 토·일 제외)."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if week == "previous":
        monday = monday - timedelta(days=7)
    elif week == "next":
        monday = monday + timedelta(days=7)
    friday = monday + timedelta(days=4)
    return monday, friday


def format_period_label(monday, friday):
    return f"{monday.month:02d}.{monday.day:02d}~{friday.month:02d}.{friday.day:02d}"


def cmd_find_existing(args):
    """기간 라벨 계산 + 동일 제목 페이지 중복 존재 여부 확인."""
    token = get_token()
    monday, friday = get_week_range(args.week)
    label = format_period_label(monday, friday)
    title = f"{label} 주간 리뷰"

    ds_id = resolve_ds_id(token, REVIEW_DB_ID)
    body = {"filter": {"property": "이름", "title": {"equals": title}}}
    resp = notion_request(token, "POST", f"/data_sources/{ds_id}/query", body)
    results = resp.get("results", [])
    page = results[0] if results else None

    print(json.dumps({
        "period_label": label,
        "title": title,
        "week_start": monday.isoformat(),
        "week_end": friday.isoformat(),
        "exists": page is not None,
        "page_id": page["id"] if page else None,
        "url": page.get("url") if page else None,
    }, ensure_ascii=False, indent=2))


def _section_blocks(heading, raw_text):
    blocks = [{
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": heading}}]},
    }]
    for line in (raw_text or "").split("\n"):
        line = sanitize_body(line.strip())
        if not line:
            continue
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        })
    return blocks


def cmd_create(args):
    """'주간 리뷰' DB에 [기간] 주간 리뷰 페이지 생성 (H2 Liked/Learned/Lacked/Longed for + 불릿)."""
    token = get_token()
    monday, friday = get_week_range(args.week)
    label = format_period_label(monday, friday)
    title = sanitize_body(f"{label} 주간 리뷰")

    ds_id = resolve_ds_id(token, REVIEW_DB_ID)

    children = (
        _section_blocks("Liked", args.liked)
        + _section_blocks("Learned", args.learned)
        + _section_blocks("Lacked", args.lacked)
        + _section_blocks("Longed for", args.longed_for)
    )

    body = {
        "parent": {"type": "data_source_id", "data_source_id": ds_id},
        "properties": {"이름": {"title": [{"text": {"content": title}}]}},
        "children": children,
    }
    result = notion_request(token, "POST", "/pages", body)
    page_id = result.get("id", "")
    page_url = result.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")

    print(json.dumps({
        "success": True,
        "title": title,
        "page_id": page_id,
        "url": page_url,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion 주간 4L 리뷰 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fe = subparsers.add_parser("find-existing", help="기간 라벨 계산 + 중복 페이지 확인")
    fe.add_argument("--week", choices=["current", "previous"], default="current")

    cr = subparsers.add_parser("create", help="주간 리뷰 DB에 4L 페이지 생성")
    cr.add_argument("--week", choices=["current", "previous"], default="current")
    cr.add_argument("--liked", default="", help="Liked 항목 (줄바꿈으로 구분)")
    cr.add_argument("--learned", default="", help="Learned 항목 (줄바꿈으로 구분)")
    cr.add_argument("--lacked", default="", help="Lacked 항목 (줄바꿈으로 구분)")
    cr.add_argument("--longed-for", dest="longed_for", default="", help="Longed for 항목 (줄바꿈으로 구분)")

    args = parser.parse_args()

    if args.command == "find-existing":
        cmd_find_existing(args)
    elif args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
