# Kiro CLI pre block. Keep at the top of this file.
[[ -f "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.pre.zsh" ]] && builtin source "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.pre.zsh"
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="robbyrussell"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
# zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
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

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='nvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch $(uname -m)"

# Set personal aliases, overriding those provided by Oh My Zsh libs,
# plugins, and themes. Aliases can be placed here, though Oh My Zsh
# users are encouraged to define aliases within a top-level file in
# the $ZSH_CUSTOM folder, with .zsh extension. Examples:
# - $ZSH_CUSTOM/aliases.zsh
# - $ZSH_CUSTOM/macos.zsh
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
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
source ~/.kubernetes/kube-ps1/kube-ps1.sh
PROMPT='$(kube_ps1)'$PROMPT
KUBE_PS1_SYMBOL_ENABLE=false

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
alias kdp="kubectl describe pod"
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
alias netshoot="cd /Users/changhwan/workspace/engineering_home/netshoot"

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

# git
alias gps="g ps"
alias gpull="g pull"

# nvim
alias vim="nvim"
alias vm="nvim"
alias vimkuber="cd ~/workspace/riiid/kubernetes && vim ."
alias vimtf="cd ~/workspace/riiid/terraform && vim ."
alias vimkuberchart="cd ~/workspace/riiid/kubernetes-charts/ $$ vim ."
alias ob='cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/obsidian_home/ch_home/ && nvim .'
alias HOME="cd $HOME"

source ~/powerlevel10k/powerlevel10k.zsh-theme

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Ghostty Configuration
export TERM=xterm-256color
if [[ "$GHOSTTY_RESOURCES_DIR" != "" ]]; then
  # Running in Ghostty - set optimizations
  export GHOSTTY_SHELL_INTEGRATION=detect
fi

export PATH="$HOME/.local/bin:$PATH"export PATH="/opt/homebrew/opt/ruby/bin:$PATH"

# Python 
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# AWS Profile
export AWS_PROFILE=okta-devops

# # gvm
# [[ -s "/Users/changhwan/.gvm/scripts/gvm" ]] && source "/Users/changhwan/.gvm/scripts/gvm" >/dev/null 2>&1

# Added by Antigravity
export PATH="/Users/changhwan/.antigravity/antigravity/bin:$PATH"
# GITHUB_MCP_TOKEN moved to ~/.secrets.zsh

# Kiro CLI post block. Keep at the bottom of this file.
[[ -f "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.post.zsh" ]] && builtin source "${HOME}/Library/Application Support/kiro-cli/shell/zshrc.post.zsh"

# bun completions
[ -s "/Users/changhwan/.bun/_bun" ] && source "/Users/changhwan/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

alias claude-mem='/Users/changhwan/.bun/bin/bun "/Users/changhwan/.claude/plugins/marketplaces/thedotmack/plugin/scripts/worker-service.cjs"'

# Secrets (tokens stored in ~/.secrets.zsh, never committed to git)
[[ -f ~/.secrets.zsh ]] && source ~/.secrets.zsh
