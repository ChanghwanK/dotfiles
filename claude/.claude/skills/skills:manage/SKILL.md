---
name: skills:manage
description: |
  스킬 생명주기 관리 도구 (CRUD + validate + package).
  사용 시점: (1) 새 스킬 생성, (2) 스킬 목록/상세 조회, (3) 스킬 구조 검증,
  (4) 스킬 frontmatter 수정, (5) 스킬 삭제 (백업 포함), (6) .skill 패키지 생성.
  트리거 키워드: "스킬 만들어줘", "스킬 생성", "스킬 목록", "스킬 삭제", "스킬 검증",
  "skill create", "skill list", "skill manager", "/skill-manager".
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
    └─ "패키지", "배포", "package"          → Package 워크플로우
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

사용자에게 확인 (대화에서 명확하면 생략):
- **스킬 이름** (아래 명명 규칙 참고, 필수)
- **한국어 설명** (사용 시점 포함, 필수)
- **타입**: `workflow` | `reference` | `tool` (기본: workflow)
- **모델**: `sonnet` | `haiku` | 미지정

#### 스킬 명명 규칙

형식: `[namespace:]action[-target]`

**핵심 원칙**: 해당 플랫폼/도메인에 스킬이 2개 이상이면 colon namespace 사용, 1개뿐이면 flat 유지.

| 케이스 | 이름 형식 | 예시 |
|--------|-----------|------|
| 단독 범용 스킬 | `noun` 또는 `noun-noun` | `commit`, `learn`, `security-manager` |
| 플랫폼 스킬 2개+ | `platform:action` | `notion:eng`, `slack:send` |
| 워크플로우 단계 | `workflow:phase` | `daily:start`, `daily:review` |

**정의된 네임스페이스**:

| Namespace | 대상 플랫폼/도메인 | 현재 소속 스킬 |
|-----------|-------------------|---------------|
| `notion:` | Notion 플랫폼 | `notion:eng`, `notion:study`, `notion:private`, `notion:send-plan` |
| `obsidian:` | Obsidian vault | `obsidian:add-notes`, `obsidian:daily` |
| `slack:` | Slack 플랫폼 | `slack:send`, `slack:search` |
| `devops:` | DevOps 운영 | `devops:alert-review`, `devops:terraform-request`, `devops:gpu-analysis` |
| `daily:` | 일과 워크플로우 | `daily:start`, `daily:review` |

**제약**: lowercase only, 최대 64자, colon 최대 2개 (3 segment).

새 플랫폼 스킬 추가 시: "이 플랫폼에 기존 스킬이 있는가?" → 있으면 namespace 추가, 없으면 flat으로 시작.

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
1. `show` 명령으로 현재 내용 확인
2. Read 도구로 전체 파일 읽기
3. Edit 도구로 수정
4. validate로 확인

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

## Package 워크플로우

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py package <name>
```

validate 통과 → `.skill` ZIP 생성 → `~/.claude/skills/<name>.skill`

검증 실패 시 먼저 Validate 워크플로우로 수정한다.

---

## 주의사항

- `allowed-tools`에 지정된 스크립트 경로는 **절대 경로** 필수
- TODO placeholder가 남아 있으면 validate가 warning을 출력한다 (에러는 아님)
- 스킬 이름: `^[a-z][a-z0-9]*([:-][a-z0-9]+)*$` 형식, 최대 64자, colon 최대 2개
- Python 스크립트는 `yaml`, `requests` 등 서드파티 라이브러리 사용 금지
- delete는 기본적으로 백업을 생성하므로 실수로 삭제해도 복구 가능
