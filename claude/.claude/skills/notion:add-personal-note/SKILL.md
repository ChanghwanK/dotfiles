---
name: notion:add-personal-note
description: |
  대화 결과를 Notion [Private] Note DB에 노트로 저장하는 스킬.
  사용 시점: (1) 대화에서 정리된 내용을 노트로 저장, (2) 학습/참고 내용을 Notion에 기록,
  (3) 설정/커맨드 치트시트를 노트로 보관.
  트리거 키워드: "노트", "note", "노트 저장", "노트 만들어줘", "notion에 저장", "/note".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:add-personal-note/scripts/notion-note.py *)
  - Write(/tmp/note-content.json)
---

# Note Skill

대화 결과를 마크다운으로 정리해 Notion [Private] Note DB에 페이지로 생성한다.

---

## 핵심 원칙

- **대화 내용을 마크다운으로 정리**한 뒤 Notion 페이지로 변환한다.
- 스크립트만 호출한다. Notion MCP 도구 사용 금지 (토큰 효율).
- 토큰은 환경변수 `$NOTION_TOKEN` 사용 (`~/.secrets.zsh`에서 로드됨).
- 생성 후 URL을 반드시 출력한다.
- **기술 학습 노트는 `obsidian:note`를 사용할 것** (Obsidian = 지식, Notion = 개인 메모/행정 기록). 개발 개념, 인프라 지식, 기술 정리는 `obsidian:note`로 저장해야 Quick Switcher 검색이 가능합니다.

---

## DB 스키마

**DB ID**: `24364745-3170-80b5-8e34-da0245b42d6c`

| 속성 | 타입 | 옵션 |
|------|------|------|
| 이름 | title | - |
| Group | select | `#Note` |
| Tags | multi_select | `Kubernetes`, `Life`, `Company`, `설정`, `Secret`, `Cursor`, `Claude Rule`, `CLI`, `VIM`, `학습`, `AI Agent` |
| Created At | date | - |

---

## 워크플로우

### Step 1 — 대화 내용 정리

대화에서 노트로 저장할 내용을 마크다운으로 정리한다.
헤딩, 리스트, 코드 블록, 테이블, 인용 등 모든 마크다운 구문을 지원한다.

### Step 2 — 메타데이터 확인

사용자에게 확인 (대화 맥락에서 명확하면 생략):
- **제목** (필수)
- **Tags** — 대화 주제에 맞는 태그 추천 (복수 선택 가능)
- **Group** — 기본 `#Note`

### Step 3 — content.json 작성 후 페이지 생성

```bash
# 1. content.json 생성 (Write 도구 사용)
# /tmp/note-content.json

# 2. 페이지 생성
python3 /Users/changhwan/.claude/skills/notion:add-personal-note/scripts/notion-note.py create \
  --title "제목" \
  --tags "VIM,학습" \
  --content /tmp/note-content.json
```

콘텐츠 없이 빈 페이지 생성:
```bash
python3 /Users/changhwan/.claude/skills/notion:add-personal-note/scripts/notion-note.py create \
  --title "제목"
```

### Step 4 — 결과 확인

```
노트 생성 완료.
- 제목: {title}
- Group: {group} | Tags: {tags}
- URL: {url}
```

### Step 5 — 검증

스크립트 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 NOTION_TOKEN 확인
- `success: false` → 에러 메시지를 사용자에게 전달 후 재실행

---

## content.json 형식

```json
{
  "blocks": "마크다운 텍스트 전체 (헤딩, 리스트, 코드, 테이블 등 모두 지원)"
}
```

---

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/notion:add-personal-note/scripts/notion-note.py list --limit 10
```
