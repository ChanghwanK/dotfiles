#!/usr/bin/env bash
#
# jvm-eventloop-tid.sh
#
# 파드 안 JVM에서 Netty event loop(기본 대상: Lettuce/Redis) 스레드의 OS TID를 찾고,
# 스레드별 CPU 부하 분포를 측정한다. 읽기 전용이며 파드 상태를 변경하지 않는다.
#
# 왜 필요한가:
#   "어느 스레드가 Redis I/O를 처리하는가"는 jstack의 논리적 스레드명만으로는 답이 안 된다.
#   커널 레벨 CPU 회계(/proc/<pid>/task/<tid>/stat)를 보려면 OS TID가 필요하고,
#   JVM 스레드와 OS 스레드를 잇는 유일한 열쇠가 jstack 헤더의 nid(16진 TID) 필드다.
#
# 사용법:
#   jvm-eventloop-tid.sh [-c CONTEXT] [-n NAMESPACE] [-C CONTAINER]
#                        [-d SECONDS] [-p REGEX] [-x] POD
#
#   -c  kubectl context        (기본: 현재 context)
#   -n  namespace              (기본: 현재 namespace)
#   -C  container              (기본: spec.containers[0])
#   -d  실시간 샘플링 구간(초)  (기본: 20)
#   -p  스레드명 매칭 regex     (기본: lettuce|netty|redis|EventLoop|eventExecutor)
#   -x  Effective CPU Count 프로브 생략 (새 JVM을 1회 fork하는 것을 피하고 싶을 때)
#
# 예:
#   jvm-eventloop-tid.sh -c k8s-prod -n santa-http-api -d 30 santa-http-api-5b77c7454d-kpz8h
#   jvm-eventloop-tid.sh -p 'kafka|http-nio' -d 10 my-pod        # 다른 스레드 풀 조사
#
# 주의:
#   jcmd Thread.print은 safepoint를 유발한다(수백 스레드 기준 수 ms). 덤프는 1회만 뜬다.
#
set -euo pipefail

CONTEXT=""; NAMESPACE=""; CONTAINER=""; DURATION=20
PATTERN='lettuce|netty|redis|EventLoop|eventExecutor'
PROBE_CPU=1

usage() { sed -n '2,32p' "$0" | sed 's/^#\{1,\} \{0,1\}//'; exit 1; }

while getopts ":c:n:C:d:p:xh" opt; do
  case "$opt" in
    c) CONTEXT="$OPTARG" ;;
    n) NAMESPACE="$OPTARG" ;;
    C) CONTAINER="$OPTARG" ;;
    d) DURATION="$OPTARG" ;;
    p) PATTERN="$OPTARG" ;;
    x) PROBE_CPU=0 ;;
    h) usage ;;
    \?) echo "unknown option: -$OPTARG" >&2; usage ;;
  esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage
POD="$1"

KC=(kubectl)
[ -n "$CONTEXT" ]   && KC+=(--context "$CONTEXT")
[ -n "$NAMESPACE" ] && KC+=(-n "$NAMESPACE")

# container 미지정 시, istio-proxy 같은 사이드카가 아니라 애플리케이션 container를
# 잡기 위해 spec.containers[0]을 기준으로 한다.
if [ -z "$CONTAINER" ]; then
  CONTAINER="$("${KC[@]}" get pod "$POD" -o jsonpath='{.spec.containers[0].name}')"
fi

echo "# pod=$POD  container=$CONTAINER  window=${DURATION}s  pattern=/$PATTERN/"
echo

"${KC[@]}" exec -i "$POD" -c "$CONTAINER" -- sh -s -- "$DURATION" "$PATTERN" "$PROBE_CPU" <<'REMOTE'
#!/bin/sh
# ===== 파드 내부 페이로드: POSIX sh + POSIX awk 전용 =====
# 컨테이너 이미지에 bash / strtonum 지원 awk(gawk) / unzip 이 없을 수 있으므로 쓰지 않는다.
DURATION="$1"; PATTERN="$2"; PROBE_CPU="$3"
unset JAVA_TOOL_OPTIONS            # 이 스크립트가 띄우는 java/jcmd에 otel javaagent가 붙지 않게 한다
TICK=$(getconf CLK_TCK 2>/dev/null || echo 100)
TAB=$(printf '\t')
TMP=/tmp/.eltid.$$
mkdir -p "$TMP"; trap 'rm -rf "$TMP"' EXIT INT TERM

# ---------- 1. 대상 JVM PID ----------
JPID=$(jcmd 2>/dev/null | awk '$1 ~ /^[0-9]+$/ && $2 !~ /jcmd|JCmd/ {print $1; exit}')
if [ -z "${JPID:-}" ]; then
  for p in /proc/[0-9]*; do
    [ -r "$p/cmdline" ] || continue
    case "$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null)" in
      *java\ *|*/java\ *) JPID="${p#/proc/}"; break ;;
    esac
  done
