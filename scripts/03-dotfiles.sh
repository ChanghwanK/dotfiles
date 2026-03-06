#!/usr/bin/env bash
# 03-dotfiles.sh — stow 심볼릭 링크 생성 (claude 패키지 포함)
source "$(dirname "$0")/lib.sh"

log_step "Dotfiles (GNU Stow)"

if ! has stow; then
  log_err "stow가 설치되어 있지 않습니다. brew install stow"
  exit 1
fi

cd "$DOTFILES"

# 기존 claude 파일 백업 (stow 충돌 방지)
CLAUDE_BACKUP="$HOME/.claude-backup-$(date +%Y%m%d%H%M%S)"
if [ -d "$HOME/.claude" ] && [ ! -L "$HOME/.claude" ]; then
  # 충돌할 수 있는 파일만 백업
  NEEDS_BACKUP=false
  for f in settings.json mcp.json statusline.py CLAUDE.md SETUP.md SECURITY.md; do
    if [ -f "$HOME/.claude/$f" ] && [ ! -L "$HOME/.claude/$f" ]; then
      NEEDS_BACKUP=true
      break
    fi
  done

  if [ "$NEEDS_BACKUP" = true ]; then
    log_info "기존 ~/.claude 설정 파일 백업 → $CLAUDE_BACKUP"
    mkdir -p "$CLAUDE_BACKUP"
    for f in settings.json mcp.json statusline.py CLAUDE.md SETUP.md SECURITY.md; do
      [ -f "$HOME/.claude/$f" ] && [ ! -L "$HOME/.claude/$f" ] && \
        mv "$HOME/.claude/$f" "$CLAUDE_BACKUP/$f"
    done
    # 디렉토리도 백업
    for d in scripts commands rules; do
      if [ -d "$HOME/.claude/$d" ] && [ ! -L "$HOME/.claude/$d" ]; then
        cp -R "$HOME/.claude/$d" "$CLAUDE_BACKUP/$d"
        rm -rf "$HOME/.claude/$d"
      fi
    done
  fi
fi

# 모든 stow 패키지 restow
PACKAGES=(bash gh git karabiner nvim ssh vim zsh claude tmux)
for pkg in "${PACKAGES[@]}"; do
  if [ -d "$pkg" ]; then
    stow --restow "$pkg"
    log_info "$pkg"
  fi
done

# claude 패키지의 $HOME 경로 치환
for f in "$HOME/.claude/settings.json" "$HOME/.claude/mcp.json"; do
  if [ -f "$f" ]; then
    sed -i '' "s|\\\$HOME|$HOME|g" "$f"
  fi
done

log_ok "Dotfiles stow 완료"
