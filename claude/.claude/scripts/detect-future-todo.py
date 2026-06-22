#!/usr/bin/env python3
"""
UserPromptSubmit hook — 미래 작업 의도 감지기.

사용자 프롬프트에 "내일 X 할 예정"처럼 미래 시점·작업 의도 표현이 묻어나오면,
Claude 컨텍스트에 "본 작업 후 로컬 Todo 등록을 제안하라"는 신호(additionalContext)를
주입한다. 등록 자체는 하지 않는다 — 진짜 할 일인지 의미 판단과 사용자 동의는
Claude 응답 흐름에 위임한다(정규식 오탐으로 Backlog가 오염되지 않게).

설계 불변식:
  - 어떤 입력·예외에서도 종료코드는 항상 0이다. UserPromptSubmit hook의 exit 2는
    프롬프트 제출을 차단하므로, 감지기 버그가 사용자의 입력을 막는 일이 절대 없어야
    한다(방어적 exit 0). 그래서 main 전체를 try/except로 감싼다.
  - stdout에 텍스트를 쓰면 그대로 Claude 컨텍스트에 주입되고 사용자 화면에는
    노출되지 않는다. 따라서 매칭이 없으면 아무것도 출력하지 않는다(no-op).
"""
import json
import re
import sys

# 미래 시점 표현 — "지금이 아니라 나중에"라는 신호.
_WHEN = re.compile(
    r"내일|모레|글피|다음\s?주|담주|이번\s?주|다음\s?달|이따|나중에|"
    r"\btomorrow\b|\blater\b",
    re.IGNORECASE,
)

# 명시적 작업 의도 표현 — 시점이 없어도 "할 일"임을 드러낸다.
_INTENT = re.compile(
    r"할\s?예정|하기로|해야\s?(겠|지|할|하)|할게|할\s?거(야|에요|예요|임)?|"
    r"잊지\s?말|까먹지\s?말|\bTODO\b",
    re.IGNORECASE,
)

# 가벼운 negative guard — 시점 표현이 가정·조건·바람과 함께 오면(예: "내일 배포
# 안 터지면 좋겠다") 할 일이 아닐 가능성이 높다. 1차에서 거르되, 명시적 의도가
# 같이 있으면 유지하고 경계 사례의 최종 판단은 Claude가 한다.
_NON_TASK = re.compile(r"안\s?(터지|되|돼|망가|죽)|(으)?면\s?좋|었으면|(으)?면\s?안")

_HINT = """[future-todo-hint] 사용자의 직전 프롬프트에 미래 작업 의도로 보이는 표현이 감지되었습니다(예: "내일", "할 예정", "나중에").
본 작업 처리를 모두 마친 뒤, 응답 맨 끝에 한 줄로 이 할 일을 로컬 Todo(Backlog)로 등록할지 제안하세요.

판단 지침:
- 단순 가정·조건·바람·과거 회상이면 제안하지 말고 무시하세요(예: "내일 안 터지면 좋겠다", "어제 한 작업").
- 진짜 미래에 해야 할 일일 때만 간결히 제안하세요(과하게 묻지 말 것).
- 사용자가 동의하면 아래로 등록하세요. 동일 항목이 이미 있으면 중복 등록하지 마세요:
    python3 ~/.claude/skills/tasks:manage/scripts/todo_store.py add \\
      --task __backlog__ --title "<핵심 할 일 한 줄>" [--due <YYYY-MM-DD>] [--repo <repo-label>]
- due 파싱(KST, Asia/Seoul): "내일"=오늘+1, "모레"=오늘+2, "다음 주 화요일" 등 구체 시점이면 YYYY-MM-DD로. 불명확하면 --due 생략.
- repo: cwd가 git repo면 그 디렉터리 이름을 라벨로, 아니면 --repo 생략."""


def _looks_like_future_task(text):
    """1차 필터: 시점 또는 명시적 의도가 있으면 후보. recall 우선(정밀도는 Claude)."""
    has_when = bool(_WHEN.search(text))
    has_intent = bool(_INTENT.search(text))
    if not (has_when or has_intent):
        return False
    # 시점만 있고 가정·조건 표현이면 비-할일로 보고 skip. 명시적 의도가 있으면 유지.
    if _NON_TASK.search(text) and not has_intent:
        return False
    return True


def main():
    data = json.loads(sys.stdin.read())
    prompt = data.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return
    if not _looks_like_future_task(prompt):
        return
    hint = _HINT
    cwd = data.get("cwd", "")
    if cwd:
        hint += f"\n- 현재 작업 디렉터리(cwd): {cwd}"
    print(hint)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # 감지기 실패가 사용자 입력을 막아선 안 된다 — 조용히 통과.
        pass
    sys.exit(0)
