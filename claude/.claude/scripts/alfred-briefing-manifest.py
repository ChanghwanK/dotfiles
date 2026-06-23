#!/usr/bin/env python3
"""alfred-briefing-latest.json 생성 — 브리핑 ↔ resume 픽업을 잇는 다리.

브리핑은 Slack 평문으로 끝나서, 나중에 "그 작업을 골라 새 세션을 열기"가 불가능했다.
이 스크립트는 브리핑이 띄운 우선순위 Task에 결정론적 번호(n)를 매기고, 각 Task에
하위 Todo와 작업 디렉터리 단서(repo)를 join해 매니페스트로 남긴다. resume picker는
이 파일을 읽어 동일한 번호로 작업을 고르고, repo로 세션을 띄운다.

번호·정렬·repo 해석을 LLM이 즉흥 생성하지 않도록 alfred-snapshot.py와 같은
결정론적 스크립트로 분리한다 (브리핑 본문의 번호와 picker 번호가 항상 일치해야 함).

스키마:
  {
    "generated_at": ISO8601(local tz),
    "items": [
      { "n": 1, "page_id", "name", "category", "priority", "roi", "due_date",
        "repo": "<repo>|null",
        "todos": [ { "id", "title", "done" }, ... ] },
      ...
    ]
  }

정렬(브리핑과 동일): ROI desc(High>Medium>Low>없음) → Priority asc(P1>P4) → due 임박 순.
repo: 그 Task의 todos 중 repo 필드가 채워진 첫 값(없으면 null).

Usage:
  alfred-briefing-manifest.py build --active-json <path|-> [--todos-json <path|->] [--top N]
      매니페스트를 생성해 ~/.claude/alfred-briefing-latest.json 에 원자적 저장 + stdout echo.
  alfred-briefing-manifest.py get
      현재 저장된 매니페스트를 그대로 출력(디버그용).

입력 JSON 허용 형태(유연 파싱):
  active: [ ... ] | {"results":[...]} | {"active":[...]} | {"tasks":[...]}
  todos:  [ ... ] | {"todos":[...]}
"""
import argparse
import datetime
import json
import os
import sys
import tempfile

STATE_PATH = os.path.expanduser("~/.claude/alfred-briefing-latest.json")

DEFAULT_TOP = 7

# 정렬 랭크 — 작을수록 위로(ascending sort). 브리핑 합성 규칙과 동일하게 유지한다.
_ROI_RANK = {"High": 0, "Medium": 1, "Low": 2, "": 3}
_FAR_DUE = "9999-12-31"  # due 없는 항목을 맨 뒤로

# 매니페스트 Task 항목에 보관할 필드(picker·launcher가 쓰는 최소 집합)
_TASK_FIELDS = ("page_id", "name", "category", "priority", "roi", "due_date")


def _load(path):
    """매니페스트 로드. 없거나 깨졌으면 빈 구조 반환(읽기 측 비파괴)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"generated_at": "", "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"generated_at": "", "items": []}
    return data


def _atomic_write(path, data):
    """temp 파일 → rename 으로 원자적 저장(부분 쓰기 방지)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".alfred-briefing.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _read_json_arg(value):
    """'-' 면 stdin, 아니면 파일 경로에서 JSON 로드."""
    if value == "-":
        return json.load(sys.stdin)
    with open(value, encoding="utf-8") as f:
        return json.load(f)


def _extract_tasks(blob):
    """search-tasks 등 다양한 출력 형태에서 Task 리스트를 추출한다."""
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        for key in ("results", "active", "tasks"):
            if isinstance(blob.get(key), list):
                return blob[key]
    return []


def _extract_todos(blob):
    """list-all-todos 등에서 Todo 리스트를 추출한다."""
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict) and isinstance(blob.get("todos"), list):
        return blob["todos"]
    return []


def _priority_rank(priority):
    """'P1' → 1 … 'P4' → 4. 비정형/없음은 맨 뒤(99)."""
    p = (priority or "").strip().upper()
    if p.startswith("P") and p[1:].isdigit():
        return int(p[1:])
    return 99


def _sort_key(task):
    roi = _ROI_RANK.get(task.get("roi", ""), 3)
    prio = _priority_rank(task.get("priority"))
    due = task.get("due_date") or _FAR_DUE
    return (roi, prio, due)


def _todos_by_task(todos):
    """task_page_id → 그 Task의 활성 Todo 리스트(완료 제외, 원래 순서 유지)."""
    out = {}
    for t in todos:
        if t.get("deleted"):
            continue
        pid = t.get("task_page_id")
        if not pid:
            continue
        out.setdefault(pid, []).append(t)
    return out


def _resolve_repo(task_todos):
    """그 Task의 todos 중 repo 필드가 채워진 첫 값. 없으면 None."""
    for t in task_todos:
        repo = t.get("repo")
        if repo:
            return repo
    return None


def _build_items(tasks, todos, top):
    grouped = _todos_by_task(todos)
    ordered = sorted(tasks, key=_sort_key)[:top]

    items = []
    for i, task in enumerate(ordered, start=1):
        pid = task.get("page_id")
        task_todos = grouped.get(pid, [])
        item = {"n": i}
        item.update({k: task.get(k, "") for k in _TASK_FIELDS})
        item["repo"] = _resolve_repo(task_todos)
        item["todos"] = [
            {"id": t.get("id", ""), "title": t.get("title", ""), "done": bool(t.get("done"))}
            for t in task_todos
            if not t.get("done")
        ]
        items.append(item)
    return items


def cmd_build(args):
    tasks = _extract_tasks(_read_json_arg(args.active_json))
    todos = _extract_todos(_read_json_arg(args.todos_json)) if args.todos_json else []

    manifest = {
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "items": _build_items(tasks, todos, args.top),
    }
    _atomic_write(STATE_PATH, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def cmd_get(args):
    print(json.dumps(_load(STATE_PATH), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="alfred-briefing-latest.json 생성 (브리핑→resume 다리)")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="active Task + todos를 join해 매니페스트 생성")
    b.add_argument("--active-json", required=True,
                   help="search-tasks --status active 출력 (path 또는 '-')")
    b.add_argument("--todos-json", default="",
                   help="todo_store list-all-todos 출력 (path 또는 '-')")
    b.add_argument("--top", type=int, default=DEFAULT_TOP,
                   help=f"매니페스트에 담을 상위 Task 수 (기본 {DEFAULT_TOP})")

    sub.add_parser("get", help="현재 저장된 매니페스트 출력")

    args = parser.parse_args()
    if args.command == "build":
        cmd_build(args)
    elif args.command == "get":
        cmd_get(args)


if __name__ == "__main__":
    main()
