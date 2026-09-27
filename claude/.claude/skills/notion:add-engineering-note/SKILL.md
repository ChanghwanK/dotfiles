---
name: notion:add-engineering-note
description: |
  Notion Engineering DB에 업무 노트를 만드는 스킬. grill-me로 인터뷰해 설계 판단의 빈틈을 메우고,
  tasks:tech-spec 방법론(문제 검증 게이트, Goal Challenge, 리뷰 Agent)으로 내용을 확정한 뒤
  업무 노트 템플릿에 저장한다. 연결된 Task의 문제/근본 원인/기대 가치도 노트 최종본으로 맞춘다.
  사용 시점: (1) 인프라/시스템 설계 대화 후 결과를 Notion에 정리, (2) 의사결정 문서화,
  (3) 기술 검토/설계 노트 생성, (4) 이슈 분석 노트 작성.
  트리거 키워드: "업무 노트", "engineering note", "노트 생성", "eng-note",
  "엔지니어링 노트 써줘", "노션에 정리해줘", "노션에 노트 만들어줘", "설계 내용 노션에".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py read-page *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-why *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py append-content *)
  - Skill
  - Write
---

# Engineering Note Skill

설계·의사결정 작업을 **인터뷰(grill-me) → 스펙 확정(tasks:tech-spec) → 노트 저장** 순서로 Engineering DB
업무 노트에 남긴다. 대화에서 나온 내용을 그대로 옮기지 않고, 인터뷰로 빈틈을 메우고 스펙 게이트로
검증한 결과를 저장하는 것이 목적이다.

---

## 핵심 원칙

- **노트가 최종본이다.** 문제/근본 원인/기대 가치는 Task에도 있지만(캡처 시점 이해), 노트를 쓰는 시점의
  정제된 내용이 최종본이다. 노트를 만들 때 연결된 Task의 같은 섹션을 `update-why`로 최종본으로 교체한다.
  이후 수정도 노트에서 한다. Task의 `작업 Context`는 캡처 기록이므로 건드리지 않는다.
- **템플릿이 구조의 단일 출처다.** 스크립트가 Notion 템플릿(`NOTE_TEMPLATE_ID`)을 적용하고 heading 아래를
  채운다. Claude는 sections JSON만 만든다. 목차는 템플릿의 네이티브 목차 블록이 자동으로 만든다.
- **추정으로 채우지 않는다.** 인터뷰·세션에 근거가 없는 섹션은 키를 생략해 템플릿의 빈 칸으로 둔다.
- 본문은 `~/.claude/docs/notion-writing-style.md`의 "쓰기 시점 체크리스트"를 초안 단계부터 적용한다:
  - 불릿 `레이블: 내용`은 레이블을 `*레이블:*`(이탤릭) 상위 불릿으로, 내용은 한 단계 들여쓴 하위 불릿으로 쓴다.
  - 버전/태그/상태 전환은 "to" 대신 화살표(`→`)로 쓴다.
  - 여러 섹션에 같은 사실을 재진술하지 않는다. 한 사실은 가장 적합한 섹션에만 쓴다.
  - 불릿 목록은 결론·핵심 판단을 첫 불릿에 둔다.
  - 코드 블록은 실행형 명령어/설정 전체에만 쓰고, 강조는 볼드로 한다.
  - em dash/본문 이모지, "to"→화살표(숫자 버전·backtick 값 한정)는 쓰기 스크립트가 결정적 backstop을 건다.
- **PR 참조는 링크 멘션으로.** `PR #1234` 대신 실제 URL(`https://github.com/riiid/kubernetes/pull/1234`)을 붙인다.
- 스크립트만 호출한다. Notion MCP 도구는 쓰지 않는다(토큰 효율). 토큰은 `$NOTION_TOKEN`을 쓴다.
- 생성 후 URL을 반드시 출력한다.

---

## DB 스키마

**DB ID**: `17964745-3170-8030-bf01-e7f20a6e1bd7`

| 속성 | 타입 | 옵션 |
|------|------|------|
| Title | title | - |
| Group | select | `#Study`, `#Article`, `#업무노트`, `#정리` |
| Created At | date | - |
| Task | relation | 개인 Task DB 관계 (반대편 속성: Task DB의 `Working Note`) |
| Task Status | rollup | Task의 `상태` (read-only, 자동) |

---

## 템플릿 구조와 sections 키

