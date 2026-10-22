#!/usr/bin/env bash
# Claude Code PostToolUse(ExitPlanMode) hook — plan mode 종료 시 frontmatter 주입 + Slack 알림

# ── 1. stdin JSON 파싱 ────────────────────────────────────────────────────────
# hook payload 예: {"session_id": "...", "tool_name": "ExitPlanMode", "tool_input": {"planFilePath": "...", ...}}
PAYLOAD=$(cat)
SESSION_ID=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)

# ── 2. plan .md 파일 식별 — planFilePath 우선, fallback은 mtime ──────────────
PLANS_DIR="${HOME}/.claude/plans"
PLAN_FILE=""

# planFilePath는 ExitPlanMode tool_input에 포함된 실제 파일 경로
PLAN_FILE=$(echo "$PAYLOAD" | python3 -c \
    "import sys,json; d=json.load(sys.stdin).get('tool_input',{}); print(d.get('planFilePath',''))" \
    2>/dev/null || true)

# fallback: 최근 10초 이내 수정된 최신 .md 파일
if [ -z "$PLAN_FILE" ] || [ ! -f "$PLAN_FILE" ]; then
    PLAN_FILE=$(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -not -name "CLAUDE.md" \
        -newer /tmp 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
fi

# 최종 fallback: 가장 최근 수정 파일
if [ -z "$PLAN_FILE" ] || [ ! -f "$PLAN_FILE" ]; then
    PLAN_FILE=$(ls -t "$PLANS_DIR"/*.md 2>/dev/null | grep -v "CLAUDE.md" | head -1)
fi

# ── 3. frontmatter 주입 ───────────────────────────────────────────────────────
if [ -n "$PLAN_FILE" ] && [ -f "$PLAN_FILE" ]; then
    # stdout은 마지막 additionalContext JSON 전용이다. 텍스트가 섞이면 JSON 파싱이 실패한다.
    python3 "${HOME}/.claude/scripts/plan-todo.py" init "$PLAN_FILE" \
        --session-id "$SESSION_ID" >/dev/null 2>&1 || true
    # 후속 판정을 장부에 미판정 행으로 옮긴다(멱등). 판정일 알림은 SessionStart 훅(ledger.py overdue)이 맡는다
    python3 "${HOME}/.claude/scripts/ledger.py" import-followups "$PLAN_FILE" --quiet >/dev/null 2>&1 || true
fi

# ── 4. Slack 알림 (기존 로직 유지) ───────────────────────────────────────────
# 플랜 .html 생성(plan-to-html.py)은 2026-10-12 제거했다. 플랜은 .md만 남긴다.
FLAG="${HOME}/.claude/scripts/.notify-enabled"
if [ -f "$FLAG" ]; then
    "${HOME}/.claude/scripts/notify-slack.sh" "📋 Plan mode 완료: 승인/검토 필요" >/dev/null 2>&1 || true
fi

# ── 5. stale active 플랜 안내 ────────────────────────────────────────────────
# 새 플랜을 시작하는 시점이 멈춘 플랜을 정리할 자연스러운 때다.
# 판단(abandon 여부)은 사용자가 하고, 모델은 한 줄로 알리기만 한다.
STALE=$(python3 "${HOME}/.claude/scripts/plan-todo.py" stale 2>/dev/null || true)
[ -z "$STALE" ] && exit 0

python3 - "$STALE" <<'PYEOF'
import json, sys

rows = sys.argv[1].strip().splitlines()
context = (
    f"[plan-todo] 14일 넘게 갱신이 없는 active 플랜이 {len(rows)}개 있습니다 "
    "(경과일, plan_id, 진행률, 제목):\n" + "\n".join(rows) + "\n"
    "이번 응답 끝에 한 줄로 알리고, 정리 여부는 사용자가 정하게 하십시오. "
    "정리는 `plan-todo.py abandon --plan-id <id>` 입니다."
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": context,
}}, ensure_ascii=False))
PYEOF
