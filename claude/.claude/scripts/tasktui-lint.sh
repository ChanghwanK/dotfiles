#!/usr/bin/env bash
#
# tasktui-lint.sh — task-tui.sh ↔ 백엔드 python 스크립트의 정합성 정적 검사.
#
# 목적:
#   "셸이 호출하는 서브커맨드가 실제로 백엔드에 존재하는가"를 CI/수동으로 검증한다.
#
# 배경:
#   백엔드의 '미사용' 명령(set-task-status)을 지웠으나 셸 호출처가 남아 ctrl-s가
#   런타임에 조용히 깨진 회귀가 있었다. 이런 dangling 호출은 fzf TTY가 필요해
#   일반 테스트로는 안 잡힌다. 여기서는 argparse를 SoT로 삼아 추출-비교의 파싱
#   취약점 없이 검출한다: 유효 서브커맨드면 `<subcmd> --help`가 exit 0, 아니면 비0.
#
# 검사 항목:
#   1) 셸/파이썬 문법 (bash -n, py_compile)
#   2) 서브커맨드 정합성 (셸이 부르는 "$VAR <subcmd>"가 백엔드에 존재하는가)
#
# 사용:
#   ~/.claude/scripts/tasktui-lint.sh          # 수동 실행
#   pre-commit / CI 단계에서 호출 가능 (종료코드 0=통과, 1=위반)
set -uo pipefail

SKILLS_DIR="$HOME/.claude/skills/tasks:manage/scripts"
TUI="$HOME/.claude/scripts/task-tui.sh"

# 셸이 호출하는 백엔드 — task-tui.sh의 변수명과 동일하게 둔다.
# 키(STORE/SYNC/...)는 task-tui.sh에서 "$KEY"로 호출되는 변수명과 일치해야 한다.
declare -A SCRIPTS=(
  [STORE]="$SKILLS_DIR/todo_store.py"
  [SYNC]="$SKILLS_DIR/todo_sync.py"
  [NOTION_TASK]="$SKILLS_DIR/notion-task.py"
  [PLAN_TODO]="$HOME/.claude/scripts/plan-todo.py"
)

fail=0
note() { printf '%s\n' "$*"; }

# ── 1) 문법 ──────────────────────────────────────────────────
note "── 문법 검사 ──"
if bash -n "$TUI"; then note "  ✓ bash -n task-tui.sh"; else note "  ✗ bash -n 실패: task-tui.sh"; fail=1; fi
for key in STORE SYNC NOTION_TASK PLAN_TODO; do
  f="${SCRIPTS[$key]}"
  if [ ! -f "$f" ]; then note "  ✗ 파일 없음: $f"; fail=1; continue; fi
  if python3 -m py_compile "$f" 2>/dev/null; then
    note "  ✓ py_compile $(basename "$f")"
  else
    note "  ✗ py_compile 실패: $f"; fail=1
  fi
done

# ── 2) 서브커맨드 정합성 ─────────────────────────────────────
# task-tui.sh에서 "$KEY" 다음의 첫 토큰(서브커맨드)을 모아, 백엔드 argparse가
# 그 서브커맨드를 아는지 `<subcmd> --help`의 exit code로 확인한다.
# 정규식의 $는 [$]로 리터럴 매칭한다(grep -E에서 $는 줄끝 앵커이므로).
note "── 서브커맨드 정합성 ──"
for key in STORE SYNC NOTION_TASK PLAN_TODO; do
  f="${SCRIPTS[$key]}"
  [ -f "$f" ] || continue
  subs=$(grep -oE "\"[\$]$key\" [a-z][a-z-]*" "$TUI" | awk '{print $2}' | sort -u)
  [ -z "$subs" ] && continue
  while IFS= read -r sub; do
    [ -z "$sub" ] && continue
    if python3 "$f" "$sub" --help >/dev/null 2>&1; then
      note "  ✓ $key $sub"
    else
      note "  ✗ $key '$sub' — $(basename "$f")에 없음 (dangling 호출)"
      fail=1
    fi
  done <<<"$subs"
done

note ""
if [ "$fail" -eq 0 ]; then
  note "정합성 통과 ✓"
else
  note "위반 발견 ✗ — 위 ✗ 항목을 수정하세요."
fi
exit "$fail"
