---
name: skills:manage
description: |
  스킬 생명주기 관리 (CRUD + validate + backup/restore).
  사용 시점: (1) 새 스킬 생성/수정/삭제, (2) 스킬 목록 조회 또는 구조 검증,
  (3) 삭제된 스킬 복원.
  트리거 키워드: "스킬 만들어줘", "스킬 생성", "스킬 수정", "스킬 삭제",
  "스킬 검증", "스킬 복원", "스킬 목록", "skill create", "skill update",
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

스킬 생명주기를 관리하는 메타 스킬. 기계적 작업(파일 I/O, 검증, 패키징)은
`manage_skill.py`가 처리하고, Claude는 내용 작성(SKILL.md body, 스크립트 로직)만 담당한다.

---

## 핵심 원칙

- **역할 분리**: 파일 조작 → 스크립트, 내용 작성 → Claude
- **검증 우선**: create/update 후 MUST validate로 확인
- **백업 보장**: delete는 기본적으로 `~/.claude/skills/.backups/`에 백업
- **절대 경로**: 스크립트 참조는 반드시 절대 경로 사용
- **stdlib only**: Python 스크립트는 표준 라이브러리만 사용

---

## 워크플로우 분기

사용자 요청을 분석해 아래 워크플로우 중 하나를 선택한다:

```
요청 분석
    │
    ├─ "목록", "어떤 스킬", "list"          → Read 워크플로우
    ├─ "상세", "보여줘", "show"             → Read 워크플로우
    ├─ "만들어줘", "생성", "create"         → Create 워크플로우
    ├─ "검증", "validate", "확인"           → Validate 워크플로우
    ├─ "리뷰", "review", "점수", "평가"     → Review 워크플로우
    ├─ "수정", "변경", "update"             → Update 워크플로우
    ├─ "삭제", "제거", "delete"             → Delete 워크플로우
    └─ "복원", "되돌려", "restore"          → Restore 워크플로우
```

---

## Read 워크플로우

### 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py list
```

결과를 표 형식으로 출력한다:
| 이름 | 설명 | 모델 | 스크립트 수 | 패키지 |

### 상세 조회

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py show <name>
```

frontmatter, 파일 목록, 검증 상태를 출력한다.

---

## Create 워크플로우

### Step 1 — 요구사항 파악

새 스킬 생성 전 다음 체크리스트를 반드시 확인한다:

- [ ] 스킬이 해결하는 문제가 명확한가? (모호하면 사용자에게 질문)
- [ ] `list`로 기존 스킬 확인 — 책임 범위가 겹치지 않는가?
- [ ] 스크립트가 필요한가? (API 호출 → workflow, 지식 정리 → reference, CLI 래핑 → tool)
- [ ] 병렬 Sub-Agent가 필요한가? (독립적 데이터 수집, 병렬 처리 등 → Step 3에서 `agents/` 생성)

#### Sub-Agent가 필요한 경우 — 모델 자동 배정 (Claude 책임)

Claude는 각 Sub-Agent의 작업 성격을 분석하여 **명시적으로** 모델을 선택한다.
사용자에게 모델을 묻지 말고, 아래 분류 신호로 직접 판단한다.

**분류 rubric:**

| 모델 | 작업 성격 신호 |
|------|----------------|
| `haiku` | 입력이 구조화/정형. 단순 변환·추출·필드 매핑·정규화·포맷팅. 판단 요소 거의 없음 |
| `sonnet` (기본) | 다단계 분석, 파일 시스템 탐색, 패턴 매칭, 일반 코드 분석, 텍스트 가공 |
| `opus` | 트레이드오프 평가, BP/원칙 해석, 아키텍처 판단, 우선순위 결정, 다중 신호 종합, 모호한 도메인 추론 |

**판단 절차:**
1. 각 agent 역할의 **출력물**을 머릿속으로 그려본다.
2. "이 출력을 만들려면 어느 정도의 추론이 필요한가?" 질문.
3. rubric의 신호와 매칭 → 모델 결정 + **결정 근거 한 줄을 사용자에게 알림**.
4. **모호하면** (sonnet ↔ opus 사이가 불명확): 작업을 한 줄 요약하고 사용자에게 *단답형*으로 물어본 뒤 진행.

