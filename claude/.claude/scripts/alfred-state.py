#!/usr/bin/env python3
"""alfred-state.json 읽기/쓰기 헬퍼.

state 파일은 alfred check 모드가 "최근 작업한 Task"를 교차 검증 기준으로 쓴다.
이전에는 current_task 1건만 추적해, 하루에 여러 Task를 오가면 마지막 1건만 남았다.
이 헬퍼는 recent_tasks 배열(최신순, 최대 N건)을 관리하되,
기존 reader(session-start hook, SKILL)가 읽던 current_task 를 항상 함께 미러링해
**하위호환을 유지**한다.

스키마:
  {
    "current_task": { page_id, name, priority, source, started_at },  # = recent_tasks[0] 미러
    "recent_tasks": [ { page_id, name, priority, source, started_at }, ... ]  # 최신순, 최대 MAX_RECENT
  }

Usage:
  alfred-state.py record --page-id <id> --name "<name>" [--priority "<p>"] [--source tui|gate|week|task]
  alfred-state.py get [--max-age-hours 8]   # TTL 이내 항목만 반환 (없으면 빈 결과)
"""
import argparse
import datetime
import json
import os
import sys
import tempfile

STATE_PATH = os.path.expanduser("~/.claude/alfred-state.json")
MAX_RECENT = 5  # 하루 작업 전환을 커버하기에 충분, state 파일 비대화 방지


def _load(path):
    """state 파일 로드. 없거나 깨졌으면 빈 구조를 반환(읽기 측을 깨뜨리지 않음)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"current_task": {}, "recent_tasks": []}
    if not isinstance(data, dict):
        return {"current_task": {}, "recent_tasks": []}
    # 구 스키마(현 current_task만 있음) → recent_tasks로 승격
    if "recent_tasks" not in data:
        ct = data.get("current_task") or {}
        data["recent_tasks"] = [ct] if ct.get("page_id") else []
    return data


def upsert_recent(state, task, max_recent=MAX_RECENT):
    """task 를 recent_tasks 맨 앞으로 올린다(page_id 기준 dedup, cap). 순수 함수.
    current_task 미러도 갱신해 반환한다."""
    recent = [t for t in state.get("recent_tasks", []) if t.get("page_id") != task.get("page_id")]
    recent.insert(0, task)
    recent = recent[:max_recent]
    return {"current_task": dict(task), "recent_tasks": recent}


def _atomic_write(path, data):
    """temp 파일 → rename 으로 원자적 저장. 매 세션 읽는 hook이 부분 쓰기를 읽지 않도록."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".alfred-state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _within_ttl(task, max_age_hours):
    started = task.get("started_at", "")
    if not started:
        return False
    try:
        ts = datetime.datetime.fromisoformat(started)
    except ValueError:
        return False
    elapsed = (datetime.datetime.now().astimezone() - ts).total_seconds() / 3600
    return elapsed <= max_age_hours


def cmd_record(args):
    task = {
        "page_id": args.page_id,
        "name": args.name,
        "priority": args.priority or "",
        "source": args.source or "",
        "started_at": datetime.datetime.now().astimezone().isoformat(),
    }
    state = upsert_recent(_load(STATE_PATH), task)
    _atomic_write(STATE_PATH, state)
    print(json.dumps({"success": True, "recent_count": len(state["recent_tasks"])}, ensure_ascii=False))


def cmd_get(args):
    state = _load(STATE_PATH)
    fresh = [t for t in state.get("recent_tasks", []) if _within_ttl(t, args.max_age_hours)]
    print(json.dumps({
        "current_task": fresh[0] if fresh else {},
        "recent_tasks": fresh,
        "max_age_hours": args.max_age_hours,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="alfred-state.json 헬퍼")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record", help="Task 를 recent_tasks 맨 앞에 기록(dedup·cap)")
    rec.add_argument("--page-id", required=True)
    rec.add_argument("--name", required=True)
    rec.add_argument("--priority", default="")
    rec.add_argument("--source", default="")

    g = sub.add_parser("get", help="TTL 이내 recent_tasks 반환")
    g.add_argument("--max-age-hours", type=float, default=8)

    args = parser.parse_args()
    if args.command == "record":
        cmd_record(args)
    elif args.command == "get":
        cmd_get(args)


if __name__ == "__main__":
    main()
