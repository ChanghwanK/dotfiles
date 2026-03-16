---
name: tasks:manage
description: |
  Task CUD 관리 스킬. Task 이월(carry-over), 상태 변경, Task 생성, Task 삭제.
  진행 상황 업데이트 (handoff 데이터 또는 수동 입력 → Daily 문서 반영).
  Obsidian Daily Note Todo 추가(append), 진행 상황 반영(sync-progress),
  개별 Task 진행 업데이트 (완료 처리, 메모 추가 — Claude 직접 편집) 지원.
  트리거 키워드: "이월", "carry-over", "Task 추가", "할 일 추가", "새 Task", "Task 삭제",
  "완료 처리", "상태 변경", "진행 업데이트", "업데이트", "진행했어", "progress update",
  "일지 반영", "일지 업데이트", "오늘 진행 상황", "tasks:manage",
  "append", "obsidian todo", "todo 추가",
  "자동 업데이트", "auto-progress", "세션 기반 업데이트", "진행 상황 자동".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py *)
  - AskUserQuestion
---

# tasks:manage

Notion Task DB의 Task를 관리한다. 읽기(View/Query) + 쓰기(Carry-over, 상태 변경, 생성, 삭제) 지원.

---

## 핵심 원칙

- Notion 데이터는 스크립트로만 조회/수정. Notion MCP 도구 사용하지 않음 (토큰 효율)
- 쓰기 작업 전 반드시 사용자 확인 (AskUserQuestion)
- carry-over 실행 전 반드시 dry-run + 사용자 확인

---

## 모드 판별

| 모드 | 트리거 | 사용 서브커맨드 |
|------|--------|--------------|
| **Carry-over** | "이월", "carry-over" | `carry-over --dry-run` → AskUserQuestion → `carry-over --apply` |
| **상태 변경** | "상태 변경", "완료 처리", "시작" | `tasks` → 대상 선택 → `update-status` |
| **Task 생성** | "Task 추가", "할 일 추가", "새 Task" | `create-task` |
| **Obsidian 추가** | "append" | `obsidian-todo.py append` (Notion 생성 없음) |
| **개별 업데이트** | "업데이트", "완료", "메모 추가", "진행했어" | `Read + Edit (직접 편집)` |
| **Task 삭제** | "Task 삭제", "할 일 삭제", "Task 제거" | `tasks` → 대상 확인 → `delete-task` |
| **Progress Update** | "진행 업데이트", "progress update", "일지 반영", "일지 업데이트", "오늘 진행 상황" | `sync-progress` |
| **Auto Progress** | "자동 업데이트", "auto-progress", "세션 기반 업데이트", "진행 상황 자동" | `auto-progress --dry-run` → AskUserQuestion → `auto-progress --apply` |
| **Query** | "지난 주", "X월", "월별" | `tasks --week previous` / `--month YYYY-MM` |

---

## Carry-over 워크플로우

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

## 상태 변경 워크플로우

### Step 1: 이번 주 Tasks 조회

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks --week current
```

### Step 2: 변경 대상 + 목표 상태 확인

사용자 발화에서 대상 Task와 목표 상태를 파악한다. 불명확한 경우 AskUserQuestion으로 확인.

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

## Task 생성 워크플로우 (Notion)

사용자가 args로 직접 지정한 값을 그대로 사용. 확인 질문 없이 바로 생성.

- 이름 (필수)
- 우선순위: `--priority P1` 또는 `--priority P2` (기본: P1 - Must Have)
- Due Date: `--due YYYY-MM-DD` (기본: 이번 주 금요일)
- Category: WORK / MY (기본: WORK)

### Step 1: Notion Task 생성

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py create-task --name "Task이름" --priority "P1 - Must Have" --due "YYYY-MM-DD" --category "WORK"
```

### Step 2: 결과 출력

```
✅ Task 생성 완료
  - [P1] Task이름 (WORK) — due: MM/DD
```

---

## Task 추가 워크플로우 (append — Obsidian Only)

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

## 개별 진행 업데이트 워크플로우

`tasks:show` 조회 후 개별 Task의 상태/메모를 Daily Note에 즉시 반영한다.
확인 질문 없이 바로 실행 (append와 동일한 즉시 실행 정책).

### 워크플로우

1. Daily Note 읽기: `Read ~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md`
2. `## Todos` 섹션에서 대상 todo 식별 (대화 맥락 기반)
3. `Edit` 도구로 직접 수정

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

## Progress Update 워크플로우

세션 작업 진행 상황을 오늘 Obsidian Daily Note의 `## Todos` 섹션에 반영한다.
완료 항목은 `[x]` 처리, 누락 항목은 새로 추가.

### Step 1: 데이터 수집

**handoff 데이터가 있는 경우:**
handoff-latest.json을 읽어 completed/in_progress/next 추출.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py sync-progress \
  --handoff ~/.claude/tmp/handoff-latest.json \
  --dry-run
```

**handoff 데이터가 없는 경우:**
현재 대화 컨텍스트에서 completed/in_progress/next를 추출하여 직접 전달.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py sync-progress \
  --completed "완료항목1,완료항목2" \
  --in-progress "진행중1,진행중2" \
  --next "다음1" \
  --dry-run
```