**예시 분류:**
- `notion-fetcher` (Notion API → JSON 추출) → `haiku` (구조화 추출)
- `code-reviewer` (PR 변경사항 패턴 분석) → `sonnet` (일반 코드 분석)
- `architect` (트레이드오프 비교 + 추천) → `opus` (판단 집약적)
- `log-summarizer` (10MB 로그에서 에러 요약) → `sonnet`/`opus` 모호 → 사용자에게 질문

이후 사용자에게 확인 (대화에서 명확하면 생략):
- **스킬 이름** (아래 명명 규칙 참고, 필수)
- **한국어 설명** (사용 시점 포함, 필수)
- **타입**: `workflow` | `reference` | `tool` (기본: workflow)
- **모델**: `sonnet` | `haiku` | 미지정

#### 스킬 명명 규칙

`references/skill-conventions.md` Section 0 "명명 규칙" 참조. 형식: `[namespace:]action[-target]`, lowercase only, 최대 64자.

### Step 2 — 스캐폴딩 생성 (스크립트)

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py create <name> \
  --description "한국어 설명. 사용 시점: (1) ..." \
  --model sonnet \
  --type workflow

# 병렬 Sub-Agent가 필요한 경우 (Step 1 체크리스트에서 판단)
# 형식: role[:model], model ∈ {haiku, sonnet, opus}, 생략 시 sonnet
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py create <name> \
  --description "..." \
  --type workflow \
  --with-agents "collector:haiku,strategist:opus,parser"
# → agents/agent-collector.md (haiku 추천), agent-strategist.md (opus 추천), agent-parser.md (sonnet 기본)
# → frontmatter allowed-tools에 'Agent' 자동 주입
# → 각 agent .md 상단에 'Recommended model' 표기 (Claude는 Agent 호출 시 model 인자로 명시)

