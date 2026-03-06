---
name: notion:send-task-plan
description: |
  Plan 파일(.claude/plans/*.md)을 Notion 페이지에 전송하는 스킬.
  사용 시점: (1) 설계 완료 후 Notion에 공유, (2) plan 문서를 팀원과 공유.
  트리거 키워드: "send-plan", "plan 전송", "plan 노션으로", "plan 보내줘".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:send-task-plan/scripts/notion-plan.py *)
  - Glob
---

# Send Plan Skill

Plan 모드에서 작성한 설계 문서(`.claude/plans/*.md`)를 Notion 페이지에 전송하는 워크플로우.

---

## 핵심 원칙

- 스크립트만 호출한다. Notion MCP 도구는 사용하지 않는다 (토큰 효율).
- Read tool로 plan 파일 내용을 직접 읽지 않는다 — 스크립트가 파일을 읽는다.
- 전송 전 반드시 사용자에게 대상 파일과 URL을 확인한다.

---

## 워크플로우

### Step 1: Plan 파일 확인

사용자가 파일 경로를 제공하지 않으면, Glob 도구로 plan 파일을 탐색한다:
- 패턴: `.claude/plans/*.md`

파일 목록을 보여주고 어떤 파일을 전송할지 선택 요청.

### Step 2: Notion 페이지 URL 확인

사용자에게 전송할 Notion 페이지 링크를 요청한다.

지원 URL 형식:
- `https://www.notion.so/workspace/Title-{32hex}`
- `https://www.notion.so/{UUID}`
- UUID 직접 입력: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### Step 3: 전송 실행

```bash
python3 /Users/changhwan/.claude/skills/notion:send-task-plan/scripts/notion-plan.py send \
  --url "<notion-page-url>" \
  --file "<plan-file-path>"
```

### Step 4: 결과 보고

JSON 응답 파싱 후 결과 출력:

**성공 시:**
```
Notion 페이지에 전송 완료.
- 전송된 블록 수: {blocks_sent}
- 배치 횟수: {batches}
- 페이지 ID: {page_id}
```

**실패 시:**
```
전송 실패: {error}
```

### Step 5: 검증

스크립트 응답의 JSON을 반드시 파싱하여 확인한다.

실패 시:
- `page not found` → URL/UUID 형식 재확인
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 NOTION_TOKEN 확인
- `success: false` → 에러 메시지를 사용자에게 전달

---

## Markdown → Notion 블록 매핑

| Markdown | Notion 블록 |
|----------|------------|
| `# H1`, `## H2`, `### H3` | heading_1, heading_2, heading_3 |
| `#### H4+` | bold paragraph |
| `- item`, `* item` | bulleted_list_item |
| `1. item` | numbered_list_item |
| `- [ ] task`, `- [x] task` | to_do (checked/unchecked) |
| ` ```lang ... ``` ` | code (언어 힌트 포함) |
| `> quote` | quote |
| `---` | divider |
| `\|table\|row\|` | paragraph (v1 단순화) |
| 일반 텍스트 | paragraph |
| `**bold**`, `*italic*`, `` `code` `` | rich_text annotations |

## 제한사항 (v1)

- 테이블: pipe-delimited 테이블은 단순 paragraph로 변환
- 중첩 리스트: 플랫하게 처리 (indent 무시)
- 이미지/링크: plain text로 처리
- 코드 블록 2000자 초과 시 자동 분할
