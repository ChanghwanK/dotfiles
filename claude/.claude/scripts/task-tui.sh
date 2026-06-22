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

# Claude Code 세션 런처(공유) — _build_and_launch_session / _launch_claude_session 제공.
# Raycast Script Command도 같은 파일을 source하여 cmux 호출을 단일 SoT로 유지한다.
source "$HOME/.claude/scripts/claude-session-launch.sh"

# NOTION_TOKEN 확보 (sync에 필요). secrets.zsh의 단순 export 라인을 bash로 로드.
[ -z "${NOTION_TOKEN:-}" ] && [ -f "$HOME/.secrets.zsh" ] && source "$HOME/.secrets.zsh" 2>/dev/null

# ── CLI 서브커맨드: add / --add / add-task / --add-task ──────────
# TUI 없이 Backlog(또는 특정 Task)에 Todo를, 또는 Notion Task(=Project)를
# 즉시 추가한다.
#
# Todo 추가 — 인터랙티브 모드 (제목 입력 프롬프트):
#   todo --add                    → gum input으로 제목 입력 후 Backlog에 추가
#
# Todo 추가 — 논인터랙티브 모드 (Claude `!` 실행, 파이프 환경):
#   todo add "제목"               → Backlog에 즉시 추가
#   todo add "제목" --task <id>   → 특정 Task에 추가
#   todo add "제목" --repo <repo> --status 진행중
#
# Task 추가 — 인터랙티브 모드 (이름→우선순위→카테고리→마감일 순서 입력):
#   todo --add-task               → gum 프롬프트로 Notion Task 생성
#   todo --add-task "이름"        → 이름만 인자로, 나머지는 프롬프트
#
# Task 추가 — 논인터랙티브 모드:
#   todo add-task "이름"                              → P3/WORK 기본값으로 생성
#   todo add-task "이름" --priority "P1 - Must Have" --category MY --due 2026-06-30

# --add 플래그: 제목을 gum input으로 입력받아 Backlog에 추가
if [ "${1:-}" = "--add" ]; then
  shift
  _ADD_TITLE="${1:-}"
  if [ -z "$_ADD_TITLE" ]; then
    if command -v gum >/dev/null; then
      _ADD_TITLE=$(gum input --placeholder "새 todo 제목..." --width 60)
    else
      read -rp "새 todo 제목: " _ADD_TITLE
    fi
  fi
  [ -z "$_ADD_TITLE" ] && exit 0
  python3 "$STORE" add --task __backlog__ --title "$_ADD_TITLE"
  exit $?
fi

# add 서브커맨드: 논인터랙티브, 추가 옵션 지원
if [ "${1:-}" = "add" ]; then
  shift
  if [ $# -eq 0 ]; then
    echo "usage: todo add <제목> [--task <page_id>] [--repo <repo>] [--description <text>] [--status 시작전|진행중|완료]" >&2
    exit 1
  fi
  _ADD_TITLE="$1"; shift
  _ADD_TASK="__backlog__"
  _ADD_EXTRA=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --task)        _ADD_TASK="$2"; shift 2 ;;
      --repo)        _ADD_EXTRA+=(--repo "$2"); shift 2 ;;
      --description) _ADD_EXTRA+=(--description "$2"); shift 2 ;;
      --status)      _ADD_EXTRA+=(--status "$2"); shift 2 ;;
      *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
    esac
  done
  python3 "$STORE" add --task "$_ADD_TASK" --title "$_ADD_TITLE" "${_ADD_EXTRA[@]}"
  exit $?
fi

