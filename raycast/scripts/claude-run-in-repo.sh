#!/usr/bin/env bash
#
# Raycast Script Command — repo 컨텍스트에서 cmux로 Claude Code 세션을 연다.
# 범용 진입점: repo는 dropdown, 초기 프롬프트(skill 포함)는 자유 입력.
#
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Claude in repo
# @raycast.mode silent
#
# Optional parameters:
# @raycast.packageName Claude Code
# @raycast.icon 🤖
# @raycast.argument1 { "type": "dropdown", "placeholder": "Repo", "data": [ {"title":"kubernetes","value":"kubernetes"}, {"title":"terraform","value":"terraform"}, {"title":"kubernetes-charts","value":"kubernetes-charts"}, {"title":"k8s-on-premise","value":"k8s-on-premise"} ] }
# @raycast.argument2 { "type": "text", "placeholder": "/skill 또는 프롬프트 (생략 가능)", "optional": true }
# @raycast.description repo 컨텍스트에서 cmux 워크스페이스로 Claude Code 세션을 연다

set -uo pipefail

# Raycast는 로그인 셸 PATH를 물려받지 않는다 → cmux(/opt/homebrew/bin) 명시.
export PATH="/opt/homebrew/bin:$PATH"
# Raycast 프로세스는 cmux 밖이라 CMUX_WORKSPACE_ID가 없다 → cmux 경로 강제.
export FORCE_CMUX=1

# cmux 앱을 앞으로 (이미 실행 중이면 activate만; single-instance).
open -a cmux 2>/dev/null || true

repo="${1:-kubernetes}"
prompt="${2:-}"
repo_dir="$HOME/workspace/riiid/$repo"
[ -d "$repo_dir" ] || repo_dir="$HOME"

source "$HOME/.claude/scripts/claude-session-launch.sh"
_build_and_launch_session "$repo_dir" "$prompt" "$repo"

# 워크스페이스 생성 후 cmux를 다시 포그라운드로 (Raycast 종료 시 포커스 복귀 방지)
open -a cmux 2>/dev/null || true
