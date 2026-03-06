#!/usr/bin/env bash
# Claude Code PostToolUse(ExitPlanMode) hook — plan mode 종료 시 Slack 알림
FLAG="${HOME}/.claude/scripts/.notify-enabled"
[ -f "$FLAG" ] || exit 0

"${HOME}/.claude/scripts/notify-slack.sh" "📋 Plan mode 완료 — 승인/검토 필요"
