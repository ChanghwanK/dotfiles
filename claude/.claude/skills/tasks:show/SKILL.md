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

세 커맨드를 순서대로 실행하여 이번 주 + 지난 주 + 오늘 Obsidian 데이터를 수집한다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py tasks --week current
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py tasks --week previous
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py today
```

`today` 커맨드가 에러를 반환하거나 파일이 없으면 해당 섹션을 생략하고 Notion 데이터만으로 진행.

#### Step 2 — 분석 & 브리핑 출력

수집한 JSON 데이터를 파싱하여 아래 형식으로 출력한다.

```
----
📋 이번 주 Task 브리핑 (MM/DD ~ MM/DD)

🚀 이번 주 Tasks

  🔄 진행 중 (N개)
    - [P1] Task이름 (WORK) — due: MM/DD

  ⏳ 시작 전 (N개)
    - [P1] Task이름 — due: MM/DD

  ✅ 완료 (N개)
    - Task이름

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 오늘 할 것들 (Obsidian Daily Note)
  Top 3 목표:
    - [ ] Task이름
    - [x] Task이름 ✅

  Todos (N개):
    - [ ] Task이름
    - [x] Task이름 ✅

  📊 오늘 진행률: N/M (XX%) — 하루 시작
  ※ Obsidian Daily Note 없으면 이 섹션 전체 생략, 대신 안내:
  ⚠️ 오늘 Obsidian Daily Note 없음 — Notion 데이터만으로 브리핑합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


💡 우선순위 제안
  1. [P1] Task이름 — 근거 설명. due D-N.
  2. [P1] Task이름 — 근거 설명. due D-N.
  3. [P1] Task이름 — 근거 설명. due D-N.

  💬 제안 근거:
  - (실제 데이터 기반 분석 내용)
  - (마감일 임박, 이월 여부, Top 3 포함 여부 등)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


⚠️ 놓친 것들
  - [P1] Task이름 — 지난 주 due: MM/DD (상태, 미이월)
  → 이번 주 Tasks에 없음. 필요하면 `/tasks:manage`로 이월하세요.
  없으면 이 섹션 생략.

----

⚡ 요약: (한 줄 핵심 요약 — 오늘 집중 포인트 + 마감 위험 알림)
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

### 우선순위 제안 기준 (최대 3개)

Obsidian + Notion 통합 데이터를 기반으로 근거를 포함한 우선순위를 제안한다.

1. **Obsidian Top 3 목표**에 지정된 항목 → 최우선 (사용자의 명시적 집중 대상)
2. **Notion "진행 중"** + **Due Date 임박** → 높음 (이미 시작한 작업 완료 우선)
3. **⏫ 마커**가 있는 항목 → 높음
4. **반복 이월 Task** (지난 주에도 있었던 항목) → 조기 처리 권장 (이월 반복 방지)
5. **개인(MY) / 비업무 항목** → 후순위 배치 (업무 항목 먼저)
6. 각 항목에 근거를 1줄씩 표시 (예: "Notion 진행 중 + Obsidian Top 3")

### 놓친 것 감지

- 지난 주 Tasks 중 `status != "완료"` 이면서 이번 주 Tasks에 동일 이름이 없는 것
- carry-over 되지 않은 미완료 Task = 놓친 것
- 없으면 "⚠️ 놓친 것들" 섹션 자체를 생략

---

## 서브커맨드 참조

| 커맨드 | 설명 |
|--------|------|
| `tasks --week previous\|current\|next` | 주 단위 Task 조회 |
| `tasks --month YYYY-MM` | 월 단위 Task 조회 (`--week` 무시) |
| `today` | Obsidian daily note 기반 경량 브리핑 (Top 3 + Todos 진행률) |
| `daily-progress` | Daily DB 이번 주 진행률 |

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- JSON 원본을 그대로 출력하지 말 것 — 반드시 브리핑 포맷으로 가공
- `--month`와 `--week` 동시 지정 시 `--month` 우선
