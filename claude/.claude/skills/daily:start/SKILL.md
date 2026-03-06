---
name: daily:start
description: |
  Notion Daily DB 업무 일지 조회 및 업데이트 스킬.
  사용 시점: (1) 오늘/어제 업무 일지 읽기, (2) 어제 리뷰 + 오늘 할 것들 정리,
  (3) carry-over 항목 추가, (4) Todo's 업데이트.
  트리거 키워드: "업무 일지", "어제 리뷰", "오늘 할 것들", "일지 읽어줘", "carry-over".
model: sonnet
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
---

# Notion Daily Work Log Skill

Notion Daily DB에서 업무 일지를 읽고, 분석하고, 업데이트하는 표준 워크플로우를 제공합니다.

---

## 핵심 원칙

- 스크립트만 호출한다. Notion MCP 도구는 사용하지 않는다 (토큰 효율).
- JSON 응답을 파싱해 구조화된 리뷰 포맷으로 출력한다.
- 명시적 요청이 없으면 Notion 페이지를 수정하지 않는다.

---

## 워크플로우

### 0. 환경 초기화 (항상 첫 번째로 실행)

워크플로우 시작 시 아래 두 작업을 백그라운드로 병렬 실행한다. Notion 데이터 fetch와도 병렬로 돌린다.
**하루 한 번만 실행한다.** 마커 파일(`~/.claude/tmp/start-daily-*-YYYY-MM-DD`)이 있으면 스킵한다.

```bash
# 백그라운드 실행 (run_in_background: true) — 2개 병렬
bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh brew
bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh gimme
```

- 마커가 없으면 실행 후 마커 생성. 마커가 있으면 "already done today" 출력.
- `brew upgrade` 완료 후 업데이트된 패키지 목록을 간단히 요약한다 (없으면 "all up to date").
- `gimme-aws-creds` 완료 후 결과를 간단히 요약한다.

### 1. 어제 리뷰 + 오늘 할 것들 정리 (기본 요청)

Notion과 어제 transcript를 **병렬로** 읽어 완전한 어제 리뷰를 만든다.

```bash
# 병렬 실행 (4개 동시)
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date yesterday
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date today
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read-weekly
python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date {YYYY-MM-DD of yesterday}
```

**오늘 페이지 자동 생성:**
`read --date today` 결과에 `error`가 있으면 (페이지 없음) 자동으로 생성한다:

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py create \
  --date today --title "@오늘 업무 일지"
```

- 생성 후 반환된 `page_id`를 이후 carry-over Todo 업데이트에 사용한다.
- 이미 페이지가 존재하면 `created: false`로 기존 `page_id`를 반환한다.

**분석 로직:**
1. 어제 Notion `todos` done=true → 완료, done=false → 미완료로 분류
2. 어제 transcript `sessions` → Notion에 없는 실제 작업 추출해 완료 목록에 보완
3. 어제 `note` → 메모/인사이트 섹션에 포함
4. carry-over = 어제 미완료 중 오늘 `todos`에 없는 항목

**Top 3 선정 로직 (Elon Musk 방식):**
이번 주 weekly tasks와 오늘 컨텍스트를 종합해 오늘 가장 임팩트 큰 3가지를 선정한다.

우선순위 가중치:
- Priority = P1: +3점 / P2: +1점
- 상태 = 진행 중: +2점 (모멘텀 유지)
- 오늘이 due_end 당일 또는 범위 내: +2점 (마감 임박)
- carry-over이며 이미 오늘 Todo's에 포함: +1점

이유 작성 규칙: "{작업명} — 이번 주 '{weekly task}' (P{N}) 달성을 위해. {오늘 해야 하는 구체적 이유 1문장}."

**Transcript 해석 방법:**
- `sessions[].project`로 어떤 리포지토리에서 작업했는지 파악
- `sessions[].user_messages`에서 실제 작업 의도 추출
- Notion 완료 목록에 없는 작업을 **추가 완료 항목**으로 보완

**출력 포맷:**
```
🎯 오늘의 Top 3 (이번 주 계획 기반)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. [작업명] — [이유]
2. [작업명] — [이유]
3. [작업명] — [이유]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{YYYY-MM-DD} 업무 리뷰

