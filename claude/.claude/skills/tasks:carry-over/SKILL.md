---
name: tasks:carry-over
description: |
  지난 주 미완료 Tasks를 이번 주로 이월하는 스킬.
  dry-run으로 이월 대상 미리보기 → 사용자 확인 → apply 실행.
  전체 이월 또는 선택 이월 지원.
  트리거 키워드: "이월", "carry-over", "미완료 이월", "지난 주 이월".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py carry-over *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks *)
  - AskUserQuestion
---

# tasks:carry-over

지난 주 미완료 Tasks를 이번 주 월요일로 이월한다.
dry-run → 사용자 확인 → apply 3단계로 안전하게 처리.

---

## 핵심 원칙

- Notion 데이터는 스크립트로만 조회/수정. Notion MCP 도구 사용하지 않음 (토큰 효율)
- carry-over 실행 전 반드시 dry-run + 사용자 확인

---

## 워크플로우

### Step 1: dry-run 실행

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py carry-over --dry-run
```

### Step 2: 미완료 Task 목록 출력

```
📋 지난 주 미완료 Tasks (MM/DD ~ MM/DD)
이월 대상 N개 → 이번 주 월요일(MM/DD)로 업데이트 예정

🔄 진행 중
  - [P1] Task이름 — 기존 due: MM/DD
⏳ 시작 전
  - [P2] Task이름 — 기존 due: MM/DD
```

미완료 0개이면 "지난 주 미완료 항목이 없습니다." 출력 후 종료.

### Step 3: AskUserQuestion

```
위 N개 Tasks를 이번 주 월요일(MM/DD)로 이월하시겠습니까?
선택지: ["전체 이월", "선택 이월 (목록 직접 지정)", "취소"]
```

### Step 4: 이월 실행

**전체 이월:**
```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py carry-over --apply
```

**선택 이월:** 사용자에게 이월할 Task 이름 확인 → page_id 매핑 후:
```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py carry-over --apply --page-ids id1,id2,...
```

### Step 5: 결과 출력

```
✅ 이월 완료 (N개)
  - [P1] Task이름 → MM/DD (이번 주 월)
```

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- 이월은 due date를 이번 주 월요일로 변경. status는 유지
