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

## Update 워크플로우

### Frontmatter 수정 (스크립트)

```bash
# 설명 변경
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --set-description "새 설명"

# 모델 변경
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --set-model sonnet

# allowed-tools 추가
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py update-frontmatter <name> \
  --add-tool "Bash(python3 /Users/changhwan/.claude/skills/<name>/scripts/new.py *)"

# allowed-tools 제거
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
# 백업 포함 (기본)
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name>

# 백업 없이
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py delete <name> --no-backup
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
