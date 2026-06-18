#!/usr/bin/env bash
#
# task-tui.sh — fzf/gum 기반 Task-Todo 2계층 TUI.
#
# Level 1: Notion Task(=Project) 목록
# Level 2: 선택 Task의 로컬 Todo 목록 (추가/토글/편집/삭제)
#
# 로직은 Python(todo_store.py/todo_sync.py)에 있고, 이 셸은 화면 표시와
# 키 바인딩만 담당한다. 인터랙티브 fzf는 tty가 필요하므로 Claude 도구 호출
# 안에서는 동작하지 않는다 — 사용자가 `!bash ~/.claude/scripts/task-tui.sh`로
# 직접 실행한다.
#
# 의존성: fzf(필수), gum(선택 — 없으면 read 프롬프트로 degrade)
set -uo pipefail

SKILLS_DIR="$HOME/.claude/skills/tasks:manage/scripts"
STORE="$SKILLS_DIR/todo_store.py"
SYNC="$SKILLS_DIR/todo_sync.py"
NOTION_TASK="$SKILLS_DIR/notion-task.py"
PLAN_TODO="$HOME/.claude/scripts/plan-todo.py"

# NOTION_TOKEN 확보 (sync에 필요). secrets.zsh의 단순 export 라인을 bash로 로드.
[ -z "${NOTION_TOKEN:-}" ] && [ -f "$HOME/.secrets.zsh" ] && source "$HOME/.secrets.zsh" 2>/dev/null

command -v fzf >/dev/null || { echo "fzf 필요: brew install fzf"; exit 1; }

# fzf는 인터랙티브 tty가 필요하다. Claude Code의 `!` 실행이나 파이프 환경에서는
# tty가 없어 TUI가 동작하지 않으므로, 일반 터미널에서 직접 실행하도록 안내한다.
if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "이 TUI는 인터랙티브 터미널이 필요합니다."
  echo "별도 터미널에서 다음을 실행하세요 (앞에 '!' 붙이지 마세요):"
  echo "    ~/.claude/scripts/task-tui.sh"
  exit 1
fi

have_gum() { command -v gum >/dev/null; }

# ── 입력 헬퍼 (gum 우선, 없으면 read) ─────────────────────────

prompt_input() {  # $1=placeholder, $2=기본값(optional)
  if have_gum; then
    gum input --placeholder "$1" --value "${2:-}"
  else
    local v; read -rp "$1: " v; echo "${v:-${2:-}}"
  fi
}

prompt_confirm() {  # $1=메시지 → 0(yes)/1(no)
  if have_gum; then gum confirm "$1"; else
    local a; read -rp "$1 [y/N]: " a; [[ "$a" == [yY] ]]; fi
}

prompt_choose() {  # $@=옵션들 → 선택값 stdout
  if have_gum; then gum choose "$@"; else
    local i=1 opt; for opt in "$@"; do echo "  $i) $opt" >&2; i=$((i+1)); done
    local n; read -rp "번호: " n; echo "${@:$n:1}"; fi
}

run_sync() {  # 전체 양방향 sync (시간 소요 — gum spinner로 피드백)
  if have_gum; then
    gum spin --title "Notion 동기화 중..." -- python3 "$SYNC" sync >/dev/null
  else
    echo "동기화 중..."; python3 "$SYNC" sync >/dev/null
  fi
}

# ── Plan 뷰 함수 ─────────────────────────────────────────────

plan_view() {
  local plan_id="$1"
  while true; do
    local out key line step_num is_done
    out=$(python3 "$PLAN_TODO" steps-fzf --plan-id "$plan_id" \
      | fzf --delimiter='\t' --with-nth='2..' --ansi \
            --layout=reverse \
            --header="📋 $plan_id   enter:done/pending 토글  ctrl-l:새로고침  esc:뒤로" \
            --expect=enter,ctrl-l)
    [ -z "$out" ] && return
    key=$(sed -n 1p <<<"$out")
    line=$(sed -n 2p <<<"$out")
    step_num=$(cut -f1 <<<"$line")
    [ "$step_num" = "0" ] && continue  # sentinel (steps 없음 / plan not found)
    case "$key" in
      enter)
        if [ -n "$step_num" ]; then
          is_done=$(python3 "$PLAN_TODO" steps-fzf --plan-id "$plan_id" \
            | awk -F'\t' -v s="$step_num" '$1==s{print $2}' | grep -c "✅" || true)
          if [ "${is_done:-0}" -ge 1 ]; then
            python3 "$PLAN_TODO" uncheck "$step_num" --plan-id "$plan_id" >/dev/null
          else
            python3 "$PLAN_TODO" check "$step_num" --plan-id "$plan_id" >/dev/null
          fi
        fi ;;
      ctrl-l) ;;  # loop → 자동 새로고침
    esac
  done
}

