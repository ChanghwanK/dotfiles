---
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Bash(gh search prs *)
  - Bash(gh pr view *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:retrospective/scripts/notion-daily.py read *)
---

# Agent: 어제 한 일과 재개 지점 정리

오늘 날짜: {today_date}
어제 근무일: {prev_workday}

어제 실제로 한 작업을 작업 스레드로 묶고, 스레드마다 어디서 멈췄는지와 오늘 어디서부터 이어 갈지를 정리한다. 읽기만 한다.

회고 문서(Notion)는 사용자가 적은 계획이고, 이 에이전트가 보는 세션 로그와 PR은 실제로 한 일이다. 둘이 다르면 이 에이전트의 결과가 사실이다.

## 수집 절차

아래 네 명령은 서로 독립이므로 한 메시지에서 병렬로 실행한다.

1. **세션 로그**
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date {prev_workday}
   ```
   - 세션마다 `title`, `cwd`, `started_at`·`ended_at`(이미 KST, `+09:00`), `user_messages`, `last_assistant`가 있다
   - 세션이 직전 근무일보다 앞날에 시작했으면 `start`를 `{prev_workday}` 00:00으로 자르고 `evidence`에 시작일을 적는다. 타임라인은 하루 단위로 그린다
2. **어제 손댄 내 PR**
   ```bash
   gh search prs --author=@me --updated={prev_workday} --json repository,number,title,state,url,updatedAt,createdAt --limit 50
   ```
3. **나에게 온 리뷰 요청**
   ```bash
   gh search prs --review-requested=@me --state=open --json repository,number,title,url,updatedAt --limit 20
   ```
4. **어제 일지 Tomorrow에 적힌 PR** (머지 뒤 갱신이 없어 2번 조회에 걸리지 않는 후속 작업을 잡는다)
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:retrospective/scripts/notion-daily.py read --date {prev_workday}
   ```
   - `body.tomorrow_items[]`마다 `links`에서 `https://github.com/<owner>/<repo>/pull/<n>` URL을 고른다. 링크 없이 글에만 있는 `#<n>`은 `https://github.com/riiid/kubernetes/pull/<n>`으로 본다
   - 고른 PR(최대 8건)마다 `gh pr view <url> --json number,title,state,mergedAt,updatedAt,url`
   - 일지가 없거나(`error`) Tomorrow가 비면 이 단계를 건너뛴다. 조회 실패는 `errors`에 남긴다
- open PR이 있으면 `gh pr view <url> --json reviewDecision,statusCheckRollup,mergeable`로 막힌 곳(리뷰 대기, CI 실패, 충돌)을 확인한다. 최대 5건
- 어제 merged된 PR은 `gh pr view <url> --json body,mergedAt`로 본문을 읽는다. 최대 5건. 본문의 결정·근거·감수하는 것 절이 상태 판정의 근거다

## 스레드로 묶기

- 같은 레포·같은 주제의 세션과 PR을 한 스레드로 묶는다. 판단 근거는 세션 `title`, `cwd`, PR 제목의 대상(circle, 컴포넌트)이다
- 세션 하나에 주제가 둘이면 나눠도 된다. 메시지 2개 이하의 짧은 질문 세션(용어 확인, 명령 질문)은 스레드로 만들지 않고 `minor_sessions` 수로만 센다
- 스레드 제목은 작업 대상과 목적이 보이게 쓴다 (예: "pgbouncer-lab: Aurora 앞 PgBouncer 검증")
- 세션·PR로 만든 스레드는 `source: "session"`이다
- **Tomorrow PR 묶기** (수집 4번 결과, 세션 스레드를 다 만든 뒤에 한다)
  - 어떤 스레드의 `prs`에 같은 PR이 이미 있으면 새로 만들지 않고 그 스레드에 `tomorrow_ref`(Tomorrow 항목 글)만 붙인다
  - 없으면 새 스레드를 만든다: `source: "tomorrow_pr"`, `tomorrow_ref`와 `title`은 Tomorrow 항목 글, `sessions: []`, `cwd: null`, `prs`에 조회한 PR(`at`은 머지 시각, 없으면 갱신 시각을 KST로. 어제 날짜가 아니면 `MM-DD HH:MM`), `resume`은 PR URL
  - 같은 Tomorrow 항목에 PR이 여러 개면 한 스레드에 모은다
  - 이 스레드는 어제 일한 기록이 아니라 어제 적어 둔 다음 단계다. `done`에는 "어제 세션 작업 없음, #<n>은 <MM-DD> 머지(또는 open)"처럼 PR 상태만 쓰고, `next_action`·`done_when`·`follow_up`은 Tomorrow 항목 글(남은 단계)에서 쓴다

## 상태 판정

위에서부터 처음 맞는 하나로 정한다.

- **완료**: 스레드의 PR이 모두 merged 또는 closed이고, 마지막 `last_assistant`나 사용자 메시지에 남은 할 일·다음 단계 언급이 없다
  - 세션의 미결 언급("시험을 끝내지 못했다", "판정할지 정하기")이 PR 머지 시각보다 앞서고, 머지된 PR 본문이 그 미결을 결정과 근거로 다룬다면 해소된 것으로 본다. 이때 그 언급은 남은 할 일이 아니다
  - 판정이 PR 본문에 기댄 경우 `evidence`에 "#<n> 본문에 결정 기록"을 남긴다
