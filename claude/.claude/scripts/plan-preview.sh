#!/usr/bin/env bash
# Claude Code PreToolUse(ExitPlanMode) hook
# 목적: 플랜 승인 프롬프트가 뜨기 "직전"에 브라우저 프리뷰를 띄우고,
#       사용자가 브라우저에서 Approve/Reject 클릭 시 터미널 프롬프트를 완전히 우회한다.
#
# 동작: 서버를 동기식으로 실행 → 사용자 클릭 대기 (최대 5분) →
#       approve: permissionDecision=allow 반환 → 터미널 확인 없이 바로 진행
#       reject:  permissionDecision=deny 반환 → 플랜 거부
#       timeout: 조용히 exit 0 → 기존 터미널 프롬프트로 fallback
#
# 주의: PreToolUse 자동 승인은 hookSpecificOutput.permissionDecision로만 동작한다.
#       구형 {"decision":"approve"}는 PreToolUse에서 deprecated → 무시됨(2.1.x).

PAYLOAD=$(cat)

PLAN=$(printf '%s' "$PAYLOAD" | python3 -c \
    "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('planContent','') or d.get('plan',''))" \
    2>/dev/null || true)

[ -z "$PLAN" ] && exit 0

PREVIEW_MD="/tmp/claude-plan-preview.md"
printf '%s' "$PLAN" > "$PREVIEW_MD" 2>/dev/null || exit 0

# 동기식 실행 — 브라우저에서 클릭할 때까지 블로킹 (최대 5분)
DECISION=$(python3 "${HOME}/.claude/scripts/plan-approval-server.py" "$PREVIEW_MD" \
    2>/tmp/plan-approval-server.log)

case "$DECISION" in
    approve)
        printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Approved via browser preview"}}\n'
        exit 0
        ;;
    reject)
        printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Plan rejected via browser preview"}}\n'
        exit 0
        ;;
    *)
        # timeout 또는 에러 — 터미널 프롬프트로 fallback
        exit 0
        ;;
esac
