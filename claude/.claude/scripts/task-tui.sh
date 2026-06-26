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

# ? 도움말 오버레이 — 헤더엔 핵심 키만 남기고 전체 키맵은 이 파일로 빼서 less로 띄운다.
# fzf execute()는 터미널을 less에 잠시 넘겼다가 복귀하므로 preview 창과 충돌하지 않는다.
HELP_FILE="$HOME/.claude/tasktui/.keymap-help.txt"

# 전체 키맵을 HELP_FILE로 쓴다. 모든 탭 공용 단일 레퍼런스 — '?'로 어디서나 같은 화면을 띄운다.
write_help_file() {
  mkdir -p "$(dirname "$HELP_FILE")"
  cat > "$HELP_FILE" <<'EOF'
  todo TUI 키맵   (q: 닫기)
  ──────────────────────────────────────────────

  탭 = 엔티티로 분리: [ Now │ Tasks │ Todos ]
    Now   = 지금 진행 중(Task+Todo 혼합, 유일한 혼합 면)
    Tasks = Notion 프로젝트 전용
    Todos = 실행 항목(Todo) 전용

  [탭 이동]
    ctrl-t        다음 탭 (Now → Tasks → Todos → Now)
    tab           탭 이동 (Tasks 탭에서는 '다중 선택' — 이동은 ctrl-t)

  [공통]
    enter         열기 (Todo=Claude 세션 / Task=하위 Todo 드릴인)
    space         상태 전환 (□ → ▷ → ✓)
    ctrl-l        새로고침(재렌더)
    ctrl-r        동기화 (메타, 빠름)
    ctrl-u        전체 동기화 (본문 포함, 느림)
    ?             이 도움말
    esc           종료 (Level 2에서는 뒤로)

  [Now 탭]  진행 중 Task+Todo
    enter         Task=드릴인 / Todo=세션
    ctrl-o        Task=Notion 페이지 열기 (Todo에는 적용 안 됨)
    ctrl-d        Todo 삭제 (Task에는 적용 안 됨 — Tasks 탭에서 삭제)
    space         Todo 상태 전환

  [Tasks 탭]  Task 전용
    1 / 2 / 3 / 0   우선순위 필터 P1 / P2 / P3 / 전체
    ctrl-f          오늘 마감 토글 (지남·오늘 마감 Task만)
    space           하위 Todo 드릴인
    tab             다중 선택 (ctrl-d 일괄 삭제용)
    ctrl-a 새 Task   ctrl-d 삭제(Notion)   ctrl-s 상태 변경
    ctrl-o Notion 열기    ctrl-i import    ctrl-p Plan

  [Todos 탭]  Todo 전용 — 렌즈 칩
    1 활성   2 오늘(지남·오늘 마감)   3 완료(=재오픈)   0 전체
    ctrl-a 추가   ctrl-e 제목   ctrl-n 설명   ctrl-d 삭제
    ctrl-g repo 필터   ctrl-p Plan
    space          상태 전환 (완료 렌즈에선 ✓→□ 재오픈)

  [Level 2 — Task 하위 Todo]
    ctrl-a 추가    ctrl-e 제목    ctrl-n 설명    ctrl-d 삭제    ctrl-p Plan
EOF
}

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
#   todo add-task "이름" --priority P1 --category MY --due 2026-06-30

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
  _ADD_PRI=""
  if command -v gum >/dev/null; then
    _ADD_PRI=$(gum choose --header "우선순위" "P1" "P2" "P3" "(없음)")
    [ "$_ADD_PRI" = "(없음)" ] && _ADD_PRI=""
  fi
  python3 "$STORE" add --task __backlog__ --title "$_ADD_TITLE" ${_ADD_PRI:+--priority "$_ADD_PRI"}
  exit $?
fi

