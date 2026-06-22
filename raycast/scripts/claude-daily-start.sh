#!/usr/bin/env bash
#
# Raycast Script Command — /daily:start 전용 hotkey 진입점.
# kubernetes repo를 cwd로 cmux 세션을 열고 /daily:start 를 초기 프롬프트로 주입.
#
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Claude · daily:start
# @raycast.mode silent
#
# Optional parameters:
# @raycast.packageName Claude Code
# @raycast.icon 🌅
# @raycast.description 하루 시작 — /daily:start 세션을 연다

set -uo pipefail

export PATH="/opt/homebrew/bin:$PATH"
export FORCE_CMUX=1
open -a cmux 2>/dev/null || true

source "$HOME/.claude/scripts/claude-session-launch.sh"
_build_and_launch_session "$HOME/workspace/riiid/kubernetes" "/daily:start" "daily:start"

# 워크스페이스 생성 후 cmux를 다시 포그라운드로 (Raycast 종료 시 포커스 복귀 방지)
open -a cmux 2>/dev/null || true
