#!/usr/bin/env bash
# env-init.sh — 환경 초기화 (멱등)
# Usage:
#   env-init.sh brew    — brew upgrade (하루 한 번)
#   env-init.sh gimme   — gimme-aws-creds (하루 한 번)
set -euo pipefail

SUBCOMMAND="${1:-}"
MARKER_DIR="$HOME/.claude/tmp"
DATE=$(date +%Y-%m-%d)

mkdir -p "$MARKER_DIR"

case "$SUBCOMMAND" in
  brew)
    MARKER="$MARKER_DIR/start-daily-brew-$DATE"
    if [ -f "$MARKER" ]; then
      echo "brew: already done today"
      exit 0
    fi
    brew upgrade
    touch "$MARKER"
    ;;
  gimme)
    MARKER="$MARKER_DIR/start-daily-gimme-$DATE"
    if [ -f "$MARKER" ]; then
      echo "gimme-aws-creds: already done today"
      exit 0
    fi
    gimme-aws-creds
    touch "$MARKER"
    ;;
  *)
    echo "Usage: $0 {brew|gimme}" >&2
    exit 1
    ;;
esac