```
[📌 목차]
## 왜 이걸 해야하는가?
### 문제              ← problem
### 근본 원인         ← root_cause
### 기대 가치         ← value
## 현재 상태와 목표
[ ### Before ← before | ### After ← after ]
### 변경 사항         ← changes
[ ### Goals ← goals | ### Non Goals ← non_goals ]
## 설계               ← design
## 실행 기록          ← plan (### 실행 계획), history (### 진행 기록)
## 작업 결과          ← result
---
## Task Review
### 성과 측정         ← review_metrics
### 성과 문장 (...)   ← review_par
### 성장 회고 (...)   ← review_retro
```

- 섹션 제목이 H2/H3이므로 섹션 내용에는 heading을 `###`만 쓴다(스크립트가 H3 기준으로 보정한다).
- 2열(Before/After, Goals/Non Goals) 안의 불릿도 2단계 중첩까지 쓸 수 있다.
- `plan`이 있으면 `### 실행 계획` 체크박스 아래에 `### 진행 기록`이 생기고, 이후 기록은 `실행 기록` 섹션 끝에 쌓인다.

---

## 워크플로우

### Step 0: 연결할 Task 확정 + Task 본문 읽기

- 대화에 Task 링크나 page_id가 있으면 그대로 쓴다. grill-me에서 넘어왔는데 Task가 없으면 묻지 않고 `tasks:capture`를
  인터뷰 결과와 함께 호출해 Task를 만든 뒤 그 page_id로 진행한다. 그 외에 Task가 없으면 "이 노트를 연결할 Task가 있나요?"라고 한 번 묻는다.
  연결할 Task가 없는데 실제 업무라면 `tasks:capture`로 먼저 Task를 만들고 이어간다. 순수 학습/정리 노트만
  Task 없이 만든다.
- Task 본문을 읽어 캡처 시점의 문제/근본 원인/기대 가치와 `작업 Context`(확인한 사실, 관련 리소스, 검토한 것)를
  인터뷰의 출발점으로 삼는다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py read-page --page-id "<task-page-id>"
```

### Step 1: grill-me 인터뷰

`grill-me`를 Skill 도구로 호출한다. args에 **eng-note 모드**임과 Task 본문 요약을 넘긴다.

- 인터뷰 대상: 문제·근본 원인이 현상이 아니라 메커니즘인가, Before/After가 구체적인가, Goals/Non Goals의
  경계가 분명한가, 설계 결정마다 이유와 기각한 대안이 있는가.
- grill-me의 라운드 진행(frontier·추천 답·가벼운 합의 확인)과 탈출 경로를 그대로 따른다. 사용자가 "인터뷰 생략"을 명시하면 Step 2를
  Quick mode로 진행한다(Claude가 스스로 생략하지 않는다).
- 인터뷰 결과(확정된 결정, 해소된 Gap, 남은 Gap)는 Step 2의 입력이 된다.
- grill-me에서 이 스킬로 넘어온 경우(args에 "grill-me 인터뷰 완료")는 인터뷰를 다시 하지 않고 Step 2로 간다.

### Step 2: tasks:tech-spec으로 내용 확정

`tasks:tech-spec`을 Skill 도구로 호출한다. args에 **eng-note 모드**, 연결할 Task page_id, Step 1 인터뷰 결과를 넘긴다.

- Standard mode의 Phase 1~3을 grill-me 결과로 미리 채운 상태에서 진행한다(이미 확정된 내용은 다시 묻지 않는다).
- 공통 문제 검증 게이트(G1~G4), Goal Challenge, 저장 전 자동 검증, 리뷰 Agent(F)를 그대로 거친다.
- tech-spec은 Obsidian에 저장하지 않는다. 확정된 스펙을 아래 Step 3의 매핑으로 이 스킬에 돌려준다.

### Step 3: sections.json 작성

tech-spec 산출물을 아래 표로 sections 키에 옮긴다.

| tech-spec 섹션 | sections 키 | 작성 기준 |
|----------------|-------------|-----------|
| 왜 이걸 해야 하는가? > 문제 | `problem` | 관측된 사건이 아니라 그 사건을 가능하게 한 경계·장치·절차의 결함을 현재형으로 쓴다(판별: `tasks:capture` "현상을 빼고 문제를 쓴다") |
| 왜 이걸 해야 하는가? > 배경(원인) | `root_cause` | 신호가 아니라 신호를 만든 메커니즘. 확인하지 못한 부분은 `(미확인)`으로 표시한다 |
| 임팩트 측정 > 기대 효과·측정 방법 | `value` | 개선 후 사람·팀이 얻는 것 + `*측정 기준:*` 대표 지표의 현재값 |
| 현재 상태와 목표 > Before / After | `before` / `after` | 같은 축으로 대응되게 쓴다(Before의 각 항목에 After가 짝을 이룬다) |
| 현재 상태와 목표 > 변경 사항 (Diff) | `changes` | 변경 대상별 As-Is → To-Be. 설정 수준 diff는 코드 블록 |
| 목표·성공 기준 | `goals` | 아래 "Goals 작성 기준" |
| Non-Goals | `non_goals` | 이번엔 다루지 않는 것(오버엔지니어링 방지 경계), 비가역 변경이면 롤백 시나리오 |
| 설계 + 왜 이 방법인가 | `design` | `### 선택 이유`, `### 대안 및 트레이드오프`, 스펙 아티팩트 표, 다이어그램(Step 3-1) |
| 실행 계획 | `plan` | 아래 "실행 계획 작성 기준" |
| (진행 기록) | `history` | 생성 시점엔 보통 비운다. 이후 `append-content --section "실행 기록"`으로 날짜별 누적 |
| 실제 결과 (Outcome) | `result` | 완료 후 채운다. 성공 기준 대비 측정값 |
| (완료 후 회고) | `review_metrics` / `review_par` / `review_retro` | `task:review` 출력 구조. PAR은 대표 PAR / 이력서 bullet(명사형 종결) / 성과평가용 확장형 3종 모두 |
| (완료 후 회고, 한 문자열) | `review` | 편의 키. `### 성과 측정` / `### ...성과 문장` / `### 성장 회고` 하위 heading으로 쓰면 스크립트가 위 세 섹션에 나눠 넣는다. `review_*`와 함께 쓰지 않는다 |