link_plan_to_target() {
  local target="$1"  # "task" | "todo"
  local id="$2"
  local selection plan_id
  selection=$(python3 "$PLAN_TODO" list-fzf \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --layout=reverse \
          --header="연결할 Plan 선택  (첫 줄=해제)  esc:취소")
  [ -z "$selection" ] && return
  plan_id=$(cut -f1 <<<"$selection")
  [ "$plan_id" = "__none__" ] && plan_id=""
  python3 "$STORE" link-plan --target "$target" --id "$id" --plan-id "$plan_id" >/dev/null
}

# ── Level 2: Todo 목록 ────────────────────────────────────────

todo_menu() {
  local page_id="$1"
  while true; do
    local out key line todo_id
    out=$(python3 "$STORE" list-todos --task "$page_id" --format fzf \
      | fzf --delimiter='\t' --with-nth='2..' --ansi \
            --header="enter:토글  ctrl-a:추가  ctrl-e:편집  ctrl-d:삭제  ctrl-p:Plan뷰  ctrl-l:새로고침  ctrl-r:sync  esc:뒤로" \
            --expect=enter,ctrl-a,ctrl-e,ctrl-d,ctrl-l,ctrl-r,ctrl-p)
    [ -z "$out" ] && return  # esc/취소 → Level 1 복귀
    key=$(sed -n 1p <<<"$out")
    line=$(sed -n 2p <<<"$out")
    todo_id=$(cut -f1 <<<"$line")
    case "$key" in
      enter)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;
      ctrl-a)  local t; t=$(prompt_input "새 todo 제목"); [ -n "$t" ] && python3 "$STORE" add --task "$page_id" --title "$t" >/dev/null ;;
      ctrl-e)  [ -z "$todo_id" ] && continue
               local cur t; cur=$(cut -f2- <<<"$line" | sed 's/^[☐☑] //; s/  \*$//')
               t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
      ctrl-d)  [ -z "$todo_id" ] && continue
               prompt_confirm "이 todo를 삭제할까요?" && python3 "$STORE" delete --id "$todo_id" >/dev/null ;;
      ctrl-p)
               local plan_id
               if [ -n "$todo_id" ]; then
                 plan_id=$(python3 "$STORE" list-todos --task "$page_id" --format json \
                   | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t.get('plan_id','') for t in d['todos'] if t['id']=='$todo_id'),''))")
                 if [ -n "$plan_id" ]; then
                   plan_view "$plan_id"
                 else
                   link_plan_to_target "todo" "$todo_id"
                 fi
               else
                 plan_id=$(python3 "$STORE" list-tasks --format json \
                   | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t.get('plan_id','') for t in d['tasks'] if t['page_id']=='$page_id'),''))")
                 if [ -n "$plan_id" ]; then
                   plan_view "$plan_id"
                 else
                   link_plan_to_target "task" "$page_id"
                 fi
               fi ;;
      ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-todos 재렌더
      ctrl-r)  run_sync ;;
    esac
  done
}

# ── 탭 UI: Tasks 탭 / Todos 탭 (tab 키로 전환) ────────────────

# 현재 탭 상태 — Tasks(Notion Project 목록) ↔ Todos(전체 평면 목록)
TAB="tasks"
NAV=""           # 탭 함수가 "quit"을 세우면 최상위 루프 종료
REPO_FILTER=""   # Todos 탭의 repo 필터 (빈값 = 전체)
PRIO_FILTER="P1" # Tasks 탭의 우선순위 필터 (P1|P2|P3|P4|"" 전체)

tab_bar() {
  if [ "$TAB" = "tasks" ]; then echo "[ ●Tasks │ ○Todos ]"; else echo "[ ○Tasks │ ●Todos ]"; fi
}

prio_bar() {
  local labels=("P1" "P2" "P3" "ALL")
  local out=""
  for p in "${labels[@]}"; do
    local key="${p}"; [ "$p" = "ALL" ] && key=""
    if [ "$PRIO_FILTER" = "$key" ]; then
      out+="●${p} "
    else
      out+="○${p} "
    fi
  done
  echo "[${out% }]"
}

run_import() {
  if have_gum; then gum spin --title "memory에서 Todos로 import 중..." -- python3 "$STORE" import-memory >/dev/null
  else echo "import 중..."; python3 "$STORE" import-memory >/dev/null; fi
}

