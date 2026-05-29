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
readonly MEM_DIR="${HOME}/.claude-mem"   # Tier 4C 대상 — CLAUDE_DIR 가드 밖의 고정 상수(사용자 입력 아님)
readonly RETENTION_DAYS=7
readonly TIER4_RETENTION=30              # Tier 4A 트랜스크립트 보존 기준 (RETENTION_DAYS=7 과 분리)
readonly BACKUP_KEEP=3                   # .claude.json.backup.* 보존 개수

# 오용 가드: 대상은 반드시 ~/.claude 여야 한다 (다른 경로 삭제 방지)
case "$CLAUDE_DIR" in
  "${HOME}/.claude") ;;
  *) echo "FATAL: CLAUDE_DIR is not ~/.claude — aborting" >&2; exit 1 ;;
esac
[ -d "$CLAUDE_DIR" ] || { echo "FATAL: $CLAUDE_DIR not found" >&2; exit 1; }

# 플래그 스캔 — --apply 와 --tier4 는 순서 무관하게 공존 가능
# --tier4 는 cron 에 등록되지 않은 opt-in 으로, 대용량 트랜스크립트/백업을 정리한다
APPLY=false
TIER4=false
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=true ;;
    --tier4) TIER4=true ;;
    *) echo "unknown arg: $arg (사용법: $0 [--apply] [--tier4])" >&2; exit 1 ;;
  esac
done

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

# tmp/ daily 센티넬 마커 — daily:start 의 once-per-day 중복실행 가드(0바이트, 날짜별 누적).
# 가드는 "오늘" 파일만 확인하므로 7일 초과분은 무의미. prefix 매칭으로
# handoff-*.json·pending-notification.txt·CLAUDE.md 는 보호된다.
if [ -d "$CLAUDE_DIR/tmp" ]; then
  sentinel=(-maxdepth 1 -type f -name 'start-daily-*' -mtime +${RETENTION_DAYS})
  n=$(find "$CLAUDE_DIR/tmp" "${sentinel[@]}" 2>/dev/null | wc -l | tr -d ' ')
  log "  tmp/start-daily-* 센티넬: ${n}개 (>${RETENTION_DAYS}d)"
  if [ "$n" -gt 0 ]; then
    while IFS= read -r f; do add_size "$f"; done < <(find "$CLAUDE_DIR/tmp" "${sentinel[@]}" 2>/dev/null)
    $APPLY && find "$CLAUDE_DIR/tmp" "${sentinel[@]}" -delete 2>/dev/null || true
  fi
fi

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
# Tier 4 — 대용량 (opt-in: --tier4, cron 미포함)
# ──────────────────────────────────────────────────────────
# 4A: ingest 완료된 오래된 subagent 트랜스크립트 (Claude Code 기본 cleanup이 놓치는 중첩 경로)
tier4_transcripts() {
  local projects_dir="$CLAUDE_DIR/projects"
  [ -d "$projects_dir" ] || return 0
  # */subagents/*.jsonl 만 매칭 → top-level 세션 트랜스크립트는 불가침.
  # -mtime +30 → 오늘 파일·활성 observer 세션(<30d)은 절대 미매칭(활성 보호).
  local pred=(-type f -path '*/subagents/*.jsonl' -mtime +"${TIER4_RETENTION}")
  local n
  n=$(find "$projects_dir" "${pred[@]}" 2>/dev/null | wc -l | tr -d ' ')
  log "  subagents/*.jsonl (>${TIER4_RETENTION}d): ${n}개"
  [ "$n" -gt 0 ] || return 0
  while IFS= read -r f; do add_size "$f"; done < <(find "$projects_dir" "${pred[@]}" 2>/dev/null)
  $APPLY && find "$projects_dir" "${pred[@]}" -delete 2>/dev/null || true
}

# 4C: claude-mem 일회성 마이그레이션 백업 — 적용 완료 마커가 있을 때만 삭제(마커 게이트)
# MEM_DIR 은 CLAUDE_DIR 가드 밖이지만 고정 상수이고 glob 이 구체적이라 blast radius 가 한정된다.
tier4_mem_backups() {
  [ -d "$MEM_DIR" ] || return 0
  if [ -f "$MEM_DIR/.cwd-remap-applied-v1" ]; then
    for f in "$MEM_DIR"/claude-mem.db.bak-cwd-remap-*; do
      [ -e "$f" ] || continue
      add_size "$f"; log "  mem backup: ${f##*/}"; $APPLY && rm -f "$f"
    done
  else
    log "  (skip cwd-remap backup: applied 마커 없음)"
  fi
  if [ -f "$MEM_DIR/.cleanup-v12.4.3-applied" ]; then
    for f in "$MEM_DIR"/backups/claude-mem-pre-12.4.3-*.db; do
      [ -e "$f" ] || continue
      add_size "$f"; log "  mem backup: ${f##*/}"; $APPLY && rm -f "$f"
    done
  else
    log "  (skip pre-12.4.3 backup: applied 마커 없음)"
  fi
}

if $TIER4; then
  log "── Tier 4A: subagent 트랜스크립트 (>${TIER4_RETENTION}d hard delete) ──"
  tier4_transcripts
  log ""
  log "── Tier 4C: claude-mem 마이그레이션 백업 (마커 게이트) ──"
  tier4_mem_backups
  log ""
fi

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
  if $TIER4; then
    log "실제 정리하려면: $0 --tier4 --apply"
  else
    log "실제 정리하려면: $0 --apply   (대용량 트랜스크립트/백업까지: --tier4 추가)"
  fi
fi