# add 서브커맨드: 논인터랙티브, 추가 옵션 지원
if [ "${1:-}" = "add" ]; then
  shift
  if [ $# -eq 0 ]; then
    echo "usage: todo add <제목> [--task <page_id>] [--repo <repo>] [--description <text>] [--status 시작전|진행중|완료] [--priority P1|P2|P3] [--roi high|medium|low]" >&2
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
      --priority)    _ADD_EXTRA+=(--priority "$2"); shift 2 ;;
      --roi)         _ADD_EXTRA+=(--roi "$2"); shift 2 ;;
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
    _TASK_PRIO=$(gum choose --header "우선순위" --selected "P3" \
      "P1" "P2" "P3")
    _TASK_CAT=$(gum choose --header "카테고리" --selected "WORK" "WORK" "MY")
    _TASK_DUE=$(gum input --placeholder "마감일 YYYY-MM-DD (선택 — 비우면 없음)")
  else
    read -rp "우선순위 [P3]: " _TASK_PRIO; _TASK_PRIO="${_TASK_PRIO:-P3}"
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
    echo "usage: todo add-task <이름> [--priority P1|P2|P3] [--category WORK|MY] [--due YYYY-MM-DD] [--description <text>]" >&2
    exit 1
  fi
  _TASK_NAME="$1"; shift
  _TASK_PRIO="P3"
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

run_sync() {  # 기본 ctrl-r: lazy sync — Task 메타 + push만(본문 스킵). 빠름(~1s).
  # 본문(to_do)은 Task 드릴인 시 pull_task_for로, 전체는 ctrl-u(run_sync_full)로 당긴다.
  if have_gum; then
    gum spin --title "동기화 중 (메타)..." -- python3 "$SYNC" sync-meta >/dev/null
  else
    echo "동기화 중..."; python3 "$SYNC" sync-meta >/dev/null
  fi
}

run_sync_full() {  # ctrl-u: full sync — 메타 + 본문 reconcile + push. 느림(Task 수 비례).
  # $1=우선순위 범위(P1/P2/P3, 비우면 전체). 평면 탭은 전체, Tasks 탭은 현재 필터 범위.
  local prio="${1:-}"
  local title="전체 동기화 중 (본문 포함)..."
  [ -n "$prio" ] && title="전체 동기화 중 ($prio 본문)..."
  if have_gum; then
    gum spin --title "$title" -- python3 "$SYNC" sync ${prio:+--priority "$prio"} >/dev/null
  else
    echo "$title"; python3 "$SYNC" sync ${prio:+--priority "$prio"} >/dev/null
  fi
}

