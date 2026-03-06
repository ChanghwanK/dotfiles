#!/usr/bin/env bash
# claude-mem summarize wrapper
# Normalizes transcript_path for worktree sessions before passing to worker-service.cjs
# Problem: When EnterWorktree is used, Claude Code passes transcript_path based on the
# worktree CWD, but the actual .jsonl file was written to the original project directory.

INPUT=$(cat)
TRANSCRIPT=$(printf '%s' "$INPUT" | python3 -c \
  'import sys,json; print(json.load(sys.stdin).get("transcript_path",""))' 2>/dev/null)

if [ -n "$TRANSCRIPT" ] && [ ! -f "$TRANSCRIPT" ]; then
  PROJECTS_DIR="${HOME}/.claude/projects"
  TRANSCRIPT_FILENAME=$(basename "$TRANSCRIPT")

  ORIGINAL=$(find "$PROJECTS_DIR" -name "$TRANSCRIPT_FILENAME" 2>/dev/null | head -1)

  if [ -n "$ORIGINAL" ] && [ -f "$ORIGINAL" ]; then
    INPUT=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
d['transcript_path'] = '$ORIGINAL'
print(json.dumps(d))
")
  fi
fi

WORKER="/Users/changhwan/.claude/plugins/cache/thedotmack/claude-mem/9.0.12/scripts/worker-service.cjs"
printf '%s' "$INPUT" | bun "$WORKER" hook claude-code summarize
