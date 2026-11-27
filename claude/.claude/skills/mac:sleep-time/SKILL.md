---
name: mac:sleep-time
description: |
  Mac의 전원 상태 로그에서 특정 시간대의 슬립/웨이크 이벤트를 조회합니다. 퇴근 시간이나 활동 패턴 추적에 사용됩니다.
  사용 시점: (1) 어제/특정일 퇴근 시간 확인, (2) 컴퓨터 슬립 패턴 분석, (3) 노트북 덮은 정확한 시각 찾기.
  트리거 키워드: "퇴근 시간", "슬립 시간", "언제 덮었어", "/mac:sleep-time".
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh *)
---
# mac:sleep-time

`pmset -g log`에서 지정한 날짜·시간 범위의 디스플레이 끔, 슬립, 웨이크 이벤트를 조회한다.

## 사용법

```bash
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh [OPTIONS]
# 예: 특정 날짜 저녁, 슬립만
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh \
  -d 2026-08-05 -s 18:00:00 -e 22:00:00 -f Sleep
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-d, --date DATE` | 조회 날짜 (YYYY-MM-DD) | 어제(로컬 시간 기준) |
| `-s, --start START` | 시작 시간 (HH:MM:SS) | 00:00:00 |
| `-e, --end END` | 종료 시간 (HH:MM:SS) | 23:59:59 |
| `-f, --filter FILTER` | 이벤트 필터 정규식, 대소문자 구분 (Display/Sleep/Wake) | 모두 |

## 출력 해석

```
2026-08-05 21:06:23 +0900 Notification        Display is turned off
2026-08-05 21:06:28 +0900 Sleep               Entering Sleep state due to 'Clamshell Sleep'
```

- `Display is turned off`: 화면이 자동으로 꺼진 시각
- `Clamshell Sleep`: 노트북을 덮은 시각. 퇴근 시간 지표로 쓴다

`pmset -g log`는 최근 부팅 이후의 로그만 보여 준다. 오래된 날짜는 `/var/log/system.log*` 아카이브가 필요하다.
