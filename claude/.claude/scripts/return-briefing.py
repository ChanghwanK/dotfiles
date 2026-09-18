#!/usr/bin/env python3
"""
복귀 감지 재브리핑 훅 (Stop + UserPromptSubmit 공용).

가설: 세션 흐름 유실의 원인은 상태 정보 부재가 아니라 "복귀 순간에 상태를 다시
조립하는 절차 부재"다. 상태는 세션 컨텍스트에 이미 있으므로, 복귀 시점에 Claude가
그것을 4줄로 먼저 꺼내 놓기만 하면 유실이 사라진다. (2026-09-09 실험 시작, 2주 판정)

동작:
  stop   : 세션별 마지막 턴 종료 시각을 기록한다.
  prompt : 직전 턴 종료로부터 임계값(기본 15분) 이상 비었으면 재브리핑 지시를
           additionalContext로 주입하고, 판정 지표용 이벤트를 로그에 남긴다.
           프롬프트에 "놓침"이 있으면 직전 재브리핑이 실패했다는 표시(miss)를 로그한다.

설계 불변식:
  - 어떤 입력·예외에서도 종료코드는 0이다. UserPromptSubmit hook의 exit 2는 입력을
    차단하므로 훅 버그가 사용자의 입력을 막아서는 안 된다.
  - 세션 상태 파일은 이 스크립트가 만들지 않은 세션(첫 프롬프트)에는 존재하지 않으므로
    첫 프롬프트에서는 조용히 no-op이다.
  - 재브리핑은 Claude가 자기 컨텍스트에서 생성한다. 이 훅은 타임스탬프와 지시문만
    다루며 세션 내용은 저장하지 않는다.

환경변수:
  RETURN_BRIEF_IDLE_MIN : 임계값(분). 기본 15.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "tmp" / "session-activity"
EVENT_LOG = Path.home() / ".claude" / "tmp" / "return-briefing-log.jsonl"
DEFAULT_IDLE_MIN = 15

# 사용자가 "짧게 다녀왔다"고 명시하면 재브리핑을 억제한다 (노이즈 통제).
_SKIP = re.compile(r"^\s*(짧게|잠깐|바로|계속)")
# 재브리핑을 받고도 흐름을 못 잡았다는 사용자 신호. 판정 지표 1의 분자.
_MISS = re.compile(r"놓침")

_BRIEF_INSTRUCTION = """[return-briefing] 이 세션은 마지막 턴 종료 후 {idle_min}분 동안 비어 있었습니다. 사용자가 다른 작업을 하다 돌아온 것으로 간주합니다.
사용자의 프롬프트에 답하기 **전에**, 아래 4줄을 먼저 출력하십시오 (각 1줄, 굵은 라벨, 이 세션 컨텍스트 기준):
- **목표**: 이 세션이 끝내려는 것
- **지금 단계**: 어디까지 왔고 무엇을 하던 중이었는지
- **마지막 결정**: 직전에 확정된 판단 (없으면 "없음")
- **지금 필요한 것**: 사용자 답이 필요한 열린 질문 (없으면 "없음, 이어서 진행")
그 다음 구분선 없이 바로 프롬프트에 답하십시오. 컨텍스트가 압축되어 확신이 낮은 항목은 "(요약본 기준)"을 붙이십시오.
"놓침이라고 말해 주세요" 같은 안내 문구는 덧붙이지 마십시오 (사용자는 이미 알고 있습니다)."""


def _now() -> float:
    return time.time()


def _state_path(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)
    return STATE_DIR / f"{safe}.json"


def _log(event: dict) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = _now()
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def on_stop(payload: dict) -> None:
    session_id = payload.get("session_id") or ""
    if not session_id:
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"last_turn_end": _now(), "cwd": payload.get("cwd", "")}
    _state_path(session_id).write_text(json.dumps(state), encoding="utf-8")


def on_prompt(payload: dict) -> None:
    session_id = payload.get("session_id") or ""
    prompt = payload.get("prompt") or ""
    if not session_id:
        return

    path = _state_path(session_id)
    if not path.exists():
        return  # 세션의 첫 프롬프트: 복귀가 아니다.

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        last_end = float(state.get("last_turn_end", 0))
    except (ValueError, OSError):
        return

    if _MISS.search(prompt):
        _log({"event": "miss", "session_id": session_id, "cwd": payload.get("cwd", "")})

    idle_min = (_now() - last_end) / 60.0
    threshold = float(os.environ.get("RETURN_BRIEF_IDLE_MIN", DEFAULT_IDLE_MIN))
    if idle_min < threshold:
        return

    if _SKIP.match(prompt):
        _log({"event": "return_skipped", "session_id": session_id,
              "idle_min": round(idle_min, 1), "cwd": payload.get("cwd", "")})
        return

    _log({"event": "return_briefed", "session_id": session_id,
          "idle_min": round(idle_min, 1), "cwd": payload.get("cwd", "")})
    print(_BRIEF_INSTRUCTION.format(idle_min=int(idle_min)))


def report() -> None:
    """판정 지표 1 요약: 복귀(재브리핑) 대비 놓침 비율. 2주 뒤 가설 판정에 사용한다."""
    if not EVENT_LOG.exists():
        print("no events yet")
        return
    briefed = skipped = miss = 0
    for line in EVENT_LOG.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line).get("event")
        except ValueError:
            continue
        briefed += ev == "return_briefed"
        skipped += ev == "return_skipped"
        miss += ev == "miss"
    ratio = f"{miss / briefed:.0%}" if briefed else "n/a"
    print(f"return_briefed={briefed} return_skipped={skipped} miss={miss} miss_ratio={ratio}")


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "report":
        report()
        return
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if action == "stop":
        on_stop(payload)
    elif action == "prompt":
        on_prompt(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
