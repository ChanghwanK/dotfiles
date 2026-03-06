DOTFILES := $(HOME)/.dotfiles
SCRIPTS  := $(DOTFILES)/scripts

.PHONY: bootstrap brew dotfiles omz runtimes claude claude-secrets \
        brew-dump help

bootstrap:          ## 전체 부트스트랩 (새 Mac)
	@bash $(SCRIPTS)/bootstrap.sh

brew:               ## Homebrew 패키지 설치/업데이트
	@bash $(SCRIPTS)/02-homebrew.sh

dotfiles:           ## stow 심볼릭 링크 (재)생성
	@bash $(SCRIPTS)/03-dotfiles.sh

omz:                ## Oh-My-Zsh + 플러그인 + p10k + kube-ps1
	@bash $(SCRIPTS)/04-omz.sh

runtimes:           ## pyenv, nvm, bun 런타임 설치
	@bash $(SCRIPTS)/05-runtimes.sh

claude:             ## Claude Code 플러그인 + 알림 설정
	@bash $(SCRIPTS)/06-claude.sh

claude-secrets:     ## 1Password → Keychain + ~/.secrets.zsh (op signin 필요)
	@bash $(SCRIPTS)/06-claude.sh --secrets-only

brew-dump:          ## 현재 brew 상태를 txt에 덤프
	brew list --formula -1 > $(DOTFILES)/brew/formulae.txt
	brew list --cask -1 > $(DOTFILES)/brew/casks.txt

help:               ## 도움말
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk -F ':.*## ' '{printf "  make %-18s %s\n", $$1, $$2}'