pull_task_for() {  # 드릴인 직전: 해당 Task 한 개의 본문만 동기화(~0.5s). Backlog은 제외.
  local page_id="$1"
  [ -z "$page_id" ] && return
  [ "$page_id" = "__backlog__" ] && return  # Backlog은 Notion 미동기화(로컬 전용)
  if have_gum; then
    gum spin --title "Task 본문 동기화 중..." -- \
      python3 "$SYNC" pull-task --page-id "$page_id" >/dev/null 2>&1 || true
  else
    python3 "$SYNC" pull-task --page-id "$page_id" >/dev/null 2>&1 || true
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

# Todo 설명(description) 편집 — gum write 우선, 없으면 $EDITOR로 degrade.
# todo_menu / todos_tab 의 ctrl-n 공용 (동일 UX를 한 곳에서 유지).
edit_description() {
  local todo_id="$1"
  [ -z "$todo_id" ] && return
  local cur_desc new_desc
  cur_desc=$(python3 "$STORE" get --id "$todo_id" --field description 2>/dev/null)
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
    --description "$new_desc" --description-only >/dev/null
}

# Todo 우선순위/ROI 편집 — gum choose 우선, 없으면 prompt_choose로 degrade.
# todo_menu / todos_tab 의 ctrl-i 공용.
edit_priority_roi() {
  local todo_id="$1"
  [ -z "$todo_id" ] && return
  local cur_pri cur_roi new_pri new_roi
  cur_pri=$(python3 "$STORE" get --id "$todo_id" --field priority 2>/dev/null)
  cur_roi=$(python3 "$STORE" get --id "$todo_id" --field roi 2>/dev/null)
  if have_gum; then
    new_pri=$(gum choose --header "우선순위 (현재: ${cur_pri:-없음})" "P1" "P2" "P3" "(없음)")
    [ "$new_pri" = "(없음)" ] && new_pri=""
    new_roi=$(gum choose --header "ROI (현재: ${cur_roi:-없음})" "high" "medium" "low" "(없음)")
    [ "$new_roi" = "(없음)" ] && new_roi=""
  else
    new_pri=$(prompt_choose "P1" "P2" "P3" "(없음)")
    [ "$new_pri" = "(없음)" ] && new_pri=""
    new_roi=$(prompt_choose "high" "medium" "low" "(없음)")
    [ "$new_roi" = "(없음)" ] && new_roi=""
  fi
  python3 "$STORE" edit --id "$todo_id" --title "" --description-only \
    --priority "$new_pri" --roi "$new_roi" >/dev/null
}

# task/todo의 plan_id를 조회해 있으면 Plan 뷰를, 없으면 Plan 연결 프롬프트를 연다.
# 3개 탭(todo_menu/tasks_tab/todos_tab)의 ctrl-p 공용 로직.
#   target: "task"(list-tasks에서 page_id 매칭) | "todo"(get에서 plan_id 추출)
resolve_and_open_plan() {
  local target="$1" id="$2"
  [ -z "$id" ] && return
  local plan_id
  if [ "$target" = "task" ]; then
    plan_id=$(python3 "$STORE" list-tasks --format json \
      | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((t.get('plan_id','') for t in d['tasks'] if t['page_id']=='$id'),''))")
  else
    plan_id=$(python3 "$STORE" get --id "$id" --field plan_id 2>/dev/null)
  fi
  if [ -n "$plan_id" ]; then
    plan_view "$plan_id"
  else
    link_plan_to_target "$target" "$id"
  fi
}

# ── Level 2: Todo 목록 ────────────────────────────────────────

todo_menu() {
  local page_id="$1"
  while true; do
    local out key line todo_id
    out=$(python3 "$STORE" list-todos --task "$page_id" --format fzf \
      | fzf --delimiter='\t' --with-nth='2..' --ansi \
            --preview "python3 '$STORE' preview-todo {1}" --preview-window=right:35% \
            --bind "?:execute(less -R -- $HELP_FILE)" \
            --header="enter:Claude  space:전환  ctrl-a:추가  ctrl-e:제목  ctrl-n:설명  ctrl-i:우선순위  ctrl-d:삭제  ?:도움말  esc:뒤로" \
            --expect=enter,space,ctrl-a,ctrl-e,ctrl-n,ctrl-i,ctrl-d,ctrl-l,ctrl-r,ctrl-p)
    [ -z "$out" ] && return  # esc/취소 → Level 1 복귀
    key=$(sed -n 1p <<<"$out")
    line=$(sed -n 2p <<<"$out")
    todo_id=$(cut -f1 <<<"$line")
    case "$key" in
      enter)   [ -n "$todo_id" ] && open_todo_session "$todo_id" ;;
      space)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;
      ctrl-a)  local t _pri
               t=$(prompt_input "새 todo 제목")
               [ -z "$t" ] && continue
               _pri=""
               if have_gum; then
                 _pri=$(gum choose --header "우선순위" "P1" "P2" "P3" "(없음)")
                 [ "$_pri" = "(없음)" ] && _pri=""
               fi
               python3 "$STORE" add --task "$page_id" --title "$t" ${_pri:+--priority "$_pri"} >/dev/null ;;
      ctrl-e)  [ -z "$todo_id" ] && continue
               # 깨끗한 title은 JSON에서 조회한다(표시줄 파싱은 글리프·배지 변경에 취약).
               local cur t
               cur=$(python3 "$STORE" get --id "$todo_id" --field title 2>/dev/null)
               t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
      ctrl-n)  edit_description "$todo_id" ;;
      ctrl-i)  [ -n "$todo_id" ] && edit_priority_roi "$todo_id" ;;
      ctrl-d)  [ -z "$todo_id" ] && continue
               prompt_confirm "이 todo를 삭제할까요?" && python3 "$STORE" delete --id "$todo_id" >/dev/null ;;
      ctrl-p)  if [ -n "$todo_id" ]; then resolve_and_open_plan todo "$todo_id"
               else resolve_and_open_plan task "$page_id"; fi ;;
      ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-todos 재렌더
      ctrl-r)  pull_task_for "$page_id" ;;  # 이 Task 본문만 동기화(Backlog은 no-op)
    esac
  done
}

