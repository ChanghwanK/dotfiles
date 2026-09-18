#!/usr/bin/env bash
# GitHub MCP server wrapper: fetches credentials from Keychain (fallback: 1Password).
#
# 2026-07-15: Anthropic 참조 구현 @modelcontextprotocol/server-github 이 아카이브(deprecated)되어
# GitHub 공식 서버(github/github-mcp-server, Go)로 이관. 토큰 env 이름(GITHUB_PERSONAL_ACCESS_TOKEN)은
# 동일해 재인증 불필요.
#
# 2026-08-21: podman 컨테이너 실행에서 Homebrew 네이티브 바이너리로 전환.
# 이유: macOS applehv에서 podman run 한 번이 곧 VM으로의 SSH 핸드셰이크 한 번이라,
# 여러 세션·서브에이전트가 동시에 뜨면 핸드셰이크가 몰려 일부가 리셋된다. MCP 로그에
# ssh handshake failed / containers/create ContentLength 불일치 / crun already exists 로
# CONNECTION_CLOSED 가 34건 누적됐고, 전부 podman 소켓 계층이며 GitHub API·서버 자체 에러는 0건이었다.
# 네이티브 실행은 SSH 홉과 컨테이너 생성을 경로에서 제거해 이 실패 모드 자체를 없앤다.
# 버전 고정은 컨테이너 태그 핀 대신 `brew pin github-mcp-server` 로 유지한다
# (토큰 다루는 컴포넌트이므로 자동 업데이트 유입을 계속 막는다).
# 롤백: mcp-github.sh.podman-backup 을 되돌리면 된다.
set -euo pipefail

export GITHUB_PERSONAL_ACCESS_TOKEN
GITHUB_PERSONAL_ACCESS_TOKEN=$(
  security find-generic-password -a "claude-mcp" -s "github-token" -w 2>/dev/null \
  || op read "op://Employee/Claude Desktop - GitHub PAT/token"
)

exec /opt/homebrew/bin/github-mcp-server stdio
