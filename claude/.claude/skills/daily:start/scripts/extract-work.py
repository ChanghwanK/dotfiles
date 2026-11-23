#!/usr/bin/env python3
"""
지정한 날짜에 작업한 Claude 세션들의 transcript를 읽어
세션별 작업 사실(무엇을 물었고, 어디서 멈췄는지)을 추출하는 스크립트.

사용법:
  python3 extract-work.py [--date YYYY-MM-DD]

출력: JSON
  {
    "date": "2026-02-26",
    "sessions": [
      {
        "project": "riiid-kubernetes",
        "file": "...",
        "user_messages": ["메시지1", "메시지2"],
        "session_id": "<jsonl 파일명>",
        "title": "<Claude Code가 붙인 세션 제목 | null>",
        "cwd": "<세션 작업 디렉터리 | null>",
        "started_at": "<첫 엔트리 시각, KST ISO8601(+09:00) | null>",
        "ended_at": "<마지막 엔트리 시각, KST ISO8601(+09:00) | null>",
        "message_count": <의미 있는 사용자 메시지 수>,
        "last_assistant": "<마지막 assistant 텍스트 앞 300자 | null>"
      }
    ]
  }

project, file, user_messages는 handoff:pause, tasks:ing-listup이 기대하는 기존 필드다.
이름이나 의미를 바꾸지 않는다. 새 필드는 뒤에 덧붙이기만 한다.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo

PROJECTS_DIR = Path.home() / ".claude" / "projects"

# transcript timestamp는 UTC(Z)다. 읽는 사람이 KST로 판단하므로 출력은 KST로 바꾼다
DISPLAY_TZ = ZoneInfo("Asia/Seoul")

MESSAGE_EXCERPT_CHARS = 300

# 필터링할 짧거나 무의미한 패턴
SKIP_PATTERNS = [
    "y", "n", "yes", "no", "ok", "ㅇㅇ", "응", "네", "아니",
]

# 사용자가 직접 쓰지 않은 메시지(하네스 주입, 스킬 본문, 자동 제목 생성 요청) 스킵
SKIP_SUBSTRINGS = [
    "<system-reminder>",
    "<command-message>",
    "<local-command-",
    "Base directory for this skill",
    "UserPromptSubmit hook",
    "SessionStart",
    "[Request interrupted",
    "Caveat: The messages below",
    # 세션 제목 자동 생성 요청. 세션마다 하나씩 생겨 작업 목록을 부풀린다
    "Name this chat from the user's first request",
]


# 프로젝트 디렉토리명 → 사람이 읽을 수 있는 이름
def parse_project_name(dir_name: str) -> str:
    # -Users-changhwan-workspace-riiid-kubernetes → riiid-kubernetes
    # -Users-changhwan--claude → .claude (home)
    name = dir_name
    for prefix in [
        "-Users-changhwan-workspace-",
        "-Users-changhwan--",
        "-Users-changhwan-",
    ]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name or dir_name


def is_meaningful_message(text: str) -> bool:
    """사용자가 직접 쓴 의미 있는 메시지인지 판별"""
    stripped = text.strip()

    if len(stripped) < 5:
        return False

    if stripped.lower() in SKIP_PATTERNS:
        return False

    for sub in SKIP_SUBSTRINGS:
        if sub in stripped:
            return False

    return True


def message_texts(entry: dict) -> list[str]:
    """user/assistant 엔트리에서 text 블록만 꺼낸다 (tool_use, tool_result 제외)"""
    content = entry.get("message", {}).get("content", "")
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [
            c.get("text", "")
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        ]
    return []


def to_display_time(ts: str | None) -> str | None:
    """UTC ISO8601 문자열을 KST ISO8601로 바꾼다. 해석할 수 없으면 원문을 둔다"""
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts
    return parsed.astimezone(DISPLAY_TZ).isoformat(timespec="seconds")


def summarize_session(jsonl_path: Path) -> dict:
    """transcript 한 개를 한 번 읽어 세션 사실을 모은다"""
    user_messages: list[str] = []
    title = None
    cwd = None
    first_ts = None
    last_ts = None
    last_assistant = None

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type")

                if entry_type == "ai-title" and entry.get("aiTitle"):
                    title = entry["aiTitle"]
                    continue

                if entry_type not in ("user", "assistant"):
                    continue

                ts = entry.get("timestamp")
                if ts:
                    first_ts = first_ts or ts
                    last_ts = ts
                if not cwd and entry.get("cwd"):
                    cwd = entry["cwd"]

                # 서브에이전트 대화는 사용자가 한 작업이 아니다
                if entry.get("isSidechain"):
                    continue

                texts = message_texts(entry)
                if entry_type == "user":
                    for text in texts:
                        if is_meaningful_message(text):
                            user_messages.append(text[:MESSAGE_EXCERPT_CHARS].strip())
                else:
                    joined = "\n".join(t for t in texts if t.strip())
                    if joined:
                        last_assistant = joined[:MESSAGE_EXCERPT_CHARS].strip()
    except Exception as e:
        sys.stderr.write(f"warn: failed to read {jsonl_path}: {e}\n")

    return {
        "user_messages": user_messages,
        "session_id": jsonl_path.stem,
        "title": title,
        "cwd": cwd,
        "started_at": to_display_time(first_ts),
        "ended_at": to_display_time(last_ts),
        "message_count": len(user_messages),
        "last_assistant": last_assistant,
    }


def get_file_date(path: Path) -> date | None:
    # glob 이후 파일이 삭제되는 race(worktree 정리 등)로 stat이 실패할 수 있다.
    # 2026-06-22, 2026-07-03 두 차례 FileNotFoundError로 전체 실행이 죽은 재발 이슈.
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(mtime).date()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="today",
                        help="날짜 (today 또는 YYYY-MM-DD)")
    args = parser.parse_args()

    if args.date == "today":
        target_date = date.today()
    else:
        target_date = date.fromisoformat(args.date)

    sessions = []

    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        # mem-observer 제외
        dir_name = project_dir.name
        if "mem-observer" in dir_name:
            continue

        project_name = parse_project_name(dir_name)

        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            # 해당 날짜에 수정된 파일만 (None = 삭제된 파일, skip)
            if get_file_date(jsonl_file) != target_date:
                continue

            summary = summarize_session(jsonl_file)
            if not summary["user_messages"]:
                continue

            sessions.append({
                "project": project_name,
                "file": str(jsonl_file),
                **summary,
            })

    sessions.sort(key=lambda s: s["started_at"] or "")

    result = {
        "date": target_date.isoformat(),
        "sessions": sessions,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
