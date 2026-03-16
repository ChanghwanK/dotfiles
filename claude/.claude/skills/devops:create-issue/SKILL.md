---
name: devops:create-issue
description: |
  대화 맥락을 분석하여 구조화된 GitHub Issue를 생성하는 워크플로우. 코드베이스 분석 → 영향도 파악 → Issue 본문 작성 → 생성.
  사용 시점: (1) 기능 변경/개선 이슈 등록, (2) Plan 모드 결과를 Issue로 전환, (3) 코드 분석 후 Breaking Change 이슈 생성.
  트리거 키워드: "이슈 생성", "GitHub issue", "issue 등록", "/devops:create-issue".
model: sonnet
allowed-tools:
  - mcp__github__create_issue
  - Read
  - Grep
  - Glob
  - Bash(git remote get-url origin)
---
# Create Issue

대화 맥락 또는 Plan 결과를 분석하여 구조화된 GitHub Issue를 생성한다.

---

## 핵심 원칙

- **맥락 기반 본문 생성**: 현재 대화/plan에서 배경, 변경 방향, 영향 범위를 자동 추출한다.
- **코드베이스 분석 필수**: 현재 구현 상태와 사용처를 조사한 후 본문에 반영한다.
- **사용자 확인 후 생성**: 최종 본문을 사용자에게 보여주고 확인받은 후 MCP 도구로 생성한다.

---

## 워크플로우

### Step 1 — 입력 수집

대화 맥락에서 다음을 파악한다 (명확하면 질문 생략):

- **리포지토리**: `owner/repo` (기본값: 현재 작업 디렉토리의 git remote)
- **제목**: `type(scope): 설명` 형식 권장 (예: `feat(webserver): Support multiple initContainers`)
- **라벨**: `enhancement`, `bug`, `documentation` 등
- **변경 대상**: 어떤 코드/설정이 변경되는지

리포지토리를 자동 감지한다:
```bash
git remote get-url origin
```

### Step 2 — 코드베이스 분석

변경 대상 코드의 현재 상태를 파악한다:

1. **현재 구현**: 대상 파일을 Read로 확인
2. **사용처 조사**: Grep/Glob으로 해당 기능을 사용하는 곳 탐색
3. **영향 범위**: Breaking Change 여부, 마이그레이션 필요 사용처 특정

### Step 3 — Issue 본문 작성

`assets/issue-template.md` 템플릿을 Read로 로드하고, 분석 결과를 채워 본문을 작성한다.

본문 구조:
- **배경**: 현재 제약 사항, 왜 변경이 필요한지
- **변경 방향**: 어떻게 바꿀 것인지 (코드 예시 포함)
- **구현 계획**: 수정 대상 파일과 변경 내용 목록
- **영향 범위**: Breaking Change 여부 + 마이그레이션 필요 사용처 표
- **수락 기준**: 체크리스트 형태

### Step 4 — 사용자 확인

작성된 본문을 사용자에게 보여주고 확인받는다.

### Step 5 — Issue 생성

MCP 도구로 GitHub Issue를 생성한다:
- `mcp__github__create_issue` 호출
- owner, repo, title, body, labels 전달

### Step 6 — 결과 출력

```
Issue 생성 완료.
- 제목: {title}
- URL: {html_url}
- 번호: #{number}
```

---

## 주의사항

- Plan 모드 결과(`~/.claude/plans/*.md`)가 있으면 해당 내용을 우선 참조한다.
- 코드 예시는 현재 코드와 변경 후 코드를 모두 포함한다.
- 사용처 조사 시 `kubernetes` 리포(`~/workspace/riiid/kubernetes`)도 탐색 대상에 포함한다.
