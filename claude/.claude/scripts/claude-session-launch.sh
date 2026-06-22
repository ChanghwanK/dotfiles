#!/usr/bin/env bash
#
# claude-session-launch.sh — repo 컨텍스트에서 Claude Code 세션을 여는 공유 런처.
#
# source 전용 라이브러리(직접 실행 X). task-tui.sh와 Raycast Script Command가
# 함께 source하여 cmux 호출 방식을 단일 SoT로 유지한다.
#
# 공개 함수:
#   _build_and_launch_session <repo_dir> <msg> [title]
#       repo_dir에서 초기 메시지(msg)와 함께 Claude Code 세션을 띄운다.
#   _launch_claude_session <dir> <launcher> [title]
#       실행 환경(cmux 내부 / tmux / ghostty / iTerm2 / Terminal)을 감지해 새 창을 연다.
#
# 두 가지 cmux 진입 경로 (호출자 위치에 따라 갈린다):
#   1) cmux 내부 (CMUX_WORKSPACE_ID/CMUX_SURFACE_ID 존재)
#      → cmux 소켓 CLI(new-workspace/send)로 워크스페이스 생성 + 명령 주입.
#   2) cmux 외부 (예: Raycast, FORCE_CMUX=1)
#      → cmux 소켓 CLI는 "cmux 앱 자손 프로세스"만 허용하므로 거부된다
#        (Error: Failed to write to socket, Broken pipe). 외부에서는 `open -a cmux <dir>`
#        Apple event로 cmux 앱이 직접 워크스페이스를 만들게 하고, 초기 프롬프트는
#        스풀 파일로 전달한다. 새 워크스페이스의 zsh 시작 훅(_cmux_raycast_consume,
#        ~/.dotfiles/zsh/.zshrc)이 스풀을 소비해 claude를 실행한다.
#        → 두 메커니즘이 짝을 이루므로 한쪽만 바꾸면 동작이 깨진다.
#
# 주의: 이 파일은 호출자의 `set -uo pipefail` 아래에서 동작하므로 모든 선택적
#       변수는 ${var:-} 기본값으로 가드한다 (단독 source 시에도 안전).

# cmux 외부 프로세스가 워크스페이스 요청 프롬프트를 남기는 스풀 디렉터리.
# zsh 시작 훅과 반드시 동일 경로를 써야 매칭된다.
_CMUX_SPOOL_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/cmux-raycast"

# 디렉터리 경로 → 스풀 파일명 안전 키. 런처와 zsh 훅이 동일 알고리즘을 써야 한다.
_cmux_spool_key() { printf '%s' "$1" | shasum | awk '{print $1}'; }

# cmux 외부(Raycast 등) 전용: open Apple event로 워크스페이스를 만들고 프롬프트를 스풀에 남긴다.
# 소켓 CLI를 쓰지 않으므로 cmux 앱 자손이 아니어도 동작한다.
_cmux_open_spool_launch() {
  local dir="$1" prompt="$2"
  # 심볼릭 링크 차이로 키가 어긋나지 않도록 물리 경로로 정규화 (zsh 훅도 pwd -P 사용).
  local dir_phys
  dir_phys=$(cd "$dir" 2>/dev/null && pwd -P) || dir_phys="$dir"

  mkdir -p "$_CMUX_SPOOL_DIR"
  local req
  req="$_CMUX_SPOOL_DIR/$(_cmux_spool_key "$dir_phys").req"
  printf '%s' "$prompt" > "$req"

  # cmux 앱에 디렉터리 오픈 이벤트 전송 → 앱이 새 워크스페이스를 생성한다(소켓 우회).
  open -a cmux "$dir_phys"
}

