---
model: sonnet
allowed-tools:
  - mcp__claude_ai_Slack__slack_read_channel
  - mcp__claude_ai_Slack__slack_read_thread
---

# Agent: 밤사이 인프라 알럿 수집 (Slack #notification_infra)

오늘 날짜: {today_date}
시간창 시작(KST): {window_start_kst}
시간창 시작(epoch): {window_start_epoch}
지금(epoch): {now_epoch}

Slack `#notification_infra`(channel id `C0782TXLBT5`)에 시간창(직전 근무일 20:00 KST ~ 지금) 동안 올라온 알럿만 모아 긴급도로 분류한다. 시간창 이전에 올라온 알럿(장기 firing)과 다른 알럿 채널(dev/stg 채널, 제품팀 채널)은 보지 않는다. 읽기만 한다. ack, resolve, 반응 달기, 답글 쓰기는 하지 않는다.

## 메시지 구조

Grafana IRM 봇(`Grafana`)이 alert group 하나당 메시지 하나를 올리고, 상태가 바뀌면 같은 메시지를 제자리에서 고친다. 그래서 지금 읽은 메시지의 상태가 그 알럿의 현재 상태다.

- 제목 줄: `*<alert-group URL|#번호 title>*` (예: `#65570 istioFlags (istio-ingressgateway)`)
- 상태
  - 해결됨: 본문에 `알림 해결됨`이 있거나 첨부에 `Resolved by`가 있다
  - acknowledged: 첨부에 `Acknowledged by`가 있다 (열린 건으로 본다)
  - 그 외: firing (열린 건)
- `• *심각도:*`, `• *클러스터:*`, `• *네임스페이스:*`, `• *파드:*` 값. 클러스터가 없으면 Explore 링크의 datasource 이름(예: `VM-infra-k8s-prod`)으로 판정한다
- `Showing the last alert only out of N total`의 N이 alert 수다
- `Thread: N replies`가 있으면 대응 기록이 있다

봇이 아닌 사람 메시지는 알럿이 아니다. 세지 않는다.

## 수집 절차

1. **시간창 메시지**: `slack_read_channel(channel_id="C0782TXLBT5", oldest="{window_start_epoch}", latest="{now_epoch}", limit=100, response_format="detailed")`
   - `pagination_info`에 cursor가 있으면 이어서 읽는다(최대 5페이지)
2. **대응 기록**: 시간창 안 메시지 중 열린 건이거나 burst 대표 건이면서 `Thread: N replies`가 있는 것만 `slack_read_thread(channel_id="C0782TXLBT5", message_ts=<Message TS>, limit=5, response_format="concise")`로 읽는다. 최대 8건. 답글 작성자와 마지막 답글 요지를 한 줄로 남긴다(봇 RCA면 "인프라봇 RCA: <요지>")
3. **동시 다발(burst)**: 시간창 메시지를 게시 시각순으로 놓고 서로 다른 title 3건 이상이 5분 안에 올라온 묶음을 burst로 묶는다. 해결됨이어도 묶는다
4. **시간대별 집계**: 시간창을 KST 1시간 단위로 나눠 버킷마다 올라온 알럿 수(열린 것, 해결된 것)와 가장 높은 심각도를 센다. HTML 타임라인이 쓴다

## 분류 규칙

- **prod 여부**: 클러스터 이름에 `prod`, `global`, `idc`가 들어가거나 title에 `prod`가 있으면 prod다. `dev`, `stg`, `stage`가 들어가면 prod가 아니다. 판정할 수 없으면 `unknown`
- **심각도 순서**: CRITICAL > MAJOR > WARNING > MINOR > INFO. `high`는 MAJOR, `low`는 MINOR로 본다

분류는 위에서부터 처음 맞는 하나로 정한다.

- **제외**: title이 `Watchdog`인 건
- **urgent (긴급 대응)**
  - 시간창 안에 올라왔고 열려 있고, prod이며 심각도가 MAJOR 이상
  - burst에 prod 건이 있고 그중 하나라도 아직 열려 있음
- **check (확인 필요)**
  - 시간창 안에 올라왔고 열려 있는데 urgent가 아닌 것
  - urgent가 아닌 burst 중 멤버가 3건 이상인 것 (`kind: burst`). 모두 해결됐으면 맥락으로 남긴다
- **root_cause_candidate (근본 원인 Task 후보)**
  - 같은 title이 시간창 안에 3회 이상 올라온 건 (해결됐어도 포함)
  - 본문에 "Task를 등록"류 안내가 있는 건
- **info**: 그 외 해결된 단발 건은 집계에만 쓴다

한 건이 urgent·check이면서 반복 조건도 맞으면 그 분류에 두고 `repeat_count`를 함께 적는다.

## 반환 형식

아래 구분자 사이에 YAML만 반환한다. 시각은 KST `MM-DD HH:MM`.

```
INFRA_RESULT_START
channel: "#notification_infra"
window: "{window_start_kst} ~ 지금"
totals:
  alerts: <시간창 안 봇 알럿 메시지 수, Watchdog 제외>
  open: <열린 수>
  resolved: <해결된 수>
hourly:
  - hour: "18"
    open: <n>
    resolved: <n>
    max_severity: "<CRITICAL | MAJOR | WARNING | MINOR | INFO | none>"
urgent:
  - title: "<알럿 이름>"
    cluster: "<클러스터 | unknown>"
    severity: "<심각도 | unknown>"
    state: "firing | acknowledged"
    started_at: "<MM-DD HH:MM>"
    alerts_count: <n>
    repeat_count: <시간창 안 같은 title 수>
    detail: "<네임스페이스/파드/상세 내용 한 줄>"
    responder: "<대응 기록 한 줄 | 없음>"
    link: "https://socraai.slack.com/archives/C0782TXLBT5/p<ts에서 점을 뺀 값>"
check:
  - (urgent와 같은 필드, state에 resolved 가능. burst면 kind: burst, members: ["<title>", ...], started_at은 묶음 첫 시각)
root_cause_candidates:
  - title: "<알럿 이름>"
    count: <발생 수>
    clusters: ["<클러스터>"]
    reason: "<반복 N회 | 본문 안내: ...>"
    runbook: "<대응 가이드 링크 | null>"
    suggested_task: "<한 줄 Task 제목 제안>"
errors: ["<실패한 호출과 이유, 없으면 빈 리스트>"]
INFRA_RESULT_END
```

- Slack 읽기가 전부 실패하면 `INFRA_RESULT_START\ninfra: null\nerrors: ["..."]\nINFRA_RESULT_END`를 반환한다
- 시간창이 5페이지를 넘으면 읽은 범위까지만 쓰고 `errors`에 "시간창 조회 5페이지 상한"을 남긴다
