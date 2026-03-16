#!/usr/bin/env python3
"""
Handoff 컨텍스트 저장/로드/소비 스크립트.

사용법:
  python3 handoff.py save --reason REASON --data PATH
  python3 handoff.py load
  python3 handoff.py consume

출력: JSON
"""

import json
import sys
import argparse
import shutil
from pathlib import Path
from datetime import datetime

TMP_DIR = Path.home() / ".claude" / "tmp"
LATEST = TMP_DIR / "handoff-latest.json"


def save(reason: str, data_path: str) -> None:
    """Handoff 데이터를 저장한다. 기존 pending은 자동 consumed 처리."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # 기존 pending handoff가 있으면 consumed로 변경
    if LATEST.exists():
        try:
            existing = json.loads(LATEST.read_text(encoding="utf-8"))
            if existing.get("status") == "pending":
                existing["status"] = "consumed"
                LATEST.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except (json.JSONDecodeError, KeyError):
            pass

    # 페이로드 읽기
    payload_path = Path(data_path)
    if not payload_path.exists():
        print(json.dumps({"error": f"데이터 파일을 찾을 수 없습니다: {data_path}"}))
        sys.exit(1)

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON 파싱 실패: {e}"}))
        sys.exit(1)

    now = datetime.now().astimezone()
    handoff = {
        "version": 1,
        "timestamp": now.isoformat(),
        "reason": reason,
        "status": "pending",
        "completed": payload.get("completed", []),
        "in_progress": payload.get("in_progress", []),
        "next": payload.get("next", []),
        "notes": payload.get("notes", ""),
    }

    # latest 저장
    LATEST.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 아카이브 복사
    archive_name = f"handoff-{now.strftime('%Y-%m-%d-%H%M')}.json"
    archive_path = TMP_DIR / archive_name
    shutil.copy2(LATEST, archive_path)

    print(json.dumps({
        "ok": True,
        "path": str(LATEST),
        "archive": str(archive_path),
        "handoff": handoff,
    }, ensure_ascii=False, indent=2))


def load() -> None:
    """Pending handoff를 반환한다."""
    if not LATEST.exists():
        print(json.dumps({"ok": False, "error": "저장된 handoff가 없습니다."}))
        sys.exit(0)

    try:
        handoff = json.loads(LATEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(json.dumps({"ok": False, "error": "handoff 파일 파싱 실패"}))
        sys.exit(1)

    if handoff.get("status") != "pending":
        print(json.dumps({"ok": False, "error": "pending 상태의 handoff가 없습니다."}))
        sys.exit(0)

    # 경과 시간 계산
    try:
        saved_at = datetime.fromisoformat(handoff["timestamp"])
        now = datetime.now().astimezone()
        elapsed = now - saved_at
        minutes = int(elapsed.total_seconds() // 60)
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            elapsed_str = f"{hours}시간 {mins}분"
        else:
            elapsed_str = f"{mins}분"
    except (KeyError, ValueError):
        elapsed_str = "알 수 없음"

    print(json.dumps({
        "ok": True,
        "elapsed": elapsed_str,
        "handoff": handoff,
    }, ensure_ascii=False, indent=2))


def consume() -> None:
    """Handoff를 consumed로 변경한다."""
    if not LATEST.exists():
        print(json.dumps({"ok": False, "error": "저장된 handoff가 없습니다."}))
        sys.exit(1)

    try:
        handoff = json.loads(LATEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(json.dumps({"ok": False, "error": "handoff 파일 파싱 실패"}))
        sys.exit(1)

    handoff["status"] = "consumed"
    handoff["consumed_at"] = datetime.now().astimezone().isoformat()

    LATEST.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps({"ok": True, "status": "consumed"}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Handoff 컨텍스트 관리")
    sub = parser.add_subparsers(dest="command", required=True)

    save_p = sub.add_parser("save", help="Handoff 저장")
    save_p.add_argument("--reason", required=True, help="자리 비움 사유")
    save_p.add_argument("--data", required=True, help="페이로드 JSON 파일 경로")

    sub.add_parser("load", help="Pending handoff 로드")
    sub.add_parser("consume", help="Handoff를 consumed로 변경")

    args = parser.parse_args()

    if args.command == "save":
        save(args.reason, args.data)
    elif args.command == "load":
        load()
    elif args.command == "consume":
        consume()


if __name__ == "__main__":
    main()
