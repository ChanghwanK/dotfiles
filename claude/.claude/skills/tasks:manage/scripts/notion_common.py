#!/usr/bin/env python3
"""
Notion 공통 헬퍼: tasktui(todo_store/todo_sync)와 향후 notion-task.py 공유용.

notion-task.py에서 검증된 패턴(notion_request, rich_text_to_plain, _parse_page,
상수)을 추출했다. 파일명에 하이픈이 있는 notion-task.py는 `import`로 불러올 수
없어, 공유가 필요한 로직을 이 모듈로 분리한다.

원본(notion-task.py)과의 한 가지 의도적 차이:
  notion-task.py의 notion_request는 실패 시 프로세스를 즉시 종료(_exit_error)한다.
  sync 엔진은 다수 Task를 순회하며 부분 실패를 회수해야 하므로, 여기서는
  NotionError 예외로 전파하고 호출자가 복구/로깅을 결정하게 한다.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

VALID_STATUSES = {"시작 전", "진행 중", "완료", "대기"}
PRIORITY_OPTIONS = {
    "P1",
    "P2",
    "P3",
}
CATEGORY_OPTIONS = {"WORK", "MY"}

KST = timezone(timedelta(hours=9))

# Notion REST API는 평균 ~3 req/s를 권장한다. 다수 Task를 순회하는 sync에서
# 429를 선제적으로 피하기 위해 호출 간 최소 간격을 둔다(보수적).
_MIN_INTERVAL_S = 0.35
_last_request_at = 0.0


class NotionError(Exception):
    """Notion API 호출 실패. CLI 진입점이 잡아서 JSON 에러로 변환한다."""

    def __init__(self, status, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


# ── 인증 ──────────────────────────────────────────────────────

def get_token():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise NotionError(0, "NOTION_TOKEN environment variable not set")
    return token


# ── HTTP ──────────────────────────────────────────────────────

def _throttle():
    """전역 호출 간격을 _MIN_INTERVAL_S 이상으로 유지한다(프로세스 내)."""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - elapsed)
    _last_request_at = time.monotonic()


def notion_request(token, method, path, body=None, *, max_retries=3):
    """
    Notion REST 호출. 429(rate limit)는 Retry-After를 존중해 재시도하고,
    소진 시 NotionError를 던진다. DELETE처럼 빈 본문 응답도 안전하게 처리한다.
    """
    url = f"{NOTION_API}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None

    for attempt in range(max_retries + 1):
        _throttle()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            if e.code == 429 and attempt < max_retries:
                # Retry-After는 초 단위. 헤더가 없으면 보수적으로 1초.
                retry_after = float(e.headers.get("Retry-After", "1") or "1")
                time.sleep(retry_after)
                continue
            raise NotionError(e.code, err_body)
        except urllib.error.URLError as e:
            # 네트워크 단절 등 일시 오류는 한 번 더 시도, 소진 시 전파.
            if attempt < max_retries:
                time.sleep(1)
                continue
            raise NotionError(0, str(e.reason))


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
            raise NotionError(0, f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


# ── rich_text 변환 ────────────────────────────────────────────

def rich_text_to_plain(rich_text_list):
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def plain_to_rich_text(text):
    """평문 → Notion rich_text 배열 (블록 생성/수정 body 구성용)."""
    return [{"type": "text", "text": {"content": text}}]


# ── 페이지/블록 파싱 ──────────────────────────────────────────

def parse_page(page):
    """
    Notion Task 페이지 → 정규화 dict.
    notion-task.py:_parse_page와 동일 스키마에 sync 비교용 notion_last_edited 추가.
    """
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
    # Description은 Task의 핵심 내용(왜/문제/계획)이 담기는 rich_text property다.
    # 페이지 객체에 함께 실려오므로 추가 API 호출 없이 캐시한다(preview 표시용).
    description = rich_text_to_plain(props.get("Description", {}).get("rich_text", []))
    return {
        "page_id": page["id"],
        "name": name,
        "priority": priority,
        "status": status,
        "due_date": due.get("start", ""),
        "category": category,
        "tags": tags,
        "description": description,
        "notion_last_edited": page.get("last_edited_time", ""),
    }


# Task 페이지 본문에서 매 Task에 자동 삽입되는 안내 callout(noise)을 제외하기 위한 시그니처.
# notion-task.py:cmd_create_task가 모든 신규 Task에 prepend하는 boilerplate다.
_BODY_NOISE_PREFIXES = ("업무 노트 작성하기",)

# 본문 미리보기 캐시 상한: 캐시 비대화 방지. fzf preview는 스크롤되므로
# 핵심 도입부만 보여도 충분하고, 전체는 ctrl-o(Notion 열기)로 본다.
_BODY_PREVIEW_CAP = 2000


def blocks_to_preview_text(blocks):
    """Notion 페이지 자식 블록 → preview용 평문(라이트 마크다운).

    to_do 블록은 preview의 Todo 섹션에서 따로 보여주므로 제외하고,
    신규 Task마다 자동 삽입되는 안내 callout도 noise라 제외한다.
    렌더러는 터미널 표시용이라 인라인 서식 없이 블록 타입별 prefix만 붙인다.
    """
    lines = []

    def _txt(block, key):
        return rich_text_to_plain(block.get(key, {}).get("rich_text", []))

    for b in blocks:
        t = b.get("type", "")
        if t == "to_do":
            continue
        if t == "paragraph":
            lines.append(_txt(b, "paragraph"))
        elif t in ("heading_1", "heading_2", "heading_3"):
            level = int(t[-1])
            text = _txt(b, t)
            if text:
                lines.append(f"{'#' * level} {text}")
        elif t == "bulleted_list_item":
            lines.append(f"• {_txt(b, 'bulleted_list_item')}")
        elif t == "numbered_list_item":
            lines.append(f"- {_txt(b, 'numbered_list_item')}")
        elif t == "quote":
            lines.append(f"> {_txt(b, 'quote')}")
        elif t == "code":
            code = _txt(b, "code")
            if code:
                lines.append(code)
        elif t == "callout":
            text = _txt(b, "callout")
            if any(text.startswith(p) for p in _BODY_NOISE_PREFIXES):
                continue
            if text:
                lines.append(text)
        elif t == "divider":
            lines.append("───")
        elif t == "toggle":
            lines.append(_txt(b, "toggle"))
        # 그 외 블록 타입(image, table 등)은 평문 표현이 어려워 생략한다.

    body = "\n".join(lines).strip()
    if len(body) > _BODY_PREVIEW_CAP:
        body = body[:_BODY_PREVIEW_CAP].rstrip() + "\n… (생략, ctrl-o로 Notion에서 전체 보기)"
    return body


# ── 조회 ──────────────────────────────────────────────────────

def query_active_tasks(token):
    """완료 제외 모든 활성 Task 조회: notion-task.py와 동일 필터/정렬."""
    body = {
        "filter": {"property": "상태", "status": {"does_not_equal": "완료"}},
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)
    return [parse_page(p) for p in resp.get("results", [])]


# 완료 Task는 Notion에 영구 누적되므로, 전부 가져오면 로컬 캐시가 무한히 커지고
# 목록이 완료본으로 도배된다. Due Date 기준 최근 윈도우만 가져와 범위를 제한한다.
#
# Due Date를 기준으로 쓰는 이유: 완료 시점을 직접 기록하는 속성이 DB에 없고,
# last_edited_time은 status 일괄 편집 등으로 쉽게 흔들려(완료 시점과 무관하게
# 최근값으로 바뀜) "최근 완료" 신호로 부적합하다. Due Date는 편집으로 흔들리지
# 않아 안정적이다. 단, Due Date가 없는 완료 Task는 이 조회에 잡히지 않는다.
COMPLETED_WINDOW_DAYS = 14


def query_recent_completed_tasks(token, days=COMPLETED_WINDOW_DAYS):
    """완료 상태 + Due Date가 최근 N일 내인 Task만 조회: Tasks 탭 ALL 뷰 노출용.

    query_active_tasks와 달리 양방향 sync 대상이 아니다(읽기 전용 캐시).
    완료본을 push/충돌 로직에 끌어들이면 의도치 않은 status 되돌림이 생길 수 있어
    의도적으로 활성 Task 캐시와 분리한다.
    """
    cutoff = (datetime.now(KST) - timedelta(days=days)).date().isoformat()
    body = {
        "filter": {
            "and": [
                {"property": "상태", "status": {"equals": "완료"}},
                {"property": "Due Date", "date": {"on_or_after": cutoff}},
            ]
        },
        "sorts": [{"property": "Due Date", "direction": "descending"}],
    }
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, TASK_DB_ID)}/query", body)
    return [parse_page(p) for p in resp.get("results", [])]


def get_all_children(token, block_id):
    """블록(페이지)의 모든 자식 블록을 페이지네이션으로 수집한다."""
    children = []
    cursor = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        resp = notion_request(token, "GET", path)
        children.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return children


# ── 타임스탬프 ────────────────────────────────────────────────

def now_kst():
    """현재 시각을 KST ISO8601(초 단위)로. 로컬 updated_at 기록용."""
    return datetime.now(KST).isoformat(timespec="seconds")


def to_utc(iso_str):
    """
    ISO8601 문자열(KST +09:00 / UTC Z / naive 혼재) → UTC aware datetime.
    로컬(updated_at, +09:00)과 Notion(last_edited_time, Z) 비교를 위한 정규화.
    빈 문자열/None은 None을 반환한다(충돌 판정에서 '정보 없음'으로 취급).
    """
    if not iso_str:
        return None
    s = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
