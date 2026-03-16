# Skill 작성 컨벤션

이 문서는 사용자의 스킬 아카이브(`~/.claude/skills/`)에서 관찰된 일관된 패턴을 정리합니다.
새 스킬을 만들 때 이 컨벤션을 준수하세요.

---

## 0. 명명 규칙 (Naming Convention)

### 기본 형식

```
[namespace:]action[-target]
```

| 항목 | 규칙 |
|------|------|
| 케이싱 | lowercase only |
| 단어 구분 | hyphen (`-`) |
| 도메인 구분 | colon (`:`) |
| Regex | `^[a-z][a-z0-9]*([:-][a-z0-9]+)*$` |
| 최대 길이 | 64자 |
| 최대 깊이 | colon 2개 (3 segment) — 예외적 상황에서만 |

### 네임스페이스 원칙

> **대상 플랫폼/도메인에 skill이 2개 이상이면 colon namespace를 사용한다. 1개뿐이면 flat으로 유지한다.**

| 기준 | 형식 | 예시 |
|------|------|------|
| 플랫폼에 skill 1개 | flat | `commit`, `learn` |
| 플랫폼에 skill 2개+ | `platform:action` | `notion:eng`, `slack:search` |
| 워크플로우 단계 | `workflow:phase` | `daily:start`, `daily:review` |

**네임스페이스 = 대상 플랫폼/도메인**:
- `notion:` — Notion에 쓰는 모든 스킬
- `obsidian:` — Obsidian vault에 쓰는 모든 스킬
- `slack:` — Slack 관련 모든 스킬
- `devops:` — DevOps 운영 워크플로우
- `daily:` — 일과 워크플로우 (워크플로우 성격이 강해 별도 유지)

### Action Part 패턴

| 패턴 | 용도 | 예시 |
|------|------|------|
| `namespace:verb` | 단일 액션 | `slack:search`, `slack:send` |
| `namespace:noun` | 콘텐츠 타입 | `notion:eng`, `notion:study` |
| `namespace:verb-noun` | 대상 명시 | `devops:alert-review`, `notion:send-plan` |
| 단독 `noun` | 범용 도구 | `commit`, `learn` |
| 단독 `noun-noun` | 복합 도구 | `gpu-analysis`, `security-manager` |

### 네임스페이스 맵

| Namespace | 기준 | 소속 스킬 |
|-----------|------|-----------|
| `notion` | Notion 플랫폼 | `notion:add-engineering-note`, `notion:study`, `notion:add-personal-note`, `notion:send-task-plan` |
| `obsidian` | Obsidian vault | `obsidian:note`, `obsidian:daily` |
| `slack` | Slack 플랫폼 | `slack:search`, `slack:send` |
| `devops` | DevOps 운영 | `devops:alert-review`, `devops:terraform-request`, `devops:gpu-analysis` |
| `daily` | 일과 워크플로우 | `daily:start`, `daily:review` |
| `learn` | 학습/성장 | `learn:interview`, `learn:growth-maker` |
| `skills` | 스킬 관리 | `skills:manage` |
| `schedule` | 일정 조회 | `schedule:view` |
| `work` | 업무 문서화 | `work:tech-spec` |
| (없음) | 단독/범용 | `commit`, `learn`, `security-manager`, `notify` |

### 미래 스킬 네이밍 예시

| 기능 | 이름 | 근거 |
|------|------|------|
| ArgoCD sync 자동화 | `devops:argocd-sync` | devops 그룹 |
| PR 리뷰 자동화 | `review-pr` | 단독 (git 그룹 아직 불필요) |
| Slack 채널 알림 전송 | `slack:notify` | slack 그룹 |
| Obsidian weekly 노트 | `obsidian:weekly` | obsidian 그룹 |
| Grafana 대시보드 생성 | `grafana:create-dashboard` | 신규 grafana 그룹 |
| 비용 분석 리포트 | `cost-report` | 단독 |
| Notion 검색 | `notion:search` | notion 그룹 |

---

## 1. Frontmatter 형식

```yaml
---
name: skill-name
description: |
  한국어로 작성된 설명.
  사용 시점: (1) 상황 1, (2) 상황 2.
  트리거 키워드: "키워드1", "키워드2", "/skill-name".
model: sonnet          # 선택사항 — haiku | sonnet | opus
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/<name>/scripts/<script>.py *)
  - Read
  - Write
  - Edit
---
```

**규칙:**
- `name`: 디렉토리명과 반드시 일치 (`^[a-z][a-z0-9]*([:-][a-z0-9]+)*$`, max 64자) — 콜론(`:`)으로 네임스페이스 구분 가능 (예: `notion:eng`, `slack:send`)
- `description`: 한국어, 블록 스칼라(`|`), 사용 시점과 트리거 키워드 포함
- `model`: 복잡한 워크플로우 → `sonnet`, 단순 작업 → `haiku`, 지정 없으면 기본값 사용
- `allowed-tools`: 스크립트는 **절대 경로** 필수 (`/Users/changhwan/...`)
- `license`, `metadata` 필드도 허용됨

