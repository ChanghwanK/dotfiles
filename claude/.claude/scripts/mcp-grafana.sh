#!/usr/bin/env bash
# Grafana MCP server wrapper — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

export GRAFANA_URL="https://riiid.grafana.net/"
export GRAFANA_SERVICE_ACCOUNT_TOKEN
GRAFANA_SERVICE_ACCOUNT_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "grafana-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Grafana/token"
)

exec podman run --rm -i \
  -e GRAFANA_URL \
  -e GRAFANA_SERVICE_ACCOUNT_TOKEN \
  docker.io/grafana/mcp-grafana:0.11.4 \
  -transport stdio
