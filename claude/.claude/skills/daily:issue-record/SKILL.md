---
name: daily:issue-record
description: |
  작업 중 발생한 이슈를 Obsidian Daily Note의 Issues 섹션에 기록하는 도구.
  사용 시점: (1) 작업 중 이슈 발생 시 기록, (2) 블로커/문제 상황 메모.
  트리거 키워드: "이슈 기록", "issue 기록", "이슈 남겨", "/daily:issue-record".
allowed-tools:
  - Read
  - Edit
---

# daily:issue-record 스킬

작업 중 발생한 이슈를 오늘 Obsidian Daily Note의 `## Issues` 섹션에 구조화된 형식으로 기록한다.

---

## 핵심 원칙

- 스크립트 없이 Read + Edit 도구만 사용한다.
- 대화 맥락에서 이슈 정보를 최대한 파악한다. 맥락이 불충분하면 질문한다.
- Daily Note가 없으면 경로를 안내하고 종료한다.
- `## Issues` 섹션이 없으면 파일 하단에 해당 섹션을 새로 추가한다.

---

## 워크플로우

### Step 1 — 이슈 정보 파악

대화 맥락을 분석하여 아래 3가지 정보를 확인한다. 명확하지 않으면 질문한다.

| 항목 | 설명 | 예시 |
|------|------|------|
| **작업명** | 어떤 작업을 하던 중이었는지 | "ai-core OTEL 설정", "vestway dev 배포" |
| **이슈 내용** | 발생한 문제의 구체적 내용 | "Elastic APM과 OTEL 충돌로 trace 미수집" |
| **작업 상태** | 현재 이슈 처리 상황 | `진행중` / `해결` / `보류` |

> **질문 예시**: "이슈 내용을 조금 더 구체적으로 알려주세요. 어떤 에러가 발생했나요?"

### Step 2 — Daily Note 읽기

오늘 날짜로 Daily Note를 읽는다.

```
경로: /Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md
```

날짜 형식: `2026-03-11` (오늘 날짜 사용)

파일이 없으면:
- "오늘 Daily Note가 없습니다. `/daily:start`로 먼저 생성해 주세요." 메시지 출력 후 종료.

### Step 3 — Issues 섹션 찾기 및 이슈 append

#### 케이스 A: `## Issues` 섹션이 존재하는 경우

Edit 도구로 섹션 하단에 새 이슈를 append한다.

**기존 이슈가 없는 경우** (`## Issues` 다음 줄이 비어있거나 다음 섹션이 바로 시작):
```
## Issues\n
```
→ 다음으로 교체:
```
## Issues\n\n- {작업명}\n\t- 이슈\n\t\t- {이슈 내용}\n\t- 작업 상태: {상태}\n
```

**기존 이슈가 있는 경우**: 섹션의 마지막 항목 다음에 append.

#### 케이스 B: `## Issues` 섹션이 없는 경우

파일 끝에 섹션 전체를 추가한다.

---

## 기록 형식

```markdown
- {작업명}
	- 이슈
		- {이슈 상세 내용}
	- 작업 상태: {진행중/해결/보류}
```

**예시:**
```markdown
- ai-core OTEL 설정
	- 이슈
		- Elastic APM 클라이언트가 OTEL auto-instrumentation과 충돌하여 trace가 수집되지 않음
		- `ELASTIC_APM_ENABLED=false` 설정으로 해결
	- 작업 상태: 해결
```

---

## 완료 출력

기록 완료 후 아래 형식으로 출력한다.

```
✅ 이슈 기록 완료
- 파일: 2026-03-11.md
- 작업: {작업명}
- 상태: {작업 상태}
```

---

## 엣지 케이스

| 상황 | 처리 방법 |
|------|-----------|
| Daily Note 파일 없음 | `/daily:start`로 생성 안내 후 종료 |
| `## Issues` 섹션 없음 | 파일 끝에 섹션 + 첫 이슈 함께 추가 |
| 이슈 정보 불충분 | Step 1에서 질문하여 확인 후 진행 |
| 동일 작업에 추가 이슈 | 기존 작업 항목 아래에 이슈 항목 추가 |
