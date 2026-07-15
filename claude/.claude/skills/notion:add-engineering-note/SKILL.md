---
name: notion:add-engineering-note
description: |
  Notion Engineering DB에 업무 노트 페이지를 생성하고 내용을 작성하는 스킬.
  사용 시점: (1) 인프라/시스템 설계 대화 후 결과를 Notion에 정리, (2) 의사결정 문서화,
  (3) 기술 검토/설계 노트 생성, (4) 이슈 분석 노트 작성.
  트리거 키워드: "업무 노트", "engineering note", "노트 생성", "eng-note",
  "엔지니어링 노트 써줘", "노션에 정리해줘", "노션에 노트 만들어줘", "설계 내용 노션에".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py append-content *)
  - Write(/tmp/eng-note-sections.json)
---

# Engineering Note Skill

Claude와의 설계/의사결정 대화 내용을 Engineering DB 업무 노트로 자동 생성하는 워크플로우.

---

## 핵심 원칙

- 본문 문장 스타일은 `~/.claude/docs/notion-writing-style.md`를 따른다 (짧고 단순하게, 핵심만). em dash/본문 이모지는 쓰기 스크립트가 자동 정리한다.
- **대화 내용을 템플릿에 매핑**한다. 섹션별로 대화에서 나온 내용을 추출해 채운다.
- 내용이 없는 섹션은 placeholder 유지: 억지로 채우지 않는다.
- **페이지 맨 위 목차(TOC) 콜아웃은 스크립트가 자동으로 만든다.** 페이지 생성 직후
  각 heading과 Goal/Non-goal 문단으로 링크가 걸린 📌 콜아웃을 붙이므로, Claude가
  `sections` 값에 목차 텍스트를 직접 넣지 않는다.
- 스크립트만 호출한다. Notion MCP 도구 사용 금지 (토큰 효율).
- 토큰은 환경변수 `$NOTION_TOKEN` 사용 (`~/.secrets.zsh`에서 로드됨).
- 생성 후 URL을 반드시 출력한다.

---

## DB 스키마

**DB ID**: `17964745-3170-8030-bf01-e7f20a6e1bd7`

| 속성 | 타입 | 옵션 |
|------|------|------|
| Title | title | - |
| Group | select | `#Study`, `#Article`, `#업무노트`, `#정리` |
| Created At | date | - |
| Task | relation | 개인 Task DB 관계 (반대편 속성: Task DB의 `Engineering`) |
| Task Status | rollup | Task의 `상태` (read-only, 자동) |

`Tag` multi_select는 실제 DB에 존재하지 않는다 (2026-07-07 드리프트 발견 후 제거). 태그가 필요하면 Task DB 쪽 속성을 사용한다.

---

## Primary Workflow: 대화 → Notion 노트

### 역할 분리: Task 문서 vs Engineering Note

Task를 연결하면(`--task`) 노트↔Task가 양방향 relation으로 묶인다. 이 경우 **문제 정의 /
목표 / 비목표는 작성하지 않는다**: 그 내용은 이미 연결된 Task 페이지의
`01. 문제 정의` / `04. Goals/Non Goals` 섹션이 단일 출처이므로, Engineering Note에
그대로 다시 쓰면 두 문서가 어긋날 때(Task는 갱신되고 노트는 그대로인 경우 등) 어느 쪽이
맞는지 판단할 근거가 없어진다. Engineering Note는 Task가 다루지 않는 부분,
즉 **설계 판단 · 실행 과정 · 사후 회고**를 담당한다.

`--task` 없이 만드는 **독립 노트**(순수 학습/정리, 연결할 Task가 없는 경우)는 참조할
Task 페이지가 없으므로 문제 정의/목표/비목표를 그대로 포함한다. 스크립트가
`--task` 유무로 자동 분기하므로(`linked_to_task`), Claude는 어느 케이스인지만 판단해
아래 표의 해당 키만 채우면 된다.

### Step 1: 대화 내용 분석 및 섹션 매핑

**Task 연결 노트** (표준 경로, Task가 있으면 항상 이 표만 사용):

