#!/usr/bin/env bash
# Alfred 저녁 일잘 리뷰 — crontab이 호출하는 헤드리스 트리거.
# claude -p 로 /alfred review --push 를 실행해 본인 Slack DM으로 일잘 리뷰(가시성·레버리지·소진)를 푸시한다.
#
# 설계 메모 (alfred-briefing.sh 와 동일 패턴):
# - cron 환경은 로그인 셸 env가 없다 → PATH·HOME·토큰을 여기서 명시적으로 주입한다.
# - NOTION_TOKEN: review 진행률 보정(reconcile-progress)이 필요. Keychain에서 조회해 export.
# - SLACK_BOT_TOKEN: notify-slack.sh 가 자체 조회하지만 일관성을 위해 함께 export.
# - 헤드리스 review 는 읽기 전용 + 본인 DM 발송뿐(동의 필요 쓰기는 하지 않음) → 프롬프트 없이 자동 실행.
set -uo pipefail

export HOME="${HOME:-/Users/changhwan}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
LOG="/tmp/alfred-review.log"
NOTIFY="${HOME}/.claude/scripts/notify-slack.sh"

echo "===== $(date '+%F %T') alfred-review start =====" >> "$LOG"

# ── 토큰 주입 (Keychain → 1Password fallback) ─────────────────
export NOTION_TOKEN="${NOTION_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "notion-personal-token" -w 2>/dev/null || op read 'op://Employee/Claude MCP - Notion-Personal/token' 2>/dev/null)}"
export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:-$(security find-generic-password -a "claude-mcp" -s "slack-token" -w 2>/dev/null || op read 'op://Employee/Claude MCP - Slack/token' 2>/dev/null)}"

# ── 빈 토큰 가드 ──────────────────────────────────────────────
# NOTION_TOKEN이 비면 진행률 보정이 통째로 빠진 리뷰가 나간다 — 잘못된 리뷰를 보내느니 중단하고 알린다.
if [ -z "${NOTION_TOKEN:-}" ]; then
  echo "[$(date '+%F %T')] ERROR: NOTION_TOKEN empty — 리뷰 중단(빈 리뷰 발송 방지)" >> "$LOG"
  [ -x "$NOTIFY" ] && bash "$NOTIFY" "⚠️ Alfred 저녁 리뷰 중단 — NOTION_TOKEN 조회 실패(Keychain/1Password 확인 바랍니다)." || true
  echo "===== $(date '+%F %T') alfred-review end (rc=skipped, no-token) =====" >> "$LOG"
  exit 0
fi

# ── 헤드리스 리뷰 실행 (실패 시 1회 재시도) ──────────────────
# --model sonnet: 자동 리뷰는 sonnet로 충분(기본 opus 비용 회피).
CLAUDE_BIN="$(command -v claude || echo /opt/homebrew/bin/claude)"
cd "$HOME" || true

MAX_ATTEMPTS=2          # 최초 1회 + 재시도 1회
RETRY_DELAY_SEC=30      # 일시 장애 회복 대기
RC=1
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  echo "[$(date '+%F %T')] attempt ${attempt}/${MAX_ATTEMPTS}" >> "$LOG"
  "$CLAUDE_BIN" -p "/alfred review --push" \
    --model sonnet \
    --dangerously-skip-permissions \
    >> "$LOG" 2>&1
  RC=$?
  [ "$RC" -eq 0 ] && break
  echo "[$(date '+%F %T')] WARN: attempt ${attempt} failed rc=$RC" >> "$LOG"
  [ "$attempt" -lt "$MAX_ATTEMPTS" ] && sleep "$RETRY_DELAY_SEC"
done

if [ "$RC" -ne 0 ]; then
  echo "[$(date '+%F %T')] ERROR: ${MAX_ATTEMPTS}회 시도 모두 실패 (rc=$RC)" >> "$LOG"
  [ -x "$NOTIFY" ] && bash "$NOTIFY" "⚠️ Alfred 저녁 리뷰 실패 (${MAX_ATTEMPTS}회 시도, rc=$RC). /tmp/alfred-review.log 확인 바랍니다." || true
fi

echo "===== $(date '+%F %T') alfred-review end (rc=$RC) =====" >> "$LOG"
exit 0