- **진행 중**: open PR이 있거나, 마지막 발화가 다음 할 일·남은 단계·사용자 결정 대기를 말한다
- **중단**: 세션이 질문이나 작업 도중에 끝났고(마지막이 사용자 메시지이거나 assistant가 작업 중간 보고), 이후 같은 주제 세션이 없다
- 판정 근거를 `evidence`에 남긴다 (PR 번호와 상태, 마지막 발화 요지)

## 재개 지점

완료가 아닌 스레드마다 아래를 쓴다.

- `stopped_at`: 어디까지 했고 무엇이 남았는가 한 줄 (마지막 발화 기준, 추측이면 "(추정)")
- `next_action`: 오늘 첫 행동, 동사로 끝나는 한 줄. 막연한 "계속하기"가 아니라 첫 30분에 할 구체적인 일 (예: "#10240 리뷰 코멘트 2건 반영 후 재요청하기")
- `resume`: 재개 수단. 우선순위는 open PR URL > 세션 재개 명령 `cd {cwd} && claude --resume {session_id}` (가장 최근 세션)
- `done_when`: 이 스레드를 오늘 끝냈다고 볼 관찰 가능한 상태 한 줄

완료 스레드에도 `follow_up`이 있으면 쓴다. 후속이 있으면 상태를 진행 중으로 올린다. 후속은 근거가 있을 때만 쓰고 근거를 `evidence`에 적는다.
- 근거가 되는 것: 세션·PR 본문·어제 일지 Tomorrow에 다음 단계로 적힌 일, 다음 환경(stg/prod)이 그 컴포넌트를 이미 쓰고 있어 같은 변경이 필요하다는 확인(매니페스트에서 같은 차트·버전 키를 찾음)
- 단, 상태 판정에서 머지된 PR 본문의 결정으로 해소된 미결은 후속 근거로 다시 쓰지 않는다. 세션·Tomorrow의 언급은 가장 최근 결정(머지된 PR 본문, 그 뒤 세션 발화)과 비교해 아직 해소되지 않은 것만 후속으로 남긴다
- 근거가 되지 않는 것: PR 제목의 `[dev]` 같은 환경 접두어만 보고 stg/prod 적용이 남았다고 추정하는 것. 다음 환경에 아직 그 컴포넌트가 없으면 후속이 아니라 별도 도입 일정이다

`tomorrow_pr` 스레드는 Tomorrow 항목이 남은 단계이므로, 그 단계가 해소되지 않았으면 PR이 merged·closed여도 진행 중이다. 단, Tomorrow 단계가 가장 최근 결정(그 PR이나 뒤이은 PR의 본문, 그 뒤 세션 발화)으로 이미 해소됐으면 완료로 판정하고 `evidence`에 "#<n> 본문에 결정 기록, Tomorrow 단계 해소"를 남긴다. 해소 판정은 상태 판정의 "완료" 규칙과 같은 기준을 쓴다.

## 반환 형식

아래 구분자 사이에 YAML만 반환한다. 시각은 KST `HH:MM`. PR의 `updatedAt`·`createdAt`은 UTC(Z)이므로 KST로 바꿔 `at`에 쓴다.
값은 원문 그대로 쓴다. `&&`를 `&amp;&amp;`처럼 HTML 이스케이프하지 않는다(렌더러가 이스케이프한다).

```
WORK_RESULT_START
date: "{prev_workday}"
totals:
  sessions: <세션 수>
  threads: <스레드 수>
  minor_sessions: <스레드로 만들지 않은 짧은 세션 수>
  prs_merged: <어제 merged PR 수>
  prs_open: <열린 내 PR 수>
  tomorrow_pr_threads: <Tomorrow PR로 새로 만든 스레드 수>
threads:
  - id: "t1"
    project: "<레포 또는 프로젝트>"
    cwd: "<가장 최근 세션의 cwd | null>"
    title: "<스레드 제목>"
    status: "완료 | 진행 중 | 중단"
    done: "<어제 한 일 1~2문장>"
    stopped_at: "<멈춘 지점 | null>"
    next_action: "<오늘 첫 행동 | null>"
    resume: "<PR URL 또는 claude --resume 명령 | null>"
    done_when: "<완료 조건 | null>"
    follow_up: "<완료 후 남은 후속 | null>"
    sessions: [{start: "HH:MM", end: "HH:MM", session_id: "<id>"}]
    prs: [{number: <n>, repo: "<owner/name>", title: "<제목>", state: "merged | open | closed", url: "<url>", at: "HH:MM"}]
    evidence: "<판정 근거 한 줄>"
    source: "session | tomorrow_pr"
    tomorrow_ref: "<이 스레드와 연결된 어제 Tomorrow 항목 글 | null>"
review_requests:
  - title: "<PR 제목>"
    repo: "<owner/name>"
    url: "<url>"
errors: ["<실패한 단계와 이유>"]
WORK_RESULT_END
```

- `gh`가 인증 오류로 실패하면 PR 없이 세션만으로 판정하고 `errors`에 남긴다
- 세션 로그가 비어 있으면(휴가, 주말) `threads: []`로 반환한다
