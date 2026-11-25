# 규칙 정본 지도

규칙별 정본 위치를 정한 지도입니다. 원칙(정본 1곳, 메모리에는 사실만, 개정 기준)은 전역 CLAUDE.md "규칙 생애주기"가 정본입니다.

## 정본과 로딩 방식

| 규칙 범주 | 정본 | 로딩 |
|-----------|------|------|
| 우선순위, 응답 기본값, 조건부 덧붙임, 작업 원칙, 하드 가드레일, 라우팅 표, 규칙 생애주기, Artifact·다이어그램 시각 규칙(기울임 금지 등) | `~/.claude/CLAUDE.md` | 상시 |
| 문제와 가설, 원인 가설 단계, 근본 원인 사슬(5 Whys), 검증 목록(항목·칸·합의·날짜 자격), 판정과 갱신 | `docs/hypothesis-first.md` | Read (CLAUDE.md 라우팅 표) |
| 검증 시나리오·테스트 케이스·DoD 판정 기준 문장 | `docs/verification-scenario.md` | Read |
| Task·업무 노트·Tech Spec의 Goals·Key Result·Todo 구분과 문체 | `skills/task:keyresult/SKILL.md` | Skill (capture·eng-note·tech-spec·grill-me가 포인터로 호출) |
| 플랜 섹션 순서·이름, 플랜 TODO 운영(`plan-todo.py`) | `docs/plan-format.md` | 훅 (PostToolUse `EnterPlanMode`) |
| 코드 작성·리팩터링·테스트 품질 | `docs/code-quality-convention.md` | Read |
| DevOps·SOCRA 작업 방식(GitOps, prod 체크리스트, 알럿·runbook, ROI, 내재화 가중치, 레거시 재설계) | `docs/devops-work.md` | 훅 (SessionStart, 인프라 레포 cwd) |
| kubectl context·네임스페이스·리포지토리 지도 | `docs/kubectl-contexts.md` | 훅 (devops-work와 함께) |
| Notion·Claude Docs 문서 문장·포맷 | `docs/notion-writing-style.md` | Read |
| Jira 티켓 유형별 템플릿과 PLE 필드 관례 | `docs/jira-ticket-template.md` | Read (CLAUDE.md 라우팅 표, weekly:plan) |
| 이력서 bullet | `docs/resume-format-convention.md` | Read (task:review, resume:bullet) |
| 경력기술서·성과평가 PAR | `docs/par-format-convention.md` | Read |
| 면접 준비·학습 세션·브리핑 같은 개인 업무 방식 | `docs/personal-workflow.md` | Read |
| 팀 운영 표준(GitOps 가드레일, 팀 원칙, wiki 규칙) | kubernetes 레포 `CLAUDE.md`, `devops-wiki/` | 프로젝트 로딩 (팀 소유, 개인 문서가 바꾸지 않음) |
| 사실·결정 이력·사례(누가 무엇을 언제 정했나, 장애 기록) | 프로젝트 auto memory | 상시 (MEMORY.md는 목차만) |

## 층 경계

- 개인 문서(`~/.claude/`)는 팀 문서(`devops-wiki/`)를 가리킬 수 있습니다. 팀 문서는 개인 문서를 가리키지 않습니다. 팀원 세션에는 개인 문서가 없기 때문입니다.
- 전역 CLAUDE.md는 특정 프로젝트의 경로나 메모리 파일을 가리키지 않습니다. 프로젝트 전용 규칙은 훅이 그 프로젝트에서만 주입하는 docs에 둡니다.
- 다른 문서를 장 번호("9장", "8장")로 가리키지 않고 섹션 이름으로 가리킵니다.

## 제거한 규칙 (다시 제안하지 않음)

| 규칙 | 제거일 | 이유 |
|------|--------|------|
| Source-First: 원리 질문에 답하기 전 웹 1차 자료 대조 강제 | 2026-09-11 | 모든 원리 질문을 느리게 만드는 병목. 검증은 `/review`를 명시 호출할 때만 한다 |
| 복귀 재브리핑 훅(15분 임계) | 2026-10-17 | 장시간 턴마다 발화해 노이즈가 됨 |
| 로컬 Todo 시스템(todo_store, TUI, todo 스킬) | 2026-09-18 | 할 일을 Notion Task로 단일화 |

## 충돌 해소 기록 (2026-10-22)

결정은 아래 정본 문장에 반영했습니다. 이 표는 어디에 반영했는지만 기록합니다(내용은 정본을 봅니다).

| 충돌 | 반영한 정본 |
|------|-------------|
| 두괄식 대 "문제와 가설 먼저" | CLAUDE.md "Hypothesis-First" |
| 간결한 답 대 위험 3종·알럿·runbook·트레이드오프 자동 첨부 | CLAUDE.md "우선순위", "응답 기본값", "조건부 덧붙임"; devops-work.md "변경을 제안하거나 만들 때" |
| 말미 제안 1줄 대 여러 제안 규칙 | CLAUDE.md "조건부 덧붙임" 응답 말미 행 |
| 정정·한계 대 "물어본 것만" | CLAUDE.md "응답 기본값" |
| 학습 경로 우선 대 사용자 선택 | devops-work.md "내재화 가중치" |
| 최소 변경 대 전면 재설계 | CLAUDE.md "하드 가드레일" Surgical Changes; devops-work.md "레거시 재설계" |
| 메커니즘 깊이 대 소스 다이빙 금지 | CLAUDE.md "응답 기본값" |
| 첫 줄 추천 하나 대 조건부 추천 | CLAUDE.md "응답 기본값"; plan-format.md "옵션 비교" |
| 경량 등급 대 필수 필드 | CLAUDE.md "Hypothesis-First"; hypothesis-first.md "언제 쓰는가" |
| 이해 점검 발동 범위(응답 대 플랜) | CLAUDE.md "조건부 덧붙임"; personal-workflow.md "이해 점검 형식"; plan-format.md "이해 점검 섹션" |
| 사용자의 빠른 길 선택 대 prod 체크리스트 | devops-work.md "변경을 제안하거나 만들 때" |
| 전역 이모지 규칙 대 프로젝트 CLAUDE.md 출력 형식 | CLAUDE.md "응답 기본값", "우선순위" |
| 응답 격식체 대 Notion 평서체 | CLAUDE.md "응답 기본값"; notion-writing-style.md "문장" |
| 새 위험을 둘 곳(한계 대 위험과 롤백) | plan-format.md "위험과 롤백" |
| 세션 = 작업 1개 대 연속 작업 | CLAUDE.md "세션과 플랜" |
