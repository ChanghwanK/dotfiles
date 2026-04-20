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
    if ! brew upgrade 2>&1; then
      echo "brew upgrade failed (exit $?). Marker not created — will retry next run." >&2
      exit 1
    fi
    touch "$MARKER"
    ;;
  gimme)
    MARKER="$MARKER_DIR/start-daily-gimme-$DATE"
    if [ -f "$MARKER" ]; then
      echo "gimme-aws-creds: already done today"
      exit 0
    fi
    if ! command -v gimme-aws-creds >/dev/null 2>&1; then
      echo "gimme-aws-creds not found in PATH" >&2
      exit 1
    fi
    if ! gimme-aws-creds 2>&1; then
      echo "gimme-aws-creds failed (exit $?). Marker not created — will retry next run." >&2
      exit 1
    fi
    touch "$MARKER"
    ;;
  *)
    echo "Usage: $0 {brew|gimme}" >&2
    exit 1
    ;;
esac
