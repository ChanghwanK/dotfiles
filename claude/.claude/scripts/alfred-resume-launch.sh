#!/usr/bin/env bash
#
# alfred-resume-launch.sh — 브리핑에서 고른 Task를 올바른 repo의 새 Claude 세션으로 띄운다.
#
# resume picker(SKILL)가 사용자의 번호 선택을 page_id로 바꿔 이 스크립트를 호출한다.
# 세션을 띄우는 "부수효과"를 skill 밖 스크립트로 격리해, 디렉터리 해석·state 기록·
# 세션 launch를 결정론적이고 테스트 가능하게 만든다 (skill = UX, 스크립트 = 메커니즘).
#
# 디렉터리 해석:
#   매니페스트 항목의 repo → ~/workspace/riiid/<repo> (또는 .claude → ~/.claude).
#   repo 없음 / 후보 디렉터리 부재 → exit 2 ("확인 필요"). picker가 1회 질문 후 --dir로 재호출.
#
# Usage:
#   alfred-resume-launch.sh <page_id> [--dir <path>] [--print-only]
#     --dir         디렉터리 자동 해석을 건너뛰고 지정 경로 사용(모호 fallback용).
#     --print-only  세션을 띄우지 않고 수동 실행 명령만 stdout에 출력(헤드리스/테스트용).
#
# Exit codes:
#   0  launch(또는 print-only) 성공
#   2  디렉터리 모호 — repo 없음 또는 후보 경로 부재 (picker가 --dir로 재호출해야 함)
#   3  page_id를 매니페스트에서 찾지 못함
#   4  매니페스트 파일 없음
set -uo pipefail

MANIFEST="$HOME/.claude/alfred-briefing-latest.json"
SCRIPTS_DIR="$HOME/.claude/scripts"
WORKSPACE_BASE="$HOME/workspace/riiid"

PAGE_ID=""
DIR_OVERRIDE=""
PRINT_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dir)        DIR_OVERRIDE="${2:-}"; shift 2 ;;
    --print-only) PRINT_ONLY=1; shift ;;
    -*)           echo "unknown option: $1" >&2; exit 64 ;;
    *)            PAGE_ID="$1"; shift ;;
  esac
done

if [ -z "$PAGE_ID" ]; then
  echo "usage: alfred-resume-launch.sh <page_id> [--dir <path>] [--print-only]" >&2
  exit 64
fi

if [ ! -f "$MANIFEST" ]; then
  echo "manifest not found: $MANIFEST" >&2
  exit 4
fi

# 매니페스트에서 name/priority/repo 추출 (탭 구분 — name의 공백을 보존).
fields=$(python3 - "$MANIFEST" "$PAGE_ID" <<'PY'
import json, sys
manifest, pid = sys.argv[1], sys.argv[2]
data = json.load(open(manifest, encoding="utf-8"))
item = next((x for x in data.get("items", []) if x.get("page_id") == pid), None)
if not item:
    sys.exit(3)
print("\t".join([item.get("name", ""), item.get("priority", ""), item.get("repo") or ""]))
PY
)
rc=$?
if [ "$rc" -eq 3 ]; then
  echo "page_id not found in manifest: $PAGE_ID" >&2
  exit 3
fi
IFS=$'\t' read -r NAME PRIORITY REPO <<< "$fields"

# 디렉터리 해석: --dir 우선, 없으면 repo 매핑.
DIR=""
if [ -n "$DIR_OVERRIDE" ]; then
  DIR="$DIR_OVERRIDE"
elif [ -n "$REPO" ]; then
  case "$REPO" in
    .claude|claude) DIR="$HOME/.claude" ;;
    *)              DIR="$WORKSPACE_BASE/$REPO" ;;
  esac
fi

if [ -z "$DIR" ] || [ ! -d "$DIR" ]; then
  # picker가 "어디서 열까요?"를 1회 묻고 --dir로 재호출하도록 신호.
  echo "AMBIGUOUS_DIR repo='${REPO}' candidate='${DIR}'" >&2
  exit 2
fi

# 새 세션 SessionStart hook이 주입할 수 있도록 최근 Task로 기록(실패해도 무시).
python3 "$SCRIPTS_DIR/alfred-state.py" record \
  --page-id "$PAGE_ID" --name "$NAME" --priority "$PRIORITY" --source resume >/dev/null 2>&1 || true

# 새 세션이 자동 실행할 초기 프롬프트 — loader 단계로 진입한다.
MSG="/alfred resume --task $PAGE_ID"

if [ "$PRINT_ONLY" -eq 1 ]; then
  printf 'cd %q && claude %q\n' "$DIR" "$MSG"
  exit 0
fi

# 세션 launch는 공유 런처에 위임(cmux 내부/Raycast/tmux/터미널 환경 감지를 단일 SoT로).
# shellcheck source=/dev/null
source "$SCRIPTS_DIR/claude-session-launch.sh"
_build_and_launch_session "$DIR" "$MSG" "$NAME"