# ── 탭 UI: Tasks 탭 / Todos 탭 (tab 키로 전환) ────────────────

# 현재 탭 상태 — 엔티티로 분리: Now(혼합 WIP) / Tasks(Project) / Todos(실행 항목)
TAB="now"         # 시작 탭 = Now (지금 붙어 있는 일)
NAV=""            # 탭 함수가 "quit"을 세우면 최상위 루프 종료
REPO_FILTER=""    # Todos 탭의 repo 필터 (빈값 = 전체)
TODOS_LENS="active" # Todos 탭 렌즈 — active(남은것)/today(지남·오늘)/done(완료)/all. 1/2/3/0 키
PRIO_FILTER="P1"  # Tasks 탭의 우선순위 필터 (P1|P2|P3|""=전체)
TASKS_DUE_TODAY="0" # Tasks 탭 마감 필터 — 1이면 지남·오늘 마감 Task만 (키 4 토글)

tab_bar() {
  local a="○Now" b="○Tasks" c="○Todos"
  case "$TAB" in
    now)   a="●Now" ;;
    tasks) b="●Tasks" ;;
    todos) c="●Todos" ;;
  esac
  echo "[ $a │ $b │ $c ]"
}

# ctrl-t/tab: now → tasks → todos → now 순환
next_tab() {
  case "$TAB" in
    now)   TAB="tasks" ;;
    tasks) TAB="todos" ;;
    todos) TAB="now" ;;
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
  local due="○오늘"; [ "$TASKS_DUE_TODAY" = "1" ] && due="●오늘"
  echo "[${out% }] $due"
}

