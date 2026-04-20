---
name: daily:start
description: |
  하루 시작 스킬. 어제 Obsidian Daily Note + Notion 주간 Task를 분석하여
  오늘 할 것들을 정리하고 Obsidian Daily Note로 저장한다.
  사용 시점: (1) 하루 시작, (2) 어제 리뷰 + 오늘 할 것들 정리, (3) Obsidian Daily Note 생성.
  트리거 키워드: "하루 시작", "daily start", "daily note", "오늘 할 것들",
  "obsidian daily", "daily note 만들어줘", "업무 일지".
model: sonnet
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py *)
  - Read
  - Write
  - Agent
  - AskUserQuestion
  - mcp__claude_ai_Gmail__gmail_search_messages
  - mcp__claude_ai_Gmail__gmail_read_message
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/reminder.py *)
---

# Daily Start Skill

어제 Obsidian Daily Note와 Notion 주간 Task를 분석하여 오늘의 Obsidian Daily Note를 생성한다.

---

## 핵심 원칙

- Notion 조회는 스크립트만 사용한다. Notion MCP 도구 사용하지 않음 (토큰 효율).
- 어제 리뷰의 primary source는 **Obsidian Daily Note** (`[x]`/`[ ]` 파싱).
- Notion은 주간 Task 조회(`read-weekly`)에만 사용한다.
- 명시적 요청이 없으면 Notion 페이지를 수정하지 않는다.

---

## 워크플로우

### 0. 환경 초기화 (반드시 첫 번째로 실행)

워크플로우 시작 시 아래 두 작업을 백그라운드로 병렬 실행한다.
**하루 한 번만 실행한다.** 마커 파일(`~/.claude/tmp/start-daily-*-YYYY-MM-DD`)이 있으면 스킵한다.

```bash
# 백그라운드 실행 (run_in_background: true) — 2개 병렬
bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh brew
bash /Users/changhwan/.claude/skills/daily:start/scripts/env-init.sh gimme
```

- 마커가 없으면 실행 후 마커 생성. 마커가 있으면 "already done today" 출력.
- `brew upgrade` 완료 후 업데이트된 패키지 목록을 간단히 요약한다 (없으면 "all up to date").
- `gimme-aws-creds` 완료 후 결과를 간단히 요약한다.

### 1. 데이터 수집 (Agent 병렬 실행)

**Agent 3개를 동시에 launch**하여 데이터 수집을 독립 서브프로세스에 위임한다.
각 Agent는 raw JSON을 파싱하여 메인 컨텍스트에는 구조화된 요약만 반환한다.

#### Agent A: 어제 리뷰 수집 (Obsidian + Transcript)

Read 도구로 `~/.claude/skills/daily:start/agents/agent-obsidian-review.md`를 읽고,
`{yesterday_date}`를 어제 날짜(YYYY-MM-DD)로 치환하여 Agent를 launch한다.

- subagent_type: `general-purpose`, model: `sonnet`
- 허용 도구는 agent 파일 frontmatter에 정의됨

#### Agent B: Notion + Google Calendar 수집

Read 도구로 `~/.claude/skills/daily:start/agents/agent-notion-calendar.md`를 읽고,
`{today_date}`를 오늘 날짜(YYYY-MM-DD)로 치환하여 Agent를 launch한다.

- subagent_type: `general-purpose`, model: `sonnet`
- 허용 도구는 agent 파일 frontmatter에 정의됨

#### Agent C: Gmail Inbox 분석

Read 도구로 `~/.claude/skills/daily:start/agents/agent-gmail-inbox.md`를 읽고,
`{today_date}`를 오늘 날짜(YYYY-MM-DD)로 치환하여 Agent를 launch한다.

- subagent_type: `general-purpose`, model: `haiku` (단순 추출/분류 작업)
- 허용 도구는 agent 파일 frontmatter에 정의됨

#### 병렬 실행 방법

