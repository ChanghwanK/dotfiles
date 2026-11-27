---
name: skills:manage
description: |
  스킬 생명주기 관리 (CRUD + validate).
  사용 시점: (1) 새 스킬 생성/수정/삭제, (2) 스킬 목록 조회 또는 구조 검증.
  트리거 키워드: "스킬 만들어줘", "스킬 생성", "스킬 수정", "스킬 삭제",
  "스킬 검증", "스킬 목록", "skill create", "skill update",
  "skill delete", "skill show", "/skills:manage".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py *)
  - Read
  - Write
  - Edit
  - Glob
---

# Skill Manager

파일 조작·검증은 `manage_skill.py`가 하고, Claude는 내용(SKILL.md body, 스크립트 로직)만 쓴다.

## 핵심 원칙

- create/update 뒤에는 반드시 `validate`로 확인한다
- delete는 hard delete(복구 불가, 백업 없음)다. 실행 전 사용자 동의가 필수다
- Python 스크립트는 표준 라이브러리만 쓴다(`yaml`, `requests` 등 금지)

## Scope

모든 subcommand는 `--scope user|project`(`-s`)를 받는다. 생략하면 CWD에 `.claude/skills/`가 있으면 `project`, 없으면 `user`다.
프로젝트 디렉토리에서 전역 스킬을 다루려면 `--scope user`를 명시한다.

| Scope | 디렉토리 | allowed-tools 스크립트 경로 (create가 적용) |
|-------|---------|------|
| `user` | `~/.claude/skills/` | `/Users/changhwan/.claude/skills/<name>/scripts/...` (절대 경로) |
| `project` | `$PWD/.claude/skills/` | `${CLAUDE_PROJECT_DIR}/.claude/skills/<name>/scripts/...` |

## 워크플로우 분기

목록·상세(list, show) → Read / 생성 → Create / 검증 → Validate / 리뷰·점수·평가 → Review / 수정 → Update / 삭제 → Delete

## Read

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py list          # 결과를 | 이름 | 설명 | 모델 | 스크립트 수 | 표로 출력
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py show <name>   # frontmatter, 파일 목록, 검증 상태
```

## Create

### Step 1: 요구사항 파악

- [ ] 스킬이 해결하는 문제가 명확한가(모호하면 묻는다)
- [ ] `list`로 기존 스킬과 책임 범위가 겹치지 않는가
- [ ] 스크립트가 필요한가(API 호출 → workflow, 지식 정리 → reference, CLI 래핑 → tool)
- [ ] 병렬 Sub-Agent가 필요한가(독립적 데이터 수집 등 → `--with-agents`)

대화에서 명확하지 않으면 확인한다: 이름(명명 규칙은 `references/skill-conventions.md` 0절), 한국어 설명(사용 시점 포함), 타입(기본 workflow), 모델.

#### Sub-Agent 모델 배정 (Claude가 판단)

사용자에게 묻지 않고 각 agent 출력물에 필요한 추론 수준으로 고른다. 결정 근거를 한 줄로 알리고, sonnet ↔ opus 경계가 모호할 때만 단답형으로 묻는다.

| 모델 | 작업 성격 신호 |
|------|----------------|
| `haiku` | 정형 입력의 단순 변환·추출·필드 매핑·포맷팅 (예: Notion API → JSON 추출) |
| `sonnet` (기본) | 다단계 분석, 파일 탐색, 패턴 매칭, 일반 코드 분석 (예: PR 변경 패턴 분석) |
| `opus` | 트레이드오프 평가, 원칙 해석, 아키텍처 판단, 다중 신호 종합 (예: 대안 비교 + 추천) |

### Step 2: 스캐폴딩 (스크립트)

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py create <name> --scope user|project \
  --description "한국어 설명. 사용 시점: (1) ..." --model sonnet --type workflow \
  [--with-agents "collector:haiku,strategist:opus,parser"]
```

`--with-agents`(형식 `role[:model]`, 생략 시 sonnet)는 `agents/agent-<role>.md`를 만들고 상단에 `Recommended model`을 적으며
allowed-tools에 `Agent`를 넣는다. Agent 호출 시 그 모델을 `model` 인자로 명시한다.

### Step 3: 내용 작성 (Claude)

`references/templates.md`의 타입별 템플릿을 참고한다.

1. SKILL.md의 TODO placeholder를 실제 내용으로 바꾼다(description, allowed-tools 경로, `TODO_script.py` 참조 포함)
2. 스크립트가 필요하면 `scripts/TODO_script.py`를 실제 이름으로 바꿔 구현한다(`references/skill-conventions.md` 3절)
3. body는 `references/skill-conventions.md` 5절을 따른다: 트리거는 description에만, body 500줄 이하, 마지막에 검증 Step,
   관심사 분리(반복 bash → `scripts/`, 15줄 이상 출력 템플릿 → `assets/`, 10줄 이상 Agent 프롬프트 → `agents/`, raw 시스템 명령은 스크립트로 래핑)
