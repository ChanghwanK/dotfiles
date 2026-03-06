#!/usr/bin/env bash
# Send pending Slack notification if queued by Claude session.
# Triggered by Claude Code Stop hook.
set -euo pipefail

PENDING="$HOME/.claude/tmp/pending-notification.txt"

[ -f "$PENDING" ] || exit 0

msg=$(cat "$PENDING")
rm -f "$PENDING"

"$HOME/.claude/bin/notify-slack.sh" "$msg"
