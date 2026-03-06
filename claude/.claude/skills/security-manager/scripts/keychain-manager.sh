#!/usr/bin/env bash
# keychain-manager.sh — Keychain 전체 재동기화 (rotate-all)
# Usage: keychain-manager.sh rotate-all
set -euo pipefail

SUBCOMMAND="${1:-}"

declare -A TOKEN_MAP=(
  [grafana-token]="op://Employee/Claude MCP - Grafana/token"
  [slack-token]="op://Employee/Claude MCP - Slack/token"
  [github-token]="op://Employee/Claude Desktop - GitHub PAT/token"
  [notion-personal-token]="op://Employee/Claude MCP - Notion-Personal/token"
)

case "$SUBCOMMAND" in
  rotate-all)
    for svc in "${!TOKEN_MAP[@]}"; do
      security add-generic-password -a "claude-mcp" -s "$svc" \
        -w "$(op read "${TOKEN_MAP[$svc]}")" -T "" -U \
        && echo "✓ $svc" || echo "✗ $svc FAILED"
    done
    ;;
  *)
    echo "Usage: $0 {rotate-all}" >&2
    exit 1
    ;;
esac
