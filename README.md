# dotfiles

changhwan의 macOS 개발 환경 설정 파일 모음. GNU Stow로 심볼릭 링크를 관리합니다.

## 구조

```
~/.dotfiles/
├── Makefile
├── brew/
│   ├── formulae.txt            # brew install 대상
│   └── casks.txt               # brew install --cask 대상
├── scripts/
│   ├── lib.sh                  # 공통 헬퍼
│   ├── bootstrap.sh            # 전체 부트스트랩
│   ├── 01-xcode.sh             # Xcode CLI tools
│   ├── 02-homebrew.sh          # Homebrew + 패키지
│   ├── 03-dotfiles.sh          # stow 심볼릭 링크
│   ├── 04-omz.sh               # Oh-My-Zsh + 플러그인
│   ├── 05-runtimes.sh          # pyenv, nvm, bun
│   └── 06-claude.sh            # Claude Code 설정
├── bash/                       # .bashrc, .profile
├── gh/                         # GitHub CLI 설정
├── git/                        # .gitconfig, global .gitignore
├── karabiner/                  # Karabiner-Elements 키 매핑
├── nvim/                       # Neovim 설정 (lazy.nvim 기반)
├── ssh/                        # SSH config
├── vim/                        # .vimrc
├── zsh/                        # .zshrc, .zshenv, .zprofile, .p10k.zsh
└── claude/                     # Claude Code 설정
    └── .claude/
        ├── settings.json
        ├── mcp.json
        ├── statusline.py
        ├── SETUP.md
        ├── SECURITY.md
        ├── scripts/            # MCP wrapper + 알림 스크립트
        ├── commands/           # 슬래시 커맨드
        └── rules/              # 규칙 파일
```

## 새 Mac 부트스트랩

```bash
xcode-select --install
git clone https://github.com/<user>/dotfiles.git ~/.dotfiles
cd ~/.dotfiles && make bootstrap
op signin && make claude-secrets
claude login
```

## Makefile 타겟

```
make bootstrap         전체 부트스트랩 (새 Mac)
make brew              Homebrew 패키지 설치/업데이트
make dotfiles          stow 심볼릭 링크 (재)생성
make omz               Oh-My-Zsh + 플러그인 + p10k + kube-ps1
make runtimes          pyenv, nvm, bun 런타임 설치
make claude            Claude Code 플러그인 + 알림 설정
make claude-secrets    1Password → Keychain + ~/.secrets.zsh
make brew-dump         현재 brew 상태를 txt에 덤프
make help              도움말
```

## 시크릿 관리

토큰은 git에 포함되지 않습니다:

- **MCP 토큰**: 1Password → macOS Keychain (`security` CLI)
- **환경 변수**: `~/.secrets.zsh` (chmod 600)
- 상세: [`~/.claude/SECURITY.md`](claude/.claude/SECURITY.md)

## 수동 인증 (bootstrap 후)

```bash
op signin                    # 1Password CLI
make claude-secrets          # Keychain 토큰 등록
claude login                 # Claude Code OAuth
gh auth login                # GitHub CLI
gimme-aws-creds              # AWS (okta-devops)
```
