# Shared Documentation

The files below are shared across all Claude Code sessions and agents.
Add a new `@` import line here whenever you add a document to ~/.claude/docs/.

<!-- @~/.claude/docs/example.md -->

## Registry

각 문서의 active import는 `CLAUDE.md`에서 관리한다 (여기서 중복 import하지 않는다).

### 상시 import (CLAUDE.md에서 @ import)

- `code-quality-convention.md`: 코드 작성·수정·리팩터링·테스트 전역 품질 기준
- `plan-format.md`: Plan 모드 출력 형식
- `kubectl-contexts.md`: K8s 컨텍스트·네임스페이스 맵·리포지토리·배포 워크플로우

### on-demand 참조 (전역 import 아님, 필요 시점에 Read)

- `notion-writing-style.md`: Notion 문서 문장 톤·문법 + 시각적 포맷·구조 기본값 (notion:add-* 스킬 + notion-review 에이전트가 참조, 2026-07-09 상시 import에서 전환)
- `plan-html-template.md`: Plan HTML 렌더링 템플릿 (plan-preview.sh 등 훅 스크립트가 소비, Claude는 읽지 않음)
- `resume-format-convention.md`: 이력서 work experience bullet 표준 포맷 (task:review 스킬 + notion-review 에이전트가 참조)
