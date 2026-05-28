#!/bin/bash
# ~/.claude/ 디렉토리 hygiene 정리 — 빈 디렉토리, stale orphan, 재생성 가능 캐시/로그
#
# 기본 동작은 dry-run (삭제 후보만 출력). 실제 정리는 --apply 필요.
# 대용량 자산(projects 트랜스크립트, plugins/node_modules)은 의도적으로 대상에서 제외한다 —
# --resume·claude-mem 동작에 직접 영향이 있어 별도 신중 검토로 분리한다.
#
# Tier 1: 빈 디렉토리          → 즉시 삭제 (잃을 것 없음)
# Tier 2: stale orphan/legacy  → quarantine 디렉토리로 이동 (복원 가능)
# Tier 3: 재생성 캐시/로그      → mtime 7일 초과분만 삭제 (재생성/복구 가치 낮음)

set -euo pipefail

readonly CLAUDE_DIR="${HOME}/.claude"
readonly RETENTION_DAYS=7
readonly BACKUP_KEEP=3   # .claude.json.backup.* 보존 개수

# 오용 가드: 대상은 반드시 ~/.claude 여야 한다 (다른 경로 삭제 방지)
case "$CLAUDE_DIR" in
  "${HOME}/.claude") ;;
  *) echo "FATAL: CLAUDE_DIR is not ~/.claude — aborting" >&2; exit 1 ;;
esac
[ -d "$CLAUDE_DIR" ] || { echo "FATAL: $CLAUDE_DIR not found" >&2; exit 1; }

APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true

# quarantine 디렉토리는 apply 모드에서 첫 이동 시점에만 생성
QUARANTINE=""
ensure_quarantine() {
  if [ -z "$QUARANTINE" ]; then
    QUARANTINE="${CLAUDE_DIR}/backups/cleanup-quarantine-$(date +%Y%m%d-%H%M%S)"
    $APPLY && mkdir -p "$QUARANTINE"
  fi
}

freed_bytes=0
add_size() { # $1: path — 누적 회수 용량(바이트) 합산
  local b
  b=$(du -sk "$1" 2>/dev/null | cut -f1 || echo 0)
  freed_bytes=$((freed_bytes + b * 1024))
}

log() { printf '%s\n' "$*"; }

if $APPLY; then
  log "=== claude-dir-cleanup: APPLY mode ==="
else
  log "=== claude-dir-cleanup: DRY-RUN (실제 삭제 없음, --apply 로 실행) ==="
fi
log ""

# ──────────────────────────────────────────────────────────
# Tier 1 — 빈 디렉토리 (hard delete)
# ──────────────────────────────────────────────────────────
log "── Tier 1: 빈 디렉토리 (즉시 삭제) ──"
empty_count=$(find "$CLAUDE_DIR/session-env" "$CLAUDE_DIR/ide" -type d -empty 2>/dev/null | wc -l | tr -d ' ')
log "빈 디렉토리: ${empty_count}개"
if $APPLY; then
  # session-env/ide 자체는 보존하고 내부 빈 디렉토리만 제거
  find "$CLAUDE_DIR/session-env" -mindepth 1 -type d -empty -delete 2>/dev/null || true
  find "$CLAUDE_DIR/ide" -mindepth 1 -type d -empty -delete 2>/dev/null || true
fi
log ""

# ──────────────────────────────────────────────────────────
# Tier 2 — stale orphan / legacy (quarantine 이동)
# ──────────────────────────────────────────────────────────
log "── Tier 2: stale orphan / legacy (quarantine 이동) ──"
quarantine_move() { # $1: 절대경로 — 존재하면 quarantine 으로 이동
  [ -e "$1" ] || return 0
  add_size "$1"
  log "  quarantine: ${1#$CLAUDE_DIR/}"
  if $APPLY; then
    ensure_quarantine
    mv "$1" "$QUARANTINE/"
  fi
}

