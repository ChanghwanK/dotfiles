---
name: obsidian:note
description: |
  Claude와의 학습/개념 설명 대화 결과를 Obsidian 노트로 저장하는 스킬.
  태그로 학습 주제를 분류하고 작성 날짜(YYYY-MM-DD)를 자동으로 기록한다.
  사용 시점: (1) 개념 설명 요청 후 노트 저장, (2) 학습 내용 정리,
  (3) 특정 주제에 대한 참고 문서 생성.
  트리거 키워드: "obsidian 노트", "노트로 저장", "obsidian에 저장", "/obsidian:note", "옵시디언 노트".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---

# Obsidian Note Skill

현재 대화에서 학습/설명한 내용을 Obsidian Engineering notes 디렉토리에 마크다운 파일로 저장한다.

**노트 저장 경로**: `/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Engineering/notes`

## 핵심 원칙

- **대화 내용 기반**: 현재 대화에서 설명된 내용을 구조화된 마크다운으로 정리한다.
- **파일명 규칙**: `slugified-title.md` 형식으로 자동 생성된다 (날짜 prefix 없음).
- **태그 분류**: 학습 주제에 맞는 태그를 복수 선택한다.
- **날짜 자동화**: 오늘 날짜(YYYY-MM-DD)가 frontmatter의 `date` 필드에 자동 기록된다.
- **태그 기반 링크**: 노트 생성 시 같은 태그를 가진 기존 노트를 탐색하여 "관련 노트" 섹션에 wikilink로 자동 추가된다.

## 지원 태그 목록

아래 태그 중 적절한 것을 선택한다 (복수 가능, 대소문자 유지):

| 카테고리 | 태그 |
|----------|------|
| 인프라 | `Kubernetes`, `AWS`, `Terraform`, `Infra`, `Network` |
| 서비스 메시 | `Istio`, `Envoy`, `ServiceMesh` |
| 관측가능성 | `Observability`, `Grafana`, `Prometheus`, `Loki`, `Tracing` |
| AI/ML | `AI`, `Agent`, `GPU`, `LLM` |
| 개발 | `Engineering`, `Security`, `자동화`, `OS`, `Git` |
| 기타 | `Issue`, `Design`, `Architecture` |

새로운 태그가 필요한 경우 직접 추가해도 된다.

## 워크플로우

### Step 1 — 대화 내용 분석 및 마크다운 정리

현재 대화에서 핵심 내용을 추출하여 마크다운으로 작성한다:

```
# {제목}

## 핵심 개념

...

## 동작 원리

...

## 코드 예시 (있는 경우)

```코드```

## 정리

...
```

지원 마크다운 요소:
- 헤딩 (`#`, `##`, `###`)
- 불릿/숫자 리스트
- 코드 블록 (``` 구문)
- 테이블 (`| col1 | col2 |`)
- 인용 (`>`)
- 인라인 서식 (`**bold**`, `*italic*`, `` `code` ``)

### Step 2 — 제목과 태그 결정

- **제목**: 학습 주제를 간결하게 (예: `Kubernetes Init Container 라이프사이클`)
- **태그**: 위 태그 목록에서 1개 이상 선택

### Step 3 — content.json 작성

마크다운 본문을 `/tmp/obsidian-content.json`에 저장한다:

```json
{
  "blocks": "마크다운 전체 텍스트"
}
```

### Step 4 — 노트 생성 스크립트 실행

```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "제목" \
  --tags "Kubernetes,Infra" \
  --content-file /tmp/obsidian-content.json
```

### Step 5 — 결과 출력

스크립트의 JSON 응답을 파싱 후 사용자에게 출력:

```
Obsidian 노트가 생성되었습니다.
- 제목: {title}
- 태그: {tags}
- 날짜: {date}
- 파일: {filename}
- 관련 노트: {related_count}개 링크됨 (없으면 생략)
```

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py list --limit 10
```

## 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
- 파일이 실제로 생성되었는지 `filepath`로 확인
