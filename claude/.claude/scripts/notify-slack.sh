#!/usr/bin/env bash
# Slack DM to changhwan (U098T8A1XL0) via devops_cc bot
# Usage: notify-slack.sh "message"
set -euo pipefail
ERROR_LOG="${HOME}/.claude/scripts/notify-slack.error.log"
MSG="${1:-Task completed}"

# Fetch token from Keychain (fallback: 1Password) if not set in environment
if [ -z "${SLACK_BOT_TOKEN:-}" ]; then
  SLACK_BOT_TOKEN=$(
    security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null \
    || op read "op://Employee/Claude MCP - Slack/token"
  ) || { echo "[$(date -u +%FT%TZ)] token fetch failed" >> "$ERROR_LOG"; exit 0; }
fi
MSG_ESCAPED=$(printf '%s' "$MSG" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))') \
  || { echo "[$(date -u +%FT%TZ)] json escape failed: $MSG" >> "$ERROR_LOG"; exit 0; }
RESPONSE=$(curl -sf -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-type: application/json; charset=utf-8" \
  -d "{\"channel\": \"U098T8A1XL0\", \"text\": $MSG_ESCAPED}" 2>&1) \
  || { echo "[$(date -u +%FT%TZ)] curl failed: $RESPONSE | msg: $MSG" >> "$ERROR_LOG"; exit 0; }
echo "$RESPONSE" | python3 -c 'import sys,json; r=json.load(sys.stdin); exit(0) if r.get("ok") else sys.stderr.write(str(r)+"\n") or exit(1)' \
  || { echo "[$(date -u +%FT%TZ)] slack api error: $RESPONSE | msg: $MSG" >> "$ERROR_LOG"; exit 0; }
