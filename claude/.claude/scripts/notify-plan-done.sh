#!/usr/bin/env bash
# Claude Code PostToolUse(ExitPlanMode) hook — plan mode 종료 시 frontmatter 주입 + Slack 알림

# ── 1. stdin JSON 파싱 ────────────────────────────────────────────────────────
# hook payload 예: {"session_id": "...", "tool_name": "ExitPlanMode", ...}
PAYLOAD=$(cat)
SESSION_ID=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)

# ── 2. 가장 최근 수정된 plan .md 파일 식별 (5초 이내) ──────────────────────
PLANS_DIR="${HOME}/.claude/plans"
PLAN_FILE=""
NOW=$(date +%s)

while IFS= read -r -d '' f; do
    MTIME=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)
    if [ -n "$MTIME" ] && [ $((NOW - MTIME)) -le 10 ]; then
        PLAN_FILE="$f"
        break
    fi
done < <(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -not -name "CLAUDE.md" \
    -newer "$PLANS_DIR" -print0 2>/dev/null | \
    xargs -0 ls -t 2>/dev/null | head -1 | tr '\n' '\0')

# find 방식 fallback: mtime 10초 이내 최신 파일
if [ -z "$PLAN_FILE" ]; then
    PLAN_FILE=$(find "$PLANS_DIR" -maxdepth 1 -name "*.md" -not -name "CLAUDE.md" \
        -newer /tmp 2>/dev/null | \
        xargs ls -t 2>/dev/null | head -1)
fi

# 최종 fallback: 단순히 가장 최근 수정 파일
if [ -z "$PLAN_FILE" ]; then
    PLAN_FILE=$(ls -t "$PLANS_DIR"/*.md 2>/dev/null | grep -v "CLAUDE.md" | head -1)
fi

# ── 3. frontmatter 주입 ───────────────────────────────────────────────────────
if [ -n "$PLAN_FILE" ] && [ -f "$PLAN_FILE" ]; then
    python3 "${HOME}/.claude/scripts/plan-todo.py" init "$PLAN_FILE" \
        --session-id "$SESSION_ID" 2>/dev/null || true
fi

# ── 4. Slack 알림 (기존 로직 유지) ───────────────────────────────────────────
FLAG="${HOME}/.claude/scripts/.notify-enabled"
[ -f "$FLAG" ] || exit 0

"${HOME}/.claude/scripts/notify-slack.sh" "📋 Plan mode 완료 — 승인/검토 필요"
