#!/usr/bin/env python3
"""
Engineering DB 업무 노트 CLI
Usage:
  python3 notion-eng-note.py create --title "제목" [--group "#업무노트"] [--tag "#Kubernetes,#Infra"] [--sections /tmp/sections.json]
  python3 notion-eng-note.py list [--limit 10]

sections.json 형식:
{
  "problem":  "문제 상황과 배경 (마크다운)",
  "goal":     "목표 (마크다운)",
  "non_goal": "비목표 (마크다운)",
  "design":   "설계 내용 (마크다운)",
  "alternatives": "대안 검토 (마크다운)",
  "plan":     "구현 계획 (마크다운)",
  "questions": "미결 질문 (마크다운)"
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
from pathlib import Path

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DB_ID = "17964745-3170-8030-bf01-e7f20a6e1bd7"

GROUP_OPTIONS = ["#Study", "#Article", "#업무노트", "#정리"]
TAG_OPTIONS = [
    "#Kubernetes", "#Network", "#Istio", "#Issue", "#Infra", "#Observabiliy",
    "#Security", "#자동화", "#AI", "#Agent", "#OS", "#Terraform", "#AWS", "#Engineering"
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


def md_to_blocks(text):
    """마크다운 텍스트를 Notion 블록 리스트로 변환 (간단 파서)."""
    blocks = []
    if not text or not text.strip():
        return blocks

    lines = text.strip().split("\n")
    in_code = False
    code_lang = ""
    code_lines = []

    for line in lines:
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
            in_code = True
            code_lang = line[3:].strip()
            continue

        if re.match(r'^-{3,}$', line.strip()):
            blocks.append({"type": "divider", "divider": {}})
            continue

        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            blocks.append({f"type": f"heading_{level}", f"heading_{level}": {
                "rich_text": [{"type": "text", "text": {"content": m.group(2).strip()}}],
                "color": "default"
            }})
            continue

        m = re.match(r'^[-*]\s+\[( |x|X)\]\s+(.*)', line)
        if m:
            checked = m.group(1).lower() == "x"
            blocks.append({"type": "to_do", "to_do": {
                "rich_text": [{"type": "text", "text": {"content": m.group(2).strip()}}],
                "checked": checked, "color": "default"
            }})
            continue

        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": m.group(1).strip()}}],
                "color": "default"
            }})
            continue

        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            blocks.append({"type": "numbered_list_item", "numbered_list_item": {
                "rich_text": [{"type": "text", "text": {"content": m.group(1).strip()}}],
                "color": "default"
            }})
            continue

        m = re.match(r'^>\s*(.*)', line)
        if m:
            blocks.append({"type": "quote", "quote": {
                "rich_text": [{"type": "text", "text": {"content": m.group(1).strip()}}],
                "color": "default"
            }})
            continue

        if not line.strip():
            continue

        blocks.append({"type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": line}}],
            "color": "default"
        }})

    return blocks


def make_template_blocks(sections=None):
    """업무 노트 템플릿 블록 구조 생성.

    sections: dict with keys: problem, goal, non_goal, design, alternatives, plan, questions
    값이 있으면 해당 섹션에 내용 채움. 없으면 placeholder 사용.
    """
    s = sections or {}

    def h1(text):
        return {"type": "heading_1", "heading_1": {
            "rich_text": [{"type": "text", "text": {"content": text}}], "color": "default"
        }}

    def quote(text=""):
        return {"type": "quote", "quote": {
            "rich_text": [{"type": "text", "text": {"content": text}}], "color": "default"
        }}

    def paragraph(text=""):
        return {"type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}], "color": "default"
        }}

    def todo(text, checked=False):
        return {"type": "to_do", "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "checked": checked, "color": "default"
        }}

    def bullet(text):
        return {"type": "bulleted_list_item", "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}], "color": "default"
        }}

    def divider():
        return {"type": "divider", "divider": {}}

    def section_blocks(key, placeholders):
        """섹션 내용 반환: sections[key]가 있으면 파싱, 없으면 placeholder."""
        content = s.get(key, "").strip()
        if content:
            return md_to_blocks(content)
        return placeholders

    blocks = [
        # TOC callout
        {"type": "callout", "callout": {
            "rich_text": [{"type": "text", "text": {"content": "1. 문제 정의\n2. 목표 / 비목표\n3. 설계\n4. 대안 검토\n5. 구현 계획\n6. 미결 질문"}}],
            "icon": {"type": "emoji", "emoji": "📋"}, "color": "gray_background"
        }},
        # 1. 문제 정의
        h1("1. 문제 정의"),
        *section_blocks("problem", [
            paragraph("현재 어떤 상황이고, 무엇이 문제인가?"),
            paragraph("해결하지 않으면 어떤 일이 생기나? (왜 진행하는가?)"),
        ]),
        divider(),
        # 2. 목표 / 비목표
        h1("2. 목표 / 비목표"),
        paragraph("Goal"),
        *section_blocks("goal", [quote()]),
        paragraph("Non-goal"),
        *section_blocks("non_goal", [quote()]),
        divider(),
        # 3. 설계
        h1("3. 설계"),
        *section_blocks("design", [quote()]),
        divider(),
        # 4. 대안 검토
        h1("4. 대안 검토"),
        *section_blocks("alternatives", [paragraph("")]),
        divider(),
        # 5. 구현 계획
        h1("5. 구현 계획"),
        *section_blocks("plan", [
            paragraph("Phase 1 (이번 스프린트)"),
            todo("작업 1"),
            todo("작업 2"),
            paragraph("Phase 2 (추후)"),
            todo("나중에 할 것"),
            paragraph("예상 리스크"),
            bullet("리스크 항목과 대응 방안"),
        ]),
        divider(),
        # 6. 미결 질문
        h1("6. 미결 질문"),
        *section_blocks("questions", [
            todo("아직 결정 안 된 것 (@담당자 YYYY-MM-DD까지)"),
            todo("확인 필요한 것"),
        ]),
    ]
    return blocks


def cmd_create(args):
    title = args.title
    group = args.group or "#업무노트"
    tags = [t.strip() for t in args.tag.split(",")] if args.tag else []
    today = date.today().isoformat()

    # Load sections from JSON file if provided
    sections = {}
    if args.sections:
        sections_path = Path(args.sections).expanduser()
        if not sections_path.exists():
            print(json.dumps({"success": False, "error": f"sections file not found: {args.sections}"}))
            sys.exit(1)
        sections = json.loads(sections_path.read_text(encoding="utf-8"))

    if group not in GROUP_OPTIONS:
        print(json.dumps({"success": False, "error": f"Invalid group '{group}'. Options: {GROUP_OPTIONS}"}))
        sys.exit(1)

    invalid_tags = [t for t in tags if t not in TAG_OPTIONS]
    if invalid_tags:
        print(json.dumps({"success": False, "error": f"Invalid tags: {invalid_tags}. Options: {TAG_OPTIONS}"}))
        sys.exit(1)

    properties = {
        "Title": {"title": [{"type": "text", "text": {"content": title}}]},
        "Group": {"select": {"name": group}},
        "Created At": {"date": {"start": today}},
    }
    if tags:
        properties["Tag"] = {"multi_select": [{"name": t} for t in tags]}

    # Create the page
    page_body = {
        "parent": {"database_id": DB_ID},
        "properties": properties,
        "children": make_template_blocks(sections),
    }

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
        title_rt = props.get("Title", {}).get("title", [])
        title = title_rt[0].get("plain_text", "") if title_rt else "(no title)"
        group = props.get("Group", {}).get("select", {})
        group_name = group.get("name", "") if group else ""
        tags = [t["name"] for t in props.get("Tag", {}).get("multi_select", [])]
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
    parser = argparse.ArgumentParser(description="Engineering DB 업무 노트 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="업무 노트 페이지 생성")
    create_p.add_argument("--title", required=True, help="페이지 제목")
    create_p.add_argument("--group", default="#업무노트",
                          help=f"Group 속성. 옵션: {GROUP_OPTIONS} (기본: #업무노트)")
    create_p.add_argument("--tag", default="",
                          help=f"Tag 속성 (쉼표 구분). 옵션: {TAG_OPTIONS}")
    create_p.add_argument("--sections", default="",
                          help="섹션 내용이 담긴 JSON 파일 경로 (keys: problem, goal, non_goal, design, alternatives, plan, questions)")

    # list
    list_p = subparsers.add_parser("list", help="최근 업무 노트 목록 조회")
    list_p.add_argument("--limit", type=int, default=10, help="최대 조회 개수 (기본: 10)")

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