# --add-task 플래그: Notion Task(=Project)를 대화형으로 생성한다.
# Task는 name/priority/category가 필수이므로 gum 프롬프트로 순서대로 입력받는다
# (gum 없으면 read로 degrade). 기본값은 백로그 적재에 흔한 P3/WORK.
if [ "${1:-}" = "--add-task" ]; then
  shift
  _TASK_NAME="${1:-}"
  if [ -z "$_TASK_NAME" ]; then
    if command -v gum >/dev/null; then
      _TASK_NAME=$(gum input --placeholder "새 Task 이름..." --width 60)
    else
      read -rp "새 Task 이름: " _TASK_NAME
    fi
  fi
  [ -z "$_TASK_NAME" ] && exit 0

  if command -v gum >/dev/null; then
    _TASK_PRIO=$(gum choose --header "우선순위" --selected "P3 - Could Have" \
      "P1 - Must Have" "P2 - Should Have" "P3 - Could Have" "P4 - Won't Have")
    _TASK_CAT=$(gum choose --header "카테고리" --selected "WORK" "WORK" "MY")
    _TASK_DUE=$(gum input --placeholder "마감일 YYYY-MM-DD (선택 — 비우면 없음)")
  else
    read -rp "우선순위 [P3 - Could Have]: " _TASK_PRIO; _TASK_PRIO="${_TASK_PRIO:-P3 - Could Have}"
    read -rp "카테고리 WORK/MY [WORK]: " _TASK_CAT; _TASK_CAT="${_TASK_CAT:-WORK}"
    read -rp "마감일 YYYY-MM-DD (선택): " _TASK_DUE
  fi
  # 프롬프트를 ESC로 취소하면 빈 값 — 생성하지 않고 종료
  [ -z "$_TASK_PRIO" ] && exit 0
  [ -z "$_TASK_CAT" ]  && exit 0

  _TASK_EXTRA=()
  [ -n "$_TASK_DUE" ] && _TASK_EXTRA+=(--due "$_TASK_DUE")
  python3 "$NOTION_TASK" create-task \
    --name "$_TASK_NAME" --priority "$_TASK_PRIO" --category "$_TASK_CAT" "${_TASK_EXTRA[@]}"
  exit $?
fi

# add-task 서브커맨드: 논인터랙티브 Task 생성 (Claude `!` 실행, 파이프 환경)
if [ "${1:-}" = "add-task" ]; then
  shift
  if [ $# -eq 0 ]; then
    echo "usage: todo add-task <이름> [--priority \"P3 - Could Have\"] [--category WORK|MY] [--due YYYY-MM-DD] [--description <text>]" >&2
    exit 1
  fi
  _TASK_NAME="$1"; shift
  _TASK_PRIO="P3 - Could Have"
  _TASK_CAT="WORK"
  _TASK_EXTRA=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --priority)    _TASK_PRIO="$2"; shift 2 ;;
      --category)    _TASK_CAT="$2"; shift 2 ;;
      --due)         _TASK_EXTRA+=(--due "$2"); shift 2 ;;
      --description) _TASK_EXTRA+=(--description "$2"); shift 2 ;;
      *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
    esac
  done
  python3 "$NOTION_TASK" create-task \
    --name "$_TASK_NAME" --priority "$_TASK_PRIO" --category "$_TASK_CAT" "${_TASK_EXTRA[@]}"
  exit $?
fi

# today 서브커맨드: 비인터랙티브 텍스트 뷰 (Claude `!` 실행 등 non-TTY 환경용)
#   todo today   → 오늘 처리할 Task/Todo를 지남/오늘/진행 그룹으로 출력
if [ "${1:-}" = "today" ]; then
  shift
  python3 "$STORE" today --format text
  exit $?
fi

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
            --preview "python3 '$STORE' preview-todo {1}" --preview-window=right:42% \
            --header="enter:Claude열기  space:상태전환(□▷✓)  ctrl-a:추가  ctrl-e:편집  ctrl-n:설명편집  ctrl-d:삭제  ctrl-p:Plan뷰  ctrl-l:새로고침  ctrl-r:sync  esc:뒤로" \
            --expect=enter,space,ctrl-a,ctrl-e,ctrl-n,ctrl-d,ctrl-l,ctrl-r,ctrl-p)
    [ -z "$out" ] && return  # esc/취소 → Level 1 복귀
    key=$(sed -n 1p <<<"$out")
    line=$(sed -n 2p <<<"$out")
    todo_id=$(cut -f1 <<<"$line")
    case "$key" in
      enter)   [ -n "$todo_id" ] && open_todo_session "$todo_id" ;;
      space)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;
      ctrl-a)  local t; t=$(prompt_input "새 todo 제목"); [ -n "$t" ] && python3 "$STORE" add --task "$page_id" --title "$t" >/dev/null ;;
      ctrl-e)  [ -z "$todo_id" ] && continue
               local cur t; cur=$(cut -f2- <<<"$line" | sed 's/^[☐☑] //; s/  \*$//')
               t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
      ctrl-n)  [ -z "$todo_id" ] && continue
               local cur_desc new_desc
               cur_desc=$(python3 "$STORE" get --id "$todo_id" 2>/dev/null \
                 | python3 -c "import sys,json;print(json.load(sys.stdin).get('description',''))" 2>/dev/null)
               if have_gum; then
                 new_desc=$(gum write --placeholder "배경, 문제, 이유 등 자유 기술..." \
                   --value "$cur_desc" --width 72 --height 8)
               else
                 local tmp; tmp=$(mktemp /tmp/todo-desc.XXXX.txt)
                 printf '%s' "$cur_desc" > "$tmp"
                 "${EDITOR:-vi}" "$tmp"
                 new_desc=$(cat "$tmp"); rm -f "$tmp"
               fi
               python3 "$STORE" edit --id "$todo_id" --title "" \
                 --description "$new_desc" --description-only >/dev/null ;;
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

