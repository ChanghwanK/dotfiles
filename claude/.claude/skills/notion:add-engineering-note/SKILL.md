---
name: notion:add-engineering-note
description: |
  Notion Engineering DB에 업무 노트 페이지를 생성하고 내용을 작성하는 스킬.
  사용 시점: (1) 인프라/시스템 설계 대화 후 결과를 Notion에 정리, (2) 의사결정 문서화,
  (3) 기술 검토/설계 노트 생성, (4) 이슈 분석 노트 작성.
  트리거 키워드: "업무 노트", "engineering note", "노트 생성", "eng-note",
  "엔지니어링 노트 써줘", "노션에 정리해줘", "노션에 노트 만들어줘", "설계 내용 노션에".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py *)
  - Write(/tmp/eng-note-sections.json)
---

# Engineering Note Skill

Claude와의 설계/의사결정 대화 내용을 Engineering DB 업무 노트로 자동 생성하는 워크플로우.

---

## 핵심 원칙

- **대화 내용을 템플릿에 매핑**한다. 섹션별로 대화에서 나온 내용을 추출해 채운다.
- 내용이 없는 섹션은 placeholder 유지 — 억지로 채우지 않는다.
- 스크립트만 호출한다. Notion MCP 도구 사용 금지 (토큰 효율).
- 토큰은 환경변수 `$NOTION_TOKEN` 사용 (`~/.secrets.zsh`에서 로드됨).
- 생성 후 URL을 반드시 출력한다.

---

## DB 스키마

**DB ID**: `17964745-3170-8030-bf01-e7f20a6e1bd7`

| 속성 | 타입 | 옵션 |
|------|------|------|
| Title | title | - |
| Group | select | `#Study`, `#Article`, `#업무노트`, `#정리` |
| Tag | multi_select | `#Kubernetes`, `#Network`, `#Istio`, `#Issue`, `#Infra`, `#Observabiliy`, `#Security`, `#자동화`, `#AI`, `#Agent`, `#OS`, `#Terraform`, `#AWS`, `#Engineering` |
| Created At | date | - |
| Task | relation | - |

---

## Primary Workflow: 대화 → Notion 노트

### Step 1: 대화 내용 분석 및 섹션 매핑

대화에서 다음 6개 섹션에 해당하는 내용을 추출한다:

| 섹션 | JSON key | 추출 기준 |
|------|----------|-----------|
| 문제 정의 | `problem` | 왜 이 작업을 하는가, 현재 상황 |
| 목표 (Goal) | `goal` | 달성하려는 것 |
| 비목표 (Non-goal) | `non_goal` | 이번 범위에서 제외한 것 |
| 설계 | `design` | 선택한 아키텍처/방식 |
| 대안 검토 | `alternatives` | 검토했던 다른 옵션들 |
| 구현 계획 | `plan` | 실행 단계, 체크리스트 |
| 미결 질문 | `questions` | 아직 결정 안 된 것 |

### Step 2: 메타데이터 확인

사용자에게 확인 (대화 맥락에서 명확하면 생략):
- **제목** (필수)
- **Tag** — 대화 주제에 맞는 태그 추천
- **Group** — 기본 `#업무노트`

### Step 3: sections.json 작성 후 페이지 생성

```bash
# 1. sections.json 생성 (Write 도구 사용)
# /tmp/eng-note-sections.json

# 2. 페이지 생성
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py create \
  --title "제목" \
  --group "#업무노트" \
  --tag "#Kubernetes,#Infra" \
  --sections /tmp/eng-note-sections.json
```

섹션 없을 때 (빈 템플릿):
```bash
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py create \
  --title "제목"
```

### Step 4: 결과 출력

```
업무 노트 생성 완료.
- 제목: {title}
- Group: {group} | Tags: {tags}
- URL: {url}
```

### Step 5: 검증

스크립트 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 NOTION_TOKEN 확인
- `invalid database` → DB ID 확인
- `success: false` → 에러 메시지를 사용자에게 전달 후 재실행

---

## sections.json 형식

```json
{
  "problem":      "문제 상황 마크다운 (- 불릿, **bold**, 코드블록 지원)",
  "goal":         "목표 마크다운",
  "non_goal":     "비목표 마크다운",
  "design":       "설계 내용 마크다운",
  "alternatives": "대안 검토 마크다운",
  "plan":         "- [ ] 작업1\n- [ ] 작업2",
  "questions":    "- [ ] 미결 질문 항목"
}
```

값이 없는 키는 생략해도 됨 (placeholder로 대체).

---

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py list --limit 10
```
