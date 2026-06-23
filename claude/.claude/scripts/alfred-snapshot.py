#!/usr/bin/env python3
"""alfred-snapshot.json 읽기/쓰기 헬퍼 — 브리핑 간 "완료 보고" 엔진.

Notion Task DB에는 completed_at 속성이 없어 "지난 브리핑 이후 무엇이 끝났는가"를
타임스탬프로 질의할 수 없다. 그래서 매 아침 브리핑마다 활성 Task의 스냅샷을 남기고,
다음 브리핑에서 직전 스냅샷과 차분(diff)하여 완료/종료/신규를 결정론적으로 가려낸다.

스키마:
  {
    "taken_at": ISO8601(local tz),
    "active": [ { page_id, name, priority, roi, due_date, status }, ... ]
  }

차분 규칙(page_id 기준):
  completed     = 직전 active ∩ 현재 completed   (확실한 완료)
  closed_unknown= 직전 active − 현재 active − 현재 completed  (아카이브·이동·삭제 추정)
  newly_added   = 현재 active − 직전 active

Usage:
  alfred-snapshot.py update --active-json <path|-> [--completed-json <path|->]
      직전 스냅샷과 차분 결과를 stdout(JSON)으로 내고, 현재 active로 스냅샷을 갱신한다.
  alfred-snapshot.py get
      현재 저장된 스냅샷을 그대로 출력(디버그용).

입력 JSON은 아래 형태를 모두 허용한다(유연 파싱):
  - 리스트:            [ {page_id,...}, ... ]
  - search-tasks 형태: { "results": [ ... ] }
  - tasks 형태:        { "tasks": { "completed": [ ... ], ... } }  (--completed-json 전용)
"""
import argparse
import datetime
import json
import os
import sys
import tempfile

STATE_PATH = os.path.expanduser("~/.claude/alfred-snapshot.json")

# 스냅샷에 보관할 필드(완료 보고 렌더에 필요한 최소 집합)
_KEEP_FIELDS = ("page_id", "name", "priority", "roi", "due_date", "status")


def _load(path):
    """스냅샷 로드. 없거나 깨졌으면 빈 구조 반환(읽기 측 비파괴)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"taken_at": "", "active": []}
    if not isinstance(data, dict) or not isinstance(data.get("active"), list):
        return {"taken_at": "", "active": []}
    return data


def _atomic_write(path, data):
    """temp 파일 → rename 으로 원자적 저장(부분 쓰기 방지)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".alfred-snapshot.", suffix=".tmp")
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


def _extract_items(blob, bucket=None):
    """다양한 출력 형태에서 Task 항목 리스트를 추출한다.

    bucket 이 주어지면 {"tasks": {bucket: [...]}} 우선 추출(완료 버킷 등).
    """
    if blob is None:
        return []
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        if bucket and isinstance(blob.get("tasks"), dict):
            return blob["tasks"].get(bucket) or []
        if isinstance(blob.get("results"), list):
            return blob["results"]
        if isinstance(blob.get("active"), list):
            return blob["active"]
        if isinstance(blob.get("tasks"), list):
            return blob["tasks"]
    return []


def _slim(item):
    """스냅샷·차분 출력용으로 필요한 필드만 남긴다."""
    return {k: item.get(k, "") for k in _KEEP_FIELDS}


def _index_by_id(items):
    """page_id → slim item. page_id 없는 항목은 무시(차분 키가 없으면 추적 불가)."""
    out = {}
    for it in items:
        pid = it.get("page_id")
        if pid:
            out[pid] = _slim(it)
    return out


def cmd_update(args):
    prev = _load(STATE_PATH)
    prev_active = _index_by_id(prev.get("active", []))

    cur_active = _index_by_id(_extract_items(_read_json_arg(args.active_json)))

    cur_completed = {}
    if args.completed_json:
        cur_completed = _index_by_id(
            _extract_items(_read_json_arg(args.completed_json), bucket="completed")
        )

    first_run = not prev.get("taken_at") and not prev_active

    prev_ids = set(prev_active)
    cur_ids = set(cur_active)
    completed_ids = set(cur_completed)

    completed = [cur_completed.get(pid) or prev_active[pid]
                 for pid in (prev_ids & completed_ids)]
    closed_unknown = [prev_active[pid]
                      for pid in (prev_ids - cur_ids - completed_ids)]
    newly_added = [cur_active[pid] for pid in (cur_ids - prev_ids)]

    result = {
        "first_run": first_run,
        "prev_taken_at": prev.get("taken_at", ""),
        "completed": completed,
        "closed_unknown": closed_unknown,
        "newly_added": newly_added,
        "active_count": len(cur_active),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    _atomic_write(STATE_PATH, {
        "taken_at": datetime.datetime.now().astimezone().isoformat(),
        "active": list(cur_active.values()),
    })


def cmd_get(args):
    print(json.dumps(_load(STATE_PATH), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="alfred-snapshot.json 헬퍼 (완료 보고 차분)")
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("update", help="직전 스냅샷과 차분 후 현재 active로 갱신")
    up.add_argument("--active-json", required=True,
                    help="search-tasks --status active 출력 (path 또는 '-')")
    up.add_argument("--completed-json", default="",
                    help="tasks --week current --status all 출력 (path 또는 '-'), 완료 확정용")

    sub.add_parser("get", help="현재 저장된 스냅샷 출력")

    args = parser.parse_args()
    if args.command == "update":
        cmd_update(args)
    elif args.command == "get":
        cmd_get(args)


if __name__ == "__main__":
    main()
