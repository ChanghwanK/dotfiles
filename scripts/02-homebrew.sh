#!/usr/bin/env bash
# 02-homebrew.sh — Homebrew 설치 + 패키지 설치
source "$(dirname "$0")/lib.sh"

log_step "Homebrew"

# Homebrew 설치
if has brew; then
  log_info "이미 설치됨: $(brew --version | head -1)"
else
  log_info "Homebrew 설치 중..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Formulae 설치
FORMULAE="$DOTFILES/brew/formulae.txt"
if [ -f "$FORMULAE" ]; then
  log_info "Formulae 설치 중..."
  grep -v '^#' "$FORMULAE" | grep -v '^$' | xargs brew install 2>&1 | tail -1 || true
  log_info "Formulae 완료"
else
  log_warn "brew/formulae.txt 없음 — 스킵"
fi

# Cask 설치
CASKS="$DOTFILES/brew/casks.txt"
if [ -f "$CASKS" ]; then
  log_info "Casks 설치 중..."
  grep -v '^#' "$CASKS" | grep -v '^$' | xargs brew install --cask 2>&1 | tail -1 || true
  log_info "Casks 완료"
else
  log_warn "brew/casks.txt 없음 — 스킵"
fi

log_ok "Homebrew 완료"