# Tasks 탭: Notion Task(Project) 목록 — enter로 해당 Task의 Todo로 드릴인
tasks_tab() {
  local out key line page_id prio_arg
  prio_arg=${PRIO_FILTER:+--priority "$PRIO_FILTER"}
  out=$(python3 "$STORE" list-tasks --format fzf $prio_arg \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-task {1}" --preview-window=right:48% \
          --header="$(tab_bar) $(prio_bar)  ctrl-t:탭전환  1/2/3/0:우선순위  enter:todo목록  ctrl-p:Plan뷰  ctrl-l:새로고침  ctrl-r:sync  ctrl-s:상태  ctrl-n:새Task  ctrl-i:import  esc:종료" \
          --expect=enter,tab,ctrl-t,ctrl-l,ctrl-r,ctrl-s,ctrl-n,ctrl-i,ctrl-p,1,2,3,0)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); page_id=$(cut -f1 <<<"$line")
  case "$key" in
    tab|ctrl-t) TAB="todos" ;;
    1) PRIO_FILTER="P1" ;;
    2) PRIO_FILTER="P2" ;;
    3) PRIO_FILTER="P3" ;;
    0) PRIO_FILTER="" ;;
    enter)   [ -n "$page_id" ] && todo_menu "$page_id" ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-tasks 재렌더
    ctrl-r)  run_sync ;;
    ctrl-s)  [ -z "$page_id" ] && return
             [ "$page_id" = "__backlog__" ] && return  # Backlog은 Notion 상태 없음
             local st; st=$(prompt_choose "시작 전" "진행 중" "완료" "대기")
             [ -n "$st" ] && python3 "$STORE" set-task-status --task "$page_id" --status "$st" >/dev/null ;;
    ctrl-n)  create_task ;;
    ctrl-i)  run_import ;;
    ctrl-p)  [ -z "$page_id" ] || [ "$page_id" = "__backlog__" ] && return
             local plan_id
             plan_id=$(python3 "$STORE" list-tasks --format json \
               | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t.get('plan_id','') for t in d['tasks'] if t['page_id']=='$page_id'),''))")
             if [ -n "$plan_id" ]; then
               plan_view "$plan_id"
             else
               link_plan_to_target "task" "$page_id"
             fi ;;
  esac
}

# 현재 repo 필터를 적용해 평면 Todo 목록을 만든다(빈값이면 전체).
list_todos_filtered() {
  if [ -n "$REPO_FILTER" ]; then
    python3 "$STORE" list-all-todos --format fzf --repo "$REPO_FILTER"
  else
    python3 "$STORE" list-all-todos --format fzf
  fi
}

# repo 선택 필터 — 현재 Todo들에 존재하는 repo만 골라 gum choose로 선택
choose_repo() {
  local repos sel; local -a opts=("전체")
  repos=$(python3 "$STORE" list-all-todos --format json \
    | python3 -c "import sys,json;rs=sorted({t.get('repo','') for t in json.load(sys.stdin)['todos'] if t.get('repo')});print('\n'.join(rs))")
  [ -z "$repos" ] && { echo "repo 라벨이 있는 Todo가 없습니다 (import된 Todos가 repo를 가짐)"; sleep 1; return; }
  while IFS= read -r r; do [ -n "$r" ] && opts+=("$r"); done <<<"$repos"
  sel=$(prompt_choose "${opts[@]}")
  case "$sel" in ""|전체) REPO_FILTER="" ;; *) REPO_FILTER="$sel" ;; esac
}

# Todo Enter → 해당 레포 디렉토리에서 Claude Code 세션 오픈
open_todo_session() {
  local todo_id="$1"

  local todo_json
  todo_json=$(python3 "$STORE" get --id "$todo_id" 2>/dev/null)
  [ -z "$todo_json" ] && return 1

  local title repo plan_id ctx
  title=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('title',''))"   <<<"$todo_json")
  repo=$(python3  -c "import sys,json; d=json.load(sys.stdin); print(d.get('repo',''))"    <<<"$todo_json")
  plan_id=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('plan_id',''))" <<<"$todo_json")
  ctx=$(python3   -c "import sys,json; d=json.load(sys.stdin); print(d.get('context',''))" <<<"$todo_json")

  # 레포 디렉토리 결정 (기본: ~/)
  local repo_dir="$HOME"
  if [ -n "$repo" ]; then
    local candidate="$HOME/workspace/riiid/$repo"
    [ -d "$candidate" ] && repo_dir="$candidate"
  fi

  # Claude Code 초기 메시지 — 줄바꿈 포함 문자열을 nl 변수로 안전하게 구성
  local nl=$'\n'
  local msg="이 세션에서 다음 Todo를 수행합니다.${nl}Todo: $title"
  [ -n "$ctx" ]     && msg+="${nl}작업: $ctx"
  [ -n "$repo" ]    && msg+="${nl}레포: $repo"
  [ -n "$plan_id" ] && msg+="${nl}Plan: $plan_id"

  # 중첩 quote 이슈를 피하기 위해 런처 스크립트로 분리
  local launcher
  launcher=$(mktemp /tmp/claude-todo-launch.XXXXXX.sh)
  {
    echo "#!/bin/bash"
    printf 'cd %q\n' "$repo_dir"
    printf 'claude %q\n' "$msg"
    printf 'rm -f %q\n' "$launcher"
  } > "$launcher"
  chmod +x "$launcher"

  _launch_claude_session "$repo_dir" "$launcher"
}

