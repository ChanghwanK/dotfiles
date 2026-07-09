---
name: todo:add
description: |
  로컬 Todo 시스템(TUI/todo_store)에 항목을 즉시 추가하는 스킬.
  기본은 Backlog 버킷에 추가. Task가 명시되면 해당 Task 하위(Task-scoped)에 추가.
  사용 시점: (1) "todo 등록해줘", (2) "todo에 추가해줘", (3) 내일/이번주 할 것 빠른 메모.
  트리거 키워드: "todo 등록", "todo 추가", "todo에 넣어줘", "할 일 등록",
  "todo:add", "/todo:add".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py *)
---

# todo:add

로컬 Todo 시스템에 항목을 **최소 인터랙션**으로 추가한다.
`tasks:capture`(Notion Task DB 신규 생성)와 다르다. 이 스킬은 기존 시스템의 Todo 항목 추가 전용이다.

---

## 핵심 원칙

- **Zero friction**: 제목과 버킷이 확정되면 즉시 추가. 질문 없음.
- **Backlog 기본**: Task 언급이 없으면 항상 `__backlog__`에 추가.
- **Repo 자동 감지**: CWD 마지막 경로 컴포넌트를 repo로 사용.
- **단일 출력**: 완료 메시지 1줄만 출력.

---

## 입력 파싱 규칙

| 속성 | 추출 방법 | 기본값 |
|------|-----------|--------|
| **title** (필수) | 메타 키워드 제거 후 핵심 동작/목표 추출 | 없음 |
| **description** | 배경·문제·이유 등 자유 텍스트 (멀티라인 가능) | 없음 |
| **due** | "내일"/"이번주 금요일"/YYYY-MM-DD → 절대 날짜 변환 (KST) | 없음 |
| **status** | "시작전"/"진행중"/"완료" 명시 시 그대로 사용 | `시작전` |
| **task** | "X task에", "X 작업 하위에" → task 이름 추출 | `__backlog__` |
| **repo** | CWD 마지막 경로 컴포넌트 자동 추출 | `""` |
| **images** | 파일 경로 또는 URL 목록 (아래 "이미지 파싱" 참조) | 없음 |

### 이미지 파싱

이미지 첨부 신호가 있으면 `--image PATH` 플래그를 추가한다.

**신호:**
- 사용자가 파일 경로를 명시: `"/Users/changhwan/Desktop/screenshot.png"`
- 대화에서 이미지(스크린샷)가 시각적으로 첨부됨 → Claude가 해당 이미지를 `~/.claude/todo-images/<title-slug>.png`로 저장 후 경로 사용
- URL 형태: `https://...` 

**규칙:**
- 경로가 여러 개면 `--image PATH1 --image PATH2` 형태로 반복
- 이미지 없으면 플래그 생략

### 제목 추출 원칙

- 메타 키워드("todo 등록", "추가해줘", "내일", due date 관련 표현) 제거 후 핵심만 남긴다.
- 동사+목적어 중심으로 20~40자 합성.
- 예: "내일 VictoriaMetrics stg 업데이트 todo 등록해줘" → `VictoriaMetrics stg 클러스터 버전 업데이트`

### Repo 자동 감지

```
CWD: /Users/changhwan/workspace/riiid/kubernetes → repo: "kubernetes"
CWD: /Users/changhwan/workspace/riiid/terraform  → repo: "terraform"
CWD: /Users/changhwan/workspace/riiid/kubernetes-charts → repo: "kubernetes-charts"
```

---

## 워크플로우

### Step 1: 입력 파싱

사용자 입력에서 title, due, task 이름, repo를 추출한다.
- 추출 과정은 내부 처리만. 사용자에게 중간 출력 없음.
- due는 KST 기준 절대 날짜(YYYY-MM-DD)로 변환.
- task가 명시되지 않으면 `target_task = "__backlog__"` 확정 → Step 3으로 즉시 진행.

### Step 2: Task 매칭 (task가 명시된 경우만)

`todo_store.py list-tasks` 출력에서 사용자가 언급한 task 이름과 fuzzy 매칭한다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py list-tasks
```

출력 형식: `<task_id>\t<display_name>`

매칭 기준:
1. 사용자가 언급한 키워드가 `<display_name>`에 포함되면 매칭.
2. 복수 후보 → 첫 번째 채택 (가장 최근 Task).
3. 매칭 실패 → `__backlog__`로 fallback, 완료 메시지에 `(Backlog로 대체)` 표시.

### Step 3: todo_store.py add 실행

확정된 속성으로 add 커맨드를 실행한다.

```bash
# Backlog (기본, 시작전)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py add \
  --task __backlog__ \
  --title "VictoriaMetrics stg 클러스터 버전 업데이트" \
  --due "2026-06-18" \
  --repo "kubernetes"

# 진행 상태 명시 (진행중)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py add \
  --task __backlog__ \
  --title "PR 코드 리뷰" \
  --status "진행중" \
  --repo "kubernetes"

# description 포함 (사용자가 배경/이유를 언급한 경우)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py add \
  --task __backlog__ \
  --title "EBS 볼륨 22개 삭제" \
  --description "비용 절감 목적. okta-devops 계정의 미연결 볼륨으로 월 $X 낭비 중." \
  --repo "terraform"

# 이미지 첨부 (스크린샷 경로 또는 URL 포함 시)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py add \
  --task __backlog__ \
  --title "OOM 발생 Pod 조사" \
  --image "/Users/changhwan/Desktop/oom-screenshot.png" \
  --repo "kubernetes"

# Task-scoped (task 명시 시)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/todo_store.py add \
  --task "35f64745-3170-8164-9381-c108da219c1f" \
  --title "stg 클러스터 버전 업데이트" \
  --repo "kubernetes"
```

`--due`는 파싱된 경우만 포함. `--repo`는 감지된 경우만 포함.
`--description`은 사용자가 배경·문제·이유를 언급한 경우에만 포함. 단순 제목만 있으면 생략.

### Step 4: 완료 출력

JSON 출력의 `success` 필드로 성공 여부를 판단한다.

**성공** (`"success": true`):

```
✅ Todo 추가: VictoriaMetrics stg 클러스터 버전 업데이트 (~2026-06-18) [kubernetes/Backlog]
✅ Todo 추가: stg 클러스터 버전 업데이트 [kubernetes/VictoriaMetrics 버전 업데이트]
✅ Todo 추가: VictoriaMetrics stg 클러스터 버전 업데이트 [kubernetes/Backlog로 대체: "stg 업데이트" 매칭 실패]
```

**실패** (`"success": false`):

```
❌ Todo 추가 실패: <error 필드 내용>
```

---

## tasks:capture와의 차이

| | todo:add | tasks:capture |
|---|---|---|
| 대상 | 로컬 Todo 시스템 (TUI) | Notion Task DB |
| 생성 단위 | Todo 항목 (Task 하위 또는 Backlog) | Task (Project 단위) |
| 동기화 | `todo-sync`로 Notion to_do 블록 양방향 sync | 즉시 Notion 생성 |
| 트리거 | "todo 등록", "todo 추가" | "task 추가", "capture", "태스크 만들어줘" |

---

## 주의사항

- TUI에서 즉시 반영된다 (로컬 write). Notion sync는 별도로 `ctrl-r` 또는 `/todo-sync`.
- Task-scoped todo는 해당 Notion Task 페이지의 to_do 블록으로 sync된다.
- Backlog todo는 Notion 미동기화 (로컬 전용).
- 동일 제목 중복 추가 허용 (GTD 원칙: 정리는 TUI에서).
