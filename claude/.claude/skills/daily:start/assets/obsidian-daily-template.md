# Obsidian Daily Note 출력 템플릿

## Markdown 템플릿

```markdown
---
title: "YYYY-MM-DD Daily"
date: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
status: active
type: daily
tags: []
aliases: []
---

## Top 3 오늘의 목표
- [ ] [실행|탐색] [작업명]
	- 완료 조건: {관찰 가능한 상태 변화}
	- 이유: {이유}
- [ ] [실행|탐색] [작업명]
	- 완료 조건: {관찰 가능한 상태 변화}
	- 이유: {이유}
- [ ] [실행|탐색] [작업명]
	- 완료 조건: {관찰 가능한 상태 변화}
	- 이유: {이유}

## 오늘 일정
- HH:MM-HH:MM [이벤트명] ([위치])

## 메일 요약
- {발신자}: {제목} — {요약}

### 인프라 액션
- 🔧 {컴포넌트} {버전} — {액션}

## Todos
- [ ] [Top 3 작업명 1]
- [ ] [Top 3 작업명 2]
- [ ] [Top 3 작업명 3]

## Notes
-

## Issues
-

## 어제 리뷰 (YYYY-MM-DD)

### 완료
- 항목1
- 항목2 (transcript에서 추가)

### 진행 중 / 미완료
- 항목

### Carry-over
- 항목

## 회고 (EOD)
- 잘 한 것:
- 개선할 것:
```

## 섹션별 작성 규칙

- `title`: `YYYY-MM-DD Daily` 형식 (실제 날짜로 치환)
- `date`: 오늘 날짜 (YYYY-MM-DD)
- `last_reviewed`: 오늘 날짜 (date와 동일)
- `status`: `active` 고정
- `type`: `daily` 고정
- `tags`: `[]` (Daily 노트는 태그 불필요)
- `aliases`: `[]`
- `Top 3 오늘의 목표`: daily:start와 동일한 선정 로직 적용. `[실행]` (분석 완료, 실행만 남은 것) 또는 `[탐색]` (분석/설계 필요) 태그를 작업명 앞에 붙인다. `[실행]` 항목을 상단에 배치. 각 항목에 `완료 조건:` (관찰 가능한 상태 변화)과 `이유:`를 들여쓰기(탭)로 중첩
- `오늘 일정`: Agent B의 `calendar_events`로 채움. 형식: `- HH:MM-HH:MM 이벤트명 (위치)`. 일정이 없으면 `- (일정 없음)` 한 줄로 표시
- `메일 요약`: Agent C 분석 결과로 채움. 미읽음 0개이면 `- (미읽음 메일 없음)`. Agent C 결과가 null이면 이 섹션을 생성하지 않음. `### 인프라 액션` 서브섹션은 infra_actionable 메일이 있을 때만 생성. `### Task 권장` 서브섹션은 suggested_tasks가 있을 때만 생성
- `Todos`: Top 3 항목을 체크박스(`- [ ]`)로 직접 작성 (daily:start가 자동 채움)
- `Notes`: 어제 Notion note 내용 + 오늘 참고사항
- `Issues`: 이슈/블로커 기록
- `어제 리뷰`: 날짜 헤딩에 실제 어제 날짜 기입 (예: `## 어제 리뷰 (2026-03-04)`)
  - `완료`: Notion done=true + transcript 추가 항목 (출처 괄호 표기)
  - `진행 중 / 미완료`: Notion done=false 항목
  - `Carry-over`: carry-over 항목이 없으면 섹션 자체를 생략
- `회고 (EOD)`: 하루 마무리 시 작성 (daily:review 스킬에서 채움). 스킬 생성 시에는 빈 상태로 둠
