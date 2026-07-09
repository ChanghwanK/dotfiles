#!/bin/bash
# Claude Code 주기 정리 스크립트 (주 1회 cron 실행)
# 목적: cleanupPeriodDays(트랜스크립트)와 claude-mem-log-cleanup(로그)이 다루지 않는
#       잔여물을 정리하고, 일회성 정리로 해결했던 항목의 재발을 감지한다.
# 로그: ~/.claude/logs/housekeeping.log (30일 초과분 자체 삭제)

set -u

CLAUDE_DIR="$HOME/.claude"
LOG_DIR="$CLAUDE_DIR/logs"
LOG_FILE="$LOG_DIR/housekeeping.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "=== housekeeping start ==="

# 1. 업로드 실패 텔레메트리 이벤트: 7일 초과분 삭제 (재전송되지 않는 dead letter)
deleted=$(find "$CLAUDE_DIR/telemetry" -name '1p_failed_events.*' -mtime +7 -print -delete 2>/dev/null | wc -l | tr -d ' ')
log "telemetry: removed $deleted stale failed-event files"

# 2. 마켓플레이스 클론 내 node_modules 재발 감지 (플러그인은 plugins/cache에서 실행되므로 불필요)
#    자동 삭제하지 않고 경고만 남긴다: 플러그인 업데이트 직후 일시적으로 필요할 가능성 배제 못함
for nm in "$CLAUDE_DIR"/plugins/marketplaces/*/node_modules; do
  [ -d "$nm" ] || continue
  size=$(du -sh "$nm" 2>/dev/null | cut -f1)
  log "WARN: marketplace node_modules detected: $nm ($size) — 수동 확인 후 삭제 권장"
done

# 3. paste-cache / image-cache: 30일 초과분 삭제
for cache in paste-cache image-cache; do
  deleted=$(find "$CLAUDE_DIR/$cache" -type f -mtime +30 -print -delete 2>/dev/null | wc -l | tr -d ' ')
  log "$cache: removed $deleted files older than 30d"
done

# 4. 전체 사용량 임계 감시: ~/.claude + ~/.claude-mem 합산 4GB 초과 시 경고
total_kb=$(( $(du -sk "$CLAUDE_DIR" 2>/dev/null | cut -f1) + $(du -sk "$HOME/.claude-mem" 2>/dev/null | cut -f1) ))
total_gb=$(( total_kb / 1024 / 1024 ))
if [ "$total_kb" -gt $(( 4 * 1024 * 1024 )) ]; then
  log "WARN: total disk usage ${total_gb}GB exceeds 4GB threshold — 수동 점검 필요 (du -sh ~/.claude/* ~/.claude-mem/*)"
else
  log "disk usage OK: ${total_gb}GB (threshold 4GB)"
fi

# 5. 자체 로그 로테이션: 30일 초과 로그 라인 정리 대신 파일 크기 1MB 초과 시 절반 truncate
if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)" -gt 1048576 ]; then
  tail -c 524288 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
  log "log file truncated to 512KB"
fi

log "=== housekeeping done ==="
