---
name: weekly:start
description: |
  주간 플래닝 워크플로우. 지난 주 리뷰 + 이번 주 목표 수립 + 분기 연계.
  사용 시점: (1) 월요일 아침 주간 계획, (2) 지난 주 회고, (3) 분기 목표 점검.
  트리거 키워드: "주간 플래닝", "이번 주 계획", "weekly start", "주간 리뷰",
  "weekly planning", "weekly:start".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/weekly:start/scripts/notion-weekly.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py *)
  - Agent
  - mcp__claude_ai_Google_Calendar__gcal_list_events
  - AskUserQuestion
  - Read
  - Write
---

# Weekly Start Skill

지난 주를 돌아보고 이번 주 목표를 수립하는 주간 플래닝 워크플로우입니다.
분기 목표와 주간 Task를 연결하여 전략적 집중도를 높입니다.

---

## 핵심 원칙

- 스크립트만 호출한다. Notion MCP 도구는 사용하지 않는다 (토큰 효율).
- 병렬 데이터 수집으로 속도를 최적화한다.
- 분기 목표 Tag(`Q1-2026` 등)가 없으면 사용자에게 안내한다.
- 반복 이월 패턴(2주 이상)을 감지하여 경고한다.

---

## 워크플로우

### Phase 1 — 데이터 수집 (Sub-Agent 병렬 실행)

3개 Sub-Agent를 **한 번에 동시** 실행한다. 각 Agent는 독립적으로 데이터를 수집하고 요약을 반환한다.

**Agent 1 — 지난 주 리뷰 데이터**

```
Agent(description="지난 주 리뷰 데이터 수집", prompt="""
아래 3개 커맨드를 순서대로 실행하고, 각 결과 JSON을 분석하여 요약을 반환하라.

1. python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py tasks --week previous
2. python3 /Users/changhwan/.claude/skills/weekly:start/scripts/notion-weekly.py weekly-daily-summary --week previous
3. python3 /Users/changhwan/.claude/skills/weekly:start/scripts/notion-weekly.py weekly-review

4. Read 도구로 지난 주 월~금 Obsidian Daily Note를 읽는다.
   경로: /Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/{YYYY-MM-DD}.md
   각 파일에서 다음을 파싱:
   - ## Top 3 오늘의 목표: [x]/[ ] 완료 여부 + [실행]/[탐색] 태그
   - ## Hypothesis Log: 가설 기록 (### [HH:MM] 이슈명, H1/H2 가설, 결과)
   파일이 없으면 해당 날짜 스킵.

반환 형식:
- 지난 주 Task 전체 목록 (이름, 우선순위, 상태, 카테고리)
- Daily 일별 완료율 + KPT 요약
- 완료/미완료/이월 통계
- 일별 Top 3 실행율 + [실행]/[탐색] 태그별 완료율
- Hypothesis Log 전체 (날짜별 가설 기록)
- 각 커맨드의 원본 JSON
""")
```

**Agent 2 — 이번 주 현황 + 분기 목표**

```
Agent(description="이번 주 현황 수집", prompt="""
아래 2개 커맨드를 실행하고 결과를 요약하라.

1. python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py dashboard --week current
2. python3 /Users/changhwan/.claude/skills/weekly:start/scripts/notion-weekly.py quarterly-goals

반환 형식:
- 이번 주 Task 현황 (진행 중/시작 전/대기/완료 각 개수 + 목록)
- 분기 목표 Task 목록 (상태별)
- 원본 JSON
""")
```

**Agent 3 — 이번 주 캘린더 일정**

```
Agent(description="이번 주 캘린더 조회", prompt="""
Google Calendar MCP 도구(mcp__claude_ai_Google_Calendar__gcal_list_events)를 사용하여
이번 주 월요일~금요일 일정을 조회하라.

반환 형식:
- 날짜별 일정 목록 (시간, 제목, 참석자 수)
- 회의 밀집도 높은 날 표시 (3개 이상이면 '바쁜 날')
- 총 회의 시간 합계
""")
```

