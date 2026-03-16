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
- [ ] [작업명]
	- [ ] [이유]
- [ ] [작업명]
	- [ ] [이유]
- [ ] [작업명]
	- [ ] [이유]

## 오늘 일정
- HH:MM-HH:MM [이벤트명] ([위치])

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
- `Top 3 오늘의 목표`: daily:start와 동일한 선정 로직 적용. 부모 체크박스(`- [ ] 작업명`)에 자식 체크박스(`\t- [ ] 이유`)를 들여쓰기(탭)로 중첩. 작업명과 이유를 분리하여 가독성 확보
- `오늘 일정`: Agent B의 `calendar_events`로 채움. 형식: `- HH:MM-HH:MM 이벤트명 (위치)`. 일정이 없으면 `- (일정 없음)` 한 줄로 표시
- `Todos`: Top 3 항목을 체크박스(`- [ ]`)로 직접 작성 (daily:start가 자동 채움)
- `Notes`: 어제 Notion note 내용 + 오늘 참고사항
- `Issues`: 이슈/블로커 기록
- `어제 리뷰`: 날짜 헤딩에 실제 어제 날짜 기입 (예: `## 어제 리뷰 (2026-03-04)`)
  - `완료`: Notion done=true + transcript 추가 항목 (출처 괄호 표기)
  - `진행 중 / 미완료`: Notion done=false 항목
  - `Carry-over`: carry-over 항목이 없으면 섹션 자체를 생략
- `회고 (EOD)`: 하루 마무리 시 작성 (daily:review 스킬에서 채움). 스킬 생성 시에는 빈 상태로 둠
