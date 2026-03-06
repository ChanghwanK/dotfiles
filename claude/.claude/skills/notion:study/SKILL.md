---
name: notion:study
description: |
  Claude와의 학습 대화 내용을 Engineering DB에 Study 노트로 저장하는 스킬.
  사용 시점: (1) Claude와 기술 학습 세션 후 내용 정리, (2) 개념 학습 대화를 Notion에 기록,
  (3) 학습한 내용을 나중에 참고할 수 있도록 저장.
  트리거 키워드: "학습 노트", "study note", "공부한 거 저장", "학습 정리", "/study-note".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:study/scripts/notion-study-note.py *)
  - Write(/tmp/study-content.json)
---

# Study Note Skill

Claude와의 학습 대화를 Engineering DB `#Study` 그룹에 자동 저장하는 워크플로우.

## 핵심 원칙

- **대화 내용을 학습 노트로 정리**한다. 핵심 개념, 설명, 코드 예시를 추출한다.
- 스크립트만 호출한다. Notion MCP 도구 사용 금지 (토큰 효율).
- 토큰은 환경변수 `$NOTION_TOKEN` 사용 (`~/.secrets.zsh`에서 로드됨). fallback: `op read "op://Employee/Claude MCP - Notion-Personal/token"`
- 생성 후 URL을 반드시 출력한다.
- 제목에 `[#Study]` 접두사가 자동 추가된다.

## DB 스키마

**DB ID**: `17964745-3170-8030-bf01-e7f20a6e1bd7` (Engineering DB)

| 속성 | 타입 | 값 |
|------|------|-----|
| Title | title | `[#Study] 제목` |
| Group | select | `#Study` (고정) |
| Tag | multi_select | `#Kubernetes`, `#Network`, `#Istio`, `#Issue`, `#Infra`, `#Observabiliy`, `#Security`, `#자동화`, `#AI`, `#Agent`, `#OS`, `#Terraform`, `#AWS`, `#Engineering` |
| Created At | date | 오늘 날짜 |

## 워크플로우

### Step 1 — 대화 내용 분석 및 정리

현재 대화에서 학습한 내용을 마크다운으로 정리한다:
- 핵심 개념과 정의
- 동작 원리 / 메커니즘
- 코드 예시 (있다면)
- 비교/대조 표 (있다면)
- 핵심 요약 (Key Takeaways)

### Step 2 — 제목 및 태그 결정

- **제목**: 학습 주제를 간결하게 (예: "Kubernetes Init Container 라이프사이클")
- **태그**: 학습 주제에 맞는 태그 선택 (복수 가능)

### Step 3 — content.json 작성 후 페이지 생성

```bash
python3 /Users/changhwan/.claude/skills/notion:study/scripts/notion-study-note.py create \
  --title "제목" \
  --tag "#Kubernetes,#Infra" \
  --content /tmp/study-content.json
```

## content.json 형식

```json
{
  "blocks": "마크다운 텍스트 전체 (헤딩, 리스트, 코드, 테이블 등 모두 지원)"
}
```

## 최근 학습 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/notion:study/scripts/notion-study-note.py list --limit 10
```

## 결과 출력 형식

```
학습 노트가 생성되었습니다.
- 제목: [#Study] {title}
- 태그: {tags}
- URL: {url}
```

## 검증

스크립트 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 NOTION_TOKEN 확인, fallback: `op read "op://Employee/Claude MCP - Notion-Personal/token"`
- `invalid tag` → DB 스키마의 Tag 옵션 확인
- `success: false` → 에러 메시지를 사용자에게 전달 후 재실행
