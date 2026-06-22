# Kiro CLI pre block. Keep at the top of this file.
[[ -f "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.pre.zsh" ]] && builtin source "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.pre.zsh"
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Oh My Zsh 설정
export ZSH="$HOME/.oh-my-zsh"

# powerlevel10k를 직접 source하므로 OMZ 테마 비활성화
ZSH_THEME=""

plugins=(
    git
    kubectl
    terraform
    podman
    zsh-syntax-highlighting
    zsh-fzf-history-search
    zsh-autosuggestions
    aws
    zsh-shift-select
)

source $ZSH/oh-my-zsh.sh

# History 설정
HISTSIZE=50000
SAVEHIST=50000
setopt HIST_IGNORE_ALL_DUPS
setopt SHARE_HISTORY

# Editor
export EDITOR='nvim'
export PATH=/opt/homebrew/bin:$PATH

# build_prompt() {
#   RETVAL=$?
#   prompt_newline
#   prompt_end
# }

# # prompt
# prompt_newline() {
#   if [[ -n $CURRENT_BG ]]; then
#     echo -n "%{%k%F{$CURRENT_BG}%}$SEGMENT_SEPARATOR
# %{%k%F{blue}%}$SEGMENT_SEPARATOR"
#   else
#     echo -n "%{%k%}"
#   fi

#   echo -n "%{%f%}"
#   CURRENT_BG=''
# }

# kube-ps1
if [[ -f ~/.kubernetes/kube-ps1/kube-ps1.sh ]]; then
  source ~/.kubernetes/kube-ps1/kube-ps1.sh
  PROMPT='$(kube_ps1)'$PROMPT
  KUBE_PS1_SYMBOL_ENABLE=false
fi

# kubectl aliases
alias k="kubectl"
alias klg="kubectl logs"
alias kgcy="kubectl get cm -o yaml"
alias kgdp="kubectl get deployment"
alias kdp="kubectl describe pod"
alias kt="kubectl top"
alias ktp="kubectl top pod"
alias ktn="kubectl top node"
alias kg="kubectl get"
alias kgn="kubectl get nodes"
alias kd="kubectl describe"
alias kdn="kubectl describe nodes"
alias kl="kubectl logs -f"
alias klogs="kubectl logs -f"
alias kgp="kubectl get pods"
alias kgpw="kubectl get pods -o wide"
alias kgpy="kubectl get pods -o yaml"
alias kep="kubectl edit pod"
alias kge="kubectl get events --sort-by=.lastTimestamp"
alias kctx="kubectx"
alias kc="kubectx"
alias kns="kubens"
alias kn="kubens"
alias kcdev="kctx infra-k8s-dev"
alias kcstg="kctx infra-k8s-stg"
alias kcprod="kctx infra-k8s-prod"

alias kdev="kctx k8s-dev"
alias kstg="kctx k8s-stg"
alias kprod="kctx k8s-prod"

# workspace aliases
alias netshoot="cd $HOME/workspace/engineering_home/netshoot"

# terraform aliases
alias tf="terraform"

# helm aliases
alias h="helm"

# podman aliases
alias p="podman"
alias docker="podman"

# cursor aliases
alias c="cursor"
alias dp="deployment"

# aws aliases
# alias gimme-aws-creds
alias gim="gimme-aws-creds"

# claude
alias cl="claude --dangerously-skip-permissions --permission-mode plan"
alias cc="claude --dangerously-skip-permissions --permission-mode plan"

# codex
alias codex="codex --dangerously-bypass-approvals-and-sandbox"

# auto alias 
alias cdriiidworkspace="cd $HOME/workspace/riiid/"
alias cdkubernetes="cd ~/workspace/riiid/kubernetes"
alias cdkubernetes-charts="cd ~/workspace/riiid/kubernetes-charts"
alias cdterraform="cd ~/workspace/riiid/terraform"
alias sr="source ~/.zshrc"
alias cdworkspace="cd ~/workspace"
alias open-zshrc="cursor ~/.zshrc"
alias open-kubernetes="cursor ~/workspace/riiid/kubernetes"
alias cdengineering101="cd $HOME/workspace/engineering101/"
alias cdidcrepo="cd $HOME/workspace/riiid/k8s-on-premise/"
alias cdk8sonprem="cd $HOME/workspace/riiid/k8s-on-premise/"

# git
alias gps="g ps"
alias gpull="g pull"

# nvim
alias vim="nvim"
alias vm="nvim"
alias vimkuber="cd ~/workspace/riiid/kubernetes && vim ."
alias vimtf="cd ~/workspace/riiid/terraform && vim ."
alias vimkuberchart="cd ~/workspace/riiid/kubernetes-charts/ && vim ."
alias ob='cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/obsidian_home/ch_home/ && nvim .'
alias HOME="cd $HOME"
alias cdob='cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/obsidian_home/ch_home/'
source ~/powerlevel10k/powerlevel10k.zsh-theme

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Ghostty Configuration
export TERM=xterm-256color
if [[ "$GHOSTTY_RESOURCES_DIR" != "" ]]; then
  # Running in Ghostty - set optimizations
  export GHOSTTY_SHELL_INTEGRATION=detect