# 모델 선택 규칙:
#   haiku  — 단순 변환/추출/형식화 (예: JSON 필드 추출, 텍스트 정규화)
#   sonnet — 일반 분석/패턴 매칭/파일 탐색 (기본값)
#   opus   — 깊은 판단/BP 해석/아키텍처 설계 (정성 평가, 트레이드오프 분석)
```

### Step 3 — 내용 작성 (Claude)

`references/templates.md`의 해당 타입 템플릿을 참고하여:

1. **SKILL.md 수정** — TODO placeholder를 실제 내용으로 교체
   - frontmatter: description 완성, allowed-tools 경로 수정
   - body: 핵심 원칙, 워크플로우 단계, 주의사항 작성
   - `TODO_script.py` 참조를 실제 스크립트명으로 변경

2. **스크립트 작성** (필요한 경우)
   - `scripts/TODO_script.py` → `scripts/<actual>.py`로 이름 변경 후 구현
   - `references/skill-conventions.md` Python 컨벤션 준수

3. **Body 품질 확인** — `references/skill-conventions.md` Section 5 "Body 작성의 5원칙" 준수
   - Description에만 "언제 사용할지" 기술. Body에 반복 금지
   - Body 500줄 이하. 초과 시 `references/`로 분리
   - 개념 설명 대신 코드 블록/예시 사용
   - 워크플로우 마지막에 검증 Step MUST 포함

4. **관심사 분리** — inline bash → `scripts/`, 출력 템플릿 → `assets/`
   - 3줄 이상의 반복 실행 bash → `scripts/*.sh`로 추출 (멱등성, `set -euo pipefail`)
   - 15줄 이상의 출력 형식/템플릿 → `assets/*.md`로 분리
   - `allowed-tools`에 raw 시스템 명령 금지 → 스크립트로 래핑

5. **Agent 프롬프트 작성** (Step 1에서 병렬 Sub-Agent 필요로 판단된 경우)
   - `agents/` 디렉토리를 생성하고 Agent별 프롬프트 파일 작성
   - 파일 명명: `agent-<역할>.md` (lowercase, hyphen-case)
   - 프롬프트 내 동적 값은 `{변수명}` placeholder 사용
   - SKILL.md body에서 Read 참조 + 변수 치환 지시 작성
   - frontmatter `allowed-tools`에 `- Agent` 추가
   - 상세 패턴: `references/templates.md` "Agent 사용 시 참고 패턴" 섹션 참조

### Step 4 — 검증 (스크립트)

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py validate <name>
```

검증 실패 항목을 수정한 후 다시 validate.

---

## Validate 워크플로우

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py validate <name>
```

`valid: false`인 경우:
1. 실패한 `checks` 항목 확인
2. 각 항목 수정 (Edit/Write 도구 또는 update-frontmatter)
3. 재검증

### 성공 시

`valid: true, warnings: []` 확인. warnings가 있으면 품질 개선 사항이므로 가능하면 해소.

### 실패 시 체크별 수정 가이드

| check | 수정 방법 |
|-------|-----------|
| `skill_md_exists` | 스킬 디렉토리에 SKILL.md 생성 |
| `frontmatter_present` | SKILL.md 최상단에 `---` 블록 추가 |
| `required_fields` | frontmatter에 name/description 추가 |
| `no_unknown_fields` | 허용: name, description, model, allowed-tools, license, metadata. 그 외 제거 |
| `name_matches_dir` | name 값을 디렉토리명과 일치시키기 |
| `name_format` | `^[a-z0-9]+([:-][a-z0-9]+)*$`, 최대 64자 |
| `description_not_empty` | 사용 시점 + 트리거 키워드 포함한 설명 작성 |
| `script_files_exist` | 스크립트 생성 또는 `update-frontmatter --remove-tool`로 경로 정리 |
| `body_not_empty` | body에 워크플로우/내용 작성 |

---

## Review 워크플로우

`validate`(구조 통과/실패)와 별개로, BP/병렬성/하네스 3개 차원의 **점수**와
정성 평가를 산출한다.

### Step 1 — 구조 점수 + 인벤토리 (스크립트)

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py review <name>
```

출력:
- `overall_score` / `scores.{bp,parallelism,harness,quality}` (0~100)
- `findings_by_dimension` — 차원별 warnings/info
- `inventory.agents` — 각 agent 파일에서 추출한 `Recommended model` (haiku/sonnet/opus/null)
- `inventory` — body LOC, description 길이, agents/scripts/references 파일 목록

### Step 1.5 — Agent 모델 적합도 평가 (Claude 책임)

`inventory.agents`에 각 agent 파일과 선언된 모델이 포함되어 있다.
Claude는 다음 절차로 적합도를 직접 평가한다:

1. 각 agent 파일을 Read하여 **역할 설명 + 절차**를 확인
2. Create 워크플로우 Step 1의 모델 분류 rubric을 적용
3. 선언된 모델과 권장 모델이 다르면 통합 리포트(Step 3)에 **불일치 항목**으로 명시
   - 예: `agent-extractor.md` → 선언 `opus`, 권장 `haiku` (단순 JSON 추출 작업)
4. `model: null`인 agent 파일 → "모델 미지정" 경고
5. 모호한 케이스는 사용자에게 1줄 질문 후 진행

### Step 2 — 정성 평가 (3개 Agent 병렬)

`overall_score < 90` 또는 사용자가 "심층 리뷰"를 요청한 경우에만 진행한다.
Step 1의 `inventory`를 입력으로 하여 아래 3개 Agent를 **단일 메시지에서 동시 호출**:

- **Agent A — BP 정성 평가** (subagent_type: `general-purpose`, **model: `opus`**)
  - 이유: BP 해석 + 우선순위 판단이 필요한 정성 평가
  - 입력: SKILL.md 본문 + Anthropic Agent Skills BP 체크리스트
  - 출력: progressive disclosure / description 정확도 / scripts vs references 분리도

- **Agent B — 컨텍스트 효율 분석** (subagent_type: `Explore`, **model: `sonnet`**)
  - 이유: 파일 시스템 탐색 + 토큰 분포 계산 (기본 분석 작업)
  - 입력: skill 디렉토리 전체
  - 출력: 중복 콘텐츠, 미참조 references, body↔references 토큰 분포

- **Agent C — 하네스 감사** (subagent_type: `general-purpose`, **model: `sonnet`**)
  - 이유: 코드 패턴 매칭 + 알려진 안티패턴 검출 (기본 분석 작업)
  - 입력: scripts/*.py + SKILL.md
  - 출력: dry-run 누락, confirmation 부재, 멱등성 위반 가능성, allowed-tools 과대 권한

각 Agent에 인벤토리 JSON을 그대로 전달하여 부모 컨텍스트 중복 로드를 회피한다.
Agent tool 호출 시 위 명시된 `model` 인자를 반드시 전달한다.

### Step 3 — 통합 리포트

3개 Agent 결과 + 스크립트 점수를 표 형식으로 정리하고, 우선순위 개선안 제시.

---

## Update 워크플로우

### Frontmatter 수정 (스크립트)

`--dry-run`으로 변경 미리보기 후 적용을 권장한다.

```bash
# 미리보기 (write 안 함)
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --set-description "새 설명" --dry-run

# 실제 적용
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --set-description "새 설명"

# 모델 변경
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --set-model sonnet

# allowed-tools 추가/제거
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --add-tool "Bash(python3 /Users/changhwan/.claude/skills/<name>/scripts/new.py *)"
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --remove-tool "Bash(old_tool *)"
```

### Body 수정 (Claude)

SKILL.md body는 Claude가 Edit 도구로 직접 수정한다:
1. `show` 명령으로 현재 내용 + validation 상태 확인
2. Read 도구로 전체 파일 읽기
3. Edit 도구로 수정
4. validate로 확인 — warnings 0개가 될 때까지 반복

수정 범위별 가이드:
- **섹션 추가**: 기존 구조(##/### 패턴) 유지, 워크플로우 끝에 삽입
- **원칙/주의사항 변경**: 핵심 원칙 섹션만 수정, body 전체 리팩토링 금지
- **스크립트 경로 변경**: frontmatter `allowed-tools`도 함께 `update-frontmatter`로 수정

---

## Delete 워크플로우

### Step 1 — 현재 상태 확인

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py show <name>
```

### Step 2 — 사용자 동의 요청

삭제 전 사용자에게 확인:
```
스킬 '<name>'을 삭제합니다.
- 경로: ~/.claude/skills/<name>/
- 백업 위치: ~/.claude/skills/.backups/<name>-<timestamp>/

계속할까요?
```

### Step 3 — 삭제 실행

```bash
# 미리보기 — 어떤 파일이 삭제되는지 확인 (write 안 함)
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name> --dry-run

# 백업 포함 (기본)
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name>

# 백업 없이 — 영구 손실 방지를 위해 --confirm-no-backup 추가 필수
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name> \
  --no-backup --confirm-no-backup
```

---

## Restore 워크플로우

실수로 삭제한 스킬을 백업에서 복원한다.

### 백업 목록 확인

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py restore <name> --list
```

### 최신 백업으로 복원

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py restore <name>
```

- 동일 이름의 스킬이 이미 존재하면 에러 — 덮어쓰기 방지
- 복원 후 자동 validate 실행

---

## 주의사항

- `allowed-tools`에 지정된 스크립트 경로는 **절대 경로** 필수
- TODO placeholder가 남아 있으면 validate가 warning을 출력한다 (에러는 아님)
- 스킬 이름: `^[a-z][a-z0-9]*([:-][a-z0-9]+)*$` 형식, 최대 64자, colon 최대 2개
- Python 스크립트는 `yaml`, `requests` 등 서드파티 라이브러리 사용 금지
- delete는 기본적으로 백업을 생성하므로 실수로 삭제해도 복구 가능
