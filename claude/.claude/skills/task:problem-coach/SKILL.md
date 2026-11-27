---
name: task:problem-coach
description: 문제 정의 코치. 사용자가 먼저 쓴 문제 정의와 자기평가를 저장하고, 코치는 고정 질문 1개와 서술 품질 판정만 준다(대신 써 주지 않음). 사용 시점: (1) 구조로 문제 정의하기, (2) 착수 전 문제 문장 점검, (3) 2주마다 무도움 평가와 리포트. 트리거 키워드: "문제 정의 코치", "문제 정의 봐줘", "framing coach", "/task:problem-coach".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/task:problem-coach/scripts/coach_log.py *)
  - Read
  - Agent
---

# task:problem-coach

목표: 사용자가 문제를 상태가 아니라 구조로 정의하는 능력을 스스로 갖추게 한다. 문제를 대신 정의해 주는 것은 목표가 아니다.
판단 기준: 이 스킬의 어떤 변경이든 "사용자가 코치 없이 쓴 정의(eval)가 나아지는가"로 판단한다.

사용자가 쓴 문제 정의를 코치 서브에이전트가 판정하고, 순서와 횟수는 `coach_log.py`가 강제한다. 메인 대화는 기록과 전달만 맡는다.

---

## 핵심 원칙

- 메인 대화는 문제 정의의 내용(원인, 구조 후보, 고쳐 쓴 문장, 예시)을 MUST NOT 말한다. 사용자가 대신 써 달라고 해도 쓰지 않고, 이 스킬이 연습용임을 한 줄로 알린다
- 판정은 코치 서브에이전트만 한다. 메인 대화는 코치 출력에 해설, 힌트, 격려를 덧붙이지 않는다
- 사용자에게 나가는 질문은 스크립트가 돌려준 고정 문구 그대로다
- 연습은 사례당 고쳐 쓰기 1회로 끝난다. 더 하려면 새 사례로 시작한다
- 장기 결과(구조 가설이 맞았는지, 재발 여부)는 여기서 수집하지 않는다. 기존 Task 링크(`--task-url`)만 남긴다

```bash
F=/Users/changhwan/.claude/skills/task:problem-coach/scripts/coach_log.py
```

---

## 모드 고르기

- 기본은 `train`(연습)이다
- "평가", "무도움", "2주 점검"이면 `eval`이다. 질문과 고쳐 쓰기가 없다
- "리포트", "얼마나 늘었나"면 Step R로 간다

---

## 워크플로우

### Step 1: 초안과 자기평가 받기

대화에 초안이 없으면 아래만 보여 주고 기다린다. 내용에 관한 제안은 하지 않는다.

```
사례 이름(한 줄):
관측(사실, 수치, 출처):
결론(구조 / 구조 확대 불필요 / 원인 미확인 중 하나와 그 설명):
영향(누구에게, 얼마나):
자기평가(이 정의가 어디까지 닿았다고 보는지, 한 줄):
연결할 Task 링크(선택):
```

자기평가가 없으면 저장하지 않고 다시 요청한다. 코치 판정을 보기 전에 받아야 한다.

`eval`이면 "이 사례를 이전에 연습하거나 코치를 받은 적이 있습니까?"를 한 번 묻는다. 처음 쓰는 사례일 때만 `--new-case`를 붙인다.

### Step 2: 저장

초안은 사용자 원문 그대로 표준 입력으로 넘긴다. 다듬지 않는다. `<mode>`는 "모드 고르기"에서 고른 값(`train` 또는 `eval`)이다.

```bash
python3 $F start --mode <mode> --case "<사례 이름>" --self-assessment "<자기평가>" [--new-case] [--task-url "<링크>"] <<'DRAFT'
<사용자 초안 원문>
DRAFT
```

출력의 `id`와 `mode`를 기억한다. 출력의 `mode`가 고른 모드와 다르면 진행하지 않고 사용자에게 알린다.

### Step 3: 코치 판정 (초안)

```bash
python3 $F coach-input --id <id> --stage draft
python3 $F questions
```

`/Users/changhwan/.claude/skills/task:problem-coach/agents/agent-coach.md`를 Read하고 `{coach_input}`, `{question_bank}`를 위 두 출력의 JSON으로 치환해 Agent를 호출한다(`subagent_type: general-purpose`, `model: "opus"`). 대화 맥락이나 메인의 의견은 넣지 않는다.

**기록 전 누출 점검**: 스크립트는 형식만 검사하고 이유 칸의 의미적 누출은 막지 못한다. 코치 JSON을 받으면 기록하기 전에 네 이유를 아래 기준으로 MUST 점검한다.

