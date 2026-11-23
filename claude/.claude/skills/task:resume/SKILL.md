---
name: task:resume
description: |
  하던 작업을 새 세션에서 이어 가는 스킬. 하루 시작 브리핑 항목, Claude 세션 id, 키워드 중 무엇으로 불러도
  지난 맥락(멈춘 곳, 다음 행동, 지난 세션 마지막 발화)을 5줄로 되살리고, 의도에 따라 구체화(grill-me) 또는
  실행(플랜 모드)으로 넘긴다.
  사용 시점: (1) 하루 시작 보드의 "구체화/실행으로 이어가기" 버튼이 연 채팅, (2) "어제 그 작업 이어서",
  (3) 세션 id로 특정 대화를 이어 갈 때.
  트리거: "/task:resume", "이어서 하자", "그 작업 이어서", "작업 재개", "어제 하던 거 이어서".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/task:resume/scripts/load-context.py *)
  - AskUserQuestion
  - Skill
  - Read
---

# task:resume

하던 작업을 새 세션에서 맥락을 다시 설명하지 않고 이어 간다. 입력이 달라도 같은 흐름을 탄다: 맥락 불러오기 → 5줄 요약 → 의도별 넘기기.

## 입력

`/task:resume <대상> [의도]`. 의도는 `구체화` 또는 `실행`이고, 없으면 Step 3에서 한 번 묻는다.

| 대상 모양 | 뜻 | 스크립트 |
|---|---|---|
| `2026-11-23 t16` (날짜 + id) | 하루 시작 브리핑 항목. id는 스레드 id 또는 `top1`~`top3` | `brief --date <날짜> --id <id>` |
| 36자 UUID | Claude 세션 id | `session --id <uuid>` |
| 그 외 단어 | 키워드 | `search --query "<키워드>"` |

Notion 링크는 지원하지 않는다(스크립트가 그렇게 알린다).

## 핵심 원칙

- 맥락은 스크립트 출력에서만 가져온다. 출력에 없는 진행 상황을 지어내지 않는다
- 이 스킬은 읽기만 한다. Notion, Task, 브리핑 파일, 세션 로그를 고치지 않는다
- 브리핑 JSON의 필드 약속은 `~/.claude/skills/daily:start/SKILL.md`의 "이어가기 흐름"이 정본이다. 필드가 바뀌면 그쪽 표를 먼저 본다
- 결과에 이모지와 em dash를 쓰지 않는다

## 워크플로우

### Step 1: 맥락 불러오기

입력 모양에 맞는 명령 하나를 실행한다.

```bash
python3 /Users/changhwan/.claude/skills/task:resume/scripts/load-context.py brief --date <날짜> --id <id>
python3 /Users/changhwan/.claude/skills/task:resume/scripts/load-context.py session --id <session_id>
python3 /Users/changhwan/.claude/skills/task:resume/scripts/load-context.py search --query "<키워드>"
```

- `error`가 있으면 그 문장을 그대로 전하고 멈춘다
- `session_error`만 있으면 지난 발화 없이 계속한다
- **키워드**: `candidates`(최대 3개)를 AskUserQuestion으로 고르게 한다. 옵션 라벨은 세션 제목, 설명은 `ended_at`(KST, MM-DD HH:MM)과 `first_message` 앞부분이다. 고른 세션으로 `session --id`를 다시 실행한다. 후보가 1개뿐이면 묻지 않고 그 세션으로 간다

### Step 2: 5줄 요약 (반드시 먼저 출력)

사용자에게 보이는 첫 응답 텍스트다. 이 요약을 출력하기 전에 Step 3의 Skill이나 EnterPlanMode를 부르지 않는다. 요약 없이 바로 넘기면 사용자는 어떤 맥락을 이어받았는지 확인할 수 없다(2026-11-23 첫 실행에서 요약 없이 grill-me로 넘어간 사례).

값이 있는 줄만 쓴다.
1. 작업: `title` (`status`, `project`)
2. 멈춘 곳: `stopped_at`. 없으면 `session.last_assistant`에서 추정하고 끝에 "(추정)"을 붙인다
3. 다음 행동: `next_action` (완료 조건: `done_when`). 없으면 마지막 사용자 질문과 마지막 답변에서 추정하고 "(추정)"을 붙인다
4. 지난 세션 마지막: `session.last_assistant` 요지 한 문장. 사용자 마지막 질문이 답 없이 열려 있으면 그것도 한 문장
5. 지금 위치: 현재 작업 디렉터리가 `cwd`와 다르면 "지난 작업 위치: `cwd`"를 적는다

### Step 3: 의도별로 넘기기

의도가 없으면 AskUserQuestion으로 한 번 묻는다(구체화 / 실행). 의도가 있으면 요약을 출력한 같은 응답에서 이어서 부르고 확인을 기다리지 않는다.

- **구체화**: `grill-me` 스킬을 Skill 도구로 부른다. args에 Step 2 요약과 "다음 행동을 구체적인 설계·결정으로 좁힌다"는 목표를 넣는다. 인터뷰 결과가 여러 컴포넌트에 걸친 설계로 커지면 `tasks:tech-spec`을 한 줄로 제안한다
- **실행**: 다음 행동을 목표로 `EnterPlanMode`에 들어가고, 플랜 Context에 Step 2 요약을 넣는다. 인프라 레포면 프로젝트 CLAUDE.md의 Explore → Plan 절차를 따른다

## 주의사항

- 브리핑 파일은 `~/.claude/tmp/daily-start/<날짜>.json`이다. daily:start가 쓰고, 이 스킬의 `brief`가 읽는다. 하루 시작 보드의 버튼은 `/task:resume <날짜> <id> <의도>`를 첫 프롬프트로 넣는다
- 세션은 `~/.claude/skills/daily:start/scripts/extract-work.py`로 읽는다. 그 스크립트의 경로와 필드(`session_id`, `title`, `cwd`, `ended_at`, `user_messages`, `last_assistant`)에 기댄다
- 키워드 검색은 최근 7일 세션의 제목, 사용자 메시지, 마지막 답변을 부분 일치로 찾고, 제목 일치에 가중을 둔다. 기간을 늘리려면 `--days`를 준다
