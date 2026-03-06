#!/usr/bin/env bash
# 01-xcode.sh — Xcode Command Line Tools 설치
source "$(dirname "$0")/lib.sh"

log_step "Xcode Command Line Tools"

if xcode-select -p &>/dev/null; then
  log_info "이미 설치됨: $(xcode-select -p)"
else
  log_info "설치 중..."
  xcode-select --install
  log_warn "팝업에서 설치 완료 후 다시 실행하세요"
  exit 1
fi

log_ok "Xcode CLI tools 완료"