# Todos 탭 렌즈 칩 — 1/2/3/0 키와 동형. active/today/done/all 중 현재 값을 강조.
lens_bar() {
  local out=""
  local pairs=("active:활성" "today:오늘" "done:완료" "all:전체")
  for kv in "${pairs[@]}"; do
    local key="${kv%%:*}" label="${kv#*:}"
    if [ "$TODOS_LENS" = "$key" ]; then out+="●${label} "; else out+="○${label} "; fi
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

# Notion에서 단일 Task를 아카이브하고, 성공 시에만 로컬 캐시를 정리한다.
# Notion API에는 페이지 영구 삭제 엔드포인트가 없다 — 삭제는 archived:true로
# 휴지통에 보내는 것이며, 이것이 Notion UI의 "삭제"와 동일한 동작이다(30일 보존).
# Notion 호출이 실패하면 로컬은 건드리지 않는다(정합성 보호 → orphan Todo 방지).
# 반환값: 0=성공, 1=Notion 삭제 실패.
_archive_task() {
  local page_id="$1"
  if have_gum; then
    gum spin --title "Notion에서 Task 삭제 중... ($page_id)" -- \
      python3 "$NOTION_TASK" delete-task --page-id "$page_id" >/dev/null
  else
    echo "Notion에서 Task 삭제 중... ($page_id)"
    python3 "$NOTION_TASK" delete-task --page-id "$page_id" >/dev/null
  fi
  local ok=$?
  if [ "$ok" -eq 0 ]; then
    python3 "$STORE" delete-task-local --task "$page_id" >/dev/null
    return 0
  fi
  return 1
}

# Tasks 탭 ctrl-d: 선택된 1개 이상의 Task를 일괄 삭제한다.
# fzf --multi + --expect 출력 규약: 1번째 줄=키, 2번째 줄~=선택 라인들.
# tab으로 다중 선택하지 않았으면 현재 포커스 1줄만 오므로 단일 삭제와 같은 경로다.
# Backlog(__backlog__)은 Notion 페이지가 없어 대상에서 제외한다.
delete_tasks() {
  local out="$1"
  local -a page_ids=()
  local line pid
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    pid=$(cut -f1 <<<"$line")
    [ -z "$pid" ] && continue
    [ "$pid" = "__backlog__" ] && continue
    page_ids+=("$pid")
  done < <(sed -n '2,$p' <<<"$out")

  local n=${#page_ids[@]}
  [ "$n" -eq 0 ] && { echo "삭제할 Task가 없습니다 (Backlog 제외)"; sleep 1; return; }

  # 확인 프롬프트용 이름 목록 — 한 번의 list-tasks 조회로 모든 대상 이름을 뽑는다.
  local names
  names=$(python3 "$STORE" list-tasks --format json | python3 -c "
import sys,json
ids=set(sys.argv[1:])
d=json.load(sys.stdin)
for t in d['tasks']:
    if t['page_id'] in ids:
        print('  · '+t.get('name',''))
" "${page_ids[@]}")

  echo "삭제 대상 (${n}개):"
  echo "$names"
  prompt_confirm "위 ${n}개 Task를 삭제할까요?" || return

  # 항목별로 아카이브 — 일부 실패해도 나머지는 진행하고, 실패 건은 로컬 유지.
  local fail=0
  for pid in "${page_ids[@]}"; do
    _archive_task "$pid" || fail=$((fail+1))
  done
  [ "$fail" -gt 0 ] && { echo "${fail}개 Task 삭제 실패, 해당 항목은 로컬에 유지됨"; sleep 1; }
}

# Tasks 탭: Notion Task(Project) 목록.
#   enter=Task 단위 Claude 세션 / space=하위 Todo 드릴인 /
#   ctrl-d=Task 삭제(Notion)
tasks_tab() {
  local out key line page_id prio_arg due_arg
  prio_arg=${PRIO_FILTER:+--priority "$PRIO_FILTER"}
  due_arg=$([ "$TASKS_DUE_TODAY" = "1" ] && echo "--due-today")
  # --multi: tab으로 여러 Task를 토글 선택해 ctrl-d 일괄 삭제. 단일 액션
  # (enter/space/ctrl-o 등)은 선택 라인 중 첫 줄만 사용한다. --multi에서 tab은
  # 선택 토글로 쓰이므로 Tasks 탭의 탭전환은 ctrl-t로만 수행한다(README 권장 키).
  out=$(python3 "$STORE" list-tasks --format fzf $prio_arg $due_arg \
    | fzf --multi --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-task {1}" --preview-window=right:48%:wrap \
          --bind "?:execute(less -R -- $HELP_FILE)" \
          --header="$(tab_bar) $(prio_bar)  ctrl-t:탭  1-3/0:우선순위  ctrl-f:오늘  enter:세션  space:todo  ctrl-a:새Task  ctrl-d:삭제  ?:도움말  esc:종료" \
          --expect=enter,space,ctrl-t,ctrl-a,ctrl-d,ctrl-o,ctrl-l,ctrl-r,ctrl-u,ctrl-s,ctrl-i,ctrl-p,ctrl-f,1,2,3,0)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); page_id=$(cut -f1 <<<"$line")
  case "$key" in
    ctrl-t) next_tab ;;
    1) PRIO_FILTER="P1" ;;
    2) PRIO_FILTER="P2" ;;
    3) PRIO_FILTER="P3" ;;
    0) PRIO_FILTER="" ;;
    ctrl-f) [ "$TASKS_DUE_TODAY" = "1" ] && TASKS_DUE_TODAY="0" || TASKS_DUE_TODAY="1" ;;  # 오늘 마감 토글
    enter)   [ -n "$page_id" ] && { pull_task_for "$page_id"; open_task_session "$page_id"; } ;;
    space)   [ -n "$page_id" ] && { pull_task_for "$page_id"; todo_menu "$page_id"; } ;;
    ctrl-d)  delete_tasks "$out" ;;
    ctrl-o)  [ -n "$page_id" ] && open_notion_page "$page_id" ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-tasks 재렌더
    ctrl-r)  run_sync ;;
    ctrl-u)  run_sync_full "$PRIO_FILTER" ;;  # 본문 포함 full sync(현재 우선순위 범위)
    ctrl-s)  [ -z "$page_id" ] && return
             [ "$page_id" = "__backlog__" ] && return  # Backlog은 Notion 상태 없음
             local st; st=$(prompt_choose "시작 전" "진행 중" "완료" "대기")
             # offline-first: 로컬 tasks.json에 기록(meta_dirty) → 화면 즉시 갱신, 종료 시
             # trap의 push가 Notion에 반영. 네트워크 없어도 동작(Todo와 동일 모델).
             [ -n "$st" ] && python3 "$STORE" set-task-status --task "$page_id" --status "$st" >/dev/null ;;
    ctrl-a)  create_task ;;
    ctrl-i)  run_import ;;
    ctrl-p)  { [ -z "$page_id" ] || [ "$page_id" = "__backlog__" ]; } && return
             resolve_and_open_plan task "$page_id" ;;
  esac
}