fi
[ -n "${JPID:-}" ] || { echo "ERROR: JVM 프로세스를 찾지 못했습니다." >&2; exit 1; }

# ---------- 2. 스레드 덤프 (safepoint 1회) ----------
jcmd "$JPID" Thread.print > "$TMP/td.txt" 2>/dev/null || {
  echo "ERROR: jcmd attach 실패. exec uid가 JVM 소유자와 같은지 확인하십시오." >&2; exit 1; }

# ---------- 3. jstack 헤더 파싱: nid(hex) -> TID(dec) ----------
# mawk에는 strtonum()이 없으므로 16진 변환을 직접 구현한다.
# 출력 컬럼: TID \t NAME \t NID \t CPU_ms \t ELAPSED_s \t STATE \t TOP_FRAME
awk -v pat="$PATTERN" '
function hex2dec(s,   i,n,d) {
  s = tolower(s); sub(/^0x/, "", s); n = 0
  for (i = 1; i <= length(s); i++) {
    d = index("0123456789abcdef", substr(s, i, 1)) - 1
    if (d < 0) return -1
    n = n * 16 + d
  }
  return n
}
function flush_rec() {
  if (name != "" && name ~ pat && nid != "")
    printf "%d\t%s\t%s\t%s\t%s\t%s\t%s\n", hex2dec(nid), name, nid, cpu, el, state, frame
  name = ""; nid = ""; cpu = "0"; el = "0"; state = "?"; frame = "-"
}
BEGIN { cpu = "0"; el = "0"; state = "?"; frame = "-" }
/^"/ {
  flush_rec()
  name = $0; sub(/^"/, "", name); sub(/".*/, "", name)
  for (i = 1; i <= NF; i++) {
    if ($i ~ /^cpu=/)     { cpu = substr($i, 5); sub(/ms$/, "", cpu) }
    if ($i ~ /^elapsed=/) { el  = substr($i, 9); sub(/s$/,  "", el)  }
    if ($i ~ /^nid=/)     { nid = substr($i, 5) }
  }
  next
}
/Thread\.State:/ { state = $2; next }
/^[ \t]*at / { if (frame == "-") { f = $0; sub(/^[ \t]*at /, "", f); frame = f } next }
END { flush_rec() }
' "$TMP/td.txt" | sort -t"$TAB" -k4 -g -r > "$TMP/threads.tsv"

if [ ! -s "$TMP/threads.tsv" ]; then
  echo "매칭되는 스레드가 없습니다 (pattern=/$PATTERN/)."
  echo "덤프에 존재하는 스레드명(숫자 정규화, 상위 25):"
  grep -o '^"[^"]*"' "$TMP/td.txt" | sed 's/[0-9][0-9]*/N/g' | sort -u | head -25
  exit 0
fi

# ---------- 4. 델타 측정 ----------
# jstack의 cpu= 는 누적값이라 "지금" 부하를 못 본다. 두 시점의 utime+stime 차이를 쓴다.
cg_usage() {   # 컨테이너 전체 CPU 사용량(usec). cgroup v2 / v1 모두 지원
  if [ -r /sys/fs/cgroup/cpu.stat ]; then
    awk '/^usage_usec/ {print $2; f=1} END {if (!f) print 0}' /sys/fs/cgroup/cpu.stat
  elif [ -r /sys/fs/cgroup/cpuacct/cpuacct.usage ]; then
    awk '{printf "%d\n", $1 / 1000}' /sys/fs/cgroup/cpuacct/cpuacct.usage
  else echo 0; fi
}
snap() {
  cut -f1 "$TMP/threads.tsv" | while read -r tid; do
    if [ -r "/proc/$JPID/task/$tid/stat" ]; then
      awk -v T="$tid" '{print T, $14 + $15}' "/proc/$JPID/task/$tid/stat"
    else
      echo "$tid 0"
    fi
  done
}

C1=$(cg_usage); snap | sort > "$TMP/s1"
sleep "$DURATION"
C2=$(cg_usage); snap | sort > "$TMP/s2"
CG_DELTA=$((C2 - C1))
join "$TMP/s1" "$TMP/s2" > "$TMP/delta"

# ---------- 5. 리포트 ----------
echo "== JVM =="
printf "pid=%s  total_threads=%s  clk_tck=%s\n" \
  "$JPID" "$(ls "/proc/$JPID/task" | wc -l | tr -d ' ')" "$TICK"
java -version 2>&1 | head -1
echo

echo "== 매칭 스레드 (누적, jstack cpu= 기준) =="
printf "%-7s %-32s %-6s %11s %9s %10s  %s\n" TID NAME NID CPU_s "%1core" STATE TOP_FRAME
awk -F"$TAB" '{
  cpus = $4 / 1000; el = $5 + 0
  pct = (el > 0) ? cpus / el * 100 : 0
  fr = $7; if (length(fr) > 44) fr = substr(fr, 1, 41) "..."
  printf "%-7s %-32s %-6s %11.1f %8.3f%% %10s  %s\n", $1, substr($2, 1, 32), $3, cpus, pct, $6, fr
}' "$TMP/threads.tsv"
echo

