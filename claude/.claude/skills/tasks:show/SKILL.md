---
name: tasks:show
description: |
  Task 조회 및 분석 스킬. 여러 소스(Notion, Obsidian 등)에서 할 일을 조회하고 분석 기반 브리핑 제공.
  오늘 집중할 것 추천, 놓친 Task 감지, 진행률 요약.
  Obsidian Daily Note 기반 중간 리뷰 (today 커맨드: Top 3 목표, Todos 진행률) 지원.
  사용 시점: (1) 할 일과 진행 상황 확인, (2) 오늘 뭐 해야 하는지 추천, (3) 놓친 Task 확인, (4) 진행률 리뷰, (5) 오늘 중간 점검.
  트리거 키워드: "일정 정리", "할 일", "task view", "진행 상황", "오늘 뭐 해야 해", "tasks:show",
  "중간 점검", "오늘 리뷰", "today".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py *)
---

# tasks:show

여러 소스에서 Task를 조회하여 **분석 기반 브리핑**을 제공한다. 단순 데이터 나열이 아닌 추천과 알림.

---

## 핵심 원칙

- Notion 데이터는 스크립트로만 조회. Notion MCP 도구 사용하지 않음 (토큰 효율)
- 읽기 전용 — Notion 데이터 수정 절대 금지
- 데이터를 분석하여 **브리핑** 형태로 출력 (JSON 원본 출력 금지)

---

## 워크플로우

사용자 요청에 따라 아래 두 가지 중 하나를 선택:

### A. 주간 브리핑 (기존)

트리거: "이번 주 현황", "주간 리뷰", "놓친 Task", "일정 정리", "할 일"

#### Step 1 — 데이터 수집

두 커맨드를 순서대로 실행하여 이번 주 + 지난 주 데이터를 수집한다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py dashboard --week current
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py tasks --week previous
```

#### Step 2 — 분석 & 브리핑 출력

수집한 JSON 데이터를 파싱하여 아래 형식으로 출력한다.

```
📋 이번 주 Task 브리핑 (MM/DD ~ MM/DD)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 이번 주 Tasks
  🔄 진행 중 (N개)
    - [P1] Task이름 (WORK) — due: MM/DD
  ⏳ 시작 전 (N개)
    - [P1] Task이름 — due: MM/DD
  ⏸️ 대기 (N개) | ✅ 완료 (N개)

💡 오늘 추천
  - [P1] Task이름 — due: MM/DD (진행 중)
  - [P1] Task이름 — due: MM/DD (시작 전)
  최대 3개. 아래 기준으로 선정.

📅 Due 미설정 진행 중 (N개)
  진행 중이지만 Due Date가 없는 Task 목록.
  - [P1] Task이름 (WORK) — ⚠️ Due Date 없음
  → Due Date를 설정하면 주간 브리핑에서 추적할 수 있습니다.
    `/task:manage`로 Due Date를 설정하세요.
  없으면 이 섹션 생략.

⚠️ 놓친 것들
  - [P1] Task이름 — 지난 주 due: MM/DD (미이월)
  없으면 이 섹션 생략.

📊 이번 주 진행률
  Daily Progress 데이터 기반 요약.
```

### B. 중간 리뷰 (신규)

트리거: "지금 뭐 해야 해", "중간 점검", "오늘 리뷰", "진행 상황"

#### Step 1 — 데이터 수집

```bash
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py today
```

#### Step 2 — 간소화된 브리핑 출력

데이터 소스: Obsidian daily note (`~/...obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md`)

```
⏰ 오늘 중간 리뷰 (HH:MM 기준)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Top 3 목표
  - [ ] Task이름 — due: MM/DD
  - [x] Task이름 ✅

🔄 미완료 (N개)
  - Task이름 — due: MM/DD
  - Task이름 (⏫)

✅ 완료 (N개)
  - Task이름

📊 오늘 진행률: N/M (XX%)
```

- Obsidian daily note에서 직접 파싱 (Notion API 호출 없음)
- NOTION_TOKEN 불필요
- 주간 브리핑 대비 **놓친 것들**, **주간 진행률** 섹션 생략
- 출력량 50% 감소

---

## 분석 로직

### 오늘 추천 기준 (최대 3개)

1. 상태가 "진행 중"인 Task 우선
2. P1 > P2 순
3. due_date가 오늘에 가까운 순
4. 최대 3개 선정

### 놓친 것 감지

- 지난 주 Tasks 중 `status != "완료"` 이면서 이번 주 Tasks에 동일 이름이 없는 것
- carry-over 되지 않은 미완료 Task = 놓친 것
- 없으면 "⚠️ 놓친 것들" 섹션 자체를 생략

---

## 서브커맨드 참조

| 커맨드 | 설명 |
|--------|------|
| `dashboard --week previous\|current\|next` | Task + Daily Progress 통합 뷰 |
| `tasks --week previous\|current\|next` | 주 단위 Task 조회 |
| `tasks --month YYYY-MM` | 월 단위 Task 조회 (`--week` 무시) |
| `today` | Obsidian daily note 기반 경량 브리핑 (Top 3 + Todos 진행률) |
| `daily-progress` | Daily DB 이번 주 진행률 |

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- JSON 원본을 그대로 출력하지 말 것 — 반드시 브리핑 포맷으로 가공
- `--month`와 `--week` 동시 지정 시 `--month` 우선