세 Agent를 **단일 메시지에서 동시에 launch**한다 (독립적이므로 병렬 실행 가능):

- Agent A (run_in_background: false) — 결과를 메인에서 기다림
- Agent B (run_in_background: false) — 결과를 메인에서 기다림
- Agent C (run_in_background: false) — 결과를 메인에서 기다림

세 Agent 결과를 모두 수신한 후 Step 2로 진행한다.

**검증:** 각 Agent가 명시된 반환 형식(YAML 블록)을 따랐는지 확인. 미준수 시 1회 재시도.

**주의:** Gmail API 오류 시 Agent C는 `email_summary: null`을 반환한다. 이 경우 스킬을 중단하지 않고 계속 진행한다 (Gmail은 선택 소스).

### 2. 어제 Obsidian Daily Note 분석

Agent A의 반환 결과를 다음 로직으로 분석한다 (파싱 규칙은 agent-obsidian-review.md 참조):

1. `completed` 목록 = 어제 `[x]` 항목 (Top 3 + Todos)
2. `incomplete` 목록 = 어제 `[ ]` 미완료 항목 → carry-over 후보
3. 어제 transcript `sessions` → Obsidian 완료 목록에 없는 실제 작업 추출해 보완
4. carry-over = `incomplete` 전체 (Notion 상태와 무관)
5. `notes` / `retrospective` → 메모/인사이트 섹션에 포함
6. `tomorrow_tasks` → Top 3 선정 시 최우선 고려 대상 (사용자가 직접 기록한 오늘 할 일)

### 3. Top 3 선정 (Elon Musk 방식)

Notion 주간 Task와 어제 Obsidian 컨텍스트를 종합해 오늘 가장 임팩트 큰 3가지를 선정한다.

**⚠️ 후보 풀 결정 (가장 먼저 적용):**
- **`level: "weekly_project"` Task는 반드시 후보에서 제외한다.** (due_end 있음 + 진행 중 = 주간 프로젝트 목표. 별도 섹션에서만 표시)
- **Obsidian `completed` 목록(어제 `[x]` 항목)과 매칭되는 Notion 주간 Task는 반드시 후보에서 제외한다.**
- 매칭 기준: 항목명이 부분 문자열로 일치하면 완료로 간주 (대소문자 무관).
- Notion `status: 완료`인 항목도 제외한다.
- 후보 풀 = Notion weekly_tasks 중 `level: "daily"`이고 위 완료 조건에 해당하지 않는 항목만.

**[실행]/[탐색] 분류 (후보 풀 내에서 각 항목에 태그 부여):**
- `[실행]`: 어제 Obsidian `[ ]` 미완료이면서, 어제 transcript에서 관련 분석/설계 작업이 있었던 항목. 즉, 분석은 완료되었고 실행만 남은 상태.
- `[탐색]`: 그 외 모든 항목 (분석/설계가 아직 필요한 것).
- 판단이 애매하면 `[탐색]`으로 분류한다.

**우선순위 가중치 (후보 풀 내에서만 적용):**
- 어제 "내일 해야할 것"에 명시됨: +4점 (사용자 직접 의도, 최고 가중치)
- `[실행]` 타입 (분석 완료, 실행만 남음): +3점
- Priority = P1: +3점 / P2: +1점
- Notion status = 진행 중: +2점 (모멘텀 유지)
- 오늘이 due_end 당일 또는 범위 내: +2점 (마감 임박)
- 어제 Obsidian `[ ]` 미완료이며 carry-over: +1점

**Top 3 정렬:** `[실행]` 태그 항목을 상단에 배치한다 (가중치 합산 후, 동점이면 [실행] 우선).

**완료 조건 작성 규칙:** 각 Top 3 항목에 "완료 조건"을 1줄 추가한다. 관찰 가능한 상태 변화로 정의한다 (예: "ArgoCD Synced + Pod healthy", "PR merged", "테스트 통과").