**데이터 매핑:**
- Agent 1 → 지난 주 Task 목록 + 일별 Daily 요약 (완료율, KPT) + 완료/미완료/이월 통계
- Agent 2 → 이번 주 Task 현황 + 분기 목표 Tag Task 목록
- Agent 3 → 이번 주 캘린더 일정 (날짜별 회의 목록, 바쁜 날 표시)

---

### Phase 2 — 지난 주 리뷰 출력

Phase 1 JSON을 종합 분석하여 다음 형식으로 출력한다.

**출력 포맷:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{YYYY-WXX} 지난 주 리뷰
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

완료율: N/M (XX%)

✅ 완료 Task
- [Task 이름] (P{N}, {카테고리})
- ...

🔄 미완료 → 이번 주 이월
- [Task 이름] (P{N}) ← 이월됨
- ...

⚠️ 미완료 → 이월 안 됨 (검토 필요)
- [Task 이름] (P{N})
- ...

📅 일별 Daily 요약
| 날짜 | 완료율 | KPT 한 줄 요약 |
|------|--------|--------------|
| 월 (YYYY-MM-DD) | N/M (XX%) | Keep: X / Problem: Y |
| ...

⚡ 반복 이월 경고 (해당 시)
- [Task 이름] — 2주 이상 이월됨. 범위 축소 또는 삭제 검토 필요.
```

**분석 로직:**
- `weekly-review.stats`에서 완료율, 이월/드랍 수 계산
- `weekly-daily-summary.days`에서 날별 완료율 + KPT 요약 추출
- 이월 경고: `incomplete_carried` 중 이번 주 `dashboard` 결과에서도 진행 중인 항목 (2주 연속 이월 = 경고 대상)

**주간 성장 리포트 출력 (Phase 2 하단에 추가):**

Agent 1이 수집한 Obsidian Daily Note 데이터를 기반으로 성장 리포트를 출력한다.
Top 3에 `[실행]`/`[탐색]` 태그가 없는 날이 전부이면 (아직 새 형식 미적용) 성장 리포트 섹션 전체를 생략한다.

```
📊 주간 성장 리포트
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
실행율 추이: 월 {N}/{M} → 화 {N}/{M} → 수 {N}/{M} → 목 {N}/{M} → 금 {N}/{M} (주간 평균: {%})
[실행] 완료율: {M}/{N} ({%}) / [탐색] 완료율: {M}/{N} ({%})

가설 사이클 (주간 {N}건):
- 첫 가설 적중률: {M}/{N} ({%})
- 가장 자주 놓친 레이어: {네트워크/리소스/설정/...}
- 평균 사이클 횟수: {X}회

💡 인사이트: {패턴 기반 1줄 피드백}
   예: "네트워크 레이어를 3번 놓쳤습니다. 트러블슈팅 시 envoy stats를 초기 가설에 포함해보세요."
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**성장 리포트 분석 로직:**
1. 일별 Top 3 파싱: `[x]`/`[ ]` 완료 여부 + `[실행]`/`[탐색]` 태그 → 일별 실행율 계산
2. `[실행]`/`[탐색]` 태그별 주간 완료율 집계
3. Hypothesis Log 파싱: 주간 가설 기록 건수, 첫 가설(H1) 적중 건수, `놓친 것:` 레이어 집계, 평균 사이클(H 항목 수) 계산
4. Hypothesis Log가 주간 전체에서 0건이면 가설 사이클 블록 생략
5. 인사이트: 놓친 레이어 빈도 Top 1을 기반으로 구체적 개선 제안 생성. 놓친 레이어가 없으면 실행율 추이 기반 피드백

---

### Phase 3 — 이번 주 컨텍스트 제시

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 이번 주 캘린더 일정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| 요일 | 일정 수 | 주요 일정 |
|------|---------|----------|
| 월   | N개     | 회의A, 회의B |
| 화   | N개     | ... |
| 수   | N개     | ... |
| 목   | N개     | ... |
| 금   | N개     | ... |

