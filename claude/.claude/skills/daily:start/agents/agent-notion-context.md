---
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:retrospective/scripts/notion-daily.py read *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py search-tasks*)
  - mcp__claude_ai_Google_Calendar__list_events
  - mcp__claude_ai_Atlassian_MCP__searchJiraIssuesUsingJql
  - Read
---

# Agent: 어제 회고 · 오늘 일지 · Task · Jira · 일정 수집

오늘 날짜: {today_date}

읽기만 한다. Notion 페이지를 만들거나 고치지 않는다.

## 수집 절차

아래 1~5는 서로 독립이므로 병렬로 실행한다. 어제 실제로 한 작업(세션 로그, PR)은 어제 작업 에이전트가 맡으므로 여기서는 보지 않는다.

1. **어제 일지 (회고 결과)**
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:retrospective/scripts/notion-daily.py read --date yesterday
   ```
   - 출력에 `error`가 있으면(주말·휴일) 하루씩 거슬러 `--date YYYY-MM-DD`로 최대 3번 더 읽는다. 찾은 날짜를 `retro_date`로 남긴다
   - `body.retro.Try`, `body.tomorrow_items`, `body.coach_tomorrow_items`, `body.todos`(체크 여부와 상관없이 전체를 받아 아래 `unchecked` 규칙으로 계층을 복원한 뒤 거른다), `body.worries`를 쓴다
   - `body.retro.Try`, `body.tomorrow_items`, `body.coach_tomorrow_items`는 `{text, detail}` 목록이다. `detail`은 하위 항목(체크박스, 메모)을 들여쓰기로 이은 문자열이다. `tomorrow_items`·`coach_tomorrow_items`의 체크된 하위 항목은 줄 앞에 `[x] `가 붙는다(Try `detail`에는 붙지 않는다). `body.tomorrow`, `body.coach_tomorrow`(제목만 담은 문자열 목록)는 하위 항목이 없으므로 쓰지 않는다
   - 그 전날 일지도 한 번 읽어(`retro_date` 하루 전, 없으면 생략) 미체크 할 일이 이틀 연속인지 판정한다
2. **오늘 일지**
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:retrospective/scripts/notion-daily.py read --date today
   ```
   - `page_id`와 `body.todos`(이미 적힌 할 일)를 쓴다. `body.missing_sections`에 `Todos`가 있으면 `today_todos_section: false`
   - `error`가 있으면(페이지 없음) 페이지를 만들지 않고 `today_page_id: null`로 반환한다
3. **활성 Task**
   ```bash
   python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py search-tasks --status active
   ```
4. **오늘 일정**
   - `mcp__claude_ai_Google_Calendar__list_events`로 `calendarId="primary"`, 오늘 00:00~23:59(`Asia/Seoul`)를 조회한다
   - 제목이 "Busy", "Todo List Up", "daily sync up(오후)"인 일정은 뺀다
5. **Jira PLE 프로젝트** (주제를 묶을 상위 항목)
   - `mcp__claude_ai_Atlassian_MCP__searchJiraIssuesUsingJql`, `cloudId="bde901ec-3020-4c95-b17b-a30a9a176fb9"`
   - `jql = "project = PLE AND statusCategory != Done AND (issuetype = Epic OR assignee = currentUser()) ORDER BY updated DESC"`
   - `fields = ["summary", "status", "issuetype", "parent", "assignee"]`, `maxResults = 100`
   - 응답에 `nextPageToken`이 있거나 `isLast`가 false면 그 토큰으로 이어서 읽는다(최대 5페이지). 5페이지를 넘으면 읽은 범위까지만 쓰고 `projects_partial: true`, `errors`에 "Jira 프로젝트 조회 5페이지 상한"
   - 도구가 없거나 실패하면 `errors`에 남기고 `projects`는 Task DB 항목만 쓴다(`projects_partial: true`)

## 가공 규칙