# repo_dir에서 초기 메시지(msg)와 함께 Claude Code 세션을 띄운다.
_build_and_launch_session() {
  local repo_dir="$1" msg="$2" title="${3:-todo}"

  # cmux 외부에서 cmux 강제(Raycast 등): 소켓 CLI가 거부되므로 open + 스풀 경로로 분기.
  if [ "${FORCE_CMUX:-}" = 1 ] && [ -z "${CMUX_WORKSPACE_ID:-}" ] && [ -z "${CMUX_SURFACE_ID:-}" ]; then
    _cmux_open_spool_launch "$repo_dir" "$msg"
    return
  fi

  # 그 외(cmux 내부 / 일반 터미널): 메시지를 임시 파일에 담아 launcher 스크립트로 실행.
  #   macOS BSD mktemp는 X가 템플릿 "끝"에 있을 때만 치환한다. `.txt`/`.sh` 접미사를
  #   붙이면 X를 그대로 둔 리터럴 파일을 만들고, 재실행 때 "File exists"로 실패한다
  #   → 끝-고정 템플릿 + fallback으로 막는다.
  local msg_file launcher
  msg_file=$(mktemp "${TMPDIR:-/tmp}/claude-todo-msg.XXXXXX" 2>/dev/null) || \
    msg_file="/tmp/claude-todo-msg.$$.$(date +%s)"
  printf '%s' "$msg" > "$msg_file"

  launcher=$(mktemp "${TMPDIR:-/tmp}/claude-todo-launch.XXXXXX" 2>/dev/null) || \
    launcher="/tmp/claude-todo-launch.$$.$(date +%s)"
  {
    echo "#!/bin/bash"
    printf 'cd %q\n' "$repo_dir"
    printf 'claude "$(cat %q)"\n' "$msg_file"
    printf 'rm -f %q %q\n' "$launcher" "$msg_file"
  } > "$launcher"
  chmod +x "$launcher"

  _launch_claude_session "$repo_dir" "$launcher" "$title"
}

_launch_claude_session() {
  local dir="$1" launcher="$2" title="${3:-todo}"

  # cmux 내부에서만 소켓 CLI를 쓴다. 외부(FORCE_CMUX)는 _build_and_launch_session에서
  # 이미 open+스풀로 분기되므로 여기 도달하지 않는다 (도달 시 터미널 폴백으로 안전하게 처리).
  if [ -n "${CMUX_WORKSPACE_ID:-}" ] || [ -n "${CMUX_SURFACE_ID:-}" ]; then
    # cmux: 워크스페이스 생성 → shell 준비 대기 → send로 명령 주입
    # (--command는 shell 초기화 전 실행돼 PATH 미설정 문제 발생)
    local ws_ref ts
    ts=$(date +%H%M)
    ws_ref=$(CMUX_QUIET=1 cmux new-workspace \
      --name "${title:0:26} ${ts}" \
      --cwd "$dir" \
      --focus true 2>/dev/null | grep "^OK " | awk '{print $2}')
    if [ -n "$ws_ref" ]; then
      sleep 0.8  # shell prompt 준비 대기
      CMUX_QUIET=1 cmux send --workspace "$ws_ref" "bash $(printf '%q' "$launcher")"
      CMUX_QUIET=1 cmux send-key --workspace "$ws_ref" "Enter"
    fi
    return
  fi

  if [ -n "${TMUX:-}" ]; then
    tmux new-window -c "$dir" -n "todo" bash "$launcher"
  elif [ "${TERM_PROGRAM:-}" = "ghostty" ]; then
    # ghostty -e로 새 창에서 launcher 실행
    local ghostty_bin
    ghostty_bin=$(command -v ghostty 2>/dev/null || echo "")
    if [ -n "$ghostty_bin" ]; then
      "$ghostty_bin" -e bash "$launcher" &
    else
      bash "$launcher" &
    fi
  elif osascript -e 'tell application "iTerm2" to get version' >/dev/null 2>&1; then
    osascript << APPLESCRIPT
tell application "iTerm2"
  set newWin to (create window with default profile)
  tell current session of newWin
    write text "bash $(printf '%q' "$launcher")"
  end tell
end tell
APPLESCRIPT
  else
    osascript -e "tell application \"Terminal\" to do script \"bash $(printf '%q' "$launcher")\""
  fi
}
