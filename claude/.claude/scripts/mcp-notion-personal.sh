#!/usr/bin/env bash
# Notion MCP server wrapper (Personal workspace) — fetches credentials from Keychain (fallback: 1Password).
set -euo pipefail

NOTION_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null \
  || op read "op://Employee/Claude MCP - Notion-Personal/token"
)
# Notion-Version 2025-09-03: data sources 모델 도입 버전.
# notion-mcp-server 2.4.0이 노출하는 data-source 계열 툴(API-query-data-source 등)이
# 구 버전(2022-06-28)에서는 동작하지 않으므로 서버 툴셋과 API 버전을 정렬한다.
export OPENAPI_MCP_HEADERS="{\"Authorization\": \"Bearer ${NOTION_TOKEN}\", \"Notion-Version\": \"2025-09-03\"}"

# 버전 핀: 토큰을 다루는 컴포넌트이므로 latest 자동 유입(공급망/재현성 위험)을 막고 명시적 업데이트만 허용.
exec npx -y @notionhq/notion-mcp-server@2.4.1
