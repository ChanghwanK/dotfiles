# dotfiles

changhwan의 macOS 개발 환경 설정 파일 모음. GNU Stow로 심볼릭 링크를 관리합니다.

## 구조

```
~/.dotfiles/
├── bash/         # .bashrc, .profile
├── gh/           # GitHub CLI 설정
├── git/          # .gitconfig, global .gitignore
├── karabiner/    # Karabiner-Elements 키 매핑
├── nvim/         # Neovim 설정 (lazy.nvim 기반)
├── ssh/          # SSH config
├── vim/          # .vimrc
└── zsh/          # .zshrc, .zshenv, .zprofile, .p10k.zsh
```

## 새 머신 복원 절차

### 1. 전제 조건 설치

```bash
# macOS (Homebrew)
brew install stow git
```

### 2. dotfiles 클론

```bash
git clone <repo-url> ~/.dotfiles
```

> 아직 remote가 없으면 먼저 GitHub에 repo 만들어야 함

### 3. stow로 심볼릭 링크 생성

```bash
cd ~/.dotfiles
stow zsh bash vim git nvim ssh karabiner gh claude
```

### 4. 시크릿 복원

`~/.secrets.zsh`는 git에 없으므로 별도로 생성:

```bash
cat > ~/.secrets.zsh << 'EOF'
export GITHUB_MCP_TOKEN="..."
export SLACK_USER_TOKEN="..."
export SLACK_BOT_TOKEN="..."
export NOTION_TOKEN="..."
EOF
chmod 600 ~/.secrets.zsh
```

> 1Password에서 값 꺼내서 채우기

### 5. 나머지 수동 설정

```bash
# Oh-My-Zsh 설치 (zsh plugins 의존)
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# zsh 커스텀 플러그인 설치 (Oh-My-Zsh 설치 후)
git clone https://github.com/zsh-users/zsh-autosuggestions \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

git clone https://github.com/zsh-users/zsh-syntax-highlighting \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

git clone https://github.com/joshskidmore/zsh-fzf-history-search \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-fzf-history-search

git clone https://github.com/jirutka/zsh-shift-select \
  ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-shift-select

# Powerlevel10k
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/powerlevel10k

# kube-ps1
mkdir -p ~/.kubernetes
git clone https://github.com/jonmosco/kube-ps1.git ~/.kubernetes/kube-ps1

# Neovim 플러그인 (첫 실행 시 lazy.nvim이 자동 설치)
nvim --headless +q
```
