---
name: learn:recall
description: |
  Obsidian 무지 노트를 불러와 재인터뷰하는 스킬.
  /wiki:note 무지 또는 /learn Phase 5에서 저장한 ignorance-note를 읽고,
  이해 점검 질문을 순차적으로 제시하여 내재화 여부를 검증한다.
  재인터뷰 통과 시 노트 status를 reviewed/mastered로 갱신 제안.
  트리거 키워드: "/learn:recall", "재인터뷰", "무지 노트 복습", "다시 인터뷰".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py *)
  - Bash(find /Users/changhwan/Library/Mobile\ Documents/com~apple~CloudDocs/obsidian_home/ch_home/04.\ Wiki/ignorance-notes/ *)
  - Bash(cat *)
  - Read
---

# Learn:Recall 스킬

## TL;DR

- Obsidian `04. Wiki/ignorance-notes/` 에서 무지 노트를 찾아 `이해 점검 질문` 섹션을 읽는다.
- 질문을 인터뷰 형식으로 하나씩 제시하고 사용자 답변을 평가한다.
- 모든 질문을 통과하면 노트 status 갱신을 제안한다.

## 진입 방식

| 입력 | 동작 |
|------|------|
| `/learn:recall` (인자 없음) | 저장된 무지 노트 목록 출력 |
| `/learn:recall {topic}` | 해당 주제 무지 노트 로드 후 재인터뷰 시작 |

## 실행 절차

### Step 0: 노트 목록 (인자 없음)

`04. Wiki/ignorance-notes/` 디렉토리의 `.md` 파일을 읽고 frontmatter에서 title, date, expires, status를 추출하여 표로 출력한다.

```
## 무지 노트 목록

| # | 주제 | 저장일 | 만료일 | 상태 |
|---|------|--------|--------|------|
| 1 | {title} | {date} | {expires} | {status} |
...

재인터뷰하려면: /learn:recall {주제명 일부}
```

만료된 노트(expires < 오늘)는 취소선으로 표시한다.

### Step 1: 노트 탐색

`topic` 인자를 파일명 및 title 필드에서 퍼지 매칭으로 찾는다.

```bash
find "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/04. Wiki/ignorance-notes/" -name "*.md"
```

매칭 결과가 여러 개면 목록을 보여주고 선택하게 한다.
매칭 결과가 없으면 유사한 파일명을 제안하거나 새 학습 세션을 권유한다.

### Step 2: 노트 로드 및 상태 확인

노트 frontmatter에서 아래 필드를 확인한다.

- `expires`: 만료 여부 확인
  - 만료된 경우: "이 노트는 {expires}에 만료되었습니다. 내용이 여전히 관련 있으면 재인터뷰를 진행하거나 새 학습 세션을 추천합니다."
  - 만료 여부와 무관하게 사용자가 원하면 재인터뷰 진행
- `status`: 이전 재인터뷰 기록 확인
  - `not-reviewed`: 첫 재인터뷰
  - `reviewed`: 한 번 통과한 상태 (더 심화 질문으로 이어갈 수 있음)
  - `mastered`: 완전히 내재화된 상태

- `## 이해 점검 질문` 섹션을 파싱하여 질문 목록을 추출한다.

### Step 3: 재인터뷰 진행

**오프닝 (상태에 따라):**

`not-reviewed` 일 때:
```
이전에 이 내용을 처음 배운 시점({date})으로부터 {경과 기간}이 지났습니다.
이해 점검을 해보겠습니다. 나의 단어로 설명해보세요.
```

`reviewed` 이상일 때:
```
이전 재인터뷰에서 통과하셨습니다. 조금 더 심화된 질문으로 확인해보겠습니다.
```

**질문 진행 방식:**
- 질문을 하나씩 순차적으로 제시한다.
- 사용자가 답변을 작성하면 평가한다.
- 모든 질문을 한 번에 보여주지 않는다 (인터뷰 방식 유지).

**평가 기준:**
- 나의 단어로 핵심 개념을 설명할 수 있으면 통과.
- 정확한 용어 사용보다 개념의 이해 여부를 기준으로 한다.
- 부족한 경우: 힌트를 제공하고 재시도 기회를 준다 (1회).
- 완전히 모르는 경우: 해당 개념을 재설명하고 다음 질문으로 넘어간다.

**실무 연계 확장 (선택):**
- 기본 질문 통과 후 "실무에 연결해보겠습니다" 한 마디 후 실무 연계 질문 1개 추가 가능.

### Step 4: 결과 및 status 갱신 제안

**모든 질문 통과 시:**
```
재인터뷰를 통과하셨습니다.
노트 status를 'reviewed'로 갱신할까요? (이미 reviewed라면 'mastered'로)
```

갱신을 선택하면 노트 파일의 frontmatter `status` 필드를 수정한다.

**일부 질문 통과 실패 시:**
```
{통과 수}/{전체 수} 질문을 통과하셨습니다.
보완이 필요한 부분: {실패한 개념 요약}
다음에 다시 시도해보세요: /learn:recall {topic}
```

## 주의사항

- 재인터뷰는 시험이 아니라 내재화 확인 과정이다. 부담 없이 진행하게 안내한다.
- 사용자가 "스킵", "다음"이라고 하면 해당 질문을 건너뛴다.
- `/learn:recall`로 로드한 노트의 `## 학습 내용` 섹션도 필요시 참조하여 보충 설명을 제공한다.
- 노트 파일 직접 수정 전 반드시 사용자 확인을 받는다.