# 렌즈($1: active|today|done|all, 기본 active)와 repo 필터를 적용해 평면 Todo 목록을 만든다.
list_todos_filtered() {
  local lens="${1:-active}"
  if [ -n "$REPO_FILTER" ]; then
    python3 "$STORE" list-all-todos --format fzf --lens "$lens" --repo "$REPO_FILTER"
  else
    python3 "$STORE" list-all-todos --format fzf --lens "$lens"
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

  # 단일 라인 필드(title/repo/plan_id)는 한 번의 python3로 탭 구분 추출 → 콜드스타트 절감.
  # description은 다줄 가능성이 있어 탭 묶음에서 분리(read가 첫 줄에서 끊기는 것 방지).
  local title repo plan_id desc
  IFS=$'\t' read -r title repo plan_id < <(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
print('\t'.join((d.get('title',''),d.get('repo',''),d.get('plan_id',''))))
" "$todo_json")
  desc=$(python3 -c "import sys,json; print(json.loads(sys.argv[1]).get('description',''))" "$todo_json")

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

  # Task 필드는 모두 단일 라인 → 한 번의 python3로 탭 구분 추출(콜드스타트 4회→1회).
  local name status priority plan_id
  IFS=$'\t' read -r name status priority plan_id < <(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
print('\t'.join((d.get('name',''),d.get('status',''),d.get('priority',''),d.get('plan_id',''))))
" "$task_json")

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

  # alfred-state.json에 현재 진행 Task 기록 (alfred check 모드 교차 검증에 활용).
  # recent_tasks 배열로 누적(dedup·cap) — 헬퍼가 current_task 하위호환 미러도 함께 갱신.
  python3 "$HOME/.claude/scripts/alfred-state.py" record \
    --page-id "$page_id" --name "$name" --priority "$priority" --source tui \
    >/dev/null 2>&1 || true

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
  out=$(list_todos_filtered "$TODOS_LENS" \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-todo {1}" --preview-window=right:35% \
          --bind "?:execute(less -R -- $HELP_FILE)" \
          --header="$(tab_bar) $(lens_bar)$fhdr  1-3/0:렌즈  enter:열기  space:전환  ctrl-a:추가  ctrl-e:제목  ctrl-i:우선순위  ctrl-d:삭제  ?:도움말  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-a,ctrl-e,ctrl-n,ctrl-i,ctrl-d,ctrl-g,ctrl-l,ctrl-r,ctrl-u,ctrl-p,1,2,3,0)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); todo_id=$(cut -f1 <<<"$line")
  case "$key" in
    1) TODOS_LENS="active" ;;   # 렌즈 칩 — Tasks 우선순위 키와 동형
    2) TODOS_LENS="today" ;;
    3) TODOS_LENS="done" ;;
    0) TODOS_LENS="all" ;;
    enter)  [ -n "$todo_id" ] && open_todo_session "$todo_id" ;;
    tab|ctrl-t) next_tab ;;
    space)   [ -n "$todo_id" ] && python3 "$STORE" toggle --id "$todo_id" >/dev/null ;;  # 완료 렌즈에선 재오픈
    ctrl-a)  t=$(prompt_input "새 Backlog todo")
             if [ -n "$t" ]; then
               local _pri=""
               if have_gum; then
                 _pri=$(gum choose --header "우선순위" "P1" "P2" "P3" "(없음)")
                 [ "$_pri" = "(없음)" ] && _pri=""
               fi
               python3 "$STORE" add --task __backlog__ --title "$t" \
                 ${REPO_FILTER:+--repo "$REPO_FILTER"} ${_pri:+--priority "$_pri"} >/dev/null
             fi ;;
    ctrl-e)  [ -z "$todo_id" ] && return
             cur=$(python3 "$STORE" get --id "$todo_id" --field title 2>/dev/null)
             t=$(prompt_input "제목 수정" "$cur"); [ -n "$t" ] && python3 "$STORE" edit --id "$todo_id" --title "$t" >/dev/null ;;
    ctrl-n)  edit_description "$todo_id" ;;
    ctrl-i)  [ -n "$todo_id" ] && edit_priority_roi "$todo_id" ;;
    ctrl-d)  [ -z "$todo_id" ] && return
             prompt_confirm "이 todo를 삭제할까요?" && python3 "$STORE" delete --id "$todo_id" >/dev/null ;;
    ctrl-p)  resolve_and_open_plan todo "$todo_id" ;;
    ctrl-g)  choose_repo ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 list-all-todos 재렌더
    ctrl-r)  run_sync ;;
    ctrl-u)  run_sync_full "" ;;  # 평면 뷰는 전체 본문 필요 → 우선순위 제한 없이 full
  esac
}