**캘린더 일정 고려:**
- 오전 미팅이 2시간 이상이면 → 오전 집중 작업 대신 미팅 후 시작 가능한 Task 우선
- 하루 중 미팅이 많으면 (3건 이상) → 독립적으로 진행 가능한 작은 단위 Task 선호
- Agent B의 `calendar_events`가 비어있으면 이 로직 스킵

**이유 작성 규칙:** "이번 주 '{weekly task}' (P{N}) 달성을 위해. {오늘 해야 하는 구체적 이유 1문장}."

**Transcript 해석 방법:**
- `sessions[].project`로 어떤 리포지토리에서 작업했는지 파악
- `sessions[].user_messages`에서 실제 작업 의도 추출
- Obsidian 완료 목록에 없는 작업을 **추가 완료 항목**으로 보완

### 3.5. 리마인드 선택

Top 3 선정 후 아래 스크립트로 최근 7일 이내 작성한 Obsidian 노트를 수집한다.

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/reminder.py \
  --vault "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home" \
  --days 7 --count 5
```

- 결과가 0개이면 `--days 14`로 늘려 재시도.
- 결과 `reminders[]`를 Step 4 콘솔 출력과 Step 5 Obsidian Daily Note에 사용.
- 빈 경우 이 섹션 출력 생략.

### 4. 콘솔 출력

Read 도구로 `~/.claude/skills/daily:start/assets/console-output-template.md`를 읽고
변수 치환 후 출력한다. 섹션별 생략 조건은 템플릿 내 주석 참조.

### 5. Obsidian Daily Note 생성

콘솔 출력 후 자동으로 오늘 Obsidian Daily Note를 생성한다.

**저장 경로:**
```
~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md
```

**템플릿 참조:** `~/.claude/skills/daily:start/assets/obsidian-daily-template.md`

**분기 로직 (파일 존재 여부 확인):**

| 케이스 | 파일 존재 여부 | 동작 |
|--------|---------------|------|
| A | 없음 | Write 도구로 새 파일 생성 |
| B | 있음 | Read → 섹션별 파싱 → 빈 섹션만 Edit으로 채움 |

**케이스 A — 새 파일 생성 (Write 도구):**
- frontmatter의 `date`, `last_reviewed`는 오늘 날짜로 설정.
- `title`: `YYYY-MM-DD Daily` 형식.
- `## Top 3 오늘의 목표`: Step 3에서 선정한 Top 3로 채움. 형식: `- [ ] [실행|탐색] 작업명` + 탭 들여쓰기로 `\t- 완료 조건: {조건}` + `\t- 이유: {이유}`. `[실행]` 항목을 상단에 배치.
- `## 어제 리뷰 (YYYY-MM-DD)`: 실제 어제 날짜 기입. 완료/진행 중/carry-over 섹션으로 구성.
- `## 오늘 일정`: Agent B의 `calendar_events`로 채움. 없으면 `- (일정 없음)`.
- `## 메일 요약`: Agent C의 `email_summary.emails`를 요약하여 채움. Agent C 결과가 null이거나 total_unread가 0이면 이 섹션을 생성하지 않음.
  - `infra_actions`가 있으면 `### 인프라 액션` 서브섹션 추가
  - `suggested_tasks`가 있으면 `### Task 권장` 서브섹션 추가
- `## Todos`: Top 3 항목 + `tomorrow_tasks` 중 Top 3에 포함되지 않은 항목을 `- [ ]` 형식으로 채움. **`weekly_project` Task는 포함하지 않는다.**
- `## 리마인드`: Step 3.5의 `reminders[]`로 채움. 형식: `- [{date}] {title}\n  {summary}`. 빈 경우 이 섹션을 생성하지 않음.
- `## 회고 (EOD)`: 빈 상태로 둠 (daily:review 스킬에서 채움).
- `## Notes`, `## Issues`: 빈 상태로 둠.

