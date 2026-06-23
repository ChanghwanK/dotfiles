#!/usr/bin/env python3
"""alfred-nudge-state.json 읽기/쓰기 헬퍼 — 알림 피로(nagging) 방지 엔진.

Alfred가 매 브리핑에서 같은 넛지(후속 액션 리마인드·미분류 K건 등)를 똑같이
반복하면 무뎌진다. 이 헬퍼는 넛지별로 "몇 번/며칠째 노출됐는지"를 추적해,
경과일수에 따라 문구를 강화("N일째")하거나 정리를 권하도록 돕는다.

스키마:
  { "<nudge-id>": { "first_shown": ISO8601, "last_shown": ISO8601, "shown_count": int } }

nudge-id 예:
  - 후속 액션:  todo id (예: "todo-abc123")
  - 미분류 넛지: "unclassified"

Usage:
  alfred-nudge-state.py bump  --id <id>   # 노출 1회 기록(없으면 생성), 누적치 반환
  alfred-nudge-state.py get   --id <id>   # 현재 상태 조회(없으면 exists:false)
  alfred-nudge-state.py clear --id <id>   # 해소 시 제거
  alfred-nudge-state.py prune --max-age-days N  # last_shown 이 N일 초과한 키 정리
"""
import argparse
import datetime
import json
import os
import tempfile

STATE_PATH = os.path.expanduser("~/.claude/alfred-nudge-state.json")


def _now():
    return datetime.datetime.now().astimezone()


def _load(path):
    """상태 로드. 없거나 깨졌으면 빈 dict 반환(읽기 측 비파괴)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _atomic_write(path, data):
    """temp 파일 → rename 으로 원자적 저장."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".alfred-nudge.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _days_since(iso_str):
    """iso_str 로부터 경과한 '전체 일수'(floor). 파싱 실패 시 0."""
    if not iso_str:
        return 0
    try:
        ts = datetime.datetime.fromisoformat(iso_str)
    except ValueError:
        return 0
    return max(0, (_now() - ts).days)


def cmd_bump(args):
    state = _load(STATE_PATH)
    now_iso = _now().isoformat()
    entry = state.get(args.id)
    if not isinstance(entry, dict):
        entry = {"first_shown": now_iso, "last_shown": now_iso, "shown_count": 0}
    entry["shown_count"] = int(entry.get("shown_count", 0)) + 1
    entry["last_shown"] = now_iso
    entry.setdefault("first_shown", now_iso)
    state[args.id] = entry
    _atomic_write(STATE_PATH, state)
    print(json.dumps({
        "id": args.id,
        "shown_count": entry["shown_count"],
        "first_shown": entry["first_shown"],
        "last_shown": entry["last_shown"],
        "days_since_first": _days_since(entry["first_shown"]),
    }, ensure_ascii=False, indent=2))


def cmd_get(args):
    entry = _load(STATE_PATH).get(args.id)
    if not isinstance(entry, dict):
        print(json.dumps({"id": args.id, "exists": False}, ensure_ascii=False))
        return
    print(json.dumps({
        "id": args.id,
        "exists": True,
        "shown_count": int(entry.get("shown_count", 0)),
        "first_shown": entry.get("first_shown", ""),
        "last_shown": entry.get("last_shown", ""),
        "days_since_first": _days_since(entry.get("first_shown", "")),
    }, ensure_ascii=False, indent=2))


def cmd_clear(args):
    state = _load(STATE_PATH)
    existed = args.id in state
    if existed:
        del state[args.id]
        _atomic_write(STATE_PATH, state)
    print(json.dumps({"id": args.id, "cleared": existed}, ensure_ascii=False))


def cmd_prune(args):
    state = _load(STATE_PATH)
    removed = [k for k, v in state.items()
               if not isinstance(v, dict) or _days_since(v.get("last_shown", "")) > args.max_age_days]
    for k in removed:
        del state[k]
    if removed:
        _atomic_write(STATE_PATH, state)
    print(json.dumps({"pruned": len(removed), "remaining": len(state)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="alfred-nudge-state.json 헬퍼 (알림 피로 방지)")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("bump", help="넛지 노출 1회 기록")
    b.add_argument("--id", required=True)

    g = sub.add_parser("get", help="넛지 상태 조회")
    g.add_argument("--id", required=True)

    c = sub.add_parser("clear", help="넛지 제거(해소 시)")
    c.add_argument("--id", required=True)

    p = sub.add_parser("prune", help="오래된 넛지 일괄 정리")
    p.add_argument("--max-age-days", type=int, default=30)

    args = parser.parse_args()
    {"bump": cmd_bump, "get": cmd_get, "clear": cmd_clear, "prune": cmd_prune}[args.command](args)


if __name__ == "__main__":
    main()