# Now 탭(혼합 예외): 지금 진행 중인 것만 — 진행 중 Task(상태=진행 중) + 진행중 Todo(상태=진행중).
# Task/Todo를 의도적으로 함께 보여 "지금 붙어 있는 일"과 레벨 교차 WIP 과부하를 점검한다.
# (다른 탭은 엔티티로 분리되지만 Now만 혼합 — 사용자 결정.)
# Task는 page_id, Todo는 td_ 접두사 id로 구분 → enter 동작을 분기한다
#   (Task=하위 Todo 드릴인 / Todo=Claude 세션 오픈).
now_tab() {
  local out key line id
  out=$(python3 "$STORE" doing --format fzf \
    | fzf --delimiter='\t' --with-nth='2..' --ansi \
          --preview "python3 '$STORE' preview-today {1}" --preview-window=right:30% \
          --bind "?:execute(less -R -- $HELP_FILE)" \
          --header="$(tab_bar)  📁=Task ▷=Todo  enter:열기  space:전환  ctrl-o:Notion  ctrl-d:Todo삭제  ?:도움말  esc:종료" \
          --expect=enter,space,tab,ctrl-t,ctrl-o,ctrl-d,ctrl-l,ctrl-r)
  if [ -z "$out" ]; then NAV="quit"; return; fi  # esc → 종료
  key=$(sed -n 1p <<<"$out"); line=$(sed -n 2p <<<"$out"); id=$(cut -f1 <<<"$line")
  [[ "$id" == __* ]] && id=""  # __none__/__info__ 등 정보 행은 선택 동작 없음
  case "$key" in
    tab|ctrl-t) next_tab ;;
    enter)
      [ -z "$id" ] && return
      if [[ "$id" == td_* ]]; then open_todo_session "$id"  # Todo → 세션
      else pull_task_for "$id"; todo_menu "$id"; fi ;;       # Task → 본문 동기화 후 하위 Todo
    space)
      # 상태 전환은 Todo만 (Task 상태는 Tasks 탭의 ctrl-s에서 변경)
      [[ "$id" == td_* ]] && python3 "$STORE" toggle --id "$id" >/dev/null ;;
    ctrl-o)
      # Task만 Notion 열기 (Todo는 Notion 페이지 없음)
      [ -z "$id" ] && return
      [[ "$id" == td_* ]] || open_notion_page "$id" ;;
    ctrl-d)
      # Todo만 삭제 (Task 삭제는 Tasks 탭의 ctrl-d에서 수행)
      [ -z "$id" ] && return
      [[ "$id" == td_* ]] || return
      prompt_confirm "이 todo를 삭제할까요?" && python3 "$STORE" delete --id "$id" >/dev/null ;;
    ctrl-l)  : ;;  # no-op → while loop 재진입으로 now 재렌더
    ctrl-r)  run_sync ;;
  esac
}

main_menu() {
  NAV=""
  while true; do
    case "$TAB" in
      tasks) tasks_tab ;;
      todos) todos_tab ;;
      *)     now_tab ;;
    esac
    [ "$NAV" = "quit" ] && return
  done
}

create_task() {
  local name pri cat
  name=$(prompt_input "새 Task 이름"); [ -z "$name" ] && return
  pri=$(prompt_choose "P1" "P2" "P3")
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

write_help_file  # '?' 도움말 오버레이용 키맵 파일 생성

main_menu
