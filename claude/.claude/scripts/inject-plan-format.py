#!/usr/bin/env python3
"""PostToolUse(EnterPlanMode) 훅: 플랜 모드에 들어가는 순간 docs/plan-format.md를 주입한다.

plan-format.md는 플랜을 쓸 때만 필요하므로 상시 import하지 않고, 플랜 모드 진입 시점에만 넣는다.
"""
import json
import pathlib
import sys

PLAN_FORMAT = pathlib.Path.home() / ".claude/docs/plan-format.md"


def main():
    try:
        body = PLAN_FORMAT.read_text()
        header = "[plan-format 주입] 플랜은 아래 형식을 따릅니다. 문제와 가설을 쓰기 전에 docs/hypothesis-first.md를 Read합니다."
    except OSError:
        body = ""
        header = "[plan-format 주입 실패] ~/.claude/docs/plan-format.md를 읽지 못했습니다. 직접 Read하세요."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": header + "\n\n" + body}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[inject-plan-format] 오류: {exc}", file=sys.stderr)
