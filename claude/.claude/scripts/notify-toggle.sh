#!/usr/bin/env bash
# Toggle Slack stop-hook notifications on/off
FLAG="${HOME}/.claude/bin/.notify-enabled"
if [ -f "$FLAG" ]; then
    rm "$FLAG"
    echo "🔕 Slack notifications OFF"
else
    touch "$FLAG"
    echo "🔔 Slack notifications ON"
fi
