#!/usr/bin/env python3
"""
Engineering DB 업무 노트 CLI
Usage:
  python3 notion-eng-note.py create --title "제목" [--group "#업무노트"] [--task <task-page-id>] [--sections /tmp/sections.json]
  python3 notion-eng-note.py list [--limit 10]

Engineering DB의 업무 노트 템플릿(NOTE_TEMPLATE_ID)으로 페이지를 만들고, 템플릿 heading 아래를
sections 내용으로 채운다(_lib/notion_template_fill.py). 노트가 "왜"(문제/근본 원인/기대 가치)의
최종본이므로 --task 유무와 관계없이 모든 섹션을 쓴다. 연결된 Task의 같은 섹션은 호출자가
notion-task.py update-why로 동기화한다.

sections.json 키 (값은 마크다운, 없는 키는 템플릿의 빈 칸으로 남는다):
{
  "problem", "root_cause", "value",          # 왜 이걸 해야하는가?
  "before", "after", "changes",              # 현재 상태와 목표 (Before | After 2열, 변경 사항)
  "goals", "non_goals",                      # Goals | Non Goals 2열
  "design",                                  # 설계 (선택 이유·대안·다이어그램 포함)
  "plan", "history",                         # 실행 기록 (### 실행 계획 체크박스 / ### 진행 기록)
  "result",                                  # 작업 결과
  "review_metrics", "review_par", "review_retro"   # Task Review 하위 3개
}

섹션 제목이 H2/H3로 깔려 있으므로 섹션 내용의 heading은 ###만 쓴다.
호출자가 ##로 써도 normalize_subsection_headings가 H3 기준으로 자동 보정한다.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import argparse
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
try:
    from notion_text import sanitize_body
except Exception:  # backstop은 쓰기 경로를 절대 깨지 않는다
    def sanitize_body(text):
        return text
try:
    import notion_template_fill as tfill
except Exception:  # 헬퍼를 못 읽으면 템플릿 경로 대신 대체 구조로 생성한다
    tfill = None

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DB_ID = "17964745-3170-8030-bf01-e7f20a6e1bd7"

GROUP_OPTIONS = ["#Study", "#Article", "#업무노트", "#정리"]
# Task DB(개인 Task DB) 페이지의 관계형 속성 이름. Engineering DB "Task" 관계의 반대편.
TASK_DB_RELATION_PROPERTY = "Working Note"

# Engineering DB "[#업무 노트]" 템플릿(목차·섹션·2열 배치 포함). 템플릿 구조는 Notion이 단일 출처이고,
# 스크립트는 아래 heading 이름으로 채울 자리를 찾는다. 전체 너비 같은 페이지 설정도 템플릿에서 이어진다
# (Notion API로는 너비를 설정할 수 없다).
NOTE_TEMPLATE_ID = "3e864745-3170-803d-a912-e4ee9c81b16f"
# (sections 키, 템플릿 heading, 접두어 매칭 여부). 접두어 매칭은 괄호 설명이 바뀌기 쉬운 Task Review 하위 heading용.
SECTION_HEADINGS = [
    ("problem", "문제", False),
    ("root_cause", "근본 원인", False),
    ("value", "기대 가치", False),
    ("before", "Before", False),
    ("after", "After", False),
    ("changes", "변경 사항", False),
    ("goals", "Goals", False),
    ("non_goals", "Non Goals", False),
    ("design", "설계", False),
    ("result", "작업 결과", False),
    ("review_metrics", "성과 측정", True),
    ("review_par", "성과 문장", True),
    ("review_retro", "성장 회고", True),
]
RUN_LOG_HEADING = "실행 기록"
PLAN_SUBHEADING = "실행 계획"
HISTORY_SUBHEADING = "진행 기록"
# review: task:review·alfred gate 출력처럼 "### 성과 측정 / ### ...성과 문장 / ### 성장 회고"를 한 문자열로
# 받는 편의 키. 하위 heading으로 나눠 review_* 세 섹션에 넣는다(REVIEW_SPLIT_RULES).
SECTION_KEYS = [key for key, _, _ in SECTION_HEADINGS] + ["plan", "history", "review"]
REVIEW_SPLIT_RULES = [("성과 측정", "review_metrics"), ("성과 문장", "review_par"),
                      ("PAAR", "review_par"), ("PAR", "review_par"), ("성장 회고", "review_retro")]
TEMPLATE_APPLY_TIMEOUT_SEC = 30
# 템플릿 본문이 들어온 뒤 heading이 다 보이기를 기다리는 시간. 넘기면 템플릿 본문이 우리 구조와 다르다고 본다.
TEMPLATE_SETTLE_SEC = 5
NOTION_APPEND_BATCH = 100  # children append 한 번에 넣을 수 있는 최대 블록 수


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


_UPLOAD_CACHE = {}  # 같은 로컬 파일을 여러 번 참조해도 한 번만 올린다 (file_upload id는 재사용 가능)
IMAGE_CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                       ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}


def upload_file(path):
    """로컬 파일을 Notion File Upload API로 올리고 file_upload id를 반환한다.

    올린 파일은 1시간 안에 블록에 붙여야 만료되지 않는다. 노트 생성 직전에 호출되므로 충분하다.
    """
    path = Path(path).expanduser().resolve()
    if path in _UPLOAD_CACHE:
        return _UPLOAD_CACHE[path]
    if not path.is_file():
        raise ValueError(f"image not found: {path}")
    content_type = IMAGE_CONTENT_TYPES.get(path.suffix.lower())
    if content_type is None:
        raise ValueError(f"unsupported image type: {path.suffix} (지원: {sorted(IMAGE_CONTENT_TYPES)})")

    created = notion_request("POST", "/file_uploads", {"filename": path.name, "content_type": content_type})
    if created.get("object") == "error":
        raise ValueError(f"file upload create failed: {created.get('message', '')}")

    boundary = "----notion-eng-note-upload"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.notion.com/v1/file_uploads/{created['id']}/send", data=body, method="POST",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2025-09-03",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        })
    try:
        with urllib.request.urlopen(req) as resp:
            sent = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"file upload send failed: HTTP {e.code} {e.read().decode()[:300]}")
    if sent.get("status") != "uploaded":
        raise ValueError(f"file upload not completed: status={sent.get('status')}")

    _UPLOAD_CACHE[path] = created["id"]
    return created["id"]


def image_block(caption, src):
    """`![caption](src)` 한 줄을 image 블록으로 만든다. http(s)면 외부 URL, 아니면 로컬 파일을 올린다."""
    if re.match(r"^https?://", src):
        image = {"type": "external", "external": {"url": src}}
    else:
        image = {"type": "file_upload", "file_upload": {"id": upload_file(src)}}
    if caption:
        image["caption"] = md_to_rich_text(caption)
    return {"type": "image", "image": image}


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
    table_buf = []  # [(indent, line)] 연속된 `|...|` 줄 버퍼

    def split_row(row):
        return [c.strip() for c in row.strip().strip("|").split("|")]

    def flush_table():
        """버퍼가 GFM 표면 table 블록으로, 아니면 기존대로 문단으로 떨군다."""
        if not table_buf:
            return
        rows = [split_row(l) for _, l in table_buf]
        is_table = (
            len(rows) >= 2
            and all(re.fullmatch(r':?-{2,}:?', c) for c in rows[1] if c)
            and len(rows[1]) == len(rows[0])
        )
        if is_table:
            width = len(rows[0])
            body = [rows[0]] + rows[2:]
            children = []
            for r in body:
                cells = (r + [""] * width)[:width]
                children.append({"type": "table_row", "table_row": {
                    "cells": [md_to_rich_text(c) if c else [] for c in cells]
                }})
            blocks.append({"type": "table", "table": {
                "table_width": width,
                "has_column_header": True,
                "has_row_header": False,
                "children": children,
            }})
            stack.clear()
        else:
            for ind, l in table_buf:
                place(ind, {"type": "paragraph", "paragraph": {
                    "rich_text": md_to_rich_text(l), "color": "default"
                }})
        table_buf.clear()

    for line in lines:
        stripped = line.rstrip()
        lstripped = stripped.lstrip(" ")
        indent = len(stripped) - len(lstripped)

        if not in_code:
            if re.match(r'^\|.*\|$', lstripped):
                table_buf.append((indent, lstripped))
                continue
            flush_table()

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

        # 이미지 한 줄: 설계 섹션의 다이어그램(archify / diagram-design PNG)을 넣는 경로
        m = re.match(r'^!\[(.*?)\]\((.+?)\)$', lstripped)
        if m:
            place(indent, image_block(m.group(1).strip(), m.group(2).strip()))
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

    flush_table()
    return blocks


MIN_SUBSECTION_HEADING_LEVEL = 3  # 섹션 제목이 H2(설계, 실행 기록 등)이므로 섹션 내용의 최상위 heading은 H3다
MAX_NOTION_HEADING_LEVEL = 3      # Notion은 heading_3까지만 지원한다


def normalize_subsection_headings(blocks):
    """섹션 내용의 heading 최상위 레벨을 H3로 맞춘다 (상대 깊이는 보존).

    템플릿이 각 섹션 제목을 H2로 깔기 때문에, 섹션 내용이 H2로 시작하면 섹션 경계가 깨지고
    (다음 섹션 제목과 같은 레벨) H1이면 계층이 뒤집힌다. 호출자마다 ## / ### 중 무엇을 쓸지
    엇갈리므로 여기서 결정론적으로 보정한다.

    Notion heading이 3단계뿐이라 H3을 넘는 깊이는 H3으로 접힌다. 접힘이 실제로
    발생하면 형제 관계가 뭉개지므로 stderr로 알린다.
    """
    levels = [
        int(b["type"][-1]) for b in blocks
        if b.get("type", "").startswith("heading_")
    ]
    if not levels:
        return blocks

    shift = MIN_SUBSECTION_HEADING_LEVEL - min(levels)
    if shift == 0:
        return blocks

    collapsed = False
    for block in blocks:
        block_type = block.get("type", "")
        if not block_type.startswith("heading_"):
            continue
        level = int(block_type[-1])
        new_level = level + shift
        if new_level > MAX_NOTION_HEADING_LEVEL:
            new_level = MAX_NOTION_HEADING_LEVEL
            collapsed = True
        if new_level == level:
            continue
        block[f"heading_{new_level}"] = block.pop(block_type)
        block["type"] = f"heading_{new_level}"

    if collapsed:
        print(
            "WARN: 섹션 내용의 heading 깊이가 Notion 한계(H3)를 넘어 일부가 H3으로 접혔습니다. "
            "섹션 내용에는 heading을 ### 한 단계만 쓰십시오.",
            file=sys.stderr,
        )
    return blocks


def _h(level, text):
    htype = f"heading_{level}"
    return {"type": htype, htype: {"rich_text": [{"type": "text", "text": {"content": text}}], "color": "default"}}


def build_section_blocks(sections):
    """sections dict → {heading 텍스트: [blocks]}. 키는 SECTION_HEADINGS 참조.

    '실행 기록'은 plan과 history를 한 섹션에 담는다: plan이 있으면 '### 실행 계획' 아래 체크박스로,
    기록은 '### 진행 기록' 아래에 둔다. 이후 append-content --section "실행 기록"으로 덧붙이는
    날짜별 기록이 섹션 끝(진행 기록 아래)에 쌓이게 하기 위한 배치다.
    """
    unknown = sorted(set(sections) - set(SECTION_KEYS))
    if unknown:
        raise ValueError(f"알 수 없는 sections 키: {unknown}. 허용: {list(SECTION_KEYS)}")

    def parsed(key):
        content = (sections.get(key) or "").strip()
        return normalize_subsection_headings(md_to_blocks(content)) if content else []

    if (sections.get("review") or "").strip():
        if any(sections.get(k) for k in ("review_metrics", "review_par", "review_retro")):
            raise ValueError("review와 review_* 키를 함께 쓸 수 없습니다")
        sections = {**sections, **split_review(sections["review"])}

    filled = {}
    for key, heading, _prefix in SECTION_HEADINGS:
        blocks = parsed(key)
        if blocks:
            filled[heading] = blocks

    plan, history = parsed("plan"), parsed("history")
    run_log = []
    if plan:
        run_log += [_h(3, PLAN_SUBHEADING), *plan]
    if plan or history:
        run_log += [_h(3, HISTORY_SUBHEADING), *history]
    if run_log:
        filled[RUN_LOG_HEADING] = run_log
    return filled


def split_review(markdown):
    """review 마크다운을 하위 heading(### 성과 측정 등) 기준으로 review_* 키별 마크다운으로 나눈다.

    heading 줄 자체는 버린다(템플릿에 같은 heading이 이미 있다). 규칙에 없는 heading이나 heading 앞의
    본문이 있으면 어디에 넣을지 알 수 없으므로 페이지를 만들기 전에 실패시킨다.
    """
    split, current = {}, None
    for line in markdown.strip().split("\n"):
        match = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if match:
            title = match.group(1)
            current = next((key for prefix, key in REVIEW_SPLIT_RULES if title.startswith(prefix)), None)
            if current is None:
                raise ValueError(f"review의 하위 heading을 Task Review 섹션에 매핑할 수 없습니다: {title}")
            split.setdefault(current, [])
            continue
        if current is None:
            if line.strip():
                raise ValueError("review는 '### 성과 측정' 같은 하위 heading으로 시작해야 합니다")
            continue
        split[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in split.items()}


def make_fallback_blocks(filled):
    """템플릿 적용이 실패했을 때 템플릿과 같은 구조를 직접 조립한다(전체 너비 등 템플릿 설정만 빠진다).

    filled: build_section_blocks 결과. 없는 섹션은 빈 불릿 placeholder로 둔다.
    """
    def bullet():
        return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [], "color": "default"}}

    def section(level, heading):
        return [_h(level, heading), *(filled.get(heading) or [bullet()])]

    def column_list(columns):
        return {"type": "column_list", "column_list": {"children": [
            {"type": "column", "column": {"children": col}} for col in columns
        ]}}

    toc = {"type": "callout", "callout": {
        "rich_text": [], "icon": {"type": "emoji", "emoji": "📌"}, "color": "default",
        "children": [{"type": "table_of_contents", "table_of_contents": {"color": "gray"}}],
    }}
    headings = {key: heading for key, heading, _ in SECTION_HEADINGS}
    return [
        toc,
        _h(2, "왜 이걸 해야하는가?"),
        *section(3, headings["problem"]),
        *section(3, headings["root_cause"]),
        *section(3, headings["value"]),
        _h(2, "현재 상태와 목표"),
        column_list([section(3, headings["before"]), section(3, headings["after"])]),
        *section(3, headings["changes"]),
        column_list([section(3, headings["goals"]), section(3, headings["non_goals"])]),
        *section(2, headings["design"]),
        *section(2, RUN_LOG_HEADING),
        *section(2, headings["result"]),
        {"type": "divider", "divider": {}},
        _h(2, "Task Review"),
        *section(3, headings["review_metrics"]),
        *section(3, headings["review_par"]),
        *section(3, headings["review_retro"]),
    ]


def create_from_template(parent, properties, filled, template_id):
    """노트 템플릿으로 페이지를 만들고 섹션을 채운다.

    전체 너비 같은 페이지 설정은 템플릿에서만 이어받을 수 있으므로(API로 설정 불가), 템플릿이 적용된 페이지는
    가능한 한 버리지 않는다.
    - 템플릿 본문에 우리 heading이 모두 있으면 heading 아래를 채운다(body_source="template").
    - 템플릿은 적용됐는데 heading이 없거나 모자라면(템플릿 본문을 누가 고친 경우) 본문을 비우고 같은 구조를
      직접 조립해 넣는다(body_source="script"). 페이지 설정은 그대로 남는다.
    - 템플릿 자체가 적용되지 않으면 페이지를 휴지통으로 보내고 (None, 사유, None)을 반환한다.
    반환: (생성 응답, 오류 사유 또는 None, body_source)
    """
    if tfill is None:
        return None, "notion_template_fill 헬퍼를 불러오지 못함", None
    resp = notion_request("POST", "/pages", {
        "parent": parent,
        "properties": properties,
        "template": {"type": "template_id", "template_id": template_id},
    })
    if resp.get("object") == "error":
        return None, f"템플릿 생성 실패: {resp.get('message', '')}", None
    page_id = resp["id"]

    def discard(reason):
        notion_request("PATCH", f"/pages/{page_id}", {"in_trash": True})
        return None, reason, None

    request = lambda method, path, body=None: notion_request(method, path, body)
    exact = [RUN_LOG_HEADING] + [h for _, h, prefix in SECTION_HEADINGS if not prefix]
    prefixed = [h for _, h, prefix in SECTION_HEADINGS if prefix]

    deadline = time.monotonic() + TEMPLATE_APPLY_TIMEOUT_SEC
    body_seen_at = None
    while True:
        groups = tfill.load_tree(request, page_id)
        if groups and groups[0]["blocks"]:
            if not tfill.find_missing(groups, exact) and not tfill.find_missing(groups, prefixed, prefix=True):
                break
            body_seen_at = body_seen_at or time.monotonic()
            if time.monotonic() - body_seen_at > TEMPLATE_SETTLE_SEC:
                return rebuild_in_place(page_id, filled, resp, discard)
        elif time.monotonic() > deadline:
            return discard(f"템플릿 본문이 {TEMPLATE_APPLY_TIMEOUT_SEC}초 안에 적용되지 않음")
        time.sleep(1)

    prefix_of = {h: prefix for _, h, prefix in SECTION_HEADINGS}
    for heading, blocks in filled.items():
        result = tfill.fill_section(request, groups, heading, blocks, prefix=prefix_of.get(heading, False))
        if result is not None:
            reason = result.get("message", "") if isinstance(result, dict) else result
            return discard(f"'{heading}' 섹션 채우기 실패: {reason}")
    return resp, None, "template"


def rebuild_in_place(page_id, filled, resp, discard):
    """템플릿이 적용된 페이지의 본문을 비우고 표준 구조를 직접 넣는다(페이지 설정은 유지)."""
    print("WARN: 템플릿 본문에 노트 heading이 없어 구조를 직접 만듭니다. 템플릿 본문이 바뀌었는지 확인하세요.",
          file=sys.stderr)
    erased = notion_request("PATCH", f"/pages/{page_id}", {"erase_content": True})
    if erased.get("object") == "error":
        return discard(f"템플릿 본문 비우기 실패: {erased.get('message', '')}")
    blocks = make_fallback_blocks(filled)
    deferred = defer_column_grandchildren(blocks)
    appended = append_blocks(page_id, blocks)
    if appended is not None:
        return discard(f"구조 추가 실패: {appended.get('message', '')}")
    restore_column_grandchildren(list_children(page_id), deferred)
    return resp, None, "script"


def link_task_relation(task_id, note_page_id):
    """Task 페이지의 Working Note relation에 note_page_id를 추가한다 (기존 링크 보존, 중복 방지)."""
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


def defer_column_grandchildren(blocks):
    """열 안 블록의 하위 블록을 떼어 내 나중에 붙일 목록으로 돌려준다.

    Notion은 한 요청에 2단계 중첩까지만 받는다. column_list → column → 블록이 이미 2단계라
    열 안의 불릿이 하위 불릿을 가지면 요청이 거부된다. 반환값은 column_list 등장 순서별
    [열 인덱스][블록 인덱스] → children 목록(없으면 None)이다.
    """
    deferred = []
    for block in blocks:
        if block.get("type") != "column_list":
            continue
        per_column = []
        for column in block["column_list"]["children"]:
            per_block = []
            for child in column["column"]["children"]:
                body = child.get(child.get("type", ""), {})
                per_block.append(body.pop("children", None) if isinstance(body, dict) else None)
            per_column.append(per_block)
        deferred.append(per_column)
    return deferred


def list_children(block_id):
    results, cursor = [], None
    while True:
        query = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        resp = notion_request("GET", f"/blocks/{block_id}/children{query}")
        results += resp.get("results", [])
        if not resp.get("has_more"):
            return results
        cursor = resp.get("next_cursor")


def restore_column_grandchildren(created_blocks, deferred):
    """defer_column_grandchildren로 떼어 둔 하위 블록을 생성된 열 안 블록에 다시 붙인다."""
    column_lists = [b for b in created_blocks if b.get("type") == "column_list"]
    for column_list_block, per_column in zip(column_lists, deferred):
        for column, per_block in zip(list_children(column_list_block["id"]), per_column):
            for child, grandchildren in zip(list_children(column["id"]), per_block):
                if grandchildren:
                    append_blocks(child["id"], grandchildren)


def append_blocks(page_id, blocks):
    """블록을 NOTION_APPEND_BATCH 단위로 나눠 페이지 끝에 붙인다. 실패하면 error 응답을 반환한다."""
    for start in range(0, len(blocks), NOTION_APPEND_BATCH):
        resp = notion_request("PATCH", f"/blocks/{page_id}/children",
                              {"children": blocks[start:start + NOTION_APPEND_BATCH]})
        if resp.get("object") == "error":
            return resp
    return None


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

    try:
        filled = build_section_blocks(sections)
    except ValueError as e:  # 알 수 없는 키·이미지 업로드 실패: 페이지를 만들기 전에 멈춰 반쪽짜리 노트를 남기지 않는다
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    parent = {"type": "data_source_id", "data_source_id": resolve_ds_id(DB_ID)}

    resp, template_error, body_source = None, None, None
    if not args.no_template:
        resp, template_error, body_source = create_from_template(parent, properties, filled, args.template_id)
        if template_error:
            print(f"WARN: {template_error}. 템플릿 없이 같은 구조로 다시 생성합니다.", file=sys.stderr)
    template_applied = resp is not None

    if resp is None:
        # 템플릿을 끈 경우와 템플릿 적용이 실패한 경우: 같은 구조를 조립해 생성 요청에 함께 넣는다
        blocks = make_fallback_blocks(filled)
        deferred = defer_column_grandchildren(blocks)
        resp = notion_request("POST", "/pages", {"parent": parent, "properties": properties, "children": blocks})
        if resp.get("object") != "error":
            restore_column_grandchildren(list_children(resp["id"]), deferred)

    if resp.get("object") == "error":
        print(json.dumps({
            "success": False,
            "error": resp.get("message", str(resp)),
        }, ensure_ascii=False))
        sys.exit(1)

    page_id = resp.get("id", "")
    page_url = resp.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")

    task_linked = False
    task_link_error = None
    if task_id:
        # Engineering DB "Task" relation은 위에서 이미 설정됨. Task DB 쪽 "Working Note"
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
        "template_applied": template_applied,
        "body_source": body_source or "script",
        "task_linked": task_linked,
    }
    if template_error:
        result["template_error"] = template_error
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
                          help=f"섹션 내용이 담긴 JSON 파일 경로 (keys: {', '.join(SECTION_KEYS)})")
    create_p.add_argument("--no-template", action="store_true",
                          help="템플릿을 적용하지 않고 같은 구조를 직접 조립해 생성")
    create_p.add_argument("--template-id", dest="template_id", default=NOTE_TEMPLATE_ID,
                          help=argparse.SUPPRESS)  # 대체 경로 검증용 override

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
