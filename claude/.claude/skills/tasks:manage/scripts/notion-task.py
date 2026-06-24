#!/usr/bin/env python3
"""
Notion Task CLI (Write + Query)

공유 라이브러리 스크립트 — tasks:capture, tasks:status, tasks:carry-over,
daily:start, daily:review 스킬에서 참조한다.

Usage:
  # 조회
  python3 notion-task.py search-tasks [--status all|active]
  python3 notion-task.py tasks [--week current|previous|next] [--month YYYY-MM] [--status in-progress|upcoming|all]
  python3 notion-task.py calendar-pending   # 개인(MY)+Due+미완료 — 캘린더 동기화 대상

  # 생성
  python3 notion-task.py create-task --name "이름" --priority "P3" --category "WORK" [--due "YYYY-MM-DD"] [--roi High|Medium|Low] [--description "설명"] [--body "Markdown" | --body-file PATH]

  # ROI 설정 (Alfred groom — 사용자 승인 후)
  python3 notion-task.py set-roi --page-id <id> --roi High|Medium|Low

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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
try:
    from notion_text import sanitize_body
except Exception:  # backstop은 쓰기 경로를 절대 깨지 않는다
    def sanitize_body(text):
        return text

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

VALID_STATUSES = {"시작 전", "진행 중", "완료", "대기"}
PRIORITY_OPTIONS = {
    "P1",
    "P2",
    "P3",
}
CATEGORY_OPTIONS = {"WORK", "MY"}
# ROI = 가치/노력 판단 버킷. Alfred groom 모드가 기록, 브리핑이 정렬 키로 사용.
ROI_OPTIONS = {"High", "Medium", "Low"}


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
        "Notion-Version": "2025-09-03",
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


# ── data source resolution (Notion-Version 2025-09-03) ────────
# 2025-09-03부터 쿼리는 database가 아니라 data source 단위다.
# 단일 data source DB를 전제로 db_id→ds_id를 1회 조회 후 프로세스 내 캐시한다.
_DS_CACHE = {}


def resolve_ds_id(token, db_id):
    """db_id → data source id (프로세스 내 캐시). 2025-09-03 쿼리/생성에 필요."""
    if db_id not in _DS_CACHE:
        db = notion_request(token, "GET", f"/databases/{db_id}")
        sources = db.get("data_sources", [])
        if not sources:
            raise RuntimeError(f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


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
    roi_sel = props.get("ROI", {}).get("select")
    roi = roi_sel.get("name", "") if roi_sel else ""
    tags = [t.get("name", "") for t in props.get("Tag", {}).get("multi_select", [])]
    return {
        "page_id": page["id"],
        "name": name,
        "priority": priority,
        "status": status,
        "due_date": due.get("start", ""),
        "category": category,
        "roi": roi,
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
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)

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
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)
    return [_parse_page(page) for page in resp.get("results", [])]


def query_calendar_pending(token):
    """Google Calendar 동기화 대상 Task 조회.

    대상 규약: 개인(Group=MY) AND Due Date 존재 AND 미완료(상태 != 완료).
    Due Date 없는 Task는 종일 이벤트로 표현할 수 없어 제외하고, 완료 Task는
    캘린더에서 삭제 대상이므로 desired set에서 빠진다(Alfred reconcile이 처리).
    """
    body = {
        "filter": {
            "and": [
                {"property": "Group", "select": {"equals": "MY"}},
                {"property": "Due Date", "date": {"is_not_empty": True}},
                {"property": "상태", "status": {"does_not_equal": "완료"}},
            ]
        },
        "sorts": [{"property": "Due Date", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)
    return [_parse_page(page) for page in resp.get("results", [])]


def cmd_calendar_pending(args):
    """캘린더 동기화 desired set 출력 — Alfred calendar 모드가 reconcile 입력으로 사용."""
    token = get_token()
    results = query_calendar_pending(token)
    print(json.dumps({
        "results": results,
        "total": len(results),
    }, ensure_ascii=False, indent=2))


def cmd_search_tasks(args):
    """Claude 매칭용: 활성 Task 전체 목록 반환."""
    token = get_token()
    status_filter = getattr(args, "status", "active")

    if status_filter == "all":
        body = {
            "sorts": [{"property": "Priority", "direction": "ascending"}],
        }
        resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)
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

    name = sanitize_body(args.name.strip())  # 제목 하드룰 backstop (em dash/이모지)
    if not name:
        _exit_error("--name is required and cannot be empty")

    priority = args.priority
    if priority not in PRIORITY_OPTIONS:
        _exit_error(f"Invalid priority '{priority}'. Valid: {sorted(PRIORITY_OPTIONS)}")

    category = args.category
    if category not in CATEGORY_OPTIONS:
        _exit_error(f"Invalid category '{category}'. Valid: {sorted(CATEGORY_OPTIONS)}")

    roi = getattr(args, "roi", None)
    if roi and roi not in ROI_OPTIONS:
        _exit_error(f"Invalid ROI '{roi}'. Valid: {sorted(ROI_OPTIONS)}")

    # 본문 템플릿(Summary/Why/기대효과/Non-Goals)을 미리 파싱해 fail-fast.
    # 페이지 POST 전에 검증해야 본문 누락된 반쪽 Task가 생기지 않는다.
    # --body(인라인)와 --body-file 중 파일 우선. 둘 다 없으면 본문 템플릿 생략.
    body_blocks = []
    body_file = getattr(args, "body_file", None)
    body_inline = getattr(args, "body", None)
    body_md = None
    if body_file:
        try:
            with open(body_file, "r", encoding="utf-8") as f:
                body_md = f.read()
        except OSError as e:
            _exit_error(f"본문 템플릿 파일을 읽을 수 없습니다: {body_file} ({e})")
    elif body_inline:
        body_md = body_inline
    if body_md:
        body_blocks = markdown_to_blocks(body_md)

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

    if roi:
        properties["ROI"] = {"select": {"name": roi}}

    if args.description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": args.description}}]
        }

    body = {
        "parent": {"type": "data_source_id", "data_source_id": resolve_ds_id(token, TASK_DB_ID)},
        "properties": properties,
    }

    result = notion_request(token, "POST", "/pages", body)
    page_id = result.get("id", "")

    # 본문 템플릿(있으면) → 업무 노트 리마인더 → 이미지 블록 순서로 본문 구성.
    # 템플릿이 페이지 최상단에 오도록 callout 앞에 prepend 한다.
    children_blocks = body_blocks + [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "업무 노트 작성하기\n"},
                        "annotations": {"bold": True},
                    },
                    {
                        "type": "text",
                        "text": {"content": "Engineering DB에서 이 Task를 연결하여 업무 노트를 작성하세요."},
                        "annotations": {"color": "gray"},
                    }
                ],
                "icon": {"type": "emoji", "emoji": "📝"},
                "color": "blue_background",
            },
        },
    ]

    images = getattr(args, "images", None) or []
    url_images = [img for img in images if img.startswith("http://") or img.startswith("https://")]
    local_images = [img for img in images if not (img.startswith("http://") or img.startswith("https://"))]

    for img_url in url_images:
        children_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": img_url},
            },
        })

    if local_images:
        paths_text = "\n".join(local_images)
        children_blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": "로컬 이미지 경로\n"},
                        "annotations": {"bold": True},
                    },
                    {
                        "type": "text",
                        "text": {"content": paths_text},
                        "annotations": {"code": True},
                    },
                ],
                "icon": {"type": "emoji", "emoji": "🖼"},
                "color": "gray_background",
            },
        })

    notion_request(token, "PATCH", f"/blocks/{page_id}/children", {
        "children": children_blocks
    })

    print(json.dumps({
        "success": True,
        "page_id": page_id,
        "name": name,
        "priority": priority,
        "category": category,
        "due_date": args.due or "",
        "roi": roi or "",
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# ROI 설정 (Alfred groom 모드 — 게이트된 자율성: 사용자 승인 후 호출)
# ─────────────────────────────────────────────

def cmd_set_roi(args):
    """Task의 ROI 버킷을 설정한다. Alfred groom이 사용자 승인을 받은 뒤 호출."""
    token = get_token()

    if args.roi not in ROI_OPTIONS:
        _exit_error(f"Invalid ROI '{args.roi}'. Valid: {sorted(ROI_OPTIONS)}")

    body = {"properties": {"ROI": {"select": {"name": args.roi}}}}
    result = notion_request(token, "PATCH", f"/pages/{args.page_id}", body)

    props = result.get("properties", {})
    name = rich_text_to_plain(props.get("이름", {}).get("title", []))

    print(json.dumps({
        "success": True,
        "page_id": args.page_id,
        "name": name,
        "roi": args.roi,
    }, ensure_ascii=False, indent=2))


# ─────────────────────────────────────────────
# 상태 변경
# ─────────────────────────────────────────────

def cmd_update_status(args):
    """Task 상태 변경."""
    token = get_token()

    if args.status not in VALID_STATUSES:
        _exit_error(f"Invalid status '{args.status}'. Valid: {sorted(VALID_STATUSES)}")

    # Task DB는 완료 여부를 상태(status)와 Done(checkbox) 두 속성으로 이중 관리한다.
    # DONE 뷰·롤업은 Done 체크박스를 필터 기준으로 쓰므로, 상태만 바꾸면
    # status=완료인데 DONE 뷰에 안 보이는 불일치가 생긴다. 둘을 항상 동기화한다.
    is_done = args.status == "완료"
    properties = {
        "상태": {"status": {"name": args.status}},
        "Done": {"checkbox": is_done},
    }

    # 완료로 전환할 때 Due Date가 비어 있으면 완료일(오늘, KST)로 채운다.
    # due 없이 완료된 Task는 캘린더 동기화·기간 조회·브리핑에서 날짜 없이 묻혀
    # "언제 끝났는지"가 사라진다. 완료 시점을 마감일로 박아 항상 날짜가 남게 한다.
    # 이미 due가 있으면 사용자가 잡은 계획 마감을 덮어쓰지 않는다(완료 시점 != 계획 마감).
    backfilled_due = None
    if is_done:
        existing = notion_request(token, "GET", f"/pages/{args.page_id}")
        existing_due = existing.get("properties", {}).get("Due Date", {}).get("date") or {}
        if not existing_due.get("start"):
            backfilled_due = date.today().isoformat()
            properties["Due Date"] = {"date": {"start": backfilled_due}}

    body = {"properties": properties}
    result = notion_request(token, "PATCH", f"/pages/{args.page_id}", body)

    props = result.get("properties", {})
    name_title = props.get("이름", {}).get("title", [])
    name = rich_text_to_plain(name_title)

    print(json.dumps({
        "success": True,
        "page_id": args.page_id,
        "name": name,
        "status": args.status,
        "done": is_done,
        "due_backfilled": backfilled_due,
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
# 본문 추가 (append-content) — Markdown → Notion blocks
# task:review 결과를 Task 페이지 본문에 누적할 때 사용.
# ─────────────────────────────────────────────

import re

# Notion 제약: rich_text 1개 text content 최대 2000자, append 1회 최대 100 블록
_NOTION_TEXT_LIMIT = 2000
_NOTION_BLOCK_LIMIT = 100
# Notion code block이 허용하는 language enum (일부). 매칭 안 되면 plain text.
_NOTION_CODE_LANGS = {
    "bash", "shell", "python", "yaml", "json", "javascript", "typescript",
    "go", "sql", "diff", "markdown", "plain text",
}


def _notion_lang(lang):
    lang = (lang or "").strip().lower()
    if lang in ("sh", "zsh", "console"):
        return "bash"
    if lang in ("yml",):
        return "yaml"
    if lang in ("py",):
        return "python"
    return lang if lang in _NOTION_CODE_LANGS else "plain text"


def _split_text_content(content):
    """content를 2000자 이하 청크로 분할."""
    if len(content) <= _NOTION_TEXT_LIMIT:
        return [content]
    return [content[i:i + _NOTION_TEXT_LIMIT]
            for i in range(0, len(content), _NOTION_TEXT_LIMIT)]


def parse_rich_text(text):
    """인라인 **bold** / `code` 를 Notion rich_text 배열로 변환."""
    text = sanitize_body(text)  # 하드룰 backstop: fenced 코드블록은 별도 빌더라 제외됨
    tokens = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    rich = []
    for tok in tokens:
        if not tok:
            continue
        annotations = None
        content = tok
        if len(tok) >= 4 and tok.startswith("**") and tok.endswith("**"):
            content, annotations = tok[2:-2], {"bold": True}
        elif len(tok) >= 2 and tok.startswith("`") and tok.endswith("`"):
            content, annotations = tok[1:-1], {"code": True}
        for chunk in _split_text_content(content):
            item = {"type": "text", "text": {"content": chunk}}
            if annotations:
                item["annotations"] = dict(annotations)
            rich.append(item)
    return rich or [{"type": "text", "text": {"content": ""}}]


def _heading_block(level, text):
    htype = f"heading_{min(level, 3)}"
    return {"object": "block", "type": htype, htype: {"rich_text": parse_rich_text(text)}}


def markdown_to_blocks(md):
    """task:review 류 Markdown을 Notion 블록 리스트로 변환.

    지원: heading(#/##/###), ═══ 구분 헤딩, bullet(-/*), numbered(1.),
    quote(>), divider(---), fenced code(```), 인라인 bold/code, paragraph.
    """
    lines = md.split("\n")
    blocks, code_lines, code_lang, in_code = [], [], "plain text", False

    for raw in lines:
        stripped = raw.rstrip()
        if stripped.lstrip().startswith("```"):
            if not in_code:
                in_code, code_lang, code_lines = True, stripped.lstrip()[3:].strip(), []
            else:
                in_code = False
                content = "\n".join(code_lines)
                rich = [{"type": "text", "text": {"content": c}}
                        for c in _split_text_content(content)] or \
                       [{"type": "text", "text": {"content": ""}}]
                blocks.append({"object": "block", "type": "code",
                               "code": {"rich_text": rich, "language": _notion_lang(code_lang)}})
            continue
        if in_code:
            code_lines.append(raw)
            continue

        s = stripped.strip()
        if not s:
            continue
        if s.startswith("═"):
            blocks.append(_heading_block(2, s.strip("═ ").strip()))
        elif s.startswith("#### "):
            blocks.append(_heading_block(3, s[5:]))
        elif s.startswith("### "):
            blocks.append(_heading_block(3, s[4:]))
        elif s.startswith("## "):
            blocks.append(_heading_block(2, s[3:]))
        elif s.startswith("# "):
            blocks.append(_heading_block(1, s[2:]))
        elif s in ("---", "***", "___"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif s.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": parse_rich_text(s[2:])}})
        elif re.match(r"^[-*] ", s):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": parse_rich_text(s[2:])}})
        elif re.match(r"^\d+\. ", s):
            blocks.append({"object": "block", "type": "numbered_list_item",
                           "numbered_list_item": {"rich_text": parse_rich_text(re.sub(r"^\d+\. ", "", s))}})
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": parse_rich_text(s)}})
    return blocks


# ─────────────────────────────────────────────
# 하드룰 가드 (CLAUDE.md): em dash 금지 + 이모지 금지.
#
# 왜 여기서 막나: notion-review 서브에이전트는 `notion-create-pages` MCP 훅으로만
# 소환되는데, 이 스크립트의 append 경로는 그 훅에 매칭되지 않아 리뷰가 못 닿는다.
# 따라서 append 경로의 하드룰은 이 스크립트가 직접 강제한다.
# 자동 치환 대신 거부(exit)하는 이유: 규칙이 "사후 치환이 아니라 처음 작성부터 적용"이므로,
# 작성자가 작성 시점에 콜론/쉼표/괄호로 고치도록 강제한다.
# ─────────────────────────────────────────────

_EMDASH_CHARS = {
    "—": "em dash (—)",
    "―": "horizontal bar (―)",
}
# 이모지: astral plane(U+1F000~) 전반 + 흔한 BMP 픽토그램.
# ✓(U+2713) ✗(U+2717) →(U+2192) ·(U+00B7) ═(U+2550) 등 서식 글리프는 의도적으로 제외한다.
_EMOJI_BMP = {"✅", "❌", "⚠", "✨", "\U0001F4A1"}


def _find_hard_rule_violations(md):
    """본문에서 em dash / 이모지 위반을 (line_no, kind, snippet)로 수집."""
    violations = []
    for n, line in enumerate(md.split("\n"), 1):
        snippet = line.strip()[:60]
        for ch, name in _EMDASH_CHARS.items():
            if ch in line:
                violations.append((n, name, snippet))
        for ch in line:
            if 0x1F000 <= ord(ch) <= 0x1FFFF or ch in _EMOJI_BMP:
                violations.append((n, f"emoji ({ch})", snippet))
    return violations


def cmd_append_content(args):
    """Markdown 콘텐츠를 Task 페이지 본문에 append (task:review 결과 누적용)."""
    token = get_token()

    if args.content_file:
        with open(args.content_file, encoding="utf-8") as f:
            md = f.read()
    elif args.content:
        md = args.content
    else:
        _exit_error("--content-file 또는 --content 중 하나가 필요합니다")

    violations = _find_hard_rule_violations(md)
    if violations:
        detail = "\n".join(
            f"  line {n}: {kind}: {snip}" for n, kind, snip in violations
        )
        _exit_error(
            "하드룰 위반(em dash/이모지)으로 append를 거부했습니다. "
            "em dash는 콜론/쉼표/괄호로, 이모지는 제거 후 다시 시도하세요:\n"
            + detail
        )

    blocks = markdown_to_blocks(md)
    if not blocks:
        _exit_error("변환된 블록이 없습니다 (빈 콘텐츠)")

    appended = 0
    for i in range(0, len(blocks), _NOTION_BLOCK_LIMIT):
        batch = blocks[i:i + _NOTION_BLOCK_LIMIT]
        notion_request(token, "PATCH", f"/blocks/{args.page_id}/children", {"children": batch})
        appended += len(batch)

    print(json.dumps({
        "success": True,
        "page_id": args.page_id,
        "blocks_appended": appended,
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

    # calendar-pending
    subparsers.add_parser(
        "calendar-pending",
        help="캘린더 동기화 대상(개인 MY + Due 존재 + 미완료) Task 조회",
    )

    # create-task
    ct = subparsers.add_parser("create-task", help="새 Task 생성")
    ct.add_argument("--name", required=True, help="Task 이름")
    ct.add_argument("--priority", required=True,
                    choices=sorted(PRIORITY_OPTIONS),
                    help="우선순위")
    ct.add_argument("--category", required=True, choices=["WORK", "MY"], help="카테고리")
    ct.add_argument("--due", default=None, help="마감일 (YYYY-MM-DD)")
    ct.add_argument("--roi", default=None, choices=sorted(ROI_OPTIONS),
                    help="ROI 버킷 (선택). 미지정 시 groom 대상으로 남음")
    ct.add_argument("--description", default=None, help="부연 설명 (Description 속성)")
    ct.add_argument("--body", dest="body", default=None,
                    help="본문 템플릿 Markdown 문자열 (Summary/Why/기대효과/Non-Goals). "
                         "본격 Task에만 사용 — 페이지 본문 최상단에 렌더링")
    ct.add_argument("--body-file", dest="body_file", default=None,
                    help="본문 템플릿 Markdown 파일 경로 (--body 대신 파일로 전달). 파일 우선")
    ct.add_argument("--image", dest="images", action="append", default=None,
                    help="이미지 URL 또는 로컬 파일 경로 (여러 번 사용 가능)")

    # set-roi
    sr = subparsers.add_parser("set-roi", help="Task ROI 버킷 설정 (groom)")
    sr.add_argument("--page-id", required=True, help="Notion page ID")
    sr.add_argument("--roi", required=True, choices=sorted(ROI_OPTIONS),
                    help="ROI 버킷")

    # update-status
    us = subparsers.add_parser("update-status", help="Task 상태 변경")
    us.add_argument("--page-id", required=True, help="Notion page ID")
    us.add_argument("--status", required=True,
                    choices=sorted(VALID_STATUSES),
                    help="변경할 상태")

    # delete-task
    dt = subparsers.add_parser("delete-task", help="Task 아카이브 (복구 가능)")
    dt.add_argument("--page-id", required=True, help="Notion page ID")

    # append-content
    ac = subparsers.add_parser("append-content", help="Task 페이지 본문에 Markdown 콘텐츠 추가")
    ac.add_argument("--page-id", required=True, help="Notion page ID")
    ac_group = ac.add_mutually_exclusive_group(required=True)
    ac_group.add_argument("--content-file", default=None, help="Markdown 파일 경로")
    ac_group.add_argument("--content", default=None, help="Markdown 문자열 (직접 전달)")

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
        "calendar-pending": cmd_calendar_pending,
        "create-task": cmd_create_task,
        "set-roi": cmd_set_roi,
        "update-status": cmd_update_status,
        "delete-task": cmd_delete_task,
        "append-content": cmd_append_content,
        "carry-over": cmd_carry_over,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
