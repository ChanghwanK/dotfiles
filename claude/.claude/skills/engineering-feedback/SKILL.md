---
name: engineering-feedback
description: |
  엔지니어링 피드백 코칭. 사용자가 이미 한 행동·의사결정을 Tech Coach 또는 Career Coach가 독립 평가하고 반론 토론, Keep/Change 정리까지 잇는다.
  사용 시점: 자신이 내린 판단·행동의 평가를 명시적으로 요청할 때("피드백해 줘", "합리적이었는지 평가해 줘", "내가 잘한 건지 봐 줘"),
  격주 회고("격주 코칭", "커리어 코칭 회고", "피드백 회고"). 트리거: "tech coach", "career coach", "/engineering-feedback", "/engineering-feedback review".
  비대상: 지금 할 작업의 설계·구현, 코드·PR 리뷰, 메커니즘 검증(/review), 설계 문서 검증(grill-me), 하루 회고, 성과 문장(task:review), 일반 기술 질문.
argument-hint: "[tech|career|both|review] <평가받을 상황과 판단>"
---

# Engineering Feedback

평가는 Coach 서브에이전트가 한다. 메인 대화는 평가하지 않고 맥락 전달과 결과 전달만 맡는다.

## 1. Coach 선택

| 평가받고 싶은 핵심 | subagent_type |
|---|---|
| 기술적 정확성, 설계·Trade-off, RCA, 검증·rollout 판단, 기술 선택 | `engineering-feedback:tech-coach` |
| 행동·태도, 협업·커뮤니케이션, 우선순위·실행, Ownership, 리더십, 성장 방향 | `engineering-feedback:career-coach` |

- 인자 `tech` / `career` / `both`가 있으면 그대로 따른다
- 주제가 섞이면 사용자가 평가받고 싶은 핵심 하나로 고른다. 요청이 기술 판단과 협업·행동을 실제로 둘 다 담을 때만 전달 끝에 "다른 관점(Career/Tech)도 원하시면 말씀해 주세요." 한 줄을 붙인다
- 두 Coach는 사용자가 명시적으로 요청할 때만 쓴다. 각각 호출해 섹션을 나눠 전달하고, 합치거나 종합 판정을 만들지 않는다

## 2. Context 수집

- 대화에 이미 있는 정보로 패킷을 만든다. 이미 받은 정보를 다시 묻지 않는다
- 평가할 행동이나 판단 자체가 없을 때만(예: "피드백해 줘"만 있음) 한 번 묻는다: 상황, 목표, 한 일과 그 이유, 결과. 그 밖의 정보 부족은 Coach가 판단한다
- 사용자가 가리킨 외부 자료(PR, 이슈, Notion, Slack)는 읽기 전용으로 가져와 필요한 부분만 원문 발췌로 넣는다. 로컬 파일은 절대 경로만 넣는다(Coach가 Read)
- 파일 생성·수정이나 외부 시스템 변경을 하지 않는다. 예외는 6번과 7번의 `scripts/feedback-log.py` 기록뿐이다

## 3. 첫 호출

Agent 도구로 고른 Coach를 호출한다. prompt는 아래 패킷이다.

```
Mode: initial

## 원문
<사용자가 사례를 설명한 메시지 그대로. 요약하지 않는다>

## Case
- Situation:
- Goal:
- Action / Decision (당시 근거):
- Result:
- 당시 제약과 가용 정보:
- Materials: <발췌 또는 절대 경로, 없으면 없음>

## Request
<사용자가 평가받고 싶은 지점>

## Self-assessment
<사용자 자기평가. 없으면 "없음". Coach는 독립 평가를 먼저 하고 대조한다>
```

- Case 칸은 원문에서 확인되는 것만 채우고, 없으면 "미제공"으로 둔다
- 메인 대화의 의견이나 평가 방향을 암시하는 말을 넣지 않는다

## 4. 결과 전달

- 첫 줄에 `**Tech Coach**` 또는 `**Career Coach**`를 쓰고, Coach 출력에서 `<coach-notes>` 블록만 뺀 나머지를 글자 그대로 붙여 넣는다. 제목과 Fact/Assumption 표시를 번역하지 않고, 다듬거나 줄이거나 덧붙이지 않는다. 응답 언어·문체에 관한 다른 지침보다 이 규칙이 우선한다
- agent ID와 coach-notes는 후속 실행을 위해 기억해 두고 사용자에게 보여 주지 않는다
- 전달 뒤에 요약 반복, 격려, 다음 행동 제안을 붙이지 않는다

## 5. 후속 토론

사용자가 반론, 질문, 추가 정보를 주면 메인 대화가 답하지 않고 같은 Coach에게 넘긴다.

