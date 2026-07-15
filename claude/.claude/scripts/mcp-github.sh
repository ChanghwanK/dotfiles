#!/usr/bin/env bash
# GitHub MCP server wrapper — fetches credentials from Keychain (fallback: 1Password).
#
# 2026-07-15: Anthropic 참조 구현 @modelcontextprotocol/server-github 이 아카이브(deprecated)되어
# GitHub 공식 서버(github/github-mcp-server, Go)로 이관. 토큰 env 이름(GITHUB_PERSONAL_ACCESS_TOKEN)은
# 동일해 재인증 불필요. 툴 이름은 신규 서버 기준으로 바뀐다(기존 mcp__github__* 인터페이스 변경).
# 버전 핀: 토큰 다루는 컴포넌트이므로 :latest 자동 유입(공급망/재현성 위험)을 막고 명시적 업데이트만 허용.
set -euo pipefail

export GITHUB_PERSONAL_ACCESS_TOKEN
GITHUB_PERSONAL_ACCESS_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "github-token" -w 2>/dev/null \
  || op read "op://Employee/Claude Desktop - GitHub PAT/token"
)

exec podman run --rm -i \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  ghcr.io/github/github-mcp-server:v1.5.0 \
  stdio