# 현재 탭 상태 — Todos(전체 평면 목록) ↔ Tasks(Notion Project 목록)
TAB="todos"
NAV=""           # 탭 함수가 "quit"을 세우면 최상위 루프 종료
REPO_FILTER=""   # Todos 탭의 repo 필터 (빈값 = 전체)
PRIO_FILTER="P1" # Tasks 탭의 우선순위 필터 (P1|P2|P3|P4|"" 전체)
TODAY_OVERDUE="0" # Today 탭의 지남(overdue) 표시 여부 (0=숨김 기본, 1=표시 / ctrl-o 토글)

tab_bar() {
  local a="○Todos" b="○Tasks" c="○Today"
  case "$TAB" in
    todos) a="●Todos" ;;
    tasks) b="●Tasks" ;;
    today) c="●Today" ;;
  esac
  echo "[ $a │ $b │ $c ]"
}

# ctrl-t/tab: todos → tasks → today → todos 순환
next_tab() {
  case "$TAB" in
    todos) TAB="tasks" ;;
    tasks) TAB="today" ;;
    today) TAB="todos" ;;
  esac
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

# Notion Task(=Project)의 Notion 페이지를 연다.
# page_id는 Notion 페이지 UUID이므로 dash를 제거한 32-hex가 곧 Notion URL 슬러그다.
# 데스크톱 앱(notion:// 딥링크) 우선 — 앱 미설치로 핸들러가 없으면 open이 실패하므로
# 웹(https://www.notion.so)으로 fallback한다.
open_notion_page() {
  local page_id="$1"
  [ -z "$page_id" ] && return
  [ "$page_id" = "__backlog__" ] && return  # Backlog은 Notion 페이지가 없음
  local slug="${page_id//-/}"
  open "notion://www.notion.so/$slug" 2>/dev/null \
    || open "https://www.notion.so/$slug"
}

# Tasks 탭에서 선택 Task를 삭제한다.
# Notion API에는 페이지 영구 삭제 엔드포인트가 없다 — 삭제는 archived:true로
# 휴지통에 보내는 것이며, 이것이 Notion UI의 "삭제"와 동일한 동작이다.
# Notion 삭제 성공 시에만 로컬 캐시(tasks + 하위 todo)를 제거해 화면을 즉시
# 갱신한다. Notion 호출이 실패하면 로컬은 건드리지 않는다(정합성 보호).
# Backlog은 Task가 아니므로 제외.
delete_task() {
  local page_id="$1"
  [ -z "$page_id" ] && return
  [ "$page_id" = "__backlog__" ] && { echo "Backlog은 삭제할 수 없습니다"; sleep 1; return; }
  local name
  name=$(python3 "$STORE" list-tasks --format json \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t['name'] for t in d['tasks'] if t['page_id']=='$page_id'),''))")
  prompt_confirm "이 Task를 삭제할까요?  $name" || return
  local ok
  if have_gum; then
    gum spin --title "Notion에서 Task 삭제 중..." -- \
      python3 "$NOTION_TASK" delete-task --page-id "$page_id" >/dev/null
    ok=$?
  else
    echo "Notion에서 Task 삭제 중..."
    python3 "$NOTION_TASK" delete-task --page-id "$page_id" >/dev/null
    ok=$?
  fi
  if [ "$ok" -eq 0 ]; then
    python3 "$STORE" delete-task-local --task "$page_id" >/dev/null
  else
    echo "Notion 삭제 실패 — 로컬 변경 없음"; sleep 1
  fi
}

