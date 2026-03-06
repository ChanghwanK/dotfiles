#!/usr/bin/env bash
# Claude Code Stop hook — sends last user prompt to Slack DM
# On/Off: touch ~/.claude/bin/.notify-enabled (ON) / rm it (OFF)

FLAG="${HOME}/.claude/scripts/.notify-enabled"
[ -f "$FLAG" ] || exit 0

INPUT=$(cat)

# Prevent recursive loops
ACTIVE=$(printf '%s' "$INPUT" | python3 -c \
  'import sys,json; print(json.load(sys.stdin).get("stop_hook_active", False))' 2>/dev/null)
[ "$ACTIVE" = "True" ] && exit 0

# Get transcript path
TRANSCRIPT=$(printf '%s' "$INPUT" | python3 -c \
  'import sys,json; print(json.load(sys.stdin).get("transcript_path",""))' 2>/dev/null)
[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# Extract last user message from transcript JSONL
MSG=$(python3 - "$TRANSCRIPT" <<'PYEOF'
import json, sys

msgs = []
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d.get("type") == "user":
                content = d.get("message", {}).get("content", "")
                if isinstance(content, list):
                    text = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                else:
                    text = str(content)
                text = text.strip()
                if text:
                    msgs.append(text)
        except Exception:
            pass

if msgs:
    print(msgs[-1][:80])
PYEOF
2>/dev/null)

[ -z "$MSG" ] && exit 0

# Skip slash commands (/clear, /resume, /rename, etc.)
[[ "$MSG" == /* ]] && exit 0

FORMATTED="✅ '${MSG}' 요청 처리 완료"
"${HOME}/.claude/scripts/notify-slack.sh" "$FORMATTED"
