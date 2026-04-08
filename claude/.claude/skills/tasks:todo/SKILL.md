---
name: tasks:todo
description: |
  Obsidian Daily Note의 Todo 항목을 직접 편집하는 스킬.
  Todo 추가(append), 완료 처리(checkbox), 메모 추가 지원.
  Notion API 미사용 — Obsidian 파일만 직접 수정.
  트리거 키워드: "append", "obsidian todo", "todo 추가", "메모 추가", "업데이트", "진행했어",
  "완료 처리", "체크", "done 처리".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py append *)
  - Read
  - Edit
  - AskUserQuestion
---

# tasks:todo

Obsidian Daily Note의 `## Todos` 섹션을 직접 편집한다.
Notion API 미사용 — 로컬 파일만 수정.

---

## 핵심 원칙

- 확인 질문 없이 바로 실행 (append / 직접 편집 모두 즉시 실행 정책)
- 대상 todo 불명확한 경우에만 AskUserQuestion으로 확인
- Notion 상태는 변경하지 않음 (EOD daily:review에서 처리)

---

## 모드 판별

| 모드 | 트리거 |
|------|--------|
| **Todo 추가 (append)** | "append", "todo 추가", "obsidian에 추가" |
| **개별 업데이트** | "업데이트", "완료", "메모 추가", "진행했어", "체크" |

---

## Todo 추가 워크플로우 (append)

`append` 키워드로 호출. Notion 생성 없이 Obsidian Daily Note `## Todos`에만 추가.
확인 질문 없이 바로 실행.

```bash
# args 있는 경우 (날짜/우선순위 메타데이터 포함)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py append --name "Task이름" --priority "P1 - Must Have" --due "YYYY-MM-DD"

# args 없는 경우 (심플 형식: - [ ] Task이름)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py append --name "Task이름"
```

### 결과 출력

```
✅ Obsidian Todo 추가됨
  - Task이름
```

Daily Note 없는 경우:
```
⚠️ 오늘 Obsidian Daily Note 미존재 — 추가 실패
```

---

## 개별 업데이트 워크플로우

`tasks:show` 조회 후 개별 Task의 상태/메모를 Daily Note에 즉시 반영한다.
확인 질문 없이 바로 실행.

### Step 1: Daily Note 읽기

```
Read ~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md
```

### Step 2: 대상 todo 식별

`## Todos` 섹션에서 대화 맥락 기반으로 대상 todo를 찾는다.

### Step 3: Edit 도구로 직접 수정

### 편집 규칙

| 작업 | 변환 |
|------|------|
| 완료 처리 | `- [ ]` → `- [x]`, 라인 끝에 ` ✅ YYYY-MM-DD` 추가 |
| 메모 추가 | 해당 todo 라인 바로 아래에 `\t- 메모 내용` 삽입 |
| 완료 + 메모 | 두 작업 동시 수행 |

### 결과 출력

```
✅ Task 업데이트 완료
  - task이름: 완료 처리 / 메모 추가
```

### Edge Cases

| 상황 | 처리 |
|------|------|
| 대상 todo 불명확 | AskUserQuestion으로 어떤 todo인지 확인 |
| 이미 완료된 todo에 완료 요청 | 스킵 안내, 메모만 추가 |
| Daily Note 없음 | daily:start로 먼저 생성 안내 |

---

## 주의사항

- Notion Task 상태 변경은 `/tasks:status` 사용
- Notion Task 생성은 `/tasks:capture` 사용