echo "== 실시간 부하 (${DURATION}s 윈도, /proc/<pid>/task/<tid>/stat 델타) =="
awk -v c="$CG_DELTA" -v d="$DURATION" \
  'BEGIN { printf "컨테이너 전체: %.3f s  (코어 대비 %.2f%%)\n", c/1000000, c/10000/d }'
printf "%-7s %-32s %9s %9s %11s\n" TID NAME DELTA_s "%1core" "%JVM_CPU"
awk -v TICK="$TICK" -v D="$DURATION" -v CG="$CG_DELTA" -v TAB="$TAB" '
  NR == FNR { split($0, f, TAB); n[f[1]] = f[2]; next }
  {
    d = ($3 - $2) / TICK
    pct = d / D * 100
    jvm = (CG > 0) ? d / (CG / 1000000) * 100 : 0
    printf "%-7s %-32s %9.2f %8.2f%% %10.1f%%\n", $1, substr(n[$1], 1, 32), d, pct, jvm
  }' "$TMP/threads.tsv" "$TMP/delta" | sort -k3 -g -r
echo

echo "== 부하 편중 (I/O event loop 한정) =="
grep -iE 'epollEventLoop|nioEventLoop|kqueueEventLoop' "$TMP/threads.tsv" \
  | awk -F"$TAB" '{ c[NR] = $4 / 1000; n[NR] = $2 }
    END {
      if (NR < 2) { print "  event loop 스레드가 " NR "개라 비교 대상이 없습니다."; exit }
      mx = -1; mn = 1e18
      for (i = 1; i <= NR; i++) {
        if (c[i] > mx) { mx = c[i]; nx = n[i] }
        if (c[i] < mn) { mn = c[i]; nn = n[i] }
      }
      printf "  loop 수: %d\n  최다: %-30s %10.1f s\n  최소: %-30s %10.1f s\n", NR, nx, mx, nn, mn
      if (mn > 0) printf "  편중 비율: %.1f : 1\n", mx / mn
      else        print  "  편중 비율: 최소값 0 (해당 loop에 트래픽 없음)"
    }'
echo

echo "== JVM이 인식하는 CPU (event loop 개수를 결정하는 값) =="
if [ -r /sys/fs/cgroup/cpu.max ]; then
  echo "  cgroup v2  cpu.max=$(cat /sys/fs/cgroup/cpu.max)  cpu.weight=$(cat /sys/fs/cgroup/cpu.weight 2>/dev/null)"
else
  echo "  cgroup v1  quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2>/dev/null) period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2>/dev/null) shares=$(cat /sys/fs/cgroup/cpu/cpu.shares 2>/dev/null)"
fi
echo "  throttling: $(awk '/nr_throttled|throttled_usec|nr_periods/ {printf "%s=%s  ", $1, $2}' /sys/fs/cgroup/cpu.stat 2>/dev/null)"
echo "  nproc(가시): $(nproc 2>/dev/null)"
if [ "$PROBE_CPU" = "1" ]; then
  java -XshowSettings:system -version 2>&1 \
    | grep -E 'Effective CPU Count|CPU Quota|CPU Shares|CPU Period|Memory Limit' \
    | sed 's/^ */  /'
else
  echo "  (Effective CPU Count 프로브 생략: -x)"
fi
echo "  GC worker 스레드 수: $(grep -cE '^"(ZWorker|GC Thread|G1 Conc|ParGC)' "$TMP/td.txt")"
echo

echo "== Redis 커넥션 분포 (ESTABLISHED) =="
RPORT=$(env | awk -F= '/REDIS_PORT/ {print $2; exit}'); [ -n "$RPORT" ] || RPORT=6379
awk -v rp="$RPORT" '
  function hex2dec(s,   i,n,d) {
    s = tolower(s); n = 0
    for (i = 1; i <= length(s); i++) {
      d = index("0123456789abcdef", substr(s, i, 1)) - 1
      if (d < 0) return -1
      n = n * 16 + d
    }
    return n
  }
  NR > 1 && $4 == "01" {
    split($3, a, ":"); h = a[1]
    ip = hex2dec(substr(h,7,2)) "." hex2dec(substr(h,5,2)) "." hex2dec(substr(h,3,2)) "." hex2dec(substr(h,1,2))
    p = hex2dec(a[2])
    if (p == rp + 0) redis[ip ":" p]++
    total++
  }
  END {
    n = 0
    for (k in redis) { printf "  %-26s x%d\n", k, redis[k]; n += redis[k] }
    if (n == 0) printf "  (포트 %s 로의 established 커넥션 없음)\n", rp
    else        printf "  redis 합계: %d  /  전체 established: %d\n", n, total
    print  "  주: 커넥션 수 > event loop 수 이면 채널이 loop에 다중 바인딩된 상태입니다."
  }' "/proc/$JPID/net/tcp" 2>/dev/null || echo "  (net/tcp 읽기 실패)"
REMOTE