_launch_claude_session() {
  local dir="$1" launcher="$2"

  if [ -n "${TMUX:-}" ]; then
    tmux new-window -c "$dir" -n "todo" bash "$launcher"
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

# Todos 탭: 모든 Todo를 평면으로 — 소속 Task/Backlog + [repo] 표시, ctrl-g로 repo 필터
todos_tab() {
  local out key line todo_id cur t fhdr
  fhdr=${REPO_FILTER:+ [repo:$REPO_FILTER]}
  out=$(list_todos_filtered \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --header="$(tab_bar)$fhdr  enter:세션열기  ctrl-t:탭전환  space:완료토글  ctrl-a:추가  ctrl-e:편집  ctrl-d:삭제  ctrl-p:Plan뷰  ctrl-g:repo필터  ctrl-l:새로고침  ctrl-r:sync  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-a,ctrl-e,ctrl-d,ctrl-g,ctrl-l,ctrl-r,ctrl-p)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); todo_id=$(cut -f1 <<<"$line")
  case "$key" in
    enter)  [ -n "$todo_id" ] && open_todo_session "$todo_id" ;;
    tab|ctrl-t) TAB="tasks" ;;
    space)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;
    ctrl-a)  t=$(prompt_input "새 Backlog todo"); [ -n "$t" ] && python3 "$STORE" add --task __backlog__ --title "$t" ${REPO_FILTER:+--repo "$REPO_FILTER"} >/dev/null ;;
    ctrl-e)  [ -z "$todo_id" ] && return
             cur=$(python3 "$STORE" list-all-todos --format json | python3 -c "import sys,json;print(next((x['title'] for x in json.load(sys.stdin)['todos'] if x['id']=='$todo_id'),''))")
             t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
    ctrl-d)  [ -z "$todo_id" ] && return
             prompt_confirm "이 todo를 삭제할까요?" && python3 "$STORE" delete --id "$todo_id" >/dev/null ;;
    ctrl-p)  [ -z "$todo_id" ] && return
             local plan_id
             plan_id=$(python3 "$STORE" list-all-todos --format json \
               | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t.get('plan_id','') for t in d['todos'] if t['id']=='$todo_id'),''))")
             if [ -n "$plan_id" ]; then
               plan_view "$plan_id"
             else
               link_plan_to_target "todo" "$todo_id"
             fi ;;
    ctrl-g)  choose_repo ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-all-todos 재렌더
    ctrl-r)  run_sync ;;
  esac
}

main_menu() {
  NAV=""
  while true; do
    if [ "$TAB" = "tasks" ]; then tasks_tab; else todos_tab; fi
    [ "$NAV" = "quit" ] && return
  done
}

create_task() {
  local name pri cat
  name=$(prompt_input "새 Task 이름"); [ -z "$name" ] && return
  pri=$(prompt_choose "P1 - Must Have" "P2 - Should Have" "P3 - Could Have" "P4 - Won't Have")
  cat=$(prompt_choose "WORK" "MY")
  [ -z "$pri" ] || [ -z "$cat" ] && return
  python3 "$NOTION_TASK" create-task --name "$name" --priority "$pri" --category "$cat" >/dev/null \
    && echo "생성됨. 동기화로 목록 갱신..." && run_sync
}

# ── 진입: 시작 시 pull, 종료 시 push ──────────────────────────

final_push() { python3 "$SYNC" push >/dev/null 2>&1 || true; }
trap final_push EXIT

# k9s처럼 로컬 캐시로 UI를 즉시 띄운다 — 시작 시 blocking pull을 하지 않는다.
# 갱신은 화면 안에서 ctrl-r로 명시적으로 수행한다(백그라운드 pull은 사용자의
# 로컬 편집과 todos.json 쓰기 경합 → 변경 유실 위험이 있어 의도적으로 배제).
# 단, 캐시가 비어 있는 최초 실행 시에만 1회 pull로 초기 데이터를 채운다.
CACHE="$HOME/.claude/tasktui/tasks.json"
if [ ! -s "$CACHE" ] || ! grep -q '"page_id"' "$CACHE" 2>/dev/null; then
  if have_gum; then gum spin --title "최초 동기화 중..." -- python3 "$SYNC" pull >/dev/null 2>&1 || true
  else echo "최초 동기화 중 (한 번만)..."; python3 "$SYNC" pull >/dev/null 2>&1 || true; fi
fi

main_menu
