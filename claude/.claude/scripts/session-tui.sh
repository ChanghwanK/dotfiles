#!/bin/bash
# Claude Code session browser TUI
# Usage: cc-sessions
# Enter: resume selected session | Ctrl-D: 3-day view | Ctrl-F: 7-day view | Ctrl-R: refresh

if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "Error: cc-sessions requires an interactive terminal (TTY)." >&2
  exit 1
fi

if ! command -v fzf &>/dev/null; then
  echo "Error: fzf is required. Install with: brew install fzf" >&2
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required." >&2
  exit 1
fi

STORE="$HOME/.claude/scripts/session_store.py"
if [[ ! -f "$STORE" ]]; then
  echo "Error: Missing $STORE" >&2
  exit 1
fi

HT="[ 오늘* | 3d | 7d ]  Enter:Resume  Ctrl-T:오늘  Ctrl-D:3일  Ctrl-F:7일  Ctrl-R:새로고침  Esc:종료"
H3="[ 오늘 | 3d* | 7d ]  Enter:Resume  Ctrl-T:오늘  Ctrl-D:3일  Ctrl-F:7일  Ctrl-R:새로고침  Esc:종료"
H7="[ 오늘 | 3d | 7d* ]  Enter:Resume  Ctrl-T:오늘  Ctrl-D:3일  Ctrl-F:7일  Ctrl-R:새로고침  Esc:종료"

SELECTED=$(
  python3 "$STORE" --today | fzf \
    --delimiter=$'\t' \
    --with-nth='3..' \
    --ansi \
    --header "$HT" \
    --preview "python3 $STORE --preview {1}" \
    --preview-window='right:45%:wrap' \
    --bind "ctrl-t:reload(python3 $STORE --today)+change-header($HT)" \
    --bind "ctrl-d:reload(python3 $STORE --days 3)+change-header($H3)" \
    --bind "ctrl-f:reload(python3 $STORE --days 7)+change-header($H7)" \
    --bind "ctrl-r:reload(python3 $STORE --today)+change-header($HT)" \
    --height='85%' \
    --border \
    --prompt='cc-sessions> ' \
    --info=inline
)

[[ -z "$SELECTED" ]] && exit 0

SESSION_ID=$(echo "$SELECTED" | cut -f1)
PROJECT_PATH=$(echo "$SELECTED" | cut -f2)

if [[ -z "$SESSION_ID" ]]; then
  echo "Error: could not extract session ID" >&2
  exit 1
fi

if [[ -n "$PROJECT_PATH" && -d "$PROJECT_PATH" ]]; then
  cd "$PROJECT_PATH"
fi

exec claude --resume "$SESSION_ID"
