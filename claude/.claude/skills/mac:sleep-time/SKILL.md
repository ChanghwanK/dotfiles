---
name: mac:sleep-time
description: |
  Mac의 전원 상태 로그에서 특정 시간대의 슬립/웨이크 이벤트를 조회합니다. 퇴근 시간이나 활동 패턴 추적에 사용됩니다.
  사용 시점: (1) 어제/특정일 퇴근 시간 확인, (2) 컴퓨터 슬립 패턴 분석, (3) 노트북 덮은 정확한 시각 찾기.
  트리거 키워드: "퇴근 시간", "슬립 시간", "언제 덮었어", "/mac:sleep-time".
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh *)
---
# mac:sleep-time Tool

Mac의 `pmset -g log` 명령으로 기록되는 전원 관리 로그를 쿼리하여,
특정 날짜와 시간 범위 내의 슬립(Clamshell Sleep), 디스플레이 끔, 웨이크 이벤트를 조회합니다.

노트북을 덮은 정확한 시각, 하루 중 활동 패턴(유휴 시간, 슬립 빈도)을 추적할 때 유용합니다.

---

## 사용법

```bash
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh [OPTIONS]
```

---

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-d, --date DATE` | 조회 날짜 (YYYY-MM-DD) | 어제 |
| `-s, --start START` | 시작 시간 (HH:MM:SS) | 00:00:00 |
| `-e, --end END` | 종료 시간 (HH:MM:SS) | 23:59:59 |
| `-f, --filter FILTER` | 이벤트 필터 (Display/Sleep/Wake) | 모두 |
| `-h, --help` | 도움말 표시 | - |

---

## 예시

### 1. 어제 전체 슬립 이벤트 조회 (기본값)
```bash
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh
```

### 2. 특정 날짜 저녁 시간대 조회
```bash
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh \
  -d 2026-08-05 -s 18:00:00 -e 22:00:00
```

### 3. 슬립 이벤트만 필터링
```bash
bash /Users/changhwan/.claude/skills/mac:sleep-time/scripts/mac-sleep-time.sh -f Sleep
```

### 4. 출력 해석

```
2026-08-05 21:06:23 +0900 Notification        Display is turned off
2026-08-05 21:06:28 +0900 Sleep               Entering Sleep state due to 'Clamshell Sleep'
```

- **21:06:23**: 화면이 자동으로 꺼진 시각
- **21:06:28**: Clamshell Sleep (노트북 덮힘) 정확한 시각 ← **퇴근 시간 지표**

---

## 주의사항

- **기본 시간대**: UTC 기준 어제. macOS의 시간대 설정에 따라 다를 수 있음
- **Log rotation**: `pmset -g log`는 최근 부팅 이후의 로그만 표시. 오래된 날짜는 `/var/log/system.log*` 아카이브 필요
- **권한**: `pmset -g log`는 일반 사용자도 실행 가능 (시스템 로그는 권한 필요)
- **필터 구문**: 정규식은 대소문자 구분. `Display is turned off` 정확히 매칭
