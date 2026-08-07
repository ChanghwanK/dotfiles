#!/usr/bin/env bash
# Claude Code PreToolUse(ExitPlanMode) hook
# 목적: 플랜 승인 프롬프트가 뜨기 "직전"에 브라우저 프리뷰를 띄우고,
#       사용자가 브라우저에서 결정하면 터미널 프롬프트를 완전히 우회한다.
#
# 동작: 서버를 동기식으로 실행 → 사용자 클릭 대기 (최대 SERVER_TIMEOUT) →
#       approve: permissionDecision=allow → 터미널 확인 없이 바로 진행
#       reject:  deny + [PLAN REJECTED]   → 플랜 폐기
#       pause:   deny + [PLAN PAUSED]     → plan mode 유지, 논의 내용을 모델에 전달
#       timeout: 조용히 exit 0            → 기존 터미널 프롬프트로 fallback
#
# 주의: PreToolUse 자동 승인은 hookSpecificOutput.permissionDecision로만 동작한다.
#       구형 {"decision":"approve"}는 PreToolUse에서 deprecated → 무시됨(2.1.x).
#       만약 향후 버전에서 deny의 의미가 바뀌어 plan mode가 유지되지 않으면,
#       reason을 stderr로 내보내고 `exit 2`하는 구형 차단 경로로 되돌린다.
#
# 타임아웃 불변식: plan-approval-server.py의 SERVER_TIMEOUT(840) + 60
#                 <= settings.json의 이 훅 timeout(900).
#                 서버가 항상 먼저 죽어야 셸이 JSON을 낼 여유가 생긴다.

PAYLOAD=$(cat)

PLAN=$(printf '%s' "$PAYLOAD" | python3 -c \
    "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('planContent','') or d.get('plan',''))" \
    2>/dev/null || true)

[ -z "$PLAN" ] && exit 0

# 세션 단위 작업 디렉터리. 고정 /tmp 경로를 쓰면 두 세션이 동시에 플랜을 검토할 때
# 서로의 프리뷰와 논의 페이로드를 덮어쓴다.
SESSION_ID=$(printf '%s' "$PAYLOAD" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('session_id','') or '')" \
    2>/dev/null || true)
SLUG=$(printf '%s' "${SESSION_ID:-$$}" | tr -cd 'a-zA-Z0-9-' | cut -c1-12)
WORKDIR="${TMPDIR:-/tmp}/claude-plan-${SLUG:-noid}"
mkdir -p "$WORKDIR" 2>/dev/null || exit 0

PREVIEW_MD="$WORKDIR/preview.md"
PAUSE_TXT="$WORKDIR/pause.txt"
COUNT_FILE="$WORKDIR/pause.count"
LOG="$WORKDIR/server.log"
# pause.count는 세션 내내 유지한다 (재제출 루프 감지용).
trap 'rm -f "$PREVIEW_MD" "$WORKDIR/preview.html" "$PAUSE_TXT"' EXIT

printf '%s' "$PLAN" > "$PREVIEW_MD" 2>/dev/null || exit 0
rm -f "$PAUSE_TXT"

# 동기식 실행 — 브라우저에서 제출할 때까지 블로킹
DECISION=$(python3 "${HOME}/.claude/scripts/plan-approval-server.py" \
    "$PREVIEW_MD" --pause-out "$PAUSE_TXT" 2>"$LOG")

case "$DECISION" in
    approve)
        printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Approved via browser preview"}}\n'
        ;;
    reject)
        printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[PLAN REJECTED] 사용자가 이 플랜을 폐기했습니다. 같은 플랜을 재제출하지 말고, 사용자에게 방향을 다시 물어보십시오."}}\n'
        ;;
    pause)
        # 페이로드가 없으면 아무 것도 주장하지 않고 터미널 프롬프트로 넘긴다.
        [ -s "$PAUSE_TXT" ] || exit 0
        COUNT=$(( $(cat "$COUNT_FILE" 2>/dev/null || echo 0) + 1 ))
        printf '%s' "$COUNT" > "$COUNT_FILE" 2>/dev/null
        # 사용자 텍스트는 셸을 거치지 않는다. 경로만 argv로 넘기고 파일에서 직접
        # 읽어 json.dumps가 이스케이프하게 한다 (printf 보간은 따옴표에서 깨진다).
        python3 - "$PAUSE_TXT" "$COUNT" <<'PYEOF'
import json, sys

reason = open(sys.argv[1], encoding="utf-8").read()
count = int(sys.argv[2])
if count >= 3:
    reason += (f"\n\n이 플랜에 대해 이미 {count}회 논의 요청이 있었습니다. "
               "재제출 전에 반드시 사용자에게 확인 질문을 하십시오.")
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}, ensure_ascii=False))
PYEOF
        ;;
    *)
        # timeout 또는 에러 — 터미널 프롬프트로 fallback
        ;;
esac

exit 0
