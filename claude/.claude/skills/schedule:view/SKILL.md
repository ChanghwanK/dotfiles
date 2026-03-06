---
name: schedule:view
description: |
  Notion Task/Goal/Daily DB와 Google Calendar을 통합 조회하는 일정 현황 스킬.
  사용 시점: (1) 이번 주 할 일과 진행 상황 확인, (2) 목표 대비 진행률 체크, (3) 일정 정리 (weekly review), (4) 오늘/내일 일정 파악.
  트리거 키워드: "일정 정리", "이번 주 현황", "목표 확인", "schedule", "weekly view", "진행 상황", "할 일 정리", "schedule:view".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/schedule:view/scripts/notion-schedule.py *)
  - mcp__claude_ai_Google_Calendar__gcal_list_events
  - mcp__claude_ai_Google_Calendar__gcal_find_my_free_time
---
# schedule:view

Notion Task/Goal/Daily DB와 Google Calendar을 통합 조회하여 이번 주 일정 현황을 한눈에 보여준다.

---

## 핵심 원칙

- Notion 데이터는 스크립트로만 조회. Notion MCP 도구 사용하지 않음 (토큰 효율)
- Google Calendar은 MCP 도구(`gcal_list_events`)로 직접 조회
- 읽기 전용 — 명시적 요청 없이 Notion 데이터 수정 금지

---

## 워크플로우

### Step A — 데이터 수집 (병렬)

Notion 통합 데이터와 Google Calendar을 동시에 조회한다.

**1. Notion 통합 조회:**
```bash
python3 /Users/changhwan/.claude/skills/schedule:view/scripts/notion-schedule.py dashboard --week current
```

**2. Google Calendar 이번 주 일정 조회 (`gcal_list_events` MCP):**
- `calendar_id`: `primary`
- `time_min`: 이번 주 월요일 00:00 KST (ISO 8601)
- `time_max`: 이번 주 일요일 23:59 KST (ISO 8601)

### Step B — 통합 출력

JSON 데이터를 파싱하여 아래 형식으로 출력한다.

```
📋 이번 주 현황 (MM/DD ~ MM/DD)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 이번 주 Tasks
  진행 중 🔄
  - [P1] Task이름 (WORK) — due: 3/5
  - [P2] Task이름 (MY) — due: 3/7

  시작 전 ⏳
  - [P1] Task이름 — due: 3/6

  대기 ⏸️  (N개) | 완료 ✅ (N개)

🎯 목표 현황

  분기 (1Q)
  - [P1] 1Q - Goals

  회사 목표
  - Riiid에서 할 수 있는 경험

📅 오늘 일정 (Google Calendar)
  - 10:00-11:00 팀 미팅
  - 14:00-15:00 1:1
```

목표 현황은 type 기준으로 그룹화한다: `1Q` / `연간` (P1 우선, P2 후순) / `회사 목표` / `Vision` 순으로 나열.

---

## 서브커맨드 참조

| 커맨드 | 설명 |
|--------|------|
| `dashboard --week current\|next` | 통합 뷰 (Task+Goal) |
| `tasks --status in-progress\|upcoming\|all` | Task만 조회 |
| `goals` | 활성 Goal 목록 |

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- Goal DB는 Task DB와 relation 없음 — 태스크와 직접 연계 불가
- 완료/대기 Task는 개수만 표시 (상세 내용은 `tasks --status all`)
- Goal type 기준 그룹: `1Q` → `회사 목표` → `Vision` (연간 목표는 별도 스킬에서 관리)
