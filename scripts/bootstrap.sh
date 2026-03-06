#!/usr/bin/env bash
# bootstrap.sh — 새 Mac 전체 부트스트랩
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPTS/lib.sh"

printf "\n${_B}${_C}═══════════════════════════════════════${_R}\n"
printf "${_B}${_C}  Mac Bootstrap — $(date +%Y-%m-%d)${_R}\n"
printf "${_B}${_C}═══════════════════════════════════════${_R}\n\n"

bash "$SCRIPTS/01-xcode.sh"
echo
bash "$SCRIPTS/02-homebrew.sh"
echo
bash "$SCRIPTS/03-dotfiles.sh"
echo
bash "$SCRIPTS/04-omz.sh"
echo
bash "$SCRIPTS/05-runtimes.sh"
echo
bash "$SCRIPTS/06-claude.sh"

printf "\n${_B}${_G}═══════════════════════════════════════${_R}\n"
printf "${_B}${_G}  Bootstrap 완료!${_R}\n"
printf "${_B}${_G}═══════════════════════════════════════${_R}\n\n"

echo "남은 수동 단계:"
echo "  1. op signin && make claude-secrets"
echo "  2. claude login"
echo "  3. gh auth login"
echo "  4. gimme-aws-creds (AWS 인증)"
echo "  5. 새 터미널 열어서 zsh 확인"
echo
