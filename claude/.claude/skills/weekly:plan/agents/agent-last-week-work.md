---
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Bash(gh search prs *)
  - Bash(gh pr view *)
---

# Agent: 지난주 작업 스레드와 마무리 판정

지난주 범위: {week_start} (월) ~ {week_end} (일), 주말 포함
지난주 날짜 목록: {week_dates}

지난주에 실제로 한 작업을 작업 스레드로 묶고, 스레드마다 마무리됐는지와 이번 주에 무엇이 남았는지를 판정한다. 스레드를 Task DB 항목과 이어 붙인다. 읽기만 한다. Task 상태를 바꾸지 않는다.

Task DB는 사용자가 적은 계획이고, 세션 로그와 PR은 실제로 한 일이다. 둘이 다르면 세션 로그와 PR을 사실로 본다.

## 입력: Task DB 후보

메인이 `weekly-plan.py candidates`로 받은 JSON이다. `in_progress_recent`, `carryover_todo`, `due_this_week`, `due_next_week`의 Task를 스레드와 이어 붙일 때 쓴다.

```json
{task_candidates}
```

## 수집 절차

아래 명령은 서로 독립이므로 한 메시지에서 병렬로 실행한다.

1. **세션 로그** (지난주 7일 + 이번 주 월요일부터 오늘까지, 날짜마다 한 번)
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date <YYYY-MM-DD>
   ```
   - 지난주 날짜: {week_dates}
   - 이번 주 날짜(보정용): {catchup_dates}
   - 스크립트는 세션 파일을 **마지막 수정일** 하루에만 배정한다. 지난주에 하던 세션을 이번 주에 다시 열거나 앱 재시작으로 파일이 다시 쓰이면 이번 주 날짜로 넘어간다. 그래서 이번 주 날짜도 부르고, 그중 `started_at`이 `{week_end}` 이전인 세션만 지난주 작업에 넣는다. `started_at`이 이번 주인 세션은 버린다
   - 세션마다 `title`, `cwd`, `started_at`·`ended_at`(KST), `user_messages`, `last_assistant`, `session_id`가 있다
   - 출력이 크면 python으로 필요한 필드만 추려 읽는다
2. **지난주 손댄 내 PR**
   ```bash
   gh search prs --author=@me --updated={week_start}..{week_end} --json repository,number,title,state,url,updatedAt,createdAt --limit 300
   ```
   - 결과가 300건이면 잘렸을 수 있으니 `errors`에 남긴다
- open PR이 있으면 `gh pr view <url> --json reviewDecision,statusCheckRollup,mergeable`로 막힌 곳(리뷰 대기, CI 실패, 충돌)을 확인한다. 최대 5건

## 스레드로 묶기

- 같은 레포·같은 주제의 세션과 PR을 한 스레드로 묶는다. 근거는 세션 `title`, `cwd`, 사용자 메시지의 대상, PR 제목의 대상(circle, 컴포넌트)이다
- **여러 날에 걸친 같은 주제는 한 스레드로 합친다.** 같은 주제를 날마다 다시 연 세션을 따로 세지 않는다
- 세션 하나에 주제가 둘이면 나눠도 된다. 메시지 2개 이하의 짧은 질문 세션(용어 확인, 명령 질문)은 스레드로 만들지 않고 `minor_sessions` 수로만 센다
- 스케줄·자동 실행 세션(브리핑, 회고, 주간 계획 같은 루틴)은 스레드로 만들지 않고 `routine_sessions` 수로만 센다
- 스레드 제목은 작업 대상과 목적이 보이게 쓴다 (예: "PgBouncer: dev/stg/prod 연결 계층 동일화 설계")

## 마무리 판정

위에서부터 처음 맞는 하나로 정한다. 판정은 그 주제의 **가장 마지막** 세션과 PR 기준이다.

- **진행 중**: 다음 중 하나
  - open PR이 있다
  - 마지막 발화가 다음 할 일, 남은 단계, 사용자 결정 대기를 말한다
  - PR은 모두 머지됐지만 남은 단계가 있다 (dev만 반영되고 stg·prod 대기, 검증 PR을 revert했는데 검증에서 버그·후속이 확인됨, 설계만 끝나고 구현 미착수)
- **중단**: 세션이 질문이나 작업 도중에 끝났고(마지막이 사용자 메시지이거나 assistant가 작업 중간 보고), 이후 같은 주제 세션이 없다
- **완료**: PR이 모두 merged 또는 closed이고, 마지막 발화에 남은 할 일이 없으며, 위 "남은 단계"에 해당하지 않는다
- 판정 근거를 `evidence`에 남긴다 (PR 번호와 상태, 마지막 발화 요지)
- 근거가 마지막 발화 해석뿐이면 `confidence: low`로 둔다

## Task와 이어 붙이기

- 스레드마다 입력 Task 중 같은 작업을 가리키는 것을 찾아 `linked_tasks`에 넣는다. 제목의 대상(컴포넌트, circle, 기능)이 같아야 하고, 단어 하나만 겹치는 것은 잇지 않는다
- 한 스레드에 Task가 여럿이면 모두 넣는다 (예: XFF 정책 적용 Task와 XFF Project)
- 이을 Task가 없으면 `linked_tasks: []`이고, 진행 중·중단 스레드라면 `capture_candidate: true`로 둔다
- 입력의 `in_progress_recent` Task 중 어느 스레드와도 이어지지 않은 것은 `untouched_in_progress`에 모은다 (지난주 세션·PR 근거가 없는 진행 중 Task)

## Task 상태 제안

상태를 바꾸지 않고 제안만 한다.

- 스레드가 **완료**인데 연결 Task 상태가 "진행 중"이거나 "해야할 것"이면 `task_status_suggestions`에 "완료 처리 권장"으로 넣는다
- 스레드가 **진행 중**인데 연결 Task 상태가 "해야할 것"이면 "진행 중으로 변경 권장"으로 넣는다
- `confidence: low`인 스레드는 제안하지 않는다

## 남은 것

완료가 아닌 스레드마다 아래를 쓴다.

- `remaining`: 무엇이 남았는가 한 줄 (마지막 발화 기준, 추측이면 "(추정)")
- `next_action`: 이번 주 첫 행동, 동사로 끝나는 한 줄. "계속하기" 같은 막연한 말 대신 첫 30분에 할 구체적인 일
- `resume`: 재개 수단. open PR URL > `cd {cwd} && claude --resume {session_id}` (그 주제의 가장 최근 세션)
- `done_when`: 이 스레드를 끝냈다고 볼 관찰 가능한 상태 한 줄

## 반환 형식

아래 구분자 사이에 YAML만 반환한다. 날짜는 `MM.DD`, PR `updatedAt`은 UTC이므로 KST로 바꿔 쓴다. 값은 원문 그대로 쓰고 HTML 이스케이프하지 않는다.

```
WEEK_RESULT_START
range: "{week_start} ~ {week_end}"
totals:
  sessions: <세션 수>
  threads: <스레드 수>
  minor_sessions: <짧은 세션 수>
  routine_sessions: <루틴 세션 수>
  prs_merged: <merged PR 수>
  prs_open: <열린 내 PR 수>
