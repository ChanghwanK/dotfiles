#!/usr/bin/env bash
# Claude Code statusLine command — plan 진행률을 1줄로 출력
# stdin: JSON {"session_id": "...", "model": {...}, "workspace": {...}, ...}

read -r json
session_id=$(echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)

python3 "$HOME/.claude/scripts/plan-todo.py" statusline --session-id "$session_id" 2>/dev/null
