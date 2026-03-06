#!/usr/bin/env bash
# Slack MCP server wrapper — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

export SLACK_BOT_TOKEN
export SLACK_TEAM_ID="T02PSFS4G"
SLACK_BOT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Slack/token"
)

exec npx -y @modelcontextprotocol/server-slack