**케이스 B — 기존 파일 병합 (Read → Edit 도구):**

1. Read로 기존 파일 읽기
2. `## ` 기준으로 섹션 분할 (헤딩 → 내용 매핑)
3. 자동 생성 대상 섹션에 대해 "빈 섹션" 여부 판정 후 Edit으로 채움:
   - `## Top 3 오늘의 목표`, `## 오늘 일정`, `## 어제 리뷰 (YYYY-MM-DD)` 대상
4. frontmatter의 `last_reviewed`만 오늘 날짜로 갱신
5. `tomorrow_tasks`가 존재하면 Todos 섹션에 기존 항목과 중복되지 않는 항목만 `- [ ]` 형식으로 append한다.
   중복 판정: 항목명이 기존 Todos의 일부 문자열과 매칭되면 중복으로 간주.

**섹션별 병합 규칙:**

| 섹션 | 자동 생성 | 기존 내용 있으면 | 기존 내용 없으면 |
|------|-----------|-----------------|-----------------|
| frontmatter | `last_reviewed`만 | `last_reviewed` 갱신 | 전체 생성 |
| Top 3 오늘의 목표 | ✅ | **보존** (사용자가 직접 설정) | 채움 |
| 오늘 일정 | ✅ | **보존** | 채움 |
| 메일 요약 | ✅ | **보존** | 채움 (Agent C null이면 생성 안 함) |
| Todos | ✅ | **보존 + tomorrow_tasks append** | Top 3 + tomorrow_tasks 미포함분을 `- [ ]` 형식으로 채움 |
| 리마인드 | ✅ | **보존** | Step 3.5 결과로 채움 (빈 경우 생성 안 함) |
| Notes | ❌ | **반드시 보존** | — |
| Issues | ❌ | **반드시 보존** | — |
| 어제 리뷰 | ✅ | **보존** | 채움 |
| 회고 (EOD) | ❌ | **반드시 보존** | — |

**"빈 섹션" 판정 기준:**
`## 헤딩` 다음 줄이 `-` 한 글자만 있거나, 헤딩 바로 다음이 다른 `##` 헤딩이면 빈 섹션으로 간주.

**검증:** 파일 작성 후 Read로 다시 읽어 frontmatter `date`와 `## Top 3 오늘의 목표` 섹션이 채워졌는지 확인.

### 5.5. Obsidian 미완료 Todo → Notion Task 등록 (선택)

Obsidian Daily Note `## Todos`의 `[ ]` 미완료 항목을 Notion Task DB와 대조하여,
미등록 항목을 Notion Task로 등록할지 사용자에게 제안한다.

**5.5.1. 활성 Task 목록 조회**

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py search-tasks
```

**5.5.2. 매칭 판정 (Claude가 직접 수행)**

Obsidian `[ ]` 항목 각각에 대해 `search-tasks` 결과의 `name`과 의미 기반 대조:
- 핵심 키워드가 70%+ 겹치거나, 한쪽이 다른 쪽의 부분 문자열이면 → **매칭 (Skip)**
- 매칭 항목 없음 → **등록 후보**

**5.5.3. 사용자 확인 (AskUserQuestion)**

등록 후보가 1개 이상이면 AskUserQuestion으로 질문:

```
📋 Notion Task에 미등록된 Todo 항목:
1. k8s event dashboard 구성
2. Cilium 패치 버전 업그레이드 검토

(이미 등록됨 — Skip: "Alert 개선" ↔ "Alert improvement - alert rule redesign")

등록 방법을 선택하세요.
options:
  - label: "전체 등록"
  - label: "선택 등록 (번호 입력)"
  - label: "스킵"