quarantine_move "$CLAUDE_DIR/mcp.json.bak"
quarantine_move "$CLAUDE_DIR/backups/mcp-20260226-083240"
# transcripts/ 레거시 jsonl (2월 구 포맷)
if [ -d "$CLAUDE_DIR/transcripts" ]; then
  tcount=$(find "$CLAUDE_DIR/transcripts" -type f -name '*.jsonl' | wc -l | tr -d ' ')
  if [ "$tcount" -gt 0 ]; then
    add_size "$CLAUDE_DIR/transcripts"
    log "  quarantine: transcripts/ (${tcount}개 레거시 jsonl)"
    if $APPLY; then
      ensure_quarantine
      mv "$CLAUDE_DIR/transcripts" "$QUARANTINE/"
    fi
  fi
fi
# tmp/ 날짜별 handoff (handoff-latest.json 포인터는 보존)
for f in "$CLAUDE_DIR"/tmp/handoff-2026-*.json; do
  [ -e "$f" ] || continue
  quarantine_move "$f"
done
log ""

# ──────────────────────────────────────────────────────────
# Tier 3 — 재생성 캐시 / 로테이션 로그 (mtime +N hard delete)
# ──────────────────────────────────────────────────────────
log "── Tier 3: 재생성 캐시/로그 (${RETENTION_DAYS}일 초과 삭제) ──"
prune_old() { # $1: 디렉토리 — RETENTION_DAYS 초과 파일 삭제
  local dir="$1"
  [ -d "$dir" ] || return 0
  local n
  n=$(find "$dir" -type f -mtime +${RETENTION_DAYS} 2>/dev/null | wc -l | tr -d ' ')
  log "  ${dir#$CLAUDE_DIR/}: ${n}개 (>${RETENTION_DAYS}d)"
  [ "$n" -gt 0 ] || return 0
  while IFS= read -r f; do add_size "$f"; done < <(find "$dir" -type f -mtime +${RETENTION_DAYS} 2>/dev/null)
  $APPLY && find "$dir" -type f -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
}

prune_old "$CLAUDE_DIR/debug"
prune_old "$CLAUDE_DIR/shell-snapshots"
prune_old "$CLAUDE_DIR/paste-cache"
prune_old "$CLAUDE_DIR/telemetry"
prune_old "$CLAUDE_DIR/cache"

# daemon.log (rotatable)
if [ -f "$CLAUDE_DIR/daemon.log" ]; then
  add_size "$CLAUDE_DIR/daemon.log"
  log "  daemon.log: 1개"
  $APPLY && : > "$CLAUDE_DIR/daemon.log"   # truncate (daemon이 핸들 유지 가능 → unlink 대신 비움)
fi

# .claude.json.backup.* — 최신 BACKUP_KEEP개 보존, 나머지 삭제
mapfile -t backups < <(ls -1t "$CLAUDE_DIR"/backups/.claude.json.backup.* 2>/dev/null || true)
if [ "${#backups[@]}" -gt "$BACKUP_KEEP" ]; then
  old=("${backups[@]:$BACKUP_KEEP}")
  log "  .claude.json.backup.*: ${#old[@]}개 (최신 ${BACKUP_KEEP}개 보존)"
  for f in "${old[@]}"; do
    add_size "$f"
    $APPLY && rm -f "$f"
  done
else
  log "  .claude.json.backup.*: 0개 (${#backups[@]}개 ≤ ${BACKUP_KEEP} 보존선)"
fi
log ""

# ──────────────────────────────────────────────────────────
# 요약
# ──────────────────────────────────────────────────────────
human() { # bytes → human readable
  local b=$1
  if   [ "$b" -ge 1073741824 ]; then awk "BEGIN{printf \"%.1fG\", $b/1073741824}"
  elif [ "$b" -ge 1048576 ];    then awk "BEGIN{printf \"%.1fM\", $b/1048576}"
  elif [ "$b" -ge 1024 ];       then awk "BEGIN{printf \"%.1fK\", $b/1024}"
  else echo "${b}B"; fi
}
log "=== 회수 예상/완료 용량: $(human "$freed_bytes") ==="
if $APPLY; then
  [ -n "$QUARANTINE" ] && log "quarantine 위치: ${QUARANTINE}  (복원: mv 내부 파일 → 원위치)"
  log "완료. --dry-run 재실행으로 idempotency 확인 가능."
else
  log "실제 정리하려면: $0 --apply"
fi
