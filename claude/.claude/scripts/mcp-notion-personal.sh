#!/usr/bin/env bash
# Notion MCP server wrapper (Personal workspace) — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

NOTION_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Notion-Personal/token"
)
export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", \"Notion-Version\": \"2022-06-28\"}"

exec npx -y @notionhq/notion-mcp-server
