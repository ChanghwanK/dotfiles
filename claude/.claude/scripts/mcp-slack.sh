#!/usr/bin/env bash
# Slack MCP server wrapper — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

export SLACK_BOT_TOKEN
export SLACK_TEAM_ID="T02PSFS4G"
SLACK_BOT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Slack/token"
)

# 2026-07-15: @modelcontextprotocol/server-slack 은 아카이브(deprecated)됐으나 공식 후속이 없다.
# deprecated는 '지원 종료'지 '제거'가 아니라 계속 동작하므로, 마지막 정상 버전에 핀해
# auto-latest 공급망/재현성 위험만 차단하고 공식 대체재가 나오면 재검토한다.
exec npx -y @modelcontextprotocol/server-slack@2025.4.25