| 섹션 | JSON key | 추출 기준 |
|------|----------|-----------|
| 설계 | `design` | 선택한 아키텍처/방식 |
| 대안 검토 | `alternatives` | 검토했던 다른 옵션들 |
| 작업 계획 | `plan` | 실행 단계, 체크리스트 |
| 작업 History | `history` | 날짜별 실제 진행 기록. 생성 시점엔 비워두고 이후 `append-content`로 계속 추가하는 것을 표준으로 한다 |
| Task Review | `review` | 완료 후 회고. task:review 출력 구조(성과 측정 / 성과 문장 PAR / 성장 회고)를 따르고, 상위 "Task Review" heading 없이 `### 성과 측정` 이하 하위 섹션만 넣는다. PAR 하위에는 3종(대표 PAR / 이력서 bullet / 성과평가용 확장형)을 모두 포함한다(이력서 bullet 생략 금지, 명사형 종결). 작업 진행 중에는 비워두고 완료 시점에 채운다 |
| 미결 질문 | `questions` | 아직 결정 안 된 것 |

**독립 노트** (`--task` 없음, 위 6개 키에 아래 2개 섹션이 추가됨):

| 섹션 | JSON key | 추출 기준 |
|------|----------|-----------|
| 문제 정의 | `problem` | 왜 이 작업을 하는가, 현재 상황 |
| 목표 / 비목표 | `goal` / `non_goal` | 달성하려는 것 / 이번 범위에서 제외한 것 |

### Step 2: 메타데이터 확인

사용자에게 확인 (대화 맥락에서 명확하면 생략):
- **제목** (필수)
- **Group**: 기본 `#업무노트`
- **연결할 Task** (표준, 있으면 항상 연결): 이 노트가 특정 Notion Task의 후속/작업 기록이면 그 Task의 page_id를 반드시 `--task`로 넘긴다. 대화에 Task 링크나 page_id가 언급돼 있으면 그대로 사용하고, 없으면 "이 노트를 연결할 Task가 있나요?"라고 한 번 확인한다. 완전히 독립적인 학습/정리 노트라면 생략 가능.

### Step 3: sections.json 작성 후 페이지 생성

```bash
# 1. sections.json 생성 (Write 도구 사용)
# /tmp/eng-note-sections.json

# 2. 페이지 생성 (Task 연결 표준, 있으면 항상 --task 전달)
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py create \
  --title "제목" \
  --group "#업무노트" \
  --task "<task-page-id>" \
  --sections /tmp/eng-note-sections.json
```

`--task`를 넘기면 스크립트가 양방향으로 관계를 건다:
1. 새 노트의 `Task` relation → 지정한 Task 페이지
2. Task 페이지의 `Engineering` relation → 새 노트 (기존 링크는 보존, 새 id만 추가)

Task와 무관한 독립 노트라면 `--task` 없이 생성한다:
```bash
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py create \
  --title "제목"
```

### Step 4: 결과 출력

```
업무 노트 생성 완료.
- 제목: {title}
- Group: {group}
- Task 연결: {있음(page_id) | 없음}
- URL: {url}
```

### Step 5: 검증

스크립트 응답의 `success` 필드를 반드시 확인한다. `--task`를 넘겼다면 `task_linked` 필드도 확인한다: `false`면 `task_link_error`를 그대로 사용자에게 전달한다(노트 자체는 생성됐지만 Task 쪽 역방향 링크만 실패한 상태이므로, Task page_id를 다시 확인 후 재시도하거나 Notion에서 수동으로 연결).

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 NOTION_TOKEN 확인
- `invalid database` → DB ID 확인
- `success: false` → 에러 메시지를 사용자에게 전달 후 재실행
- `task_linked: false` → Task page_id 오타 여부 확인, 재실행 또는 수동 연결

---

## sections.json 형식