⚠️ 바쁜 날: {요일} ({N}개 일정), {요일} ({N}개 일정)  ← 3개 이상인 날만 표시
→ 이 날에 마감인 Task는 사전 진행 권장

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 이번 주 ({YYYY-WXX}) 등록 Task 현황
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

진행 중 (N개)
- [Task 이름] (P{N}, ~MM/DD)
- ...

시작 전 (N개)
- [Task 이름] (P{N}, ~MM/DD)
- ...

대기 (N개)
- [Task 이름] (P{N})
- ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 분기 목표 연계 ({quarter})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

진행 중 (N개) / 완료 (N개) / 미시작 (N개)

이번 주 Task 중 분기 목표 연계:
- [Task 이름] ← {quarter} 연계

분기 목표가 없는 이번 주 Task (검토 권장):
- [Task 이름]
- ...
```

**분기 목표 Tag 없음 처리:**
- `quarterly-goals.total == 0` 이면: "현재 분기 목표 Tag({quarter})가 설정된 Task가 없습니다. Task에 `{quarter}` Tag를 추가하면 분기 목표 연계 분석이 가능합니다." 출력.

---

### Phase 4 — 대화형 주간 목표 수립 (AskUserQuestion)

**Top 5 목표 추천 로직 (가중치 합산):**

| 요소 | 점수 |
|------|------|
| Priority = P1 | +4 |
| Priority = P2 | +2 |
| 분기 목표 Tag 보유 | +3 |
| 지난 주 이월 (incomplete_carried) | +2 |
| 상태 = 진행 중 | +2 |
| 이번 주 내 마감 (due_date ≤ 이번 주 일요일) | +2 |
| 반복 이월 (incomplete_carried이면서 이번 주 dashboard에도 미완료) | +1 |

이번 주 Task + 이월 Task 전체를 대상으로 점수를 계산하여 Top 5를 선정한다.
동점 시 P 숫자 낮은 순(P1 > P2) → 마감 임박 순.

**출력 포맷:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 이번 주 Top 5 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. [Task 이름] (점수: N) — P1, 분기 목표 연계, 이번 주 마감
2. [Task 이름] (점수: N) — P2, 지난 주 이월
3. [Task 이름] (점수: N) — P1, 진행 중
4. [Task 이름] (점수: N) — P2, 분기 목표 연계
5. [Task 이름] (점수: N) — P2, 이번 주 마감
```

**AskUserQuestion으로 확인:**

```
AskUserQuestion:
  question: "위 Top 5를 이번 주 주간 목표로 확정할까요?"
  options:
    - label: "확정"
      description: "Top 5를 이번 주 주간 목표로 사용합니다."
    - label: "수정하기"
      description: "일부 항목을 변경하거나 순서를 조정합니다."
    - label: "직접 작성"
      description: "주간 목표를 직접 입력합니다."
```

- **"확정"**: Top 5를 그대로 주간 목표로 사용 → Phase 5로 이동
- **"수정하기"**: 어떤 항목을 변경하는지 자유 텍스트로 입력받아 반영 → Phase 5로 이동
- **"직접 작성"**: 자유 텍스트로 주간 목표 입력 → Phase 5로 이동

---

### Phase 5 — Obsidian Weekly Note 저장

**저장 경로:**
```
~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/{YYYY}-{WXX}-weekly.md
```

예시: `2026-W10-weekly.md`

**파일 작성 전 체크:**
- 파일이 이미 존재하면 AskUserQuestion으로 덮어쓸지 확인.

**파일 내용 포맷:**