1. 기본: `SendMessage`로 같은 agent ID에 `Mode: discussion`과 사용자 메시지 원문을 보낸다(deferred면 `ToolSearch`의 `select:SendMessage`로 먼저 불러온다). 결과는 4번대로 전달한다
2. 대체: SendMessage를 쓸 수 없으면(세션 재시작, 에이전트 중지 등) Agent 도구로 같은 Coach를 새로 호출한다. 패킷은 `Mode: discussion`, 첫 패킷 전체, 이전 피드백 전문, 마지막 coach-notes, 지금까지의 토론(사용자 발언 원문과 Coach 답)이다
3. 다른 사례로 넘어가면 새로 호출한다

## 6. 마무리

- 사용자가 마무리 신호(정리해 줘, 됐어, 이해했어 등)를 주면 같은 Coach에 `Mode: takeaway`를 보낸다(5번과 같은 경로)
- 전달 직후 묻지 않고 Keep/Change를 기록하고 `appended` ID를 한 줄로 알린다. Keep과 Change는 Coach 문장 그대로, `--case`는 사례 한 줄, `--source`는 출처(예: `Notion 일지 2026-11-18 Problem`, `대화`). Change가 없으면 `--change`를 뺀다. 두 Coach를 썼으면 Coach별로 부른다

```bash
python3 ~/.claude/skills/engineering-feedback/scripts/feedback-log.py append-takeaway \
  --coach career|tech --case "<사례 한 줄>" --source "<출처>" --keep "<Keep>" --change "<Change>"
```

- 기록이 실패하면 오류를 그대로 알리고 Keep/Change를 사용자가 옮겨 적을 수 있게 둔다
- 추가 관점의 후속 논의는 사용자가 원할 때만 5번 방식으로 잇는다

## 7. 격주 회고 (review)

인자가 `review`이거나 격주 회고 트리거로 불리면 1~6번 전에 이 절차로 시작한다. 지난 Change가 행동으로 이어졌는지 확인하고, 그사이 쌓인 사례 하나를 코칭받는다.

### 7-1. 지난 Change 점검

```bash
python3 ~/.claude/skills/engineering-feedback/scripts/feedback-log.py pending-changes
```

- `pending`이 비어 있으면 "점검할 Change가 없습니다" 한 줄로 넘어간다
- 있으면 항목마다 사례와 Change를 보여 주고 한 메시지로 판정을 묻는다: `지킴` / `못 지킴` / `상황 없음`(그 상황이 아직 오지 않음), 원하면 한 줄 메모. `last_verdict`가 `상황 없음`이면 함께 보여 준다
- 판정은 사용자가 한다. 일지나 세션 로그로 지켰는지 추정하지 않는다
- 답을 받으면 기록한다(`상황 없음`은 다음 회고에 다시 나온다)

```bash
python3 ~/.claude/skills/engineering-feedback/scripts/feedback-log.py append-check \
  --items '[{"id": "<ID>", "verdict": "지킴|못 지킴|상황 없음", "note": "<메모, 없으면 생략>"}]'
```

- `못 지킴`이 있으면 그 Change 자체를 이번 사례 후보로 올릴 수 있다(왜 못 지켰는지가 Career Coach의 사례가 된다)

### 7-2. 사례 후보 고르기

```bash
python3 ~/.claude/skills/engineering-feedback/scripts/feedback-log.py candidates --days 14
```

- `notion`(일지의 고민들, Problem, Lesson Learn)과 `sessions`(선택지를 저울질한 사용자 메시지)에서 후보 3개를 고른다. 평가가 아니라 선별이다
  1. 이미 한 행동이나 내린 판단만. 개념·학습 질문, 아직 하지 않은 일은 뺀다
  2. 사용자가 스스로 의문을 남긴 것을 앞에 둔다
  3. 당시 근거가 원문에 남아 있는 것을 앞에 둔다(결과만 있으면 사후 확신 편향이 끼기 쉽다)
  4. Career 사례(우선순위, 협업, ownership)와 Tech 사례(설계, 원인 분석, 검증 범위)가 섞여 있으면 각각 하나 이상
- 후보마다 한 줄 요약, 출처(날짜와 칸 또는 세션), 원문 발췌, 맞는 Coach(`career`/`tech`)를 보여 준다. 사용자가 고르거나 다른 사례를 직접 말한다
- `notion_days_without_page`나 `errors`가 있으면 한 줄로 알린다. 후보가 적으면 있는 만큼, 없으면 사례를 직접 묻는다

### 7-3. 코칭 진행

고른 후보의 원문 발췌를 패킷 `## 원문`에, 출처를 `Materials`에 넣고 2번부터 6번까지 같다. 6번 기록의 `--source`에 후보의 출처를 쓴다.