#### Goals 작성 기준

- **행동·동작 기반으로 쓴다.** "무엇을 한다"가 아니라 작업이 끝났을 때 시스템이 어떤 조건에서 어떻게
  동작하는지를 서술한다. 형식은 `{조건}일 때, {관찰 가능한 결과}가 발생한다 / 발생하지 않는다`.
- **억제 케이스와 정상 케이스를 쌍으로 쓴다.** "X일 때 안 온다"만 쓰면 과잉 억제(전면 침묵) 회귀를 잡지 못하므로
  "Y일 때는 온다"를 함께 둔다. 이렇게 쓰면 Goals가 그대로 완료 판정 기준 겸 검증 시나리오가 된다.
  - 좋은 예: "promote가 완료된 stable 리비전에서 replica가 부족해질 때, abort 알림이 오지 않는다" /
    "promote 전 리비전이 카나리 진행 중 abort될 때, abort 알림이 온다"
  - 나쁜 예(plan으로 옮길 대상): "trigger에 when 조건을 추가한다", "dev/stg/prod에 배포한다"
- tech-spec의 성공 기준(수치)은 해당 Goal 옆에 괄호로 붙인다.
- 환경이 여러 개인 변경은 "위 동작이 dev, stg, prod에서 동일하게 성립한다"를 마지막 Goal로 둔다.

#### 실행 계획 작성 기준

- 실행 단위 액션을 체크박스(`- [ ]`)로 실제 실행 순서대로 나열한다. **한 체크박스 = 따로 착수하고 따로 끝낼 수 있는
  한 덩어리**(결정 기록, PR 하나, 환경 롤아웃 하나, 검증 한 번). 형식은 `{단위 이름}: {무엇을 하는가 한 줄}`,
  5~7개 기준. tech-spec의 Phase 구분이 있으면 `###`가 아니라 항목 이름 앞에 Phase를 붙인다.
- 환경 단계(dev → stg → prod)는 항목을 쪼개지 않고 한 항목 안에 순서로 적는다.
- 검증 항목은 무엇으로 판정하는지를 지표·관찰 이름 수준으로 적는다(쿼리·명령은 쓰지 않는다).
- 인프라·설정 변경이 있으면 마지막에 `*롤백:*` 라벨 불릿으로 원복 방법과 소요 시간을 적고, 생략하지 않는다.
  문서·설계만 하는 작업처럼 되돌릴 인프라 변경이 없으면 `*롤백:*` 라벨째 생략한다("변경 없음, 문서 수정으로 되돌림" 같은
  빈 문장을 쓰지 않는다. 2026-09-27 QA 피드백).
- 범위를 넘는 후속 조사·분리 작업도 체크박스로 남긴다.
- 이 체크리스트가 alfred gate의 세부 계획 대조 원본이다. 계획이 실행 중 바뀌면 이 체크리스트를 고치고,
  왜 바뀌었는지는 `진행 기록`에 남긴다.

#### Step 3-1: 설계 시각화 (가능하면 다이어그램 1개 이상)

`design`에는 가능하면 `archify` 또는 `diagram-design`으로 만든 다이어그램을 넣는다.