```markdown
---
tags:
  - weekly
  - {YYYY-WXX}
date: {YYYY-MM-DD (월요일)}
---

# {YYYY} {WXX} 주간 계획

## 🏆 이번 주 목표

- [ ] {목표1}
- [ ] {목표2}
- [ ] {목표3}
- [ ] {목표4}
- [ ] {목표5}

## 지난 주 리뷰 ({PREV-WXX})

**완료율:** N/M (XX%)

### 완료 Task

{완료 Task 목록}

### 미완료 / 이월

{미완료 Task 목록}

### 일별 요약

| 날짜 | 완료율 | 메모 |
|------|--------|------|
{일별 행}

## 📊 주간 성장 리포트

실행율 추이: 월 {N}/{M} → 화 {N}/{M} → 수 {N}/{M} → 목 {N}/{M} → 금 {N}/{M} (주간 평균: {%})
[실행] 완료율: {M}/{N} ({%}) / [탐색] 완료율: {M}/{N} ({%})

가설 사이클 (주간 {N}건):
- 첫 가설 적중률: {M}/{N} ({%})
- 가장 자주 놓친 레이어: {목록}
- 평균 사이클 횟수: {X}회

💡 인사이트: {패턴 기반 피드백}

## 🎯 분기 목표 ({quarter}) 현황

**진행 중:** N개 | **완료:** N개 | **미시작:** N개

{분기 목표 Task 목록}

## 📝 주간 메모

<!-- 이번 주 진행하면서 기록할 것들 -->
```

`## 📊 주간 성장 리포트` 섹션은 Agent 1이 수집한 Obsidian Top 3 + Hypothesis Log 데이터가 있을 때만 포함한다.
Top 3에 `[실행]`/`[탐색]` 태그가 주간 전체에서 없으면 이 섹션을 생략한다.
Hypothesis Log가 주간 전체에서 0건이면 가설 사이클 블록만 생략하고 실행율은 유지한다.

Write 도구로 파일을 저장한 후 저장 경로를 출력한다.

---

## 스크립트 동작 상세

**`weekly-daily-summary` 커맨드:**
- Daily DB (`2bf64745-3170-8016-b20a-ff022dea06cb`)를 주간 범위로 쿼리
- 날짜별 Todo's(strikethrough → done), Note, KPT 파싱
- KPT 파싱: `K:`/`P:`/`T:` 또는 `Keep:`/`Problem:`/`Try:` 접두사로 섹션 구분
- 반환: `week`, `period`, `summary(week_rate)`, `days[]`

**`weekly-review` 커맨드:**
- Task DB에서 지난 주 + 이번 주 Task 각각 조회
- 이월 감지: 지난 주 미완료 중 이번 주 동일 이름 Task 존재 여부로 판단
- 반환: `stats(completion_rate, carried_over, dropped)`, `completed_tasks`, `incomplete_carried`, `incomplete_dropped`, `current_week_tasks`

**`quarterly-goals` 커맨드:**
- Task DB에서 Tag multi_select contains 필터로 `Q{N}-{YYYY}` 검색
- `--quarter` 미지정 시 현재 날짜 기반 자동 추론 (1~3월=Q1, 4~6월=Q2 등)
- 반환: `quarter`, `total`, `by_status`, `tasks(in_progress/upcoming/waiting/completed)`

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필요: `~/.secrets.zsh`에서 로드
- `quarterly-goals.total == 0`은 정상 케이스 — Tag 미설정 안내만 하고 계속 진행
- 이월 감지는 **이름 일치**로 판단 (동일 Task를 동일 이름으로 유지해야 정확)
- Weekly Note 파일명: ISO week 기준 (`{YYYY}-W{WW}-weekly.md`, WW는 2자리 0패딩)

---

## 검증

스크립트 실행 후 JSON 응답 확인:

```bash
# 단위 테스트
python3 ~/.claude/skills/weekly:start/scripts/notion-weekly.py weekly-daily-summary --week previous
python3 ~/.claude/skills/weekly:start/scripts/notion-weekly.py weekly-review
python3 ~/.claude/skills/weekly:start/scripts/notion-weekly.py quarterly-goals
```

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh` 확인
- `HTTP 400` → 필터 파라미터 확인 (날짜 형식 YYYY-MM-DD)
- `quarterly-goals` 빈 결과 → Tag 미설정 (정상)