---

## 2. 디렉토리 구조

```
~/.claude/skills/<name>/
├── SKILL.md           # 필수: 도메인 규칙 + 워크플로우
├── scripts/           # 실행 스크립트 (Python, Shell)
│   ├── <script>.py
│   └── <script>.sh
├── assets/            # 출력 템플릿, 정적 리소스
│   └── <template>.md
├── references/        # 보조 문서 (상세 가이드)
│   └── <doc>.md
└── agents/            # (선택) Sub-Agent 프롬프트 — Claude가 필요 시 생성
    └── agent-<역할>.md
```

- `scripts/`, `references/`, `assets/` 3개 디렉토리는 `create` 시 자동 생성됨
- `agents/` 디렉토리는 Claude가 Step 1 요구사항 분석에서 병렬 Sub-Agent가 필요하다고 판단할 때 수동 생성
- `.skill` 패키지는 `~/.claude/skills/<name>.skill` 위치에 생성됨

---

## 3. Python 스크립트 컨벤션

### stdlib only
```python
# 허용: argparse, json, pathlib, shutil, zipfile, re, os, datetime,
#        urllib.request, urllib.parse, http.client, subprocess 등
# 금지: requests, yaml, pydantic, boto3 등 서드파티 라이브러리
```

### argparse 서브커맨드 패턴
```python
#!/usr/bin/env python3
import argparse, json, sys

def cmd_subcommand(args):
    # ...
    print(json.dumps({"success": True, "result": "값"}, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("subcommand")
    p.add_argument("--option")

    args = parser.parse_args()
    {"subcommand": cmd_subcommand}[args.command](args)

if __name__ == "__main__":
    main()
```

### JSON 출력 형식
```python
# 성공
print(json.dumps({"success": True, "key": "value"}, ensure_ascii=False, indent=2))

# 실패 (+ sys.exit(1))
print(json.dumps({"success": False, "error": "오류 메시지"}, ensure_ascii=False, indent=2))
sys.exit(1)
```

---

## 4. 1Password 토큰 패턴

API 토큰은 하드코딩 금지. 두 가지 주입 방법:

### 방법 A: 환경 변수 (~/.secrets.zsh에서 로드)
```yaml
allowed-tools:
  - Bash(python3 /path/to/script.py *)
```

`~/.secrets.zsh`에 `export NOTION_TOKEN="..."` 정의 → `~/.zshenv`에서 source.
스크립트 내에서:
```python
token = os.environ.get("NOTION_TOKEN")
if not token:
    print(json.dumps({"success": False, "error": "NOTION_TOKEN not set"}))
    sys.exit(1)
```

### 방법 B: 스크립트 인수
```bash
TOKEN=$(op read "op://Employee/vault/item/field") python3 script.py --token "$TOKEN"
```

---

## 5. Body 작성의 5원칙

### 5.1 Progressive Disclosure (3단계 로딩)

Claude Code는 스킬을 3단계로 로드한다:

| 단계 | 컨텐츠 | 항상 로드? |
|------|--------|-----------|
| Frontmatter | `description`, `allowed-tools`, `model` | ✅ 항상 |
| Body | SKILL.md의 `---` 이후 본문 | 트리거 시 로드 |
| References | `references/` 하위 파일 | 명시적 참조 시 로드 |

**함의**: Description은 "언제 사용할지" 판단 기준. Body는 활성화 후 "무엇을/어떻게" 지시.

### 5.2 Description vs Body 역할 분리

- Description = **언제 사용할지** (트리거만)
- Body = **무엇을/어떻게 할지** (절차만)

나쁜 예 — Body에 트리거 설명 중복:
```
# My Skill

이 스킬은 Notion 업무 일지를 작성할 때 사용합니다.
```

좋은 예 — Body는 절차/결과만:
```
# My Skill

Notion 업무 일지 생성 → 내용 작성 → 완료 URL 출력.
```

### 5.3 500줄의 법칙

Body는 **500줄 이하**. 초과 시 `references/`로 분리하고 body에는 링크만:

```
## 상세 가이드

자세한 내용은 `references/advanced-guide.md` 참조.
```

Body = 목차 역할. 상세 절차/예시는 references에.

### 5.4 개념 설명 금지

Claude가 이미 아는 개념(JSON, REST API, kubectl, Docker 등)은 설명하지 않는다.
**프로젝트 고유 값**(엔드포인트, 토큰 경로, 클러스터명)만 포함.

| 자유도 | 처리 방식 |
|--------|-----------|
| Low (절차 고정) | 코드 블록으로 명시 |
| High (Claude 판단) | 지침/원칙만 제시 |

### 5.5 검증 루프 심기

워크플로우 마지막에 검증 Step을 MUST 포함. 구체적인 에러 메시지와 수정 방법 제시:

```
### Step N — 검증

실패 시:
- `error: missing field` → 필드 추가 후 재실행
- `error: invalid format` → 형식 확인 후 재실행
```