# Tasks 탭: Notion Task(Project) 목록.
#   enter=Task 단위 Claude 세션 / space=하위 Todo 드릴인 /
#   ctrl-d=Task 삭제(Notion)
tasks_tab() {
  local out key line page_id prio_arg
  prio_arg=${PRIO_FILTER:+--priority "$PRIO_FILTER"}
  out=$(python3 "$STORE" list-tasks --format fzf $prio_arg \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-task {1}" --preview-window=right:48% \
          --header="$(tab_bar) $(prio_bar)  ctrl-t:탭전환  1:P1 2:P2 3:P3 0:전체  enter:Claude세션  space:todo목록  ctrl-d:Task삭제  ctrl-o:Notion열기  ctrl-p:Plan뷰  ctrl-l:새로고침  ctrl-r:sync  ctrl-s:상태  ctrl-n:새Task  ctrl-i:import  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-d,ctrl-o,ctrl-l,ctrl-r,ctrl-s,ctrl-n,ctrl-i,ctrl-p,1,2,3,0)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); page_id=$(cut -f1 <<<"$line")
  case "$key" in
    tab|ctrl-t) next_tab ;;
    1) PRIO_FILTER="P1" ;;
    2) PRIO_FILTER="P2" ;;
    3) PRIO_FILTER="P3" ;;
    0) PRIO_FILTER="" ;;
    enter)   [ -n "$page_id" ] && open_task_session "$page_id" ;;
    space)   [ -n "$page_id" ] && todo_menu "$page_id" ;;
    ctrl-d)  [ -n "$page_id" ] && delete_task "$page_id" ;;
    ctrl-o)  [ -n "$page_id" ] && open_notion_page "$page_id" ;;
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

# repo 미지정 todo를 열 때, riiid 작업공간의 디렉토리를 골라 cwd로 쓴다.
# 선택값은 이번 세션 열기에만 적용하고 todo의 repo 필드에는 저장하지 않는다
# (TUI에 repo 편집 수단이 없어, 잘못 저장하면 되돌릴 길이 없기 때문).
# stdout으로 repo 이름만 반환(없으면 빈 문자열). 호출부에서 fzf 출력만 캡처하도록
# fzf의 화면 출력은 /dev/tty로 보낸다.
pick_riiid_repo() {
  local root="$HOME/workspace/riiid"
  [ -d "$root" ] || return 0
  ( cd "$root" && ls -d */ 2>/dev/null | sed 's#/$##' ) \
    | fzf --layout=reverse --height=40% \
          --header="repo 미지정 — 세션을 열 repo 선택 (esc: riiid 루트)"
}

# Todo Enter → 해당 레포 디렉토리에서 Claude Code 세션 오픈
open_todo_session() {
  local todo_id="$1"

  local todo_json
  todo_json=$(python3 "$STORE" get --id "$todo_id" 2>/dev/null)
  [ -z "$todo_json" ] && return 1

  local title repo plan_id desc
  title=$(python3   -c "import sys,json; d=json.load(sys.stdin); print(d.get('title',''))"       <<<"$todo_json")
  repo=$(python3    -c "import sys,json; d=json.load(sys.stdin); print(d.get('repo',''))"         <<<"$todo_json")
  plan_id=$(python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('plan_id',''))"     <<<"$todo_json")
  desc=$(python3    -c "import sys,json; d=json.load(sys.stdin); print(d.get('description',''))" <<<"$todo_json")

  # 레포 디렉토리 결정.
  # - repo 필드가 있고 디렉토리가 존재 → $HOME/workspace/riiid/<repo>
  # - repo 미지정 → riiid 작업공간에서 repo를 골라 그 디렉토리로 연다(선택은 저장 안 함).
  #   고르지 않고 esc로 취소하면 riiid 작업공간 루트로 연다.
  # - riiid 워크스페이스가 없는 머신에서는 $HOME으로 최종 fallback.
  local riiid_root="$HOME/workspace/riiid"
  local repo_dir="$riiid_root"
  [ -d "$repo_dir" ] || repo_dir="$HOME"
  if [ -n "$repo" ]; then
    local candidate="$riiid_root/$repo"
    [ -d "$candidate" ] && repo_dir="$candidate"
  elif [ -d "$riiid_root" ]; then
    local picked; picked=$(pick_riiid_repo)
    [ -n "$picked" ] && repo_dir="$riiid_root/$picked"
  fi

  # Claude Code 초기 메시지 — 한글+줄바꿈을 파일로 분리 (printf %q 토큰 분리 버그 회피)
  local nl=$'\n'
  local msg="이 세션에서 다음 Todo를 수행합니다.${nl}Todo: $title"
  [ -n "$desc" ]    && msg+="${nl}${nl}배경/설명:${nl}$desc"
  [ -n "$repo" ]    && msg+="${nl}${nl}레포: $repo"
  [ -n "$plan_id" ] && msg+="${nl}Plan: $plan_id"

  _build_and_launch_session "$repo_dir" "$msg" "$title"
}