```json
{
  "design":       "설계 내용 마크다운 (- 불릿, **bold**, 코드블록 지원)",
  "alternatives": "대안 검토 마크다운",
  "plan":         "- [ ] Step 1: ...\n- [ ] Step 2: ...",
  "history":      "- YYYY-MM-DD: 진행 기록 한 줄",
  "review":       "### 성과 측정\n- ...\n### 성과 문장 (PAR)\n**대표 PAR**\n- **Problem:** ...\n- **Action:** ...\n- **Result:** ...\n**이력서 bullet**\n- {명사형 종결}\n**성과평가용 확장형**\n- ...\n### 성장 회고\n- **Keep:** ...\n- **Try:** ...",
  "questions":    "- [ ] 미결 질문 항목",

  "problem":      "문제 상황 마크다운 (--task 없는 독립 노트에서만 사용)",
  "goal":         "목표 마크다운 (--task 없는 독립 노트에서만 사용)",
  "non_goal":     "비목표 마크다운 (--task 없는 독립 노트에서만 사용)"
}
```

값이 없는 키는 생략해도 됨 (placeholder로 대체). `history`/`review`는 생성 시점에
비워두고 작업 진행 중/완료 후 뒤늦게 채우는 것이 표준 흐름이다. `notion-eng-note.py`에는
`create`/`list`만 있고 append 전용 커맨드가 없지만, `/blocks/{page_id}/children` PATCH는
Notion API에서 Task DB 전용이 아니라 페이지 ID만 있으면 어느 DB의 페이지든 동작하므로
`tasks:manage/scripts/notion-task.py append-content --page-id <노트 page_id> --content "..."`를
그대로 재사용한다 (하드룰 위반 시 append 자체를 거부하는 검증도 동일하게 적용됨).

### 중첩 (구현 계획에 세부 내용 + 코드/설정 붙이기)

들여쓰기(2/4-space 무관, 상대 들여쓰기)로 하위 항목을 부모의 children으로 중첩할 수 있다.
`구현 계획`처럼 스텝 하나에 구체적인 내용과 실제 코드/설정을 함께 담을 때 이 형태를 표준으로 쓴다:

```json
{
  "plan": "- [ ] Step 1: values.yaml 수정\n  - requests.memory 2Gi -> 6Gi, limits.memory 12Gi -> 10Gi\n  ```yaml\n  resources:\n    requests:\n      memory: 6Gi\n    limits:\n      memory: 10Gi\n  ```\n- [ ] Step 2: yamllint 검증\n  - `yamllint src/infra/argocd/infra-k8s-global/values.yaml`"
}
```

- 코드 펜스(` ``` `)는 그 코드블록을 연 줄과 같은 들여쓰기 깊이의 형제로 붙는다 (스텝의 자식이 된다).
- Notion 페이지 **생성**(POST) 시 중첩은 한 번에 전부 반영된다. 단, 스텝 아래 세부 항목은 1단계 들여쓰기까지만 쓴다. 그 이상 깊어지면 가독성이 떨어지고, 이후 `notion-task.py append-content` 류로 내용을 덧붙일 때는 2단계(부모→자식→손자) 중첩 제약이 걸린다.

---

## 작업 History / Task Review 갱신 (생성 이후)

노트 생성 시 `history`/`review`를 비워뒀다면, 작업이 진행되거나 완료될 때 아래로 이어서 채운다.
Engineering DB 페이지도 일반 Notion 페이지이므로 Task DB 전용 스크립트가 아니라
블록 자체를 다루는 `append-content`를 그대로 쓴다 (페이지 ID만 있으면 어느 DB든 동작).

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py append-content \
  --page-id "<노트 page_id>" \
  --content "- 2026-07-07: canary 배포 완료, AnalysisRun 통과"
```

- **작업 History**: 진행 중 의미 있는 이벤트(배포, 이슈 발견, 방향 전환)가 생길 때마다 짧게 append.
- **Task Review**: Task가 완료 처리될 때 한 번, 목표 대비 결과·잘된 점/아쉬운 점·다음에 다르게 할 것을 append.
- append는 페이지 **맨 끝**에 붙는다 (특정 섹션 안으로 삽입되지 않음). "작업 History" 갱신임을
  알 수 있게 append 내용 앞에 날짜를 명시한다.

---

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py list --limit 10
```
