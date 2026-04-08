---
name: tasks:status
description: |
  기존 Notion Task의 상태 변경 및 삭제 스킬.
  상태 변경: 시작 전/진행 중/완료/대기 간 전환.
  삭제: Notion 아카이브 (복구 가능).
  트리거 키워드: "상태 변경", "완료 처리", "시작 처리", "Task 삭제", "Task 제거",
  "할 일 삭제", "완료로 변경", "진행 중으로 변경".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py *)
  - AskUserQuestion
---

# tasks:status

기존 Notion Task의 상태를 변경하거나 삭제(아카이브)한다.

---

## 핵심 원칙

- Notion 데이터는 스크립트로만 조회/수정. Notion MCP 도구 사용하지 않음 (토큰 효율)
- 쓰기 작업 전 반드시 사용자 확인 (AskUserQuestion)

---

## 모드 판별

| 모드 | 트리거 |
|------|--------|
| **상태 변경** | "상태 변경", "완료 처리", "시작", "진행 중으로" |
| **Task 삭제** | "Task 삭제", "할 일 삭제", "Task 제거" |

---

## 상태 변경 워크플로우

### Step 1: 이번 주 Tasks 조회

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks --week current
```

### Step 2: 변경 대상 + 목표 상태 확인

사용자 발화에서 대상 Task와 목표 상태를 파악한다. 불명확한 경우 AskUserQuestion으로 확인.

**유효한 상태값:**
- `시작 전`
- `진행 중`
- `완료`
- `대기`

### Step 3: 상태 변경 실행

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-status --page-id <id> --status "진행 중"
```

### Step 4: 결과 출력

```
✅ 상태 변경 완료
  - Task이름: 시작 전 → 진행 중
```

---

## Task 삭제 워크플로우

Notion API는 page 삭제 = `archived: true` PATCH. 복구 가능.

### Step 1: 이번 주 Tasks 조회

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks --week current
```

### Step 2: AskUserQuestion으로 삭제 대상 확인

### Step 3: 삭제 실행

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py delete-task --page-id <id>
```

### Step 4: 결과 출력

```
🗑️ Task 삭제 완료 (아카이브)
  - Task이름
```

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- 삭제는 아카이브 처리 (복구 가능). 영구 삭제 아님
- 이번 주 범위 외 Task 변경 시 `--week previous` 또는 `--month YYYY-MM`으로 조회 후 page-id 확인
