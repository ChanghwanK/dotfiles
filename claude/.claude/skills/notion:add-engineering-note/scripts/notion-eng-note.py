#!/usr/bin/env python3
"""
Engineering DB 업무 노트 CLI
Usage:
  python3 notion-eng-note.py create --title "제목" [--group "#업무노트"] [--task <task-page-id>] [--sections /tmp/sections.json]
  python3 notion-eng-note.py list [--limit 10]

--task를 지정하면(Task 연결) 문제 정의/목표/비목표 섹션은 생략된다: 그 내용은 연결된
Task 페이지의 01.문제 정의 / 04.Goals-Non Goals 섹션이 단일 출처이므로 중복 작성하지 않는다.
--task 없이 만드는 독립 노트는 참조할 Task가 없으므로 문제 정의/목표/비목표를 그대로 포함한다.

sections.json 형식 (--task 지정 시, problem/goal/non_goal 생략 가능):
{
  "problem":  "문제 상황과 배경 (마크다운, 독립 노트에서만 사용)",
  "goal":     "목표 (마크다운, 독립 노트에서만 사용)",
  "non_goal": "비목표 (마크다운, 독립 노트에서만 사용)",
  "design":   "설계 내용 (마크다운)",
  "alternatives": "대안 검토 (마크다운)",
  "plan":     "작업 계획 (마크다운)",
  "history":  "작업 History (마크다운, 날짜별 진행 기록. append-content로 계속 추가 권장)",
  "review":   "Task Review (마크다운, 완료 후 회고)",
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
try:
    from notion_text import sanitize_body
except Exception:  # backstop은 쓰기 경로를 절대 깨지 않는다
    def sanitize_body(text):
        return text
try:
    from notion_toc import placeholder_callout, build_toc_rich_text
except Exception:  # backstop: TOC 링크 없이도 페이지 생성 자체는 깨지지 않는다
    def placeholder_callout():
        return {"type": "callout", "callout": {
            "rich_text": [{"type": "text", "text": {"content": "목차"}}],
            "icon": {"type": "emoji", "emoji": "📌"}, "color": "gray_background",
        }}

    def build_toc_rich_text(created_blocks, page_url):
        return None, None

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DB_ID = "17964745-3170-8030-bf01-e7f20a6e1bd7"

GROUP_OPTIONS = ["#Study", "#Article", "#업무노트", "#정리"]
# Task DB(개인 Task DB) 페이지의 관계형 속성 이름. Engineering DB "Task" 관계의 반대편.
TASK_DB_RELATION_PROPERTY = "Engineering"


def notion_request(method, path, body=None):
    token = NOTION_TOKEN
    if not token:
        print(json.dumps({"success": False, "error": "NOTION_TOKEN not set"}))
        sys.exit(1)
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
        err = e.read().decode()
        try:
            return json.loads(err)
        except Exception:
            return {"object": "error", "message": f"HTTP {e.code}: {err}"}


# ── data source resolution (Notion-Version 2025-09-03) ────────
# 2025-09-03부터 쿼리는 database가 아니라 data source 단위다.
# 단일 data source DB를 전제로 db_id→ds_id를 1회 조회 후 프로세스 내 캐시한다.
_DS_CACHE = {}


def resolve_ds_id(db_id):
    """db_id → data source id (프로세스 내 캐시). 2025-09-03 쿼리/생성에 필요."""
    if db_id not in _DS_CACHE:
        db = notion_request("GET", f"/databases/{db_id}")
        sources = db.get("data_sources", [])
        if not sources:
            raise RuntimeError(f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


def md_to_rich_text(text):
    """인라인 마크다운(**bold**, *italic*, `code`)을 Notion rich_text 세그먼트 리스트로 변환."""
    text = sanitize_body(text)  # 하드룰 backstop: fenced 코드블록은 별도 빌더라 제외됨
    segments = []
    pattern = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`', re.DOTALL)
    last_end = 0
    for m in pattern.finditer(text):
        if m.start() > last_end:
            segments.append({"type": "text", "text": {"content": text[last_end:m.start()]}})
        if m.group(0).startswith("**"):
            segments.append({"type": "text", "text": {"content": m.group(1)},
                             "annotations": {"bold": True, "italic": False, "code": False,
                                             "strikethrough": False, "underline": False, "color": "default"}})
        elif m.group(0).startswith("*"):
            segments.append({"type": "text", "text": {"content": m.group(2)},
                             "annotations": {"bold": False, "italic": True, "code": False,
                                             "strikethrough": False, "underline": False, "color": "default"}})
        else:
            segments.append({"type": "text", "text": {"content": m.group(3)},
                             "annotations": {"bold": False, "italic": False, "code": True,
                                             "strikethrough": False, "underline": False, "color": "default"}})
        last_end = m.end()
    if last_end < len(text):
        segments.append({"type": "text", "text": {"content": text[last_end:]}})
    return segments if segments else [{"type": "text", "text": {"content": text}}]


# children을 가질 수 있는(중첩 컨테이너로 동작하는) 블록 타입.
# heading/divider는 목록 중첩의 부모가 되지 않고 항상 top-level로 둔다.
_CONTAINER_TYPES = {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph", "quote"}


def md_to_blocks(text):
    """마크다운 텍스트를 Notion 블록 리스트로 변환.

    들여쓰기(2/4-space 무관, 상대 들여쓰기)로 리스트/문단을 중첩한다: `- 부모\\n  - 자식`
    또는 `- 부모\\n    - 자식` 모두 자식이 부모의 children으로 들어간다. 구현 계획처럼
    스텝 아래에 세부 내용이나 코드/설정을 붙일 때 이 중첩을 쓴다:

        - [ ] Step 1: values.yaml 수정
          - requests.memory 2Gi -> 6Gi, limits.memory 12Gi -> 10Gi
          ```yaml
          resources:
            requests:
              memory: 6Gi
          ```

    fenced 코드블록은 자신을 연 줄의 들여쓰기를 기준으로 같은 깊이의 형제로 붙는다
    (코드 자체는 컨테이너가 아니라 그 아래에 더 중첩되지 않는다).
    heading/divider는 항상 top-level이며 중첩 스택을 리셋한다.
    """
    blocks = []
    if not text or not text.strip():
        return blocks

    stack = []  # [(indent, block)] 현재 조상 체인

    def place(indent, block):
        # 현재 indent 이하(형제·더 얕음)인 조상은 pop → 남은 top이 부모
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            ptype = parent["type"]
            parent[ptype].setdefault("children", []).append(block)
        else:
            blocks.append(block)
        if block["type"] in _CONTAINER_TYPES:
            stack.append((indent, block))

    lines = text.strip("\n").split("\n")
    in_code = False
    code_lang = ""
    code_lines = []
    code_indent = 0

    for line in lines:
        stripped = line.rstrip()
        lstripped = stripped.lstrip(" ")
        indent = len(stripped) - len(lstripped)

        if in_code:
            if lstripped.startswith("```"):
                content = "\n".join(code_lines)
                code_block = {"type": "code", "code": {
                    "rich_text": [{"type": "text", "text": {"content": content[:2000]}}],
                    "language": code_lang or "plain text",
                }}
                place(code_indent, code_block)
                in_code = False
                code_lines = []
            else:
                # 여는 펜스의 들여쓰기만큼 걷어내 코드 자체의 상대 들여쓰기를 보존한다.
                if len(line) >= code_indent and line[:code_indent].strip() == "":
                    code_lines.append(line[code_indent:])
                else:
                    code_lines.append(line.lstrip())
            continue

        if lstripped.startswith("```"):
            in_code = True
            code_lang = lstripped[3:].strip()
            code_indent = indent
            continue

        if re.match(r'^-{3,}$', lstripped.strip()):
            blocks.append({"type": "divider", "divider": {}})
            stack.clear()
            continue

        m = re.match(r'^(#{1,3})\s+(.*)', lstripped)
        if m:
            level = len(m.group(1))
            blocks.append({f"type": f"heading_{level}", f"heading_{level}": {
                "rich_text": md_to_rich_text(m.group(2).strip()),
                "color": "default"
            }})
            stack.clear()
            continue

        m = re.match(r'^[-*]\s+\[( |x|X)\]\s+(.*)', lstripped)
        if m:
            checked = m.group(1).lower() == "x"
            place(indent, {"type": "to_do", "to_do": {
                "rich_text": md_to_rich_text(m.group(2).strip()),
                "checked": checked, "color": "default"
            }})
            continue

        m = re.match(r'^[-*]\s+(.*)', lstripped)
        if m:
            place(indent, {"type": "bulleted_list_item", "bulleted_list_item": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        m = re.match(r'^\d+\.\s+(.*)', lstripped)
        if m:
            place(indent, {"type": "numbered_list_item", "numbered_list_item": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        m = re.match(r'^>\s*(.*)', lstripped)
        if m:
            place(indent, {"type": "quote", "quote": {
                "rich_text": md_to_rich_text(m.group(1).strip()),
                "color": "default"
            }})
            continue

        if not lstripped.strip():
            continue

        place(indent, {"type": "paragraph", "paragraph": {
            "rich_text": md_to_rich_text(lstripped),
            "color": "default"
        }})

    return blocks


def make_template_blocks(sections=None, linked_to_task=False):
    """업무 노트 템플릿 블록 구조 생성.

    sections: dict with keys: problem, goal, non_goal, design, alternatives, plan, history, review, questions
    값이 있으면 해당 섹션에 내용 채움. 없으면 placeholder 사용.

    linked_to_task: True면 problem/goal/non_goal 섹션을 생략한다: 그 내용은 연결된 Task
    페이지(01.문제 정의 / 04.Goals-Non Goals)가 단일 출처이므로 여기서 중복 작성하지 않는다.
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

    section_count = (0 if linked_to_task else 2) + 6  # 6개 공통 섹션 + (독립 노트만) 문제정의/목표비목표
    n = iter(range(1, section_count + 1))

    blocks = [
        # TOC 콜아웃 placeholder: cmd_create가 페이지 생성 후 각 heading/Goal-Non-goal
        # 문단의 실제 block id로 링크를 채운다 (build_toc_rich_text).
        placeholder_callout(),
    ]

    if not linked_to_task:
        # 문제 정의 (독립 노트에만 포함, Task 연결 노트는 연결된 Task 01.문제 정의가 단일 출처)
        blocks += [
            h1(f"{next(n)}. 문제 정의"),
            *section_blocks("problem", [
                paragraph("현재 어떤 상황이고, 무엇이 문제인가?"),
                paragraph("해결하지 않으면 어떤 일이 생기나? (왜 진행하는가?)"),
            ]),
            divider(),
            # 목표 / 비목표 (독립 노트에만 포함, Task 연결 노트는 04.Goals-Non Goals가 단일 출처)
            h1(f"{next(n)}. 목표 / 비목표"),
            paragraph("Goal"),
            *section_blocks("goal", [quote()]),
            paragraph("Non-goal"),
            *section_blocks("non_goal", [quote()]),
            divider(),
        ]

    blocks += [
        # 설계
        h1(f"{next(n)}. 설계"),
        *section_blocks("design", [quote()]),
        divider(),
        # 대안 검토
        h1(f"{next(n)}. 대안 검토"),
        *section_blocks("alternatives", [paragraph("")]),
        divider(),
        # 작업 계획
        h1(f"{next(n)}. 작업 계획"),
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
        # 작업 History: 진행하며 append-content로 날짜별 기록을 계속 추가한다
        h1(f"{next(n)}. 작업 History"),
        *section_blocks("history", [
            bullet("YYYY-MM-DD: 무엇을 했는지, 어떤 이슈가 있었는지 한 줄로"),
        ]),
        divider(),
        # Task Review: 완료 후 작성 (목표 대비 결과 회고)
        h1(f"{next(n)}. Task Review"),
        *section_blocks("review", [
            paragraph("목표 대비 결과"),
            quote(""),
            paragraph("잘된 점 / 아쉬운 점"),
            quote(""),
            paragraph("다음에 다르게 할 것"),
            quote(""),
        ]),
        divider(),
        # 미결 질문
        h1(f"{next(n)}. 미결 질문"),
        *section_blocks("questions", [
            todo("아직 결정 안 된 것 (@담당자 YYYY-MM-DD까지)"),
            todo("확인 필요한 것"),
        ]),
    ]
    return blocks