- 원인이나 구조 후보를 말한다("~일 수 있습니다", "~때문으로 보입니다", 특정 정책·설정·장치 이름을 원인으로 지목)
- 고쳐 쓴 문장, 모범 문장, 예시를 담는다
- 살펴볼 영역을 나열한다("장치, 경계, 기준, 확인 단계 중..."처럼 범주를 늘어놓음)
- 칭찬, 격려, 다음에 볼 것에 대한 조언을 담는다

하나라도 걸리면 기록하지 않고, 걸린 기준을 붙여 같은 코치에게 다시 내게 한다(최대 2회). 2회 뒤에도 걸리면 기록하지 않고 "코치 출력에 답이 섞여 이 사례는 무효로 둡니다. 새 사례로 다시 시작해 주세요"라고 알린 뒤, 코치 프롬프트를 고칠 대상으로 보고한다. 걸린 출력의 내용은 사용자에게 보여 주지 않는다.

점검을 통과한 JSON을 그대로 기록한다.

```bash
python3 $F verdict --id <id> --stage draft <<'VERDICT'
<코치 JSON>
VERDICT
```

스크립트가 거부하면(`success: false`) 오류 메시지를 붙여 같은 코치에게 다시 내게 한다. 메인이 JSON을 고치지 않는다.

### Step 4: 판정 전달

스크립트 출력으로 아래만 보여 준다. `eval`이면 질문 줄과 고쳐 쓰기 요청을 빼고 Step 7로 간다.

```
| 항목 | 판정 | 이유 |   (관측, 연결, 범위, 영향 네 줄)
결론 유형: <conclusion_type>
내 자기평가: <self_assessment>
질문: <question.text>
위 질문을 스스로 확인한 뒤, 정의를 한 번 고쳐 써 주세요.
```

### Step 5: 고쳐 쓰기 저장

```bash
python3 $F revise --id <id> <<'REVISION'
<사용자 수정본 원문>
REVISION
```

### Step 6: 재판정

Step 3과 같은 방식(기록 전 누출 점검 포함)으로 `coach-input --stage revision`을 넣어 코치를 호출하고 `verdict --stage revision`으로 기록한다. 초안 판정과 재판정을 항목별로 나란히 보여 주고 끝낸다.

### Step 7: 검증

```bash
python3 $F show --id <id>
```

- `train`: `verdicts`에 `draft`와 `revision`이 모두 있고 `revision`이 비어 있지 않으면 완료다
- `eval`: `verdicts.draft`만 있으면 완료다
- 빠진 단계가 있으면 그 Step부터 다시 한다

| 오류 | 처리 |
|------|------|
| `자기평가가 비어 있습니다` | Step 1로 돌아가 자기평가를 받는다 |
| `고쳐 쓰기는 사례당 한 번입니다` | 새 사례로 시작하도록 안내한다 |
| `rubric은 ... 네 항목` / `reason이 160자를 넘습니다` | 오류를 붙여 코치에게 다시 내게 한다 |
| `question_id가 null이어야 합니다` | 평가 모드나 재판정이다. 코치에게 `null`로 다시 내게 한다 |
| `...번째 줄이 손상됐습니다` | 기록 파일을 고치지 않고 줄 번호와 함께 사용자에게 알린다. 사용자가 그 줄을 정리한 뒤 다시 실행한다 |

### Step R: 리포트

```bash
python3 $F report
```

- `counts`(연습 시작·완료, 평가 전체, 처음 쓴 사례의 평가, 그중 현재 판정 기준 버전, 항목별 판정 불가 수)와 `eval_timeline`을 표로 보여 준다
- 실력 변화는 `new_case`가 true인 평가로만 읽는다. `rubric_version`이 다른 기록끼리는 판정 기준이 달라 직접 비교하지 않는다고 함께 쓴다
- `trend_judgeable`이 false면(처음 쓴 사례의 평가 5건 미만) "표본이 작아 추세를 판단하지 않습니다"를 함께 쓴다
- `eval_due`가 true면 평가 1건을 권한다(2주 간격)

---

## 주의사항

- 기록은 Obsidian `03. Resources/Problem Coach Log.jsonl`에 append-only로 쌓인다. 테스트는 `PROBLEM_COACH_LOG_PATH`로 다른 파일을 쓴다
- 질문을 받는 것 자체가 도움이다. 실력은 처음 쓰는 사례의 `eval` 기록으로만 판단한다
- 스크립트가 보장하는 것은 저장 순서, 횟수, 형식뿐이다. 답 흘리기는 기록 전 누출 점검과 코치 프롬프트에 기대므로 완전히 막히지 않는다
- `references/coach-examples.md`는 코치 전용이다. 메인 대화는 읽지 않고, 사용자가 예시를 요청해도 보여 주지 않는다(따라 쓰기를 막는다)
- 하루 1건, 또는 착수 전 중요한 문제에만 쓴다
