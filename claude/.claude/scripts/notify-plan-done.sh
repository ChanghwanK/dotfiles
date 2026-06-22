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
    python3 "${HOME}/.claude/scripts/plan-todo.py" init "$PLAN_FILE" \
        --session-id "$SESSION_ID" 2>/dev/null || true
fi

# ── 4. 정적 HTML 보관 (오프라인 참조용 — 브라우저는 열지 않는다) ──────────────
# 인터랙티브 프리뷰(승인/거부 버튼 + 브라우저 오픈)는 PreToolUse(plan-preview.sh)가
# 승인 프롬프트 "직전"에 이미 처리한다. 여기서는 frontmatter가 주입된 최종 .md 기준으로
# 영속 .html 파일만 동일 경로에 갱신한다. (중복 브라우저 오픈 방지)
if [ -n "$PLAN_FILE" ] && [ -f "$PLAN_FILE" ]; then
    python3 -c "import importlib.util; \
spec=importlib.util.spec_from_file_location('p','${HOME}/.claude/scripts/plan-to-html.py'); \
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.convert('$PLAN_FILE')" \
        >/dev/null 2>&1 || true
fi

# ── 5. Slack 알림 (기존 로직 유지) ───────────────────────────────────────────
FLAG="${HOME}/.claude/scripts/.notify-enabled"
[ -f "$FLAG" ] || exit 0

"${HOME}/.claude/scripts/notify-slack.sh" "📋 Plan mode 완료 — 승인/검토 필요"
