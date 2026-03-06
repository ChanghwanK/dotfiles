#!/usr/bin/env bash
# 04-omz.sh — Oh-My-Zsh + 플러그인 + Powerlevel10k + kube-ps1
source "$(dirname "$0")/lib.sh"

log_step "Oh-My-Zsh + 플러그인"

ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"

# Oh-My-Zsh
if [ -d "$HOME/.oh-my-zsh" ]; then
  log_info "Oh-My-Zsh 이미 설치됨"
else
  log_info "Oh-My-Zsh 설치 중..."
  RUNZSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# 플러그인 (git clone 또는 pull)
clone_or_pull() {
  local repo="$1" dest="$2"
  if [ -d "$dest" ]; then
    git -C "$dest" pull --quiet 2>/dev/null || true
    log_info "$(basename "$dest") (updated)"
  else
    git clone --quiet "$repo" "$dest"
    log_info "$(basename "$dest") (installed)"
  fi
}

clone_or_pull "https://github.com/zsh-users/zsh-autosuggestions" \
  "$ZSH_CUSTOM/plugins/zsh-autosuggestions"

clone_or_pull "https://github.com/zsh-users/zsh-syntax-highlighting" \
  "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"

clone_or_pull "https://github.com/joshskidmore/zsh-fzf-history-search" \
  "$ZSH_CUSTOM/plugins/zsh-fzf-history-search"

clone_or_pull "https://github.com/jirutka/zsh-shift-select" \
  "$ZSH_CUSTOM/plugins/zsh-shift-select"

# Powerlevel10k
if [ -d "$HOME/powerlevel10k" ]; then
  git -C "$HOME/powerlevel10k" pull --quiet 2>/dev/null || true
  log_info "Powerlevel10k (updated)"
else
  git clone --depth=1 "https://github.com/romkatv/powerlevel10k.git" "$HOME/powerlevel10k"
  log_info "Powerlevel10k (installed)"
fi

# kube-ps1
KUBE_PS1_DIR="$HOME/.kubernetes/kube-ps1"
if [ -d "$KUBE_PS1_DIR" ]; then
  git -C "$KUBE_PS1_DIR" pull --quiet 2>/dev/null || true
  log_info "kube-ps1 (updated)"
else
  mkdir -p "$HOME/.kubernetes"
  git clone --quiet "https://github.com/jonmosco/kube-ps1.git" "$KUBE_PS1_DIR"
  log_info "kube-ps1 (installed)"
fi

log_ok "Oh-My-Zsh + 플러그인 완료"
