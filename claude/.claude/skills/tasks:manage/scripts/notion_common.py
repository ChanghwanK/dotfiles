#!/usr/bin/env python3
"""
Notion 공통 헬퍼 — tasktui(todo_store/todo_sync)와 향후 notion-task.py 공유용.

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
NOTION_VERSION = "2022-06-28"
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

VALID_STATUSES = {"시작 전", "진행 중", "완료", "대기"}
PRIORITY_OPTIONS = {
    "P1 - Must Have",
    "P2 - Should Have",
    "P3 - Could Have",
    "P4 - Won't Have",
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
    return {
        "page_id": page["id"],
        "name": name,
        "priority": priority,
        "status": status,
        "due_date": due.get("start", ""),
        "category": category,
        "tags": tags,
        "notion_last_edited": page.get("last_edited_time", ""),
    }


# ── 조회 ──────────────────────────────────────────────────────

def query_active_tasks(token):
    """완료 제외 모든 활성 Task 조회 — notion-task.py와 동일 필터/정렬."""
    body = {
        "filter": {"property": "상태", "status": {"does_not_equal": "완료"}},
        "sorts": [{"property": "Priority", "direction": "ascending"}],
    }
    resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)
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
