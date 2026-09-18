#!/bin/bash
set -euo pipefail

# Mac의 pmset 로그에서 특정 날짜/시간 범위의 슬립/웨이크 이벤트 조회

usage() {
  cat << 'EOF'
Usage: mac-sleep-time.sh [OPTIONS]

Options:
  -d, --date DATE       조회 날짜 (YYYY-MM-DD 형식, 기본: 어제)
  -s, --start START     시작 시간 (HH:MM:SS 형식, 기본: 00:00:00)
  -e, --end END         종료 시간 (HH:MM:SS 형식, 기본: 23:59:59)
  -f, --filter FILTER   이벤트 필터 (Display|Sleep|Wake, 기본: 모두)
  -h, --help            이 도움말 표시

Examples:
  # 어제 전체 슬립 이벤트 조회
  mac-sleep-time.sh

  # 특정 날짜 저녁 시간 조회
  mac-sleep-time.sh -d 2026-08-05 -s 18:00:00 -e 22:00:00

  # 슬립 이벤트만 필터링
  mac-sleep-time.sh -f Sleep
EOF
  exit 0
}

# 기본값
DATE=$(date -u -v-1d +%Y-%m-%d)  # 어제 (UTC 기준, macOS)
START="00:00:00"
END="23:59:59"
FILTER=""

# 옵션 파싱
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--date)
      DATE="$2"
      shift 2
      ;;
    -s|--start)
      START="$2"
      shift 2
      ;;
    -e|--end)
      END="$2"
      shift 2
      ;;
    -f|--filter)
      FILTER="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

# 필터 조건 구성
if [ -z "$FILTER" ]; then
  # 모든 슬립/웨이크 관련 이벤트
  FILTER_REGEX='Display is turned off|Entering Sleep|Wake|UserIsActive|keyboard|trackpad'
else
  FILTER_REGEX="$FILTER"
fi

# pmset 로그 필터링
echo "═════════════════════════════════════════" >&2
echo "조회 결과: $DATE $START ~ $END" >&2
echo "필터: $FILTER_REGEX" >&2
echo "═════════════════════════════════════════" >&2

pmset -g log | awk -v date="$DATE" -v start="$START" -v end="$END" -v regex="$FILTER_REGEX" \
  '$1 == date && $2 >= start && $2 <= end && $0 ~ regex { print }'
