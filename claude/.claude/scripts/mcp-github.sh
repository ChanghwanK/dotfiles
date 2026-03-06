#!/usr/bin/env bash
# GitHub MCP server wrapper — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

export GITHUB_PERSONAL_ACCESS_TOKEN
GITHUB_PERSONAL_ACCESS_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "github-token" -w 2>/dev/null \
  || op read "op://Employee/Claude Desktop - GitHub PAT/token"
)

exec npx -y @modelcontextprotocol/server-github
