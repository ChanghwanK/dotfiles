---
name: task:resume
description: |
  Notion Task 링크로 작업을 재개할 때 사용. 본문을 읽어 컨텍스트를 파악하고,
  상태가 '시작 전'이면 '진행 중'으로 전환한다(이미 진행 중이면 무변경, 멱등).
  사용 시점: (1) Task 링크를 주며 "이어서 하자"라고 할 때, (2) 새 세션에서 특정
  Task를 픽업할 때. 트리거: "/task:resume", "task 이어서", "이 task 재개".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/task:resume/scripts/resolve_task.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-status *)
  - mcp__notion-personal__API-retrieve-page-markdown
---

# task:resume Skill

Notion Task 링크 하나로 "지금까지 뭘 했는지"와 "지금 상태"를 파악하고, 착수
시점(시작 전 -> 진행 중) 전환까지 한 번에 처리한다.

---

## 핵심 원칙

- **읽기는 MCP, 쓰기는 스크립트**: 본문 읽기는 `API-retrieve-page-markdown`
  (렌더링된 마크다운을 그대로 받는다), 속성 조회/상태 변경은 스크립트를 통해서만
  한다. 블록 파싱을 직접 재구현하지 않는다.
- **상태 전이는 단방향·멱등**: '시작 전' -> '진행 중' 전환만 한다. 이미
  '진행 중'/'완료'/'대기'면 아무것도 바꾸지 않는다(사용자가 이미 손댄 상태를
  덮어쓰지 않는다).
- **update-status 로직은 재구현하지 않는다**: 상태 변경은 반드시
  `tasks:manage/scripts/notion-task.py update-status`를 호출한다. 이 스크립트가
  Done 체크박스 동기화, `started_at` backfill을 이미 처리한다.
- `/task:resume <링크>` 호출 자체가 착수 의사표시이므로, 상태 전환 전 별도
  확인 질문은 하지 않는다(alfred의 `resume --task` 로더와 달리, 여기서는
  브리핑 매니페스트를 거치지 않고 사용자가 링크를 직접 골라 왔기 때문).

---

## 워크플로우

### Step 1: 링크 파싱 + Task 속성 조회

```bash
python3 /Users/changhwan/.claude/skills/task:resume/scripts/resolve_task.py resolve --url "<사용자가 준 노션 링크 또는 page_id>"
```

출력 JSON: `page_id`, `is_task_db`, `name`, `status`, `priority`, `due_date`,
`category`, `roi`.

- `success: false` → 에러 메시지를 그대로 사용자에게 보여주고 종료.
- `is_task_db: false` → Task DB 페이지가 아닌 것으로 보인다는 점을 한 줄
  경고하고 계속 진행한다(본문 읽기는 여전히 유효하나, 상태 값이 없거나
  의미가 다를 수 있음: Step 2의 상태 전환은 `status` 값 자체가 없으면
  자연히 스킵된다).

### Step 2: 상태 전환 ('시작 전' -> '진행 중', 조건부)

Step 1에서 얻은 `status` 값으로 분기한다:

| status | 동작 |
|--------|------|
| `시작 전` | `update-status`로 '진행 중' 전환 |
| `진행 중` / `완료` / `대기` | 건드리지 않음 (이미 손댄 상태) |
| 없음 (Task DB 아님) | 건드리지 않음 |

전환이 필요하면:

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-status \
  --page-id <page_id> --status "진행 중"
```

이 호출이 실패해도 멈추지 않는다. 경고 한 줄만 남기고 Step 3으로 진행한다
(상태 전환은 부가 효과이지, 컨텍스트 파악의 필수 전제조건이 아니다).

**검증**: `update-status` 응답 JSON의 `"status": "진행 중"`으로 전환 성공을
확인한다. 실패(에러 응답)면 Step 4 출력에 "상태 전환 실패, 수동 확인 필요"를
덧붙인다.

### Step 3: 본문 읽기

```
mcp__notion-personal__API-retrieve-page-markdown(page_id=<Step 1의 page_id>)
```

반환된 마크다운을 읽고 다음을 파악한다:
- 지금까지 진행된 작업(로그/체크리스트 중 완료 항목)
- 아직 안 된 것(미완료 체크박스, "다음 단계" 류 섹션)
- 막혔던 지점이나 의사결정이 필요했던 부분

### Step 4: 컨텍스트 요약 출력

아래 형식으로 정리해 응답한다(짧고 핵심만, 표 대신 목록):

```
이어서 진행: {name} ({priority}, {category}) · due {due_date}
상태: {변경 전} -> {변경 후} (전환됨 / 변경 없음)

지금까지
- {본문에서 파악한 완료/진행 내용 1}
- {완료/진행 내용 2}

남은 것
- {미완료 항목 1}
- {미완료 항목 2}

이어서 {첫 액션}부터 진행하겠습니다.
```

이후부터는 일반 작업 세션으로 전환한다(이 스킬은 컨텍스트 로딩과 상태
전환까지만 담당하고, 실제 작업 수행은 메인 대화 흐름이 이어받는다).

---

## 주의사항

- `resolve_task.py`는 제목 슬러그가 붙은 URL, 대시 없는/있는 UUID, 순수
  page_id 문자열을 모두 처리한다. 파싱 실패 시(`success: false`) 링크가
  잘렸거나 잘못 복사됐을 가능성을 안내한다.
- `NOTION_TOKEN` 환경변수가 없으면 `resolve_task.py`가 즉시 에러를 낸다.
  `tasks:manage`의 다른 스크립트들과 동일한 토큰을 공유한다.
- 이 스킬은 Task 속성(상태) 변경만 하며, 본문 콘텐츠는 수정하지 않는다.
  본문에 진행 로그를 추가하려면 `tasks:manage/scripts/notion-task.py
  append-content`를 별도로 사용한다.