# Task(Project) Enter → repo를 골라 Task 컨텍스트로 Claude Code 세션 오픈.
# Task에는 repo 필드가 없어 항상 repo 선택(pick_riiid_repo)을 거친다.
# __backlog__는 Notion Task가 아니므로 하위 Todo 드릴인으로 분기한다.
open_task_session() {
  local page_id="$1"
  [ -z "$page_id" ] && return 1
  [ "$page_id" = "__backlog__" ] && { todo_menu "$page_id"; return; }

  local task_json
  task_json=$(python3 "$STORE" list-tasks --format json 2>/dev/null \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(next((t for t in d['tasks'] if t['page_id']=='$page_id'),{}),ensure_ascii=False))")
  [ -z "$task_json" ] || [ "$task_json" = "{}" ] && return 1

  local name status priority plan_id
  name=$(python3     -c "import sys,json;print(json.load(sys.stdin).get('name',''))"     <<<"$task_json")
  status=$(python3   -c "import sys,json;print(json.load(sys.stdin).get('status',''))"   <<<"$task_json")
  priority=$(python3 -c "import sys,json;print(json.load(sys.stdin).get('priority',''))" <<<"$task_json")
  plan_id=$(python3  -c "import sys,json;print(json.load(sys.stdin).get('plan_id',''))"  <<<"$task_json")

  # 하위 Todo 목록을 체크박스 형태로 컨텍스트에 담는다 (Task 단위 작업 시작 시 유용)
  local todos_block
  todos_block=$(python3 "$STORE" list-todos --task "$page_id" --format json 2>/dev/null \
    | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('\n'.join(('[x] ' if t.get('done') else '[ ] ')+t.get('title','') for t in d.get('todos',[])))
" 2>/dev/null)

  # repo 결정: Task는 repo가 없으므로 항상 선택 (esc 취소 시 riiid 루트)
  local riiid_root="$HOME/workspace/riiid"
  local repo_dir="$riiid_root"
  [ -d "$repo_dir" ] || repo_dir="$HOME"
  if [ -d "$riiid_root" ]; then
    local picked; picked=$(pick_riiid_repo)
    [ -n "$picked" ] && repo_dir="$riiid_root/$picked"
  fi

  # Notion 상태를 "진행 중"으로 변경 (현재 "시작 전"일 때만)
  if [ "$status" = "시작 전" ] || [ "$status" = "대기" ]; then
    python3 "$NOTION_TASK" update-status --page-id "$page_id" --status "진행 중" >/dev/null 2>&1 || true
    status="진행 중"
  fi

  # alfred-state.json에 현재 진행 Task 기록 (alfred check/briefing에서 활용)
  ALFRED_PAGE_ID="$page_id" ALFRED_NAME="$name" ALFRED_PRIORITY="$priority" \
  python3 - <<'PYEOF' 2>/dev/null || true
import json, datetime, os
state = {'current_task': {
  'page_id':    os.environ['ALFRED_PAGE_ID'],
  'name':       os.environ['ALFRED_NAME'],
  'priority':   os.environ['ALFRED_PRIORITY'],
  'source':     'tui',
  'started_at': datetime.datetime.now().astimezone().isoformat(),
}}
json.dump(state, open(os.path.expanduser('~/.claude/alfred-state.json'), 'w'),
          ensure_ascii=False, indent=2)
PYEOF

  local nl=$'\n'
  local msg="이 세션에서 다음 Task(프로젝트)를 수행합니다.${nl}Task: $name"
  [ -n "$status" ]      && msg+="${nl}상태: $status"
  [ -n "$priority" ]    && msg+="${nl}우선순위: $priority"
  [ -n "$plan_id" ]     && msg+="${nl}Plan: $plan_id"
  [ -n "$todos_block" ] && msg+="${nl}${nl}하위 Todo:${nl}$todos_block"

  _build_and_launch_session "$repo_dir" "$msg" "$name"
}

# Todos 탭: 모든 Todo를 평면으로 — 소속 Task/Backlog + [repo] 표시, ctrl-g로 repo 필터
todos_tab() {
  local out key line todo_id cur t fhdr
  fhdr=${REPO_FILTER:+ [repo:$REPO_FILTER]}
  out=$(list_todos_filtered \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-todo {1}" --preview-window=right:42% \
          --header="$(tab_bar)$fhdr  enter:Claude열기  space:상태전환(□▷✓)  ctrl-a:추가  ctrl-e:편집  ctrl-n:설명편집  ctrl-d:삭제  ctrl-p:Plan뷰  ctrl-g:repo필터  ctrl-l:새로고침  ctrl-r:sync  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-a,ctrl-e,ctrl-n,ctrl-d,ctrl-g,ctrl-l,ctrl-r,ctrl-p)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); todo_id=$(cut -f1 <<<"$line")
  case "$key" in
    enter)  [ -n "$todo_id" ] && open_todo_session "$todo_id" ;;
    tab|ctrl-t) next_tab ;;
    space)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;
    ctrl-a)  t=$(prompt_input "새 Backlog todo"); [ -n "$t" ] && python3 "$STORE" add --task __backlog__ --title "$t" ${REPO_FILTER:+--repo "$REPO_FILTER"} >/dev/null ;;
    ctrl-e)  [ -z "$todo_id" ] && return
             cur=$(python3 "$STORE" list-all-todos --format json | python3 -c "import sys,json;print(next((x['title'] for x in json.load(sys.stdin)['todos'] if x['id']=='$todo_id'),''))")
             t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
    ctrl-n)  [ -z "$todo_id" ] && return
             local cur_desc new_desc
             cur_desc=$(python3 "$STORE" get --id "$todo_id" 2>/dev/null \
               | python3 -c "import sys,json;print(json.load(sys.stdin).get('description',''))" 2>/dev/null)
             if have_gum; then
               new_desc=$(gum write --placeholder "배경, 문제, 이유 등 자유 기술..." \
                 --value "$cur_desc" --width 72 --height 8)
             else
               local tmp; tmp=$(mktemp /tmp/todo-desc.XXXX.txt)
               printf '%s' "$cur_desc" > "$tmp"
               "${EDITOR:-vi}" "$tmp"
               new_desc=$(cat "$tmp"); rm -f "$tmp"
             fi
             python3 "$STORE" edit --id "$todo_id" --title "" \
               --description "$new_desc" --description-only >/dev/null ;;
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

