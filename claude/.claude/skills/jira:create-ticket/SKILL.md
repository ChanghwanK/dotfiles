---
name: jira:create-ticket
description: |
  요청(Slack 스레드, 대화, 붙여 넣은 글)을 읽고 현재 설정과 측정으로 근거를 확인한 뒤 Background·문제 정의·원인·Goal·Key Result 초안을 만들어, 사용자 확인 후 Jira(PLE) 백로그 티켓으로 등록하는 스킬. 사용 시점: (1) 다른 팀의 요청·문의를 백로그로 옮길 때, (2) 대화로 정리한 개선 과제를 Jira 티켓으로 남길 때, (3) 요청자의 제안을 측정으로 검증해 목표를 다시 잡을 때. 트리거 키워드: "jira 등록", "백로그에 등록", "jira 티켓 만들어", "티켓으로 만들어", "jira:create-ticket", "/jira:create-ticket".
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - AskUserQuestion
  - mcp__claude_ai_Slack__slack_read_thread
  - mcp__claude_ai_Atlassian_MCP__searchJiraIssuesUsingJql
  - mcp__claude_ai_Atlassian_MCP__createJiraIssue
  - mcp__claude_ai_Atlassian_MCP__getJiraIssue
  - mcp__claude_ai_Atlassian_MCP__editJiraIssue
  - mcp__claude_ai_Atlassian_MCP__atlassianUserInfo
---
# jira:create-ticket

요청을 측정으로 검증해 문제 정의와 목표를 다시 세우고, 사용자 확인을 거쳐 Jira 백로그 티켓 하나로 등록한다.

티켓 형식(유형, 섹션, 필드 관례)의 정본은 `~/.claude/docs/jira-ticket-template.md`, Goal·Key Result·Todo 문체의 정본은 `task:keyresult` 스킬이다. 이 스킬은 두 정본을 채우는 절차만 정한다.

---

## 핵심 원칙

- **요청자의 수단이 아니라 목표를 티켓으로 만든다.** 요청은 대개 수단("메모리를 줄이자")으로 온다. Goal은 그 수단이 노리는 상태("job이 쓰는 만큼만 자원을 점유한다")로 쓰고, 제안한 수단은 원인·설계 검토 대상으로 내린다.
- **요청자의 측정은 다시 잰다.** 같은 기간·대상으로 독립 측정해 일치하는지 본다. 일치하면 그렇다고 쓰고, 다르면 차이와 이유를 쓴다.
- **문제 정의와 원인을 섞지 않는다.** 판별은 정본 템플릿의 "쓰기 전 점검"을 따른다.
- **재지 못한 것은 재지 않았다고 쓴다.** 금액, 효과 추정처럼 측정하지 않은 값은 `(미측정)`, `(추정)`을 붙이고 Todo에 측정 항목을 둔다.
- **등록 전에 초안을 보인다.** 승인 없이 createJiraIssue를 부르지 않는다.
- Slack 스레드에 답장하지 않는다. 요청자에게 알리는 일은 사용자가 한다.

---

## 워크플로우

### Step 1: 정본과 요청 읽기

1. `~/.claude/docs/jira-ticket-template.md`를 Read한다. `task:keyresult`의 기준을 함께 적용한다.
2. 요청 원문을 읽는다.
   - Slack URL `https://<ws>.slack.com/archives/<CHANNEL>/p<16자리>`: `channel_id=<CHANNEL>`, `message_ts`는 16자리 앞 10자리 + `.` + 뒤 6자리 (예: `p1795416468641819` → `1795416468.641819`). `slack_read_thread`로 부모와 답글을 모두 읽고, 첨부 파일·캔버스가 있으면 함께 읽는다.
   - 대화·붙여 넣은 글이면 그 내용을 원문으로 쓴다.
3. 요청을 세 칸으로 나눠 메모한다(출력하지 않는다): 요청자의 관측·측정, 요청자의 제안(수단), 실제로 묻는 것.

### Step 2: 현재 상태와 근거 확인