완료 ✅
- 항목1 (Notion)
- 항목2 (riiid-kubernetes)  ← transcript에서 추가

진행 중 / 미완료 🔄
- 항목 — (추가 컨텍스트가 있으면 포함)

메모 / 인사이트 📝
- 메모 내용

전체 평가
(한 문장 평가)
---
{오늘 날짜} 오늘 할 것들
1. 항목1
2. 항목2
---
어제 미완료 → 오늘 이어갈 것들 (Todo에 없지만 carry-over)
- 항목
```

**Notion Todo's 업데이트 확인:**
리뷰 출력 후, 오늘 Notion Todo's가 비어있거나 carry-over 항목이 있으면 AskUserQuestion으로 업데이트 여부를 묻는다.

```
AskUserQuestion:
  question: "오늘 Notion Todo's를 위 제안 항목으로 업데이트할까요?"
  options:
    - label: "Yes"
      description: "위 제안 항목으로 오늘 Notion Todo's를 업데이트합니다."
    - label: "No"
      description: "업데이트하지 않고 넘어갑니다."
```

- "Yes" 선택 시 `update-todos` 커맨드로 오늘 페이지에 제안 항목 반영
- "No" 선택 시 추가 작업 없이 종료

### 2. 특정 날짜 일지 읽기

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date 2026-02-25
python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date 2026-02-25
```

### 3. Todo 업데이트

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py update-todos \
  --page-id PAGE_ID \
  --content "- 항목1\n- 항목2"
```

- `--content`의 각 줄이 `Todo's` rich_text 프로퍼티의 한 세그먼트로 저장됨 (기존 내용 **덮어쓰기**)
- `page_id`는 `read` 명령 응답의 `page_id` 필드 사용

---

## 스크립트 동작 상세

**`read` 커맨드:**
- Daily DB (`2bf64745-3170-8016-b20a-ff022dea06cb`)를 Due Date 필터로 쿼리
- 페이지 블록을 파싱해 섹션(Todo's, Note, Tomorrow, KPT) 구분
- `to_do` 블록: `checked` 또는 strikethrough → `done: true`
- `bulleted_list_item`: strikethrough → `done: true`

**`read-weekly` 커맨드:**
- Task DB (`2da64745-3170-8072-80bd-fb05cf592929`)를 이번 주 월~일 Due Date 범위로 필터
- Priority 오름차순 정렬 (P1 먼저)
- 반환 필드: page_id, name, priority, status, due_start, due_end, tags

**`create` 커맨드:**
- 해당 날짜에 이미 페이지가 있으면 `created: false` + 기존 `page_id` 반환 (중복 방지)
- 없으면 DB에 새 페이지 생성: `이름`(title) + `Due Date`(date) 프로퍼티 설정
- `--title` 미지정 시 기본값: `@YYYY-MM-DD 업무 일지`

**`update-todos` 커맨드:**
- `Todo's` rich_text 프로퍼티를 **교체** (PATCH `/pages/{page_id}`)
- 각 줄이 별도 rich_text 세그먼트로 저장됨 (strikethrough=false)

---

## 주의사항

- 토큰은 1Password에서 런타임에 fetch: `op://Employee/Claude MCP - Notion-Personal/token`
- 날짜가 없는 경우 `error` 필드가 JSON에 포함됨
- 섹션 헤딩이 없는 페이지는 모든 블록이 파싱되지 않을 수 있음

---

## 검증

스크립트 실행 후 JSON 응답의 `success` 또는 `error` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 `NOTION_TOKEN` 환경변수 확인
- `error: page not found` → 해당 날짜에 Daily 페이지가 없음 → `create` 커맨드로 생성
- `update-todos` 후 Notion에 반영 안 됨 → `page_id` 필드 값 재확인