4. Agent 프롬프트는 `agents/agent-<역할>.md`에 `{변수명}` placeholder로 쓰고, body에 Read + 치환 지시를 둔다(`references/templates.md` "Agent 사용 시 참고 패턴")

### Step 4: 검증

`python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py validate <name>`을 돌리고, 실패 항목을 고쳐 다시 돌린다.

## Validate

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py validate <name>
```

`valid: true`이고 warnings가 없으면 끝이다. warnings는 품질 개선 사항이므로 가능하면 해소한다. `valid: false`면 실패한 `checks`의
`detail`대로 고치고(Edit 또는 `update-frontmatter`) 다시 돌린다. 판단이 필요한 check:

| check | 수정 방법 |
|-------|-----------|
| `no_unknown_fields` | 허용: name, description, model, effort, allowed-tools, license, metadata, disable-model-invocation. 그 외 제거 |
| `name_format` | `^[a-z0-9]+([:-][a-z0-9]+)*$`, 최대 64자, 디렉토리명과 일치 |
| `script_files_exist` | 스크립트를 만들거나 `update-frontmatter --remove-tool`로 경로 정리 |

TODO placeholder가 남아 있으면 warning이다(에러 아님).

## Review

`validate`(구조 통과/실패)와 별개로 BP·병렬성·하네스 점수와 정성 평가를 낸다.

### Step 1: 구조 점수 + 인벤토리

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py review <name>
```

출력: `overall_score`, `scores.{bp,parallelism,harness,quality}`(0~100), `findings_by_dimension`, `inventory`(body LOC, description 길이,
agents/scripts/references 목록, `inventory.agents`의 `Recommended model`).

### Step 1.5: Agent 모델 적합도 (Claude)

각 agent 파일을 Read해 Create의 모델 배정 표를 적용한다. 선언과 권장이 다르면 Step 3 리포트에 불일치로 적고
(예: `agent-extractor.md` 선언 `opus`, 권장 `haiku`), `model: null`은 "모델 미지정"으로 경고한다. 모호하면 1줄로 묻는다.

### Step 2: 정성 평가 (3개 Agent 병렬)

`overall_score < 90`이거나 사용자가 "심층 리뷰"를 요청했을 때만 한다. Step 1의 `inventory` JSON을 그대로 넘기고
단일 메시지에서 동시에 호출하며, 아래 `model` 인자를 반드시 전달한다.

- **A: BP 정성 평가** (`general-purpose`, `opus`): SKILL.md + Agent Skills BP 체크리스트 → progressive disclosure, description 정확도, scripts/references 분리도
- **B: 컨텍스트 효율** (`Explore`, `sonnet`): 스킬 디렉토리 전체 → 중복 콘텐츠, 미참조 references, body↔references 토큰 분포
- **C: 하네스 감사** (`general-purpose`, `sonnet`): scripts/*.py + SKILL.md → dry-run 누락, confirmation 부재, 멱등성 위반, allowed-tools 과대 권한

### Step 3: 통합 리포트

Agent 결과와 스크립트 점수를 표로 정리하고 우선순위 개선안을 낸다.

## Update

### Frontmatter (스크립트)

`--dry-run`으로 미리 본 뒤 적용한다.

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> --set-description "새 설명" --dry-run
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> --set-model sonnet
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> --add-tool "Bash(python3 /Users/changhwan/.claude/skills/<name>/scripts/new.py *)"
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> --remove-tool "Bash(old_tool *)"
```

### Body (Claude)

`show`로 상태를 보고 Read → Edit → validate(warnings 0까지)를 반복한다. 기존 `##`/`###` 구조를 유지하고, 요청 범위 밖의 body 전체 리팩토링은 하지 않는다.
스크립트 경로를 바꾸면 allowed-tools도 `update-frontmatter`로 함께 고친다.

## Delete

1. `python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py show <name>`으로 상태를 확인한다
2. `python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name> --dry-run`으로 지울 파일과 `referrers`(이 스킬 경로를 참조하는 다른 스킬·에이전트·docs)를 본다
3. 사용자에게 명시적으로 확인한다:
   ```
   스킬 '<name>'을 삭제합니다 (HARD DELETE: 복구 불가, 백업 없음).
   - 경로: <scope_dir>/<name>/
   계속할까요?
   ```
4. 동의를 받은 뒤 `python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name>`을 실행한다. 참조가 남아 있으면 스크립트가 거부하므로 참조를 먼저 정리한다.
   사용자가 참조를 남긴 채 지우라고 명시한 경우에만 `--force-referenced`를 붙인다
