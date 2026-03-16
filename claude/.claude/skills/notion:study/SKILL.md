---
name: notion:study
description: |
  Claude와의 학습 대화 내용을 Obsidian 노트로 저장하는 스킬 (obsidian:note로 리다이렉트).
  학습 노트는 Obsidian(지식 저장소)에 저장한다. Notion은 업무 기록 전용.
  사용 시점: (1) Claude와 기술 학습 세션 후 내용 정리, (2) 개념 학습 대화를 Obsidian에 기록,
  (3) 학습한 내용을 나중에 참고할 수 있도록 저장.
  트리거 키워드: "학습 노트", "study note", "공부한 거 저장", "학습 정리", "/study-note".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---

# Study Note Skill

> **리다이렉트 안내**: 학습 노트는 Obsidian에 저장합니다 (Obsidian = 지식, Notion = 업무).
> 이 스킬은 내부적으로 `obsidian:note` 워크플로우를 실행합니다.

Claude와의 학습 대화를 Obsidian `02. Notes/engineering/`에 자동 저장하는 워크플로우.

## 핵심 원칙

- **대화 내용을 학습 노트로 정리**한다. 핵심 개념, 설명, 코드 예시를 추출한다.
- `obsidian-note.py` 스크립트를 통해 Obsidian에 저장한다.
- aliases를 자동 추출하여 Quick Switcher 검색성을 높인다.
- 생성 후 파일 경로를 반드시 출력한다.

## 워크플로우

### Step 1 — 대화 내용 분석 및 정리

현재 대화에서 학습한 내용을 마크다운으로 정리한다:
- 핵심 개념과 정의
- 동작 원리 / 메커니즘
- 코드 예시 (있다면)
- 비교/대조 표 (있다면)
- 핵심 요약 (Key Takeaways)

### Step 2 — 제목, 태그, aliases 결정

- **제목**: 학습 주제를 간결하게 (예: "Kubernetes Init Container 라이프사이클")
- **태그**: `domain/kubernetes`, `domain/observability` 등 `domain/` 네임스페이스 사용
- **aliases**: 검색 키워드 (약어, 한/영 양방향, 증상 키워드 등)

### Step 3 — content.json 작성 후 노트 생성

```json
// /tmp/obsidian-content.json
{
  "title": "제목",
  "tags": ["domain/kubernetes"],
  "aliases": ["키워드1", "키워드2"],
  "type": "learning-note",
  "category": "engineering",
  "body": "마크다운 본문 전체"
}
```

```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --input /tmp/obsidian-content.json
```

## 결과 출력 형식

```
학습 노트가 생성되었습니다.
- 파일: 02. Notes/engineering/{slug}.md
- 제목: {title}
- 태그: {tags}
- aliases: {aliases}
```

## 검증

스크립트 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `success: false` → 에러 메시지를 사용자에게 전달 후 재실행
- 저장 경로 오류 → `02. Notes/engineering/` 디렉토리 존재 확인