1. **현재 설정을 직접 읽는다.** 요청이 가리키는 리포 파일·리소스를 열어 값을 확인한다. 요청 글에 적힌 값을 그대로 옮기지 않는다.
2. **요청자의 측정을 재현한다.** 같은 지표·기간·대상으로 잰다. 쿼리가 메모리 한도로 실패하면 시간창·step·시리즈 범위를 줄여 다시 잰다.
3. **요청자가 재지 않은 층을 잰다.** 제안의 효과를 가르는 값이다. 예: 컨테이너 요청을 줄이자는 제안이면 노드 단 용량·요청 비율(노드 수를 실제로 정하는 차원)까지 본다.
4. **안 바뀔 것의 기준선을 잰다.** 변경으로 나빠지면 안 되는 지표(실패율, 지연, 성공률)의 현재 값. Key Result의 "유지" 항목이 이 값을 쓴다.
5. 모든 측정에 출처, 대상 범위, 시간창을 붙여 둔다. 다시 돌릴 수 있게 쿼리 원문을 보관한다.
6. 측정에 쓸 도구는 세션에 붙은 MCP·CLI에서 고른다(메트릭, 로그, kubectl, 비용 조회). 도구가 없으면 그 항목을 `(미측정)`으로 두고 Todo로 넘긴다.

### Step 3: 제안 검토

요청자의 제안을 그대로 적용할 때의 위험과 전제를 적는다. 각 항목은 측정값이나 공식 문서·코드에 기대고, 모델 지식이면 그렇게 표시한다.

- 제안이 문제를 실제로 줄이는가(예: 줄이려는 차원이 비용을 정하는 차원인가)
- 제안이 깨뜨릴 수 있는 것(성능 저하, 실패 증가, 운영 표준 위반)
- 제안이 전제한 동작이 실제로 가능한가(플랫폼 제약, 버전 지원)

### Step 4: 중복 확인

```
searchJiraIssuesUsingJql(
  cloudId="bde901ec-3020-4c95-b17b-a30a9a176fb9",
  jql='project in (PLE, PTR) AND text ~ "<핵심 키워드>" ORDER BY created DESC')
```

같은 주제의 티켓이 있으면 새로 만들지 않고 사용자에게 알린다(기존 티켓 갱신은 정본의 "기존 티켓을 다시 쓸 때"를 따른다).

### Step 5: 초안 작성과 확인

정본 템플릿의 섹션 순서로 초안을 채팅에 보인다. 근거 수치가 두 축 이상이면 표로 둔다.

초안을 보인 뒤 AskUserQuestion으로 묻는다: "이대로 등록 / 수정 후 등록". 수정 요청이 오면 반영한 초안을 다시 보이고 같은 질문을 반복한다. 사용자가 프로젝트(PLE·PTR), 담당자를 따로 말하지 않았으면 정본의 필드 관례를 쓴다.

### Step 6: 등록

```
createJiraIssue(
  cloudId="bde901ec-3020-4c95-b17b-a30a9a176fb9",
  projectKey="PLE", issueType="Task",
  summary=..., description=<승인된 초안 markdown>,
  priority=..., labels=[...])
```

- 담당자를 본인으로 정했으면 `atlassianUserInfo`로 accountId를 얻는다. 지정이 없으면 비운다.
- 등록 뒤 고칠 일이 생기면 `editJiraIssue`로 description 전체를 다시 보낸다(부분 수정이 안 되므로 기존 사실을 빠뜨리지 않는다).

### Step 7: 검증

1. createJiraIssue 응답의 description을 읽어 표·체크박스·코드가 깨지지 않았는지 확인한다. `<`가 `&lt;`로 남는 등 깨진 곳이 있으면 editJiraIssue로 고친다.
2. 정본의 "쓰기 전 점검"을 등록본에 한 번 더 적용한다.
3. 결과를 보고한다.

---

## 결과 보고 형식

```
[PLE-NN](https://riiid-pioneer.atlassian.net/browse/PLE-NN)로 등록했습니다.

- 문제 정의: <한 줄, 핵심 측정값>
- Goal: <한 줄>
- Key Result: <지표 → 목표값 나열>
- 요청자 제안과 다르게 잡은 점: <있을 때만, 이유 한 줄>
- 미측정으로 남긴 것: <있을 때만>
```

---

## 주의사항

- 요청자 실명은 Background의 출처 표기에만 쓴다. 판단·평가 문장의 주어로 쓰지 않는다.
- 링크에는 팀원이 열 수 있는 것만 넣는다(정본 템플릿의 링크 규칙).
- 이 스킬은 티켓 하나를 만든다. 여러 티켓으로 나눌 일이면 나눔 안을 제안만 하고, Epic 생성 여부는 사용자가 정한다.
