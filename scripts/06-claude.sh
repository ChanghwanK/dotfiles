#!/usr/bin/env bash
# 06-claude.sh — Claude Code 환경 설정 (플러그인, 알림, 시크릿)
source "$(dirname "$0")/lib.sh"

SECRETS_ONLY=false
[ "${1:-}" = "--secrets-only" ] && SECRETS_ONLY=true

# ── Keychain 토큰 등록 (1Password 필요) ──────────────────────────────────
register_keychain() {
  log_step "Keychain 토큰 등록 (1Password → Keychain)"

  if ! has op; then
    log_err "1Password CLI (op) 없음. brew install 1password-cli"
    return 1
  fi

  # op 인증 확인
  if ! op account list &>/dev/null; then
    log_warn "op signin 먼저 실행하세요"
    return 1
  fi

  local -A TOKENS=(
    ["grafana-token"]="op://Employee/Claude MCP - Grafana/token"
    ["slack-token"]="op://Employee/Claude MCP - Slack/token"
    ["github-token"]="op://Employee/Claude Desktop - GitHub PAT/token"
    ["notion-personal-token"]="op://Employee/Claude MCP - Notion-Personal/token"
  )

  for service in "${!TOKENS[@]}"; do
    local op_path="${TOKENS[$service]}"
    if security find-generic-password -a "claude-mcp" -s "$service" -w &>/dev/null; then
      log_info "$service (이미 등록됨)"
    else
      local token
      token=$(op read "$op_path" 2>/dev/null) || {
        log_warn "$service — 1Password에서 읽기 실패"
        continue
      }
      security add-generic-password -a "claude-mcp" -s "$service" -w "$token" -T ""
      log_info "$service (등록 완료)"
    fi
  done

  # ~/.secrets.zsh 생성
  if [ ! -f "$HOME/.secrets.zsh" ]; then
    log_info "~/.secrets.zsh 생성 중..."
    cat > "$HOME/.secrets.zsh" <<SECRETS
export GITHUB_MCP_TOKEN="$(op read 'op://Employee/Claude Desktop - GitHub PAT/token' 2>/dev/null || echo 'FILL_ME')"
export SLACK_USER_TOKEN="$(op read 'op://Employee/Claude MCP - Slack/user-token' 2>/dev/null || echo 'FILL_ME')"
export SLACK_BOT_TOKEN="$(op read 'op://Employee/Claude MCP - Slack/token' 2>/dev/null || echo 'FILL_ME')"
export NOTION_TOKEN="$(op read 'op://Employee/Claude MCP - Notion-Personal/token' 2>/dev/null || echo 'FILL_ME')"
SECRETS
    chmod 600 "$HOME/.secrets.zsh"
    log_info "~/.secrets.zsh 생성 완료"
  else
    log_info "~/.secrets.zsh 이미 존재"
  fi

  log_ok "Keychain 토큰 등록 완료"
}

# secrets-only 모드
if [ "$SECRETS_ONLY" = true ]; then
  register_keychain
  exit 0
fi

log_step "Claude Code 환경 설정"

# scripts 실행 권한
if [ -d "$HOME/.claude/scripts" ]; then
  chmod +x "$HOME/.claude/scripts"/*.sh 2>/dev/null || true
  log_info "scripts chmod +x 완료"
fi

# 알림 활성화
touch "$HOME/.claude/scripts/.notify-enabled"
log_info "Slack 알림 활성화됨"

# 플러그인 설치
if has claude; then
  PLUGINS=(
    "helm-chart@socraai-devops-skills"
    "istio-troubleshooting@socraai-devops-skills"
    "pod-crash@socraai-devops-skills"
    "socra-infra-design@socraai-devops-skills"
    "example-skills@anthropic-agent-skills"
    "claude-mem@thedotmack"
  )

  log_info "플러그인 설치 중..."
  for plugin in "${PLUGINS[@]}"; do
    claude plugins install "$plugin" 2>/dev/null || true
    log_info "  $plugin"
  done
else
  log_warn "claude CLI 없음 — brew install claude-code 후 플러그인 수동 설치"
fi

log_ok "Claude Code 환경 설정 완료"
