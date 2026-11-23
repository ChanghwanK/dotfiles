---
name: weekly:plan
description: |
  주간 Plan 노트 스킬. Notion API로 Weekly DB(#주간 Plan 페이지)에 이번 주 노트(N주차 MM.DD ~ MM.DD)를 만들고, 지난주 Claude 세션 로그와 PR을 작업 스레드로 묶어 마무리 여부를 판정한 뒤, Task DB의 진행 중·마감·이월 Task와 합쳐 주간 목표 후보와 리마인드를 뽑는다. 목표와 할 일을 Jira PLE 티켓과 대조해 새 티켓을 제안한다. 결과는 HTML 리뷰 페이지(Artifact)로 먼저 게시하고, 사용자가 승인한 뒤에만 노트에 쓰고 Jira 티켓을 만든다.
  사용 시점: (1) 월요일 주간 목표 설정, (2) 위클리 노트 생성, (3) 이번 주 목표 후보 정리, (4) 지난주 하던 작업 이어 가기.
  트리거 키워드: "위클리 노트", "위클리 Plan", "주간 Plan", "weekly plan", "이번 주 목표", "/weekly:plan".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/weekly-plan.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Bash(gh search prs *)
  - Bash(gh pr view *)
  - Bash(python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/render-review.py *)
  - Read
  - Write
  - Agent
  - Artifact
  - Skill
  - mcp__claude_ai_Atlassian_MCP__searchJiraIssuesUsingJql
  - mcp__claude_ai_Atlassian_MCP__atlassianUserInfo
  - mcp__claude_ai_Atlassian_MCP__createJiraIssue
---
# weekly:plan Skill

`/weekly:plan` 한 번으로 지난주 작업을 판정하고, 이번 주 목표·리마인드·Jira 티켓 제안을 HTML 리뷰 페이지로 게시한다. 노트 반영과 티켓 생성은 사용자가 페이지를 보고 승인한 뒤에만 한다.

## 흐름 한눈에

| 구간 | 단계 | 쓰기 | 멈춤 |
|------|------|------|------|
| 자동 | Step 1 노트 틀 생성 → 2 Task 후보 → 3 지난주 스레드 판정 (Jira 조회와 병렬) → 4 후보 고르기 → 5 Jira 대조 → 6 리뷰 페이지 게시 | 빈 노트 틀(Step 1)과 로컬 JSON·HTML뿐 | 없음. 사용자에게 묻지 않고 Step 6까지 이어서 실행한다 |
| 승인 대기 | Step 6 게시 뒤 | 없음 | **여기서만 멈춘다**. 콘솔 네 줄과 페이지 링크로 끝낸다 |
| 승인 후 | Step 7 노트 반영, Step 8 Jira 생성, `set-status` | 사용자가 고른 것만 | 각 반영 뒤 페이지를 갱신한다 |

### 승인 응답 대응표

| 사용자 응답 | 할 일 |
|-------------|-------|
| "반영해", "노트에 써" | Step 7 (`apply`) |
| "Jira 등록해", "J1, J3만 등록해", "나로 할당" | Step 8 (고른 제안만, 담당자 본인) |
| "목표 2 바꿔", "리마인드에 X 추가" 같은 수정 | JSON을 고치고 Step 6의 2~3으로 같은 URL에 다시 게시한 뒤 다시 승인을 기다린다 |
| "XX Task 진행 중으로 바꿔" | Step 7의 `set-status` |
| 여러 가지를 한 번에 | 위를 순서대로(수정 → 노트 → Jira) 실행하고 페이지를 한 번만 다시 게시한다 |

## 핵심 원칙

- Notion 호출은 `weekly-plan.py`만 쓴다. MCP로 페이지를 만들지 않는다.
- `create`는 멱등이다. 같은 제목의 노트가 있으면 새로 만들지 않고 기존 URL을 돌려준다.
- 목표는 사용자가 정한다. **노트에 쓰기 전에 HTML 리뷰 페이지를 먼저 게시하고**, 사용자가 승인("반영해" 등)한 뒤에만 `apply`로 쓴다. 리뷰 페이지와 `apply`는 같은 JSON 한 파일을 읽으므로 리뷰한 내용이 그대로 쓰인다.
- 주차는 ISO 주차, 기간은 월~금이다 (예: `46주차 11.09 ~ 11.13`).
- **지난주를 이어 간다.** 후보 순위는 마감일이 아니라 지난주 작업 스레드의 상태(진행 중, 중단)로 정한다. 마감일은 가산점과 경고로만 쓴다. 지난주 탐색 범위는 주말을 포함한 월~일이다(주말 작업도 이어 갈 작업이다).
- **Jira 티켓은 승인한 것만 만든다.** 노트 반영 승인("반영해")과 티켓 생성 승인("Jira 등록해")은 따로 받는다. 티켓은 팀 보드에 보이는 외부 산출물이기 때문이다. 기존 티켓의 상태·담당자는 바꾸지 않고 메모로만 짚는다.
- **Task 상태는 제안만 한다.** 스레드 판정과 Task 상태가 어긋나도 직접 바꾸지 않고 사용자가 승인한 것만 반영한다.

## 워크플로우

### Step 1: 이번 주 노트 생성

```bash
python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/weekly-plan.py create
```

- 다른 주는 `--date YYYY-MM-DD`(그 주의 아무 날)로 지정한다.
- `NOTION_TOKEN` 누락 오류가 나면 `source ~/.secrets.zsh` 후 다시 실행하라고 안내한다.
- 생성되는 틀: 회고 질문 콜아웃, 이번 주 목표(체크박스 3개 + 완료 기준), 이번 주 하지 않을 것, 일별 기록(월~금 토글), 주간 회고.
- 이 단계는 빈 틀만 만든다. 목표와 리마인드 내용은 승인 뒤 Step 7에서 쓴다. 출력의 `url`은 Step 6 JSON의 `note_url`로 쓴다.

### Step 2: 목표 후보 수집

```bash
python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/weekly-plan.py candidates
```

출력 키:
- `due_this_week`: 이번 주 마감 Task
- `in_progress_recent`: 진행 중이고 최근 4주 안에 손댄 Task. 최근 여부는 `max(Due Date, last_edited)`로 판정하고 최근 순으로 정렬한다. 진행 중 Task 대부분은 Due Date가 비어 있어 `last_edited`가 실질 신호다 (마무리 후보)
- `carryover_todo`: 최근 4주 안 마감이 지났는데 손대지 않은 Task (이월 후보)
- `due_next_week`: 다음 주 마감 Task (이번 주 착수 후보)
- `stale_in_progress_count`: 4주 넘게 손대지 않은 "진행 중" Task 수 (정리 필요 신호)

`last_edited`는 페이지의 어떤 수정에도 갱신되는 거친 신호다. 실제로 작업했는지는 Step 3의 세션 탐색으로 가린다.

### Step 3: 지난주 작업 스레드 판정 (서브에이전트)

먼저 지난주 범위를 계산한다(`Asia/Seoul`). `week_start`는 이번 주 월요일 - 7일, `week_end`는 이번 주 월요일 - 1일(일요일), `week_dates`는 그 사이 7개 날짜, `catchup_dates`는 이번 주 월요일부터 오늘까지의 날짜다. `catchup_dates`가 필요한 이유는 `extract-work.py`가 세션을 파일 마지막 수정일로 배정하기 때문이다. 지난주 세션을 이번 주에 다시 열거나 앱 재시작으로 파일이 다시 쓰이면 이번 주로 넘어가므로, 이번 주 날짜도 읽고 `started_at`이 지난주인 세션만 되살린다.

```bash
TZ=Asia/Seoul date -v-mon -v-7d '+%Y-%m-%d'   # week_start (오늘이 월요일이면 -v-mon은 오늘)
```

Step 5의 PLE 티켓 조회(1번)는 이 서브에이전트와 독립이므로 서브에이전트를 띄운 같은 메시지에서 함께 실행한다.

`agents/agent-last-week-work.md`를 Read로 읽어 `{week_start}`, `{week_end}`, `{week_dates}`, `{catchup_dates}`, `{task_candidates}`(Step 2 JSON 전체)를 치환한 뒤 `Agent`(`subagent_type: general-purpose`, `model: sonnet`)로 실행한다. 7일치 세션 로그는 양이 많아 메인 컨텍스트에서 읽지 않는다.

- 반환은 `WEEK_RESULT_START/END` 사이의 YAML이다. 형식을 지키지 않았으면 1회 재시도한다
- **Agent 도구를 쓸 수 없으면**(서브에이전트 안에서 실행된 경우) 프롬프트의 수집·판정 절차를 직접 수행한다
- 실패해도 중단하지 않는다. "지난주 탐색 실패: {이유}"를 쓰고 Task DB 후보만으로 Step 4를 진행한다

### Step 4: 후보 고르기

후보 3개를 추천 순으로 고른다. 점수는 아래를 더한다.

| 신호 | 점수 |
|------|------|
| 지난주 스레드 진행 중 | +4 |
| 지난주 스레드 중단 | +3 |
| 스레드의 마지막 작업일이 지난주 목~일 | +1 |
| 연결 Task가 P1 / P2 | +2 / +1 |
| 이번 주 마감 | +2 |
| 장애 재발 방지 Task | +1 |
| 이월 2주 이상 | +1 |

- 스레드와 연결된 Task는 하나의 후보로 합친다. 후보 이름은 Task 이름, 근거에 스레드의 `remaining`을 쓴다
- 완료 기준은 스레드의 `done_when`을 다듬어 **Key Result 형태**(한 줄 지표 제목 + 구체 기준 하위 불릿)로 쓴다. "PR을 연다" 같은 행동이면 그 결과로 바꾼다. 문체 정본은 `task:keyresult`다. 노트의 완료 기준과 Jira 티켓의 Key Result는 같은 문장을 쓴다. 스레드가 없는 Task는 제목에서 초안을 만들고 "(제목 기반 초안)"을 붙인다
- 스레드와 연결되지 않은 이번 주 마감 Task가 후보 3개에 못 들면 경고로 따로 적는다
- 나머지는 "예비 후보"로 짧게 나열한다

리뷰 페이지(Step 6)에는 후보 아래 다음 섹션을 해당할 때만 넣는다.
- **지난주 스레드**: `스레드 | 판정 | 마지막 작업일 | 연결 Task | 남은 것` 표 (완료 포함 전부)
- **Task 상태 제안**: `task_status_suggestions`. "승인하시면 반영합니다"로 끝낸다
- **Task 없는 스레드**: `capture_candidate: true`인 스레드. `/tasks:capture` 후보로 표시한다
- **지난주 손대지 않은 진행 중 Task**: `untouched_in_progress` 수와 상위 3건
- `stale_in_progress_count`가 5 이상이면 Task DB 정리가 필요하다고 한 줄로 짚는다

리마인드 구성: 목표로 고르지 않은 진행 중·중단 스레드와 마감 지난 Task 중 행동이 정해진 것은 "해야할 것", Task 상태 제안·capture 후보·중단 스레드 재개 여부·손대지 않은 진행 중 Task 정리처럼 판단이 필요한 것은 "볼 것"에 둔다. 정리가 필요한 임시 자원(수집기, 실험 리소스)은 "해야할 것" 맨 앞에 둔다. Task 상태 제안은 "볼 것"에 "(승인 대기)"로 넣는다.

### Step 5: Jira 티켓 대조와 제안 (읽기만 한다)

팀은 Jira PLE Space(보드 1562, 담당자별 그룹)로 일한다. 목표와 리마인드 "해야할 것"을 PLE 티켓과 대조한다. 이 단계에서는 티켓을 만들지 않는다.

1. PLE 티켓을 조회한다 (cloudId `bde901ec-3020-4c95-b17b-a30a9a176fb9`)
   - `searchJiraIssuesUsingJql`: `project = PLE AND (statusCategory != Done OR updated >= -14d) ORDER BY created DESC`, fields `summary, status, issuetype, assignee, priority, labels, parent, duedate`
   - 본인 accountId는 `atlassianUserInfo`로 얻는다. 하드코딩하지 않는다
2. 항목마다 대조한다. 대상(컴포넌트, circle, 기능)이 같은 티켓만 잇는다
   - **이미 있는 티켓**(`jira.linked`): 같은 작업의 티켓. 담당자 없음, 다른 팀원이 진행 중(중복 작업 위험), 티켓은 DONE인데 스레드상 남은 일이 있음 같은 어긋남은 `note`에 쓴다. "볼 것"의 중단 스레드도 다른 사람 티켓과 겹치면 넣는다
   - **새 티켓 제안**(`jira.proposals`): 목표와 "해야할 것" 중 맞는 티켓이 없는 것. 같은 주제의 Epic이 있으면 `parent`로 건다. 기존 티켓이 범위가 다르면(예: "검토" 티켓과 이번 주 "적용") 새 티켓으로 나누고 `linked`에 그 이유를 쓴다
   - "볼 것"(판단 항목)에는 티켓을 제안하지 않는다
3. 제안의 유형·필드는 `~/.claude/docs/jira-ticket-template.md`(정본)를 Read해 따른다. Epic은 제안하지 않는다
   - `done_when`에는 템플릿의 Key Result 문장을 쓴다. 행동("PR을 연다")이면 결과 문장으로 바꾼다
   - `id`는 `J1`부터 붙인다. 사용자가 번호로 고른다

### Step 6: HTML 리뷰 페이지 게시 (노트에 쓰지 않는다)

1. 리뷰 데이터를 `~/.claude/tmp/weekly-plan/{week_start}.json`에 Write로 쓴다. `week_start`는 이번 주 월요일이다. 스키마는 `assets/review-data.example.json`을 따른다
   - 머리 필드(필수): `title`("{N}주차 주간 Plan", 탭과 갤러리 이름), `week`(Step 1 제목), `week_start`(이번 주 월요일), `range`({start, end}: 지난주 월·일), `headline`(결론 한두 문장: 무엇을 이어 가고 무엇을 리마인드에 두었는지), `note_url`(Step 1 url), `totals`(sessions, threads, prs_merged, prs_open), `stale_in_progress_count`
   - `goals`(title, url, done_when, status, last_worked, why, remaining, linked_tasks)와 `reminders`(label, items[text, url])는 `apply`가 노트에 그대로 쓰는 필드다
   - 나머지(`jira`, `threads`, `task_status_suggestions`, `capture_candidates`, `untouched_in_progress`, `reserve`, `totals`, `errors`)는 리뷰 전용이다. Step 3 YAML과 Step 5 대조 결과에서 옮긴다
   - `applied: false`로 둔다
2. HTML을 만든다
   ```bash
   python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/render-review.py --data ~/.claude/tmp/weekly-plan/{week_start}.json
   ```
3. `artifact-design` 스킬을 Skill 도구로 불러 page contract를 확인한 뒤, 출력된 `path`를 Artifact로 게시한다. 주차별 경로라 주마다 새 URL이 된다
   - 첫 게시: `icon: "calendar"`, `description`: "{week} 목표 후보와 리마인드, 지난주 작업 스레드 판정을 노트에 반영하기 전에 검토하는 페이지"
   - 수정 요청을 받으면 JSON을 고치고 2~3을 다시 실행한다(같은 경로라 같은 URL로 갱신된다)
4. 콘솔 응답은 아래 "결과 출력 형식"의 네 줄로 끝낸다

### Step 7: 노트에 반영 (사용자가 승인한 뒤에만)

사용자가 리뷰 페이지를 보고 승인하면 같은 JSON으로 반영한다. 고쳐 달라는 요청이면 Step 6으로 돌아가 페이지를 갱신하고 다시 승인을 받는다.

```bash
python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/weekly-plan.py apply --spec ~/.claude/tmp/weekly-plan/{week_start}.json
```

- `goals`는 "목표 1~3" 체크박스 텍스트와 그 아래 완료 기준 불릿을 바꾼다. 체크 상태는 유지한다
- `reminders`는 목표 바로 아래 `이번 주 리마인드` 구역(H2)에 체크박스로 쓴다. 다시 실행해도 같은 결과다(멱등)
- **사용자가 노트에서 한 체크는 지우지 않는다.** 같은 텍스트의 리마인드는 체크를 이어받고, 새 spec에 없는 체크된 항목은 `이전에 체크한 항목:` 아래에 남긴다. 출력의 `carried_checked`, `kept_checked`로 확인한다
- 주중에 목표나 리마인드 한쪽만 고칠 때는 `--only goals` 또는 `--only reminders`를 쓴다. JSON을 고치고 Step 6의 2~3으로 페이지를 갱신한 뒤, 승인을 받고 실행한다
- 반영 뒤 JSON의 `applied`를 `true`로 바꾸고 Step 6의 2~3을 다시 실행해 페이지에 "노트에 반영됨"을 표시한다
- Task 상태 제안은 사용자가 따로 승인한 것만 Task DB에 반영한다
  ```bash
  python3 /Users/changhwan/.claude/skills/weekly:plan/scripts/weekly-plan.py set-status --task <Task URL> --status "진행 중"
  ```
  반영한 제안은 JSON의 `task_status_suggestions`에서 빼고, 해당 "볼 것" 리마인드 문구를 "(MM.DD 반영 완료)"로 바꾼다
- 반영 뒤 노트 URL을 알려 확인을 받는다

### Step 8: Jira 티켓 생성 (사용자가 "Jira 등록해"라고 승인한 것만)

- 사용자가 고른 제안(`J1, J3` 또는 전부)만 `createJiraIssue`로 만든다. 고르지 않은 것은 만들지 않는다
  - `projectKey: "PLE"`, `issueType`, `summary`, `priority`, `labels`, `parent`(있을 때), `assignee`: 본인 accountId
  - `description`(markdown): `~/.claude/docs/jira-ticket-template.md`의 유형별 템플릿(Background, Goal, Key Result (완료 기준), Todo, 범위 밖, 링크)으로 쓴다. 내용은 스레드의 done·remaining, 제안의 `done_when`, PR·Notion Task·노트 링크에서 채운다
- 만들기 전에 같은 요약의 티켓이 생겼는지 `summary ~ "<핵심어>"` JQL로 한 번 더 확인한다(중복 생성 방지). 있으면 만들지 않고 `linked`로 옮긴다
- 실패하면 응답의 `repairHint`대로 한 번만 고쳐 다시 시도한다. 그래도 실패하면 그 제안만 건너뛰고 이유를 알린다
- 만든 티켓은 JSON의 해당 제안에 `created_key`, `created_url`을 쓰고 Step 6의 2~3을 다시 실행해 페이지에 "생성됨"을 표시한다
- 생성한 티켓 키와 링크를 콘솔에 목록으로 알린다

## 결과 출력 형식

리뷰 단계(Step 6)의 콘솔 응답:

```
48주차 목표 후보 3개와 리마인드 N건을 리뷰 페이지에 올렸습니다. 노트에는 아직 쓰지 않았습니다.
목표: <목표 1> / <목표 2> / <목표 3>
Jira: 이미 있는 티켓 N건, 새 티켓 제안 M건
리뷰: <Artifact URL> (노트는 '반영해', 티켓은 'Jira 등록해' 또는 'J1, J3만 등록해'로 답해 주십시오)
```

상세(목표 표, 리마인드, Task 상태 제안, 지난주 스레드 막대, 정리 후보)는 페이지에만 둔다.

## 주의사항

- Weekly DB는 `#주간 Plan (Weekly Planner)` 페이지의 인라인 DB이며 속성은 `이름`(title), `생성일`(date) 둘뿐이다.
- 38·39주차 노트의 동기화 블록(Task 링크 뷰)은 API로 복제할 수 없어 틀에 넣지 않는다.
- Task DB 상태 속성 이름은 `상태`(해야할 것/대기/진행 중/완료)다. `Status`가 아니다. 제목 속성은 `Title`이다.
- `daily:start/scripts/extract-work.py`는 다른 스킬과 공유하는 스크립트다. 이 스킬에서 고치지 않고 날짜별 호출로만 쓴다.
