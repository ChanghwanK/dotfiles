---
name: tasks:progress
description: |
  세션 작업 진행 상황을 Obsidian Daily Note Todos에 반영하는 스킬.
  수동 모드(sync-progress): handoff 데이터 또는 직접 입력 기반.
  자동 모드(auto-progress): claude-mem DB 세션 분석 → fuzzy match → 자동 완료 처리.
  트리거 키워드: "진행 업데이트", "progress update", "일지 반영", "오늘 진행 상황",
  "자동 업데이트", "auto-progress", "세션 기반 업데이트", "진행 상황 자동".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/obsidian-todo.py *)
  - AskUserQuestion
---

# tasks:progress

세션 작업 진행 상황을 오늘 Obsidian Daily Note의 `## Todos` 섹션에 반영한다.
수동(handoff/직접 입력)과 자동(claude-mem DB) 두 모드 지원.

---

## 핵심 원칙

- 반영 전 반드시 dry-run 미리보기 + 사용자 확인 (AskUserQuestion)
- Notion Task 상태는 변경하지 않음 (EOD daily:review에서 처리)

---

## 모드 판별

| 모드 | 트리거 |
|------|--------|
| **수동 (sync-progress)** | "진행 업데이트", "progress update", "일지 반영", "handoff" |
| **자동 (auto-progress)** | "자동 업데이트", "auto-progress", "세션 기반 업데이트", "진행 상황 자동" |

---

## Progress Update 워크플로우 (수동)

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

## Auto Progress 워크플로우 (자동)

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
