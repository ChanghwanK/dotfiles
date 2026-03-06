#!/usr/bin/env python3
"""
[Private] Note DB CLI
Usage:
  python3 notion-note.py create --title "제목" [--group "#Note"] [--tags "VIM,학습"] [--content /tmp/note-content.json]
  python3 notion-note.py list [--limit 10]

content.json 형식:
{
  "blocks": "마크다운 텍스트 (Notion 블록으로 변환)"
}
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import argparse
from datetime import date

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DB_ID = "24364745-3170-80b5-8e34-da0245b42d6c"

GROUP_OPTIONS = ["#Note"]
TAG_OPTIONS = [
    "Kubernetes", "Life", "Company", "설정", "Secret",
    "Cursor", "Claude Rule", "CLI", "VIM", "학습", "AI Agent"
]


def notion_request(method, path, body=None):
    token = NOTION_TOKEN
    if not token:
        print(json.dumps({"success": False, "error": "NOTION_TOKEN not set"}))
        sys.exit(1)
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
        err = e.read().decode()
        try:
            return json.loads(err)
        except Exception:
            return {"object": "error", "message": f"HTTP {e.code}: {err}"}


def md_to_rich_text(text):
    """마크다운 인라인 서식을 Notion rich_text 배열로 변환."""
    segments = []
    # bold+italic, bold, italic, code, plain 순서로 파싱
    pattern = re.compile(
        r'(\*\*\*(.+?)\*\*\*)'   # bold+italic
        r'|(\*\*(.+?)\*\*)'       # bold
        r'|(\*(.+?)\*)'           # italic
        r'|(`(.+?)`)'             # inline code
    )
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            plain = text[pos:m.start()]
            if plain:
                segments.append({"type": "text", "text": {"content": plain}})
        if m.group(2):  # bold+italic
            segments.append({"type": "text", "text": {"content": m.group(2)},
                             "annotations": {"bold": True, "italic": True}})
        elif m.group(4):  # bold
            segments.append({"type": "text", "text": {"content": m.group(4)},
                             "annotations": {"bold": True}})
        elif m.group(6):  # italic
            segments.append({"type": "text", "text": {"content": m.group(6)},
                             "annotations": {"italic": True}})
        elif m.group(8):  # code
            segments.append({"type": "text", "text": {"content": m.group(8)},
                             "annotations": {"code": True}})
        pos = m.end()
    if pos < len(text):
        remaining = text[pos:]
        if remaining:
            segments.append({"type": "text", "text": {"content": remaining}})
    if not segments:
        segments.append({"type": "text", "text": {"content": text}})
    return segments


def md_to_blocks(text):
    """마크다운 텍스트를 Notion 블록 리스트로 변환."""
    blocks = []
    if not text or not text.strip():
        return blocks

    lines = text.strip().split("\n")
    in_code = False
    code_lang = ""
    code_lines = []
    # 테이블 파싱용
    table_rows = []
    in_table = False

    def flush_table():
        nonlocal table_rows, in_table
        if not table_rows:
            return
        # 구분선 행 제거 (|---|---|)
        data_rows = [r for r in table_rows if not re.match(r'^[\s|:-]+$', r.replace('-', '').replace(':', '').replace('|', '').strip()) or r.replace('-', '').replace(':', '').replace('|', '').replace(' ', '') != '']
        filtered = []
        for r in table_rows:
            cells = [c.strip() for c in r.strip().strip('|').split('|')]
            if all(re.match(r'^:?-+:?$', c) for c in cells if c):
                continue
            filtered.append(r)
        if not filtered:
            table_rows = []
            in_table = False
            return
        # 테이블 블록 생성
        parsed_rows = []
        for r in filtered:
            cells = [c.strip() for c in r.strip().strip('|').split('|')]
            parsed_rows.append(cells)
        if not parsed_rows:
            table_rows = []
            in_table = False
            return
        max_cols = max(len(r) for r in parsed_rows)
        table_children = []
        for i, row in enumerate(parsed_rows):
            while len(row) < max_cols:
                row.append("")
            cells_rt = []
            for cell in row[:max_cols]:
                cells_rt.append(md_to_rich_text(cell) if cell else [{"type": "text", "text": {"content": ""}}])
            table_children.append({
                "type": "table_row",
                "table_row": {"cells": cells_rt}
            })
        blocks.append({
            "type": "table",
            "table": {
                "table_width": max_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": table_children
            }
        })
        table_rows = []
        in_table = False

    for line in lines:
        # 코드 블록 처리
        if in_code:
            if line.startswith("```"):
                content = "\n".join(code_lines)
                blocks.append({"type": "code", "code": {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}],
                    "language": code_lang or "plain text",
                }})
                in_code = False
                code_lines = []
            else:
                code_lines.append(line)
            continue

        if line.startswith("```"):
            if in_table:
                flush_table()
            in_code = True
            code_lang = line[3:].strip()
            continue

        # 테이블 행 감지
        if re.match(r'^\s*\|.*\|\s*$', line):
            in_table = True
            table_rows.append(line)
            continue
        elif in_table:
            flush_table()

        # 수평선
        if re.match(r'^-{3,}$', line.strip()):
            blocks.append({"type": "divider", "divider": {}})
            continue

        # 헤딩
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            blocks.append({f"type": f"heading_{level}", f"heading_{level}": {
                "rich_text": md_to_rich_text(m.group(2).strip()),
                "color": "default"
            }})
            continue

        # 체크박스
        m = re.match(r'^[-*]\s+\[( |x|X)\]\s+(.*)', line)
        if m:
            checked = m.group(1).lower() == "x"
            blocks.append({"type": "to_do", "to_do": {
                "rich_text": md_to_rich_text(m.group(2).strip()),
                "checked": checked, "color": "default"
            }})
            continue

        # 불릿 리스트
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        # 숫자 리스트
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            blocks.append({"type": "numbered_list_item", "numbered_list_item": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        # 인용
        m = re.match(r'^>\s*(.*)', line)
        if m:
            blocks.append({"type": "quote", "quote": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        # 빈 줄
        if not line.strip():
            continue

        # 일반 문단
        blocks.append({"type": "paragraph", "paragraph": {
            "rich_text": md_to_rich_text(line),
            "color": "default"
        }})

    # 마지막 테이블 플러시
    if in_table:
        flush_table()

    return blocks


def cmd_create(args):
    title = args.title
    group = args.group or "#Note"
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    today = date.today().isoformat()

    # 태그 유효성 검증
    invalid_tags = [t for t in tags if t not in TAG_OPTIONS]
    if invalid_tags:
        print(json.dumps({"success": False, "error": f"Invalid tags: {invalid_tags}. Options: {TAG_OPTIONS}"}, ensure_ascii=False))
        sys.exit(1)

    if group not in GROUP_OPTIONS:
        print(json.dumps({"success": False, "error": f"Invalid group '{group}'. Options: {GROUP_OPTIONS}"}, ensure_ascii=False))
        sys.exit(1)

    # 콘텐츠 로드
    children = []
    if args.content:
        from pathlib import Path
        content_path = Path(args.content).expanduser()
        if not content_path.exists():
            print(json.dumps({"success": False, "error": f"Content file not found: {args.content}"}, ensure_ascii=False))
            sys.exit(1)
        content_data = json.loads(content_path.read_text(encoding="utf-8"))
        md_text = content_data.get("blocks", "")
        if md_text:
            children = md_to_blocks(md_text)

    properties = {
        "이름": {"title": [{"type": "text", "text": {"content": title}}]},
        "Group": {"select": {"name": group}},
        "Created At": {"date": {"start": today}},
    }
    if tags:
        properties["Tags"] = {"multi_select": [{"name": t} for t in tags]}

    page_body = {
        "parent": {"database_id": DB_ID},
        "properties": properties,
    }
    if children:
        page_body["children"] = children

    resp = notion_request("POST", "/pages", page_body)

    if resp.get("object") == "error":
        print(json.dumps({
            "success": False,
            "error": resp.get("message", str(resp)),
        }, ensure_ascii=False))
        sys.exit(1)

    page_id = resp.get("id", "")
    page_url = resp.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")
    print(json.dumps({
        "success": True,
        "page_id": page_id,
        "title": title,
        "group": group,
        "tags": tags,
        "url": page_url,
    }, ensure_ascii=False, indent=2))


def cmd_list(args):
    limit = args.limit or 10
    body = {
        "sorts": [{"property": "Created At", "direction": "descending"}],
        "page_size": limit,
    }
    resp = notion_request("POST", f"/databases/{DB_ID}/query", body)

    if resp.get("object") == "error":
        print(json.dumps({"success": False, "error": resp.get("message", str(resp))}, ensure_ascii=False))
        sys.exit(1)

    results = []
    for page in resp.get("results", []):
        props = page.get("properties", {})
        title_rt = props.get("이름", {}).get("title", [])
        title = title_rt[0].get("plain_text", "") if title_rt else "(no title)"
        group = props.get("Group", {}).get("select", {})
        group_name = group.get("name", "") if group else ""
        tags = [t["name"] for t in props.get("Tags", {}).get("multi_select", [])]
        created = props.get("Created At", {}).get("date", {})
        created_date = created.get("start", "") if created else ""
        page_id = page.get("id", "")
        url = f"https://www.notion.so/{page_id.replace('-', '')}"
        results.append({
            "title": title,
            "group": group_name,
            "tags": tags,
            "created": created_date,
            "url": url,
        })

    print(json.dumps({"success": True, "count": len(results), "pages": results}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="[Private] Note DB CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="노트 페이지 생성")
    create_p.add_argument("--title", required=True, help="페이지 제목")
    create_p.add_argument("--group", default="#Note",
                          help=f"Group 속성. 옵션: {GROUP_OPTIONS} (기본: #Note)")
    create_p.add_argument("--tags", default="",
                          help=f"Tags 속성 (쉼표 구분). 옵션: {TAG_OPTIONS}")
    create_p.add_argument("--content", default="",
                          help="콘텐츠 JSON 파일 경로 (key: blocks)")

    # list
    list_p = subparsers.add_parser("list", help="최근 노트 목록 조회")
    list_p.add_argument("--limit", type=int, default=10, help="최대 조회 개수 (기본: 10)")

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