# Today 탭: 오늘 처리할 Task/Todo를 한 화면에 — 지남(overdue)·오늘(today)·진행(doing).
# Task는 page_id, Todo는 td_ 접두사 id로 구분 → enter 동작을 분기한다
#   (Task=하위 Todo 드릴인 / Todo=Claude 세션 오픈).
today_tab() {
  local out key line id ov_flag ov_label
  if [ "$TODAY_OVERDUE" = "1" ]; then ov_flag="--include-overdue"; ov_label="지남:표시"; else ov_flag=""; ov_label="지남:숨김"; fi
  out=$(python3 "$STORE" today --format fzf $ov_flag \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-today {1}" --preview-window=right:46% \
          --header="$(tab_bar) [$ov_label]  📁=Task ▷=Todo  enter:열기/드릴인  space:Todo상태전환  ctrl-o:지남토글  ctrl-t:탭전환  ctrl-l:새로고침  ctrl-r:sync  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-o,ctrl-l,ctrl-r)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); id=$(cut -f1 <<<"$line")
  [[ "$id" == __* ]] && id=""  # __none__/__info__ 등 정보 행은 선택 동작 없음
  case "$key" in
    tab|ctrl-t) next_tab ;;
    ctrl-o)  [ "$TODAY_OVERDUE" = "1" ] && TODAY_OVERDUE="0" || TODAY_OVERDUE="1" ;;
    enter)
      [ -z "$id" ] && return
      if [[ "$id" == td_* ]]; then open_todo_session "$id"  # Todo → 세션
      else todo_menu "$id"; fi ;;                            # Task → 하위 Todo 목록
    space)
      # 상태 전환은 Todo만 (Task 상태는 Tasks 탭의 ctrl-s에서 변경)
      [[ "$id" == td_* ]] && python3 "$STORE" toggle --id "$id" >/dev/null ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 today 재렌더
    ctrl-r)  run_sync ;;
  esac
}

main_menu() {
  NAV=""
  while true; do
    case "$TAB" in
      tasks) tasks_tab ;;
      today) today_tab ;;
      *)     todos_tab ;;
    esac
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