```

등록 후보가 0개이면 이 Step 전체를 메시지 없이 스킵한다.
"전체 등록" 선택 시 등록할 항목 목록을 최종 재확인 메시지로 표시 후 진행.

**5.5.4. Task 생성**

선택된 항목별:

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "항목명" --priority "P3 - Could Have" --category "WORK" \
  --due "오늘 날짜(YYYY-MM-DD)"
```

- Priority: 기본 P3. Top 3에 포함된 항목은 해당 주간 Task의 priority를 따름.
- Due Date: 오늘 날짜.
- Category: WORK.
- 성공 시 `📥 등록 완료: [P3] 항목명 (~YYYY-MM-DD)` 형식으로 출력.

### 6. Notion Todo's 업데이트 확인 (선택)

Obsidian 파일 저장 후, Notion Todo's가 비어있거나 carry-over 항목이 있으면 AskUserQuestion으로 업데이트 여부를 묻는다.

```
AskUserQuestion:
  question: "오늘 Notion Todo's를 Obsidian 전체 Todo 항목으로 업데이트할까요?"
  options:
    - label: "Yes"
      description: "Obsidian Daily Note의 ## Todos 항목 전체를 Notion Todo's에 반영합니다."
    - label: "No"
      description: "업데이트하지 않고 넘어갑니다."
```

- "Yes" 선택 시 `update-todos` 커맨드로 오늘 페이지에 반영. **Obsidian `## Todos` 섹션의 모든 `[ ]`/`[x]` 항목 전체**를 Notion에 동기화한다.
- 변경 미리보기가 필요하면 `--dry-run`을 추가하여 먼저 확인.
- "No" 선택 시 추가 작업 없이 종료.

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py update-todos \
  --page-id PAGE_ID \
  --content "- 항목1\n- 항목2\n- tomorrow_task1\n- tomorrow_task2"
```

### 7. 특정 날짜 일지 읽기 (서브 모드)

"2월 25일 업무 일지 읽어줘" 등 특정 날짜 요청 시:

```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date 2026-02-25
python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date 2026-02-25
```

해당 날짜 Obsidian Daily Note도 Read 도구로 함께 읽는다.

---

## 참조 문서

- 스크립트 동작 상세 (`read`/`read-weekly`/`create`/`update-todos`): `references/script-reference.md`
- 콘솔 출력 템플릿: `assets/console-output-template.md`
- Obsidian Daily 템플릿: `assets/obsidian-daily-template.md`
- Agent 프롬프트: `agents/agent-obsidian-review.md`, `agents/agent-notion-calendar.md`, `agents/agent-gmail-inbox.md`

---

## 주의사항

- 토큰은 1Password에서 런타임에 fetch: `op://Employee/Claude MCP - Notion-Personal/token`
- 어제 Obsidian Daily Note가 없으면 (주말, 휴가 등) Agent A 내부에서 Notion `read --date yesterday`로 폴백한다.
- Obsidian 파일이 이미 존재하면 섹션별로 파싱하여 빈 섹션만 채운다. 사용자 작성 내용은 절대 덮어쓰지 않는다.
- 날짜가 없는 경우 Notion `error` 필드가 JSON에 포함됨
- Google Calendar 조회 실패 시 (권한 없음, API 오류 등) 캘린더 섹션을 빈 리스트로 처리하고 계속 진행한다.
- Agent의 `subagent_type`은 `general-purpose` 사용 (Explore 에이전트는 쓰기 도구 없음)

---

## 검증

스크립트 실행 후 JSON 응답의 `success` 또는 `error` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 `NOTION_TOKEN` 환경변수 확인
- `error: page not found` → 해당 날짜에 Daily 페이지가 없음 → `create` 커맨드로 생성
- Obsidian 파일 없음 → 경로 확인 (`~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/`)
- Google Calendar 조회 실패 → `calendar_events: []`로 처리하고 스킬 계속 진행 (캘린더는 선택 소스)

구조 검증:
```bash
python3 ~/.claude/skills/skills:manage/scripts/manage_skill.py validate daily:start
```
