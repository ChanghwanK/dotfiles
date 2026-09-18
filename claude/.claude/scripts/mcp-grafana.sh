#!/usr/bin/env bash
# Grafana MCP server wrapper: fetches credentials from Keychain (fallback: 1Password).
#
# 2026-08-21: podman 컨테이너 실행에서 Homebrew 네이티브 바이너리로 전환.
# 근거는 mcp-github.sh 주석 참조 (동일한 podman SSH 전송 계층 실패를 공유한다).
# 버전 고정은 `brew pin mcp-grafana` 로 유지한다.
# 롤백: mcp-grafana.sh.podman-backup 을 되돌리면 된다.
set -euo pipefail

export GRAFANA_URL="https://riiid.grafana.net/"
export GRAFANA_SERVICE_ACCOUNT_TOKEN
GRAFANA_SERVICE_ACCOUNT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "grafana-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Grafana/token"
)

exec /opt/homebrew/bin/mcp-grafana -transport stdio