fi

export PATH="$HOME/.local/bin:$PATH"
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"

# Python 
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init -)"
  eval "$(pyenv virtualenv-init -)"
fi

# AWS Profile
export AWS_PROFILE=okta-devops

# # gvm
# [[ -s "/Users/changhwan/.gvm/scripts/gvm" ]] && source "/Users/changhwan/.gvm/scripts/gvm" >/dev/null 2>&1

# Added by Antigravity
export PATH="$HOME/.antigravity/antigravity/bin:$PATH"
# GITHUB_MCP_TOKEN moved to ~/.secrets.zsh

# Kiro CLI post block. Keep at the bottom of this file.
[[ -f "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.post.zsh" ]] && builtin source "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.post.zsh"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

alias claude-mem="$HOME/.bun/bin/bun $HOME/.claude/plugins/marketplaces/thedotmack/plugin/scripts/worker-service.cjs"
alias cdk8s="cd $HOME/workspace/riiid/kubernetes"
alias cdonprem="cd $HOME/workspace/riiid/k8s-on-premise"

# === cmux Raycast 워크스페이스 런처 훅 ===
# Raycast 등 cmux 외부 프로세스는 cmux 소켓 CLI(new-workspace/send)를 못 쓴다
# (cmux가 앱 자손이 아닌 클라이언트의 연결을 거부 → Broken pipe). 그래서 외부에서는
# `open -a cmux <dir>`로 워크스페이스만 열고, 초기 프롬프트는 스풀 파일로 넘긴다.
# 이 훅은 새로 열린 cmux 워크스페이스의 zsh가 자기 cwd에 해당하는 스풀 요청을
# 발견하면 그 프롬프트로 claude를 실행한다. (런처: ~/.claude/scripts/claude-session-launch.sh)
# 첫 프롬프트 시점에 claude를 실행하는 일회성 precmd 훅.
# .zshrc 본문에서 직접 실행하면 p10k instant prompt가 stdin/stdout을 가로채
# claude가 TTY 없는 --print 모드로 빠져 실패한다. 셸이 TTY를 완전히 점유한
# 첫 프롬프트로 미뤄야 claude가 정상적으로 대화형 실행된다.
_cmux_raycast_launch() {
  add-zsh-hook -d precmd _cmux_raycast_launch   # 일회성: 즉시 자기 자신 해제
  # claude는 stdin이 tty가 아니면 --print(비대화형) 모드로 빠진다. precmd 시점이라도
  # fd가 리다이렉트된 경우를 대비해 controlling terminal(/dev/tty)에 명시적으로 연결한다.
  if [[ -n "${_CMUX_RAYCAST_PROMPT:-}" ]]; then
    claude "$_CMUX_RAYCAST_PROMPT" < /dev/tty
  else
    claude < /dev/tty
  fi
  unset _CMUX_RAYCAST_PROMPT
}

_cmux_raycast_consume() {
  [[ -o interactive ]] || return                                   # 대화형 셸만
  [[ -n "${CMUX_WORKSPACE_ID:-}" || -n "${CMUX_SURFACE_ID:-}" ]] || return  # cmux 워크스페이스만
  local spool="${XDG_STATE_HOME:-$HOME/.local/state}/cmux-raycast"
  [[ -d "$spool" ]] || return

  # 런처와 동일한 키(물리 경로 sha)로 이 워크스페이스에 대한 요청을 찾는다.
  # printf '%s'로 개행 없이 넘겨야 런처(_cmux_spool_key)와 해시가 일치한다.
  local req
  req="$spool/$(printf '%s' "$(pwd -P)" | shasum | awk '{print $1}').req"
  [[ -f "$req" ]] || return

  # 신선도(TTL 60s) 검사 — 오래된 요청은 오발화 방지를 위해 폐기.
  local now mtime
  now=$(date +%s); mtime=$(stat -f %m "$req" 2>/dev/null || echo 0)
  if (( now - mtime > 60 )); then rm -f "$req"; return; fi

  # 원자적 클레임 — 동시에 뜬 셸 중 하나만 소비(mv 성공자가 소유권 획득).
  local claim="$req.claimed.$$"
  mv "$req" "$claim" 2>/dev/null || return
  _CMUX_RAYCAST_PROMPT=$(cat "$claim"); rm -f "$claim"

  # 실제 claude 실행은 첫 프롬프트(precmd)로 미룬다(위 주석 참고).
  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _cmux_raycast_launch
}
_cmux_raycast_consume
# === /cmux Raycast 워크스페이스 런처 훅 ===