### Step 2: 미리보기 결과 출력

```
📊 진행 상황 반영 미리보기

📝 Todo 변경:
  ✅ 완료 처리 (N개):
    - 항목A
  ➕ 새로 추가 (N개):
    - 항목B (진행 중)
    - 항목C (다음)
```

### Step 3: AskUserQuestion

```
선택지: ["반영", "취소"]
```

### Step 4: 적용 + 결과 출력

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py sync-progress \
  --handoff ~/.claude/tmp/handoff-latest.json \
  --apply
```

출력:
```
✅ 진행 상황 반영 완료
  - Todo 완료 처리: N개
  - Todo 추가: N개
```

### Edge Cases

| 상황 | 처리 |
|------|------|
| 오늘 Daily Note 없음 | 에러 반환, daily:start로 노트 먼저 생성 안내 |
| handoff 파일 없음/경로 오류 | 에러 반환, 수동 입력으로 전환 |
| handoff와 --completed 동시 지정 | --handoff 우선, 나머지 무시 |
| completed 항목이 기존 todo에 이미 done | 스킵 (중복 변경 방지) |

---

## Auto Progress 워크플로우

`claude-mem.db`에 자동 수집된 세션 요약을 분석하여 Daily Note todos를 자동 업데이트한다.
수동 요약 입력 없이 오늘 진행된 세션 데이터 기반으로 완료 항목을 fuzzy match → `[x]` 처리.

### Step 1: dry-run 실행

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py auto-progress --dry-run
```

### Step 2: 결과 해석 및 출력

JSON 결과를 포맷하여 사용자에게 제시:

```
🤖 Auto Progress 분석 결과 (세션 N개 분석)

✅ 완료 처리 추천 (N개):
  - todo이름 (score: 0.XX)
    근거: matched_by 텍스트...

🔄 진행 중으로 보이는 항목 (N개):
  - todo이름 (score: 0.XX)
    근거: matched_by 텍스트...

⚪ 매칭 없는 Todo (N개):
  - todo이름 (수동 업데이트 필요)

📝 세션에서 완료됐으나 Todo 목록에 없는 작업 (N개):
  - 세션 완료 텍스트 요약...
```

### Step 3: AskUserQuestion

```
선택지: ["완료 항목 전체 적용", "수동으로 개별 선택", "취소"]
```

### Step 4: 적용

**전체 적용:**
```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py auto-progress --apply
```

**개별 선택:** 사용자가 선택한 항목만 `sync-progress --completed "항목명" --apply`로 처리.

### Step 5: 결과 출력

```
✅ Auto Progress 반영 완료
  - 완료 처리: N개 (todos이름들)
```

### Edge Cases

| 상황 | 처리 |
|------|------|
| claude-mem DB 없음 | `{"error": "db_not_found"}` → 수동 sync-progress 안내 |
| 오늘 세션 0개 | "기록된 세션 없음" → 수동 sync-progress 안내 |
| Daily Note 없음 | 에러 반환 → daily:start 안내 |
| 매칭 점수 낮음 | threshold 기본 0.5 — `--threshold 0.3` 옵션으로 조정 가능 |

---

## Query Mode 워크플로우

### 지난 주 조회

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks --week previous
```

출력:
```
📋 지난 주 Tasks (MM/DD ~ MM/DD)
완료 ✅ (N개) | 미완료 ⏳ (N개) | 진행 중 🔄 (N개)

🔄 진행 중
  - [P1] Task이름 — due: MM/DD
⏳ 시작 전
  - [P2] Task이름 — due: MM/DD
✅ 완료
  - [P1] Task이름 — due: MM/DD
```

### 월별 조회

발화에서 월을 파싱한다. "이번 달"이면 현재 YYYY-MM 사용.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py tasks --month 2026-03
```

---

## 서브커맨드 참조

| 커맨드 | 설명 |
|--------|------|
| `dashboard --week previous\|current\|next` | Task + Daily Progress 통합 뷰 |
| `tasks --week previous\|current\|next` | 주 단위 Task 조회 |
| `tasks --month YYYY-MM` | 월 단위 Task 조회 (`--week` 무시) |
| `carry-over --dry-run` | 이월 대상 미리보기 |
| `carry-over --apply [--page-ids id1,id2]` | 이월 실행 |
| `update-status --page-id <id> --status <상태>` | Task 상태 변경 |
| `create-task --name --priority --due [--category]` | 새 Task 생성 |
| `delete-task --page-id <id>` | Task 아카이브 (삭제) |
| `daily-progress` | Daily DB 이번 주 진행률 |
| `obsidian-todo.py sync-progress (--dry-run\|--apply) [--handoff PATH]` | Obsidian Daily Note Todo 진행 상황 반영 |

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필수 (미설정 시 에러 출력 후 종료)
- 쓰기 작업(carry-over, update-status, create-task, delete-task)은 반드시 사용자 확인 후 실행
- `--month`와 `--week` 동시 지정 시 `--month` 우선