"항상" 대신 "MUST" 또는 "반드시" 사용 (Rule 5 자기준수).

### 5.6 관심사 분리

각 파일이 하나의 역할만 담당하도록 분리한다:

| 분리 대상 | Before (나쁜 예) | After (좋은 예) |
|-----------|-----------------|----------------|
| 반복 실행 bash (3줄 이상) | SKILL.md body에 inline bash | `scripts/env-init.sh` 추출, `allowed-tools`에 등록 |
| 출력 템플릿 (15줄 이상) | SKILL.md body에 markdown 템플릿 | `assets/template.md`로 분리, Read로 참조 |
| Raw 시스템 명령 | `Bash(brew *)` in allowed-tools | `Bash(bash .../scripts/init.sh *)` 래핑 |
| Agent 인라인 프롬프트 (10줄 이상) | SKILL.md body에 멀티라인 Agent 프롬프트 | `agents/agent-<역할>.md`로 분리, body에서 Read 참조 |

**판단 기준**:
- 3줄 이상의 반복 실행 bash → `scripts/*.sh`로 추출 (멱등성, `set -euo pipefail` 추가)
- 15줄 이상의 출력 형식/템플릿 → `assets/*.md`로 분리
- `allowed-tools`에 raw 시스템 명령(brew, apt, pip 등) 금지 → 스크립트로 래핑
- 10줄 이상의 Agent 인라인 프롬프트 → `agents/agent-<역할>.md`로 분리

**agents/ 디렉토리 규칙**:
- 파일 명명: `agent-{역할}.md` (lowercase, hyphen-case) — 예: `agent-notion-reader.md`, `agent-transcript-parser.md`
- 프롬프트 내 동적 값: `{변수명}` placeholder 사용 — 예: `{date}`, `{yesterday_note_path}`
- SKILL.md body에서 Read로 참조 후 변수 치환 지시 작성
- `allowed-tools` frontmatter에 `- Agent` 추가
- Claude가 Step 1 요구사항 분석에서 병렬 Sub-Agent 필요 여부를 판단하여 생성 (자동 스캐폴딩 없음)

**허용 패턴** (allowed-tools):
- `Bash(python3 /abs/path/scripts/*.py *)` — Python 스크립트 호출
- `Bash(bash /abs/path/scripts/*.sh *)` — Shell 스크립트 호출
- `Bash(kubectl *)` — kubectl은 예외적으로 직접 허용
- `Read`, `Write`, `Edit`, `Glob`, `Grep` — 비-Bash 도구

---

## 6. SKILL.md Body 구조

### Workflow 스타일 (eng-note, commit)
```markdown
# <Name> Skill

한 문장 설명.

---

## 핵심 원칙

- 원칙 1
- 원칙 2

---

## 워크플로우

### Step 1 — 단계명

설명

```bash
python3 /abs/path/to/script.py subcommand --option value
```

### Step 2 — ...

---

## 결과 출력 형식 (선택사항)

---

## 주의사항 (선택사항)
```

### Reference 스타일 (gpu-analysis)
```markdown
# <Name> Reference

---

## 도메인 지식

### 개념

---

## 사용 가이드

### 시나리오
```

### Tool 스타일 (send-plan)
```markdown
# <Name> Tool

---

## 사용법

---

## 옵션

---

## 주의사항
```

---

## 7. 스킬 타입 선택 가이드

| 타입 | 사용 시점 | 예시 |
|------|-----------|------|
| `workflow` | 여러 단계를 거치는 자동화 | eng-note, start-daily, commit |
| `reference` | 도메인 지식 + 도구 가이드 | gpu-analysis |
| `tool` | 단순 CLI 래퍼 | send-plan |

---

## 8. 언어 규칙

- **Description, 워크플로우 설명, 주의사항**: 한국어
- **코드, 명령, JSON 키, 변수명**: 영어
- **섹션 헤더**: 한국어 (예: `## 핵심 원칙`, `## 주의사항`)
- **Step 이름**: `### Step N — 한국어 설명`

---

## 9. 검증 체크리스트

스킬 완성 전 확인:

**구조 검증** (manage_skill.py validate로 자동 확인):
- [ ] `name` = 디렉토리명
- [ ] `description`에 사용 시점 + 트리거 키워드 포함
- [ ] `allowed-tools` 스크립트 경로가 실제로 존재
- [ ] TODO placeholder 없음
- [ ] body가 비어있지 않음
- [ ] Python 스크립트: stdlib only, JSON 출력

**품질 검증** (수동 확인):
- [ ] Description에만 "언제 사용할지" 기술. Body에 반복 없음 (Rule 2)
- [ ] Body 500줄 이하 (Rule 3)
- [ ] 범용 개념 설명 없음. 프로젝트 고유 값만 포함 (Rule 4)
- [ ] 워크플로우 마지막에 검증 Step 포함 (Rule 5)
- [ ] "항상" 대신 "MUST" 또는 "반드시" 사용 (Rule 5)
