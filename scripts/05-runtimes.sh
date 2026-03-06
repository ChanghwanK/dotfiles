#!/usr/bin/env bash
# 05-runtimes.sh — pyenv, nvm, bun 런타임 설치
source "$(dirname "$0")/lib.sh"

log_step "Language Runtimes"

# pyenv
if has pyenv; then
  log_info "pyenv 이미 설치됨"

  PYTHON_VERSIONS=("3.12.9" "3.13.6")
  for ver in "${PYTHON_VERSIONS[@]}"; do
    if pyenv versions --bare | grep -qF "$ver"; then
      log_info "Python $ver 이미 설치됨"
    else
      log_info "Python $ver 설치 중..."
      pyenv install "$ver"
    fi
  done
else
  log_warn "pyenv 없음 — brew install pyenv 후 재실행"
fi

# nvm
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  source "$NVM_DIR/nvm.sh"
  log_info "nvm 이미 설치됨"

  log_info "Node.js LTS 설치 중..."
  nvm install --lts
else
  # nvm은 brew로 설치된 경우 다른 경로일 수 있음
  if has brew && [ -s "$(brew --prefix nvm)/nvm.sh" ]; then
    source "$(brew --prefix nvm)/nvm.sh"
    log_info "nvm (brew) 이미 설치됨"
    nvm install --lts
  else
    log_warn "nvm 없음 — brew install nvm 후 재실행"
  fi
fi

# bun
if has bun; then
  log_info "bun 이미 설치됨: $(bun --version)"
else
  log_info "bun 설치 중..."
  curl -fsSL https://bun.sh/install | bash
fi

log_ok "Runtimes 완료"
