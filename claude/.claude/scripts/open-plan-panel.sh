#!/usr/bin/env bash
# Claude Code PostToolUse(Write|Edit|MultiEdit) 훅: 플랜 파일(~/.claude/plans/*.md)이 쓰이면
# Orca 우측 사이드바의 Plan 패널(local.plan-viewer 플러그인)을 연다.
# Orca 밖이거나 무엇이 실패해도 조용히 exit 0 한다. stdout에는 아무것도 쓰지 않는다.

[ -n "${ORCA_CLI_COMMAND:-}" ] && [ -x "$ORCA_CLI_COMMAND" ] || exit 0

FILE_PATH=$(python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" \
    2>/dev/null) || exit 0

case "$FILE_PATH" in
    "$HOME"/.claude/plans/*.md) ;;
    *) exit 0 ;;
esac

# plugin open은 창을 앞으로 가져오거나 포커스를 뺏지 않는다. 사이드바가 닫혀 있으면 연다.
"$ORCA_CLI_COMMAND" plugin open local.plan-viewer --panel plan >/dev/null 2>&1 || true
exit 0