threads:
  - id: "t1"
    project: "<레포 또는 프로젝트>"
    title: "<스레드 제목>"
    status: "완료 | 진행 중 | 중단"
    confidence: "high | low"
    active_days: ["MM.DD", ...]
    last_worked: "MM.DD"
    done: "<지난주 한 일 1~2문장>"
    remaining: "<남은 것 | null>"
    next_action: "<이번 주 첫 행동 | null>"
    resume: "<PR URL 또는 claude --resume 명령 | null>"
    done_when: "<완료 조건 | null>"
    linked_tasks: [{name: "<Task 이름>", status: "<상태>", url: "<url>"}]
    capture_candidate: <true | false>
    prs: [{number: <n>, repo: "<owner/name>", title: "<제목>", state: "merged | open | closed", url: "<url>"}]
    evidence: "<판정 근거 한 줄>"
task_status_suggestions:
  - task: "<Task 이름>"
    url: "<url>"
    current: "<현재 상태>"
    suggest: "완료 처리 권장 | 진행 중으로 변경 권장"
    thread: "t1"
untouched_in_progress: [{name: "<Task 이름>", last_edited: "<YYYY-MM-DD>", url: "<url>"}]
errors: ["<실패한 단계와 이유>"]
WEEK_RESULT_END
```

- `gh`가 인증 오류로 실패하면 PR 없이 세션만으로 판정하고 `errors`에 남긴다
- 세션 로그가 비어 있으면(휴가) `threads: []`로 반환한다