- **continue_items (어제 이어서)**: 아래를 모아 뜻이 같은 것은 하나로 합친다. 각 항목에 `source`를 남긴다
  - `try`: 어제 Try (회고에서 정한 행동)
  - `tomorrow`: 어제 Tomorrow (사용자가 쓴 내일 할 일)
  - `coach`: 어제 회고 코치 추천
  - `unchecked`: 어제 미체크 할 일. 일지는 프로젝트 > 주제 > 하위 할 일 세 단계일 수 있다. 아래 순서를 지킨다(체크 필터를 먼저 걸면 프로젝트 이름과 부모 경로를 잃는다)
    1. 계층 복원: `body.todos`는 위에서부터 깊이 우선 순서의 평탄 목록이다(`text`, `checked`, `depth`). 체크 여부와 상관없이 전체를 순서대로 읽어, 각 항목의 부모를 "바로 앞에 나온 depth가 하나 작은 항목"으로 정해 트리를 만든다
    2. 맨 위 항목 분류: 맨 위 항목의 하위에 depth 2 항목이 하나라도 있으면 그 맨 위 항목은 프로젝트다. 그 밖의 맨 위 항목(프로젝트 없는 주제, 예전 두 단계 일지)은 주제다
    3. 거르기: 이어가기 항목은 주제 단위로 만든다. 프로젝트 아래 주제는 그 주제가 미체크면 항목으로 만든다(프로젝트가 체크돼 있어도 같다). 프로젝트 자체는 항목으로 만들지 않고 글을 `project`에 적는다. 프로젝트 없는 주제는 미체크면 항목으로 만들고 `project`는 null
    4. `detail`: 주제의 하위 항목을 들여쓰기로 이어 넣는다. 체크된 하위 항목도 지우지 않고 줄 앞에 `[x] `를 붙여 남긴다(남은 범위를 판정하는 근거다)
  - `worry_next`: 고민 detail에 "다음", "다음 행동"이 적힌 것
  - `try`·`coach` 항목의 `detail`에는 원본 `detail`을 줄여 옮긴다. `tomorrow` 항목은 보드가 하위 항목을 체크리스트로 그리므로 원본 `detail`을 줄바꿈·들여쓰기·`[x] ` 표시까지 그대로 옮기고, 뜻이 같은 다른 출처 항목과 합치지 않는다. 하위 항목이 있으면 그것이 그 항목의 실제 범위다(예: "인증서 관리" 아래 "만료 처리 및 로테이션 어떻게?"). 이미 체크된 하위 항목은 "(완료)"를 붙여 남긴다
  - 오늘 일지 Todos에 이미 있는 항목(뜻이 같으면)은 `already_in_today: true`로 표시한다
  - 이틀 연속 미체크면 `carry_days: 2` (그 이상 알 수 있으면 그 수)
- **tasks_due**: 활성 Task 중 아래만 넣는다. 지난 일수를 `overdue_days`로
  - `due_date`가 오늘인 것 전부
  - `due_date`가 오늘 이전이고 7일 이내로 지난 것 전부
  - 그보다 오래 지난 것은 넣지 않고 `overdue_old_count`로 수만 센다 (오래 지난 마감은 오늘의 신호가 아니다)
- **tasks_in_progress**: 상태가 "진행 중"인 Task (due 무관), 최근 due 순 최대 10건
- **projects** (주제를 묶을 상위 항목 후보): 아래를 모은다. 메인이 어제 작업 스레드와 주제를 이 목록에 연결한다
  - Jira: 5번 결과 전부. Epic은 `type: epic`, 그 밖은 `type: issue`이고 `parent`가 Epic이면 `parent_key`에 적는다
  - Task DB: 상태가 "진행 중"인 Task 전부(due 유무와 상관없이, `tasks_in_progress`의 10건 제한을 받지 않음). `#Project`, `#Task` 같은 접두어는 `title`에서 뺀다. `type: task`. `search-tasks`는 페이지를 끝까지 읽는다. 출력의 `truncated`가 true면(1,000건 상한에서 멈춤) `projects_partial: true`
  - Jira와 Task DB가 같은 일이면(예: Epic "Python 백엔드 pgbouncer 도입"과 Task "pgbouncer 도입") 둘 다 남기고 Task 쪽 `same_as`에 Jira 키를 적는다
- `search-tasks` 출력의 `truncated`가 true면 `errors`에 "Task 조회 상한(1,000건)에서 멈춤"을 남긴다. 건수(예: 정확히 100건)로 잘림을 추정하지 않는다

## 반환 형식

```
NOTION_RESULT_START
retro_date: "<YYYY-MM-DD | null>"
today_page_id: "<id | null>"
today_todos_section: <true | false>
today_todos: ["<이미 적힌 오늘 할 일>", ...]
continue_items:
  - text: "<할 일>"
    source: "try | tomorrow | coach | unchecked | worry_next"
    detail: "<하위 항목이나 메모 한 줄 | null>"
    project: "<어제 일지에서 이 주제가 들어 있던 프로젝트 글 | null>"
    carry_days: <n | null>
    already_in_today: <true | false>
tasks_due:
  - name: "<Task명>"
    status: "<상태>"
    due: "<YYYY-MM-DD>"
    overdue_days: <0이면 오늘 마감>
    category: "WORK | MY"
    page_id: "<id>"
overdue_old_count: <7일 넘게 지난 활성 Task 수>
tasks_in_progress:
  - name: "<Task명>"
    due: "<YYYY-MM-DD | 없음>"
    category: "WORK | MY"
projects_partial: <Jira 또는 Task DB 조회가 잘렸으면 true>
projects:
  - source: "jira | notion"
    key: "<PLE-12 | Notion page_id>"
    type: "epic | issue | task"
    title: "<요약 또는 Task명(접두어 제외)>"
    status: "<상태>"
    parent_key: "<상위 Epic 키 | null>"
    mine: <내게 할당됐으면 true>
    same_as: "<같은 일인 Jira 키 | null>"
    url: "<Jira URL | null>"
calendar_events:
  - title: "<제목>"
    start: "HH:MM"
    end: "HH:MM"
errors: ["<실패한 단계와 이유>"]
NOTION_RESULT_END
```

- `NOTION_TOKEN` 오류로 Notion 단계가 실패하면 `errors`에 적고 나머지 필드는 빈 값으로 둔다
