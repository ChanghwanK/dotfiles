---
name: obsidian:daily
description: |
  Obsidian Daily 노트 생성 스킬 (daily:start의 출력 어댑터).
  daily:start와 동일한 전체 워크플로우(Notion fetch → 분석 → Top 3 선정)를 실행하되,
  최종 결과를 Obsidian 00. Daily/YYYY-MM-DD.md 파일로 저장한다.
  사용 시점: (1) 하루 시작 시 Obsidian Daily 노트 생성, (2) 어제 리뷰 + 오늘 할 것들을 Obsidian에 기록.
  트리거 키워드: "obsidian daily", "obsidian 일지", "daily note 만들어줘", "/obsidian:daily".
model: sonnet
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/obsidian:daily/scripts/env-init.sh *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Read
  - Write
---

# Obsidian Daily Note Skill

`daily:start`의 전체 워크플로우를 실행하고, 분석 결과를 Obsidian `00. Daily/YYYY-MM-DD.md` 파일로 저장한다.

---

## 핵심 원칙

- `daily:start`의 스크립트를 그대로 재사용한다. Notion MCP 도구 직접 사용 금지 (토큰 효율).
- 파일이 이미 존재하면 덮어쓰지 않고 스킵한다 (멱등). 사용자가 "덮어써줘" 등 명시적 요청 시에만 덮어쓴다.
- Claude가 분석 결과를 Obsidian 형식으로 포맷 후 Write 도구로 저장한다.
- Notion Todo 업데이트 제안 로직은 제거한다 (daily:start 역할).

---

## 출력 파일 경로

`/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/00. Daily/YYYY-MM-DD.md`

---

## 워크플로우

### 0. 환경 초기화 (항상 첫 번째로 실행)

워크플로우 시작 시 아래 두 작업을 백그라운드로 병렬 실행한다. Notion 데이터 fetch와도 병렬로 돌린다.

```bash
# 백그라운드 실행 (run_in_background: true) — 2개 병렬
bash /Users/changhwan/.claude/skills/obsidian:daily/scripts/env-init.sh brew
bash /Users/changhwan/.claude/skills/obsidian:daily/scripts/env-init.sh gimme
```

### 1. Notion 데이터 fetch (병렬 실행)

아래 4개 명령을 동시에 실행한다.

```bash
# 병렬 실행 (4개 동시)
NOTION_TOKEN=$(op read "op://Employee/Claude MCP - Notion-Personal/token") \
  python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date yesterday

NOTION_TOKEN=$(op read "op://Employee/Claude MCP - Notion-Personal/token") \
  python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date today

NOTION_TOKEN=$(op read "op://Employee/Claude MCP - Notion-Personal/token") \
  python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read-weekly

python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date {YYYY-MM-DD of yesterday}
```

**오늘 Notion 페이지 자동 생성:**
`read --date today` 결과에 `error`가 있으면 (페이지 없음) 자동으로 생성한다:

```bash
NOTION_TOKEN=$(op read "op://Employee/Claude MCP - Notion-Personal/token") \
  python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py create \
  --date today --title "@오늘 업무 일지"
```

### 2. 분석 로직

1. 어제 Notion `todos` done=true → 완료, done=false → 미완료로 분류
2. 어제 transcript `sessions` → Notion에 없는 실제 작업 추출해 완료 목록에 보완
3. 어제 `note` → 메모 섹션에 포함
4. carry-over = 어제 미완료 중 오늘 `todos`에 없는 항목

**Top 3 선정 로직 (Elon Musk 방식):**
이번 주 weekly tasks와 오늘 컨텍스트를 종합해 오늘 가장 임팩트 큰 3가지를 선정한다.

우선순위 가중치:
- Priority = P1: +3점 / P2: +1점
- 상태 = 진행 중: +2점 (모멘텀 유지)
- 오늘이 due_end 당일 또는 범위 내: +2점 (마감 임박)
- carry-over이며 이미 오늘 Todo's에 포함: +1점

이유 작성 규칙: "{작업명} — 이번 주 '{weekly task}' (P{N}) 달성을 위해. {오늘 해야 하는 구체적 이유 1문장}."

### 3. Obsidian 파일 저장

출력 형식은 `assets/obsidian-daily-template.md`를 Read로 읽어 참조한다.

**멱등성 체크:** 파일 존재 여부를 Read로 먼저 확인한다. 파일이 이미 있으면 사용자에게 알리고 스킵한다. 사용자가 명시적으로 덮어쓰기를 요청한 경우에만 덮어쓴다.

---

## 주의사항

- 토큰은 1Password에서 런타임 fetch: `op://Employee/Claude MCP - Notion-Personal/token`
- iCloud Drive 경로에 스페이스 포함 — Write 도구는 절대 경로 사용으로 자동 처리됨
- Notion 페이지가 없으면 빈 템플릿(Top 3 없음, Todos/Notes 섹션만)으로 생성

---

## 검증

스킬 실행 완료 후 확인:

- Obsidian 파일이 `/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/00. Daily/YYYY-MM-DD.md` 경로에 생성되었는가
- Top 3 섹션이 포함되었는가 (Notion/transcript 데이터가 충분한 경우)
- 파일이 이미 존재하면 스킵 처리 여부 확인

실패 시:
- `NOTION_TOKEN not set` → 1Password 토큰 fetch 명령 확인
- 파일 Write 실패 → iCloud Drive 경로 존재 여부 확인 (`00. Daily/` 디렉토리)