- *도구 선택:*
  - `archify`: 시스템·인프라 아키텍처, 요청 흐름, 시퀀스, 데이터 흐름, 상태 전이
  - `diagram-design`: 선택지 비교(매트릭스·사분면), 계층·우선순위, 타임라인·전환 순서, 수치 차트, 의사결정 흐름도
- *절차:*
  - 해당 스킬로 HTML을 만든 뒤 그 스킬의 PNG 내보내기 절차로 **흰 배경 PNG**를 만든다(Notion 다크 모드 대비). 파일은 스크래치패드에 둔다.
  - `design` 마크다운에 `![캡션](/절대/경로/diagram.png)` 한 줄을 넣는다. 스크립트가 업로드해 이미지 블록으로 넣는다(png·jpg·gif·webp·svg, 20MB 이하).
- *생략 조건:*
  - 구조·흐름·비교가 없는 순수 텍스트 결정은 그리지 않는다. 생략했으면 결과 출력에 이유를 한 줄로 적는다.
- 다이어그램은 본문을 대신하지 않는다. 결정에 필요한 핵심은 불릿으로도 남긴다.

### Step 4: 페이지 생성 + Task 동기화

sections JSON은 스크래치패드에 Write한 뒤 넘긴다.

```bash
# 1. 노트 생성 (Task가 있으면 항상 --task)
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py create \
  --title "제목" \
  --group "#업무노트" \
  --task "<task-page-id>" \
  --sections "/path/to/scratchpad/eng-note-sections.json"

# 2. Task의 문제/근본 원인/기대 가치를 노트 최종본으로 교체 (같은 문장을 그대로 넘긴다)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-why \
  --page-id "<task-page-id>" \
  --sections-file "/path/to/scratchpad/task-why.json"   # {"problem": ..., "root_cause": ..., "value": ...}
```

- `--task`를 넘기면 스크립트가 노트의 `Task` relation과 Task의 `Working Note` relation을 양방향으로 건다.
- `update-why`는 Task에 해당 heading이 없으면(구 템플릿 Task) 아무것도 쓰지 않고 실패한다. 이때는 동기화를
  건너뛰고 결과 출력에 "Task 동기화 생략(구 템플릿)"을 적는다.
- 템플릿이 30초 안에 적용되지 않으면 스크립트가 그 페이지를 휴지통으로 보내고 같은 구조로 다시 만든다
  (`template_applied: false`, 전체 너비 등 템플릿 설정만 빠진다).

### Step 5: 결과 출력

```
업무 노트 생성 완료.
- 제목: {title}
- Group: {group}
- Task 연결: {있음(page_id) | 없음}
- Task 동기화: {문제/근본 원인/기대 가치 교체 | 생략(이유)}
- 템플릿: {적용 | 미적용(template_error) → 같은 구조로 대체 생성}
- 인터뷰: {grill-me 결정 N개, 남은 Gap M개 | 사용자 요청으로 생략}
- 설계 다이어그램: {N개 (도구명) | 생략 (이유)}
- URL: {url}
```

### Step 6: 검증

- `success`를 확인한다. `false`면 `error`를 그대로 전달한다(`NOTION_TOKEN not set` → `~/.secrets.zsh` 확인).
- `--task`를 넘겼다면 `task_linked`를 확인한다. `false`면 `task_link_error`를 전달한다(노트는 생성됐고 Task 쪽
  역방향 링크만 실패한 상태이므로 page_id 확인 후 재시도하거나 Notion에서 수동 연결).
- `template_applied: false`면 `template_error`를 전달한다(템플릿 ID 변경·권한 문제일 수 있다).

---

## 생성 이후 갱신 (진행 기록 / 작업 결과 / Task Review)

생성 시점에 비워 둔 섹션은 작업이 진행되거나 끝날 때 `append-content --section`으로 해당 섹션 끝에 붙인다.
페이지 끝이 아니라 섹션 안에 들어가므로 템플릿 구조가 유지된다.

```bash
# 진행 기록: 의미 있는 이벤트(배포, 이슈 발견, 방향 전환)마다 날짜를 붙여 짧게
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py append-content \
  --page-id "<노트 page_id>" --section "실행 기록" \
  --content "- 2026-07-07: canary 배포 완료, AnalysisRun 통과"

# 작업 결과 / Task Review 하위 섹션
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py append-content \
  --page-id "<노트 page_id>" --section "작업 결과" --content "- ..."
```

- `--section`은 heading 텍스트다. 정확히 일치하는 heading이 없으면 접두어로 찾으므로 괄호 설명은 생략해도 된다(`성장 회고`).
- 실행 계획 체크박스를 대신 체크하지 않는다(본문 덮어쓰기 위험). 진행 상황은 진행 기록에 남긴다.

---

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py list --limit 10
```