def link_task_relation(task_id, note_page_id):
    """Task 페이지의 Engineering relation에 note_page_id를 추가한다 (기존 링크 보존, 중복 방지)."""
    task_page = notion_request("GET", f"/pages/{task_id}")
    if task_page.get("object") == "error":
        return {"success": False, "error": task_page.get("message", str(task_page))}

    existing = task_page.get("properties", {}).get(TASK_DB_RELATION_PROPERTY, {}).get("relation", [])
    existing_ids = [r["id"] for r in existing]
    if note_page_id not in existing_ids:
        existing_ids.append(note_page_id)

    patch_body = {"properties": {TASK_DB_RELATION_PROPERTY: {"relation": [{"id": i} for i in existing_ids]}}}
    resp = notion_request("PATCH", f"/pages/{task_id}", patch_body)
    if resp.get("object") == "error":
        return {"success": False, "error": resp.get("message", str(resp))}
    return {"success": True}


def cmd_create(args):
    title = sanitize_body(args.title)  # 제목 하드룰 backstop (em dash/이모지)
    group = args.group or "#업무노트"
    task_id = args.task.strip() if args.task else ""
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

    properties = {
        "Title": {"title": [{"type": "text", "text": {"content": title}}]},
        "Group": {"select": {"name": group}},
        "Created At": {"date": {"start": today}},
    }
    if task_id:
        properties["Task"] = {"relation": [{"id": task_id}]}

    # Create the page
    page_body = {
        "parent": {"type": "data_source_id", "data_source_id": resolve_ds_id(DB_ID)},
        "properties": properties,
        "children": make_template_blocks(sections, linked_to_task=bool(task_id)),
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

    # POST /pages 응답은 생성된 자식 블록의 id를 담지 않으므로, 콜아웃/heading id를
    # 얻으려면 별도로 top-level children을 조회해야 한다.
    children_resp = notion_request("GET", f"/blocks/{page_id}/children?page_size=100")
    created_blocks = children_resp.get("results", []) if children_resp.get("object") != "error" else []
    callout_id, toc_rich_text = build_toc_rich_text(created_blocks, page_url)
    if callout_id:
        notion_request("PATCH", f"/blocks/{callout_id}", {"callout": {"rich_text": toc_rich_text}})

    task_linked = False
    task_link_error = None
    if task_id:
        # Engineering DB "Task" relation은 위에서 이미 설정됨. Task DB 쪽 "Engineering"
        # relation은 dual-property가 아닐 수 있으므로 반대편도 명시적으로 채운다.
        link_result = link_task_relation(task_id, page_id)
        task_linked = link_result["success"]
        if not task_linked:
            task_link_error = link_result["error"]

    result = {
        "success": True,
        "page_id": page_id,
        "title": title,
        "group": group,
        "url": page_url,
        "task_linked": task_linked,
    }
    if task_link_error:
        result["task_link_error"] = task_link_error
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_list(args):
    limit = args.limit or 10
    body = {
        "sorts": [{"property": "Created At", "direction": "descending"}],
        "page_size": limit,
    }
    resp = notion_request("POST", f"/data_sources/{resolve_ds_id(DB_ID)}/query", body)

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
        task_relation = props.get("Task", {}).get("relation", [])
        created = props.get("Created At", {}).get("date", {})
        created_date = created.get("start", "") if created else ""
        page_id = page.get("id", "")
        url = f"https://www.notion.so/{page_id.replace('-', '')}"
        results.append({
            "title": title,
            "group": group_name,
            "task_linked": bool(task_relation),
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
    create_p.add_argument("--task", default="",
                          help="연결할 Notion Task 페이지 ID. 지정 시 노트↔Task 양방향 relation을 건다")
    create_p.add_argument("--sections", default="",
                          help="섹션 내용이 담긴 JSON 파일 경로 "
                               "(keys: design, alternatives, plan, history, review, questions; "
                               "problem/goal/non_goal은 --task 미지정 독립 노트에서만 사용)")

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
