# Skill 작성 컨벤션

새 스킬을 만들 때 따르는 컨벤션이다. 구조 규칙은 `manage_skill.py validate`가 검사한다.

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
| Regex | `^[a-z0-9]+([:-][a-z0-9]+)*$` (`manage_skill.py`와 동일) |
| 최대 길이 | 64자 |
| 최대 깊이 | colon 2개 (3 segment), 예외적 상황에서만 |

### 네임스페이스 원칙

대상 플랫폼/도메인에 skill이 2개 이상이면 colon namespace를 쓰고, 1개뿐이면 flat으로 둔다. 현재 쓰는 네임스페이스는 `list`로 확인한다.

| 패턴 | 용도 | 예시 |
|------|------|------|
| `namespace:verb` | 단일 액션 | `git:commit`, `slack:send` |
| `namespace:verb-noun` | 대상 명시 | `notion:add-engineering-note`, `notion:send-task-plan` |
| `workflow:phase` | 워크플로우 단계 | `daily:start`, `daily:retrospective` |
| 단독 `noun` / `noun-noun` | 범용 도구 | `learn`, `security-manager` |

## 1. Frontmatter 형식

```yaml
---
name: skill-name
description: |
  한국어로 작성된 설명.
  사용 시점: (1) 상황 1, (2) 상황 2.
  트리거 키워드: "키워드1", "키워드2", "/skill-name".
model: sonnet          # 선택사항: haiku | sonnet | opus
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/<name>/scripts/<script>.py *)
  - Read
  - Write
  - Edit
---
```

**규칙:**
- `name`: 디렉토리명과 일치, 위 Regex
- `description`: 한국어, 블록 스칼라(`|`), 사용 시점과 트리거 키워드 포함
- `model`: 복잡한 워크플로우 `sonnet`, 단순 작업 `haiku`, 생략하면 기본값
- `allowed-tools`: user scope 스크립트는 절대 경로, project scope는 `${CLAUDE_PROJECT_DIR}/...`
- 허용 필드 외(name, description, model, effort, allowed-tools, license, metadata, disable-model-invocation)는 쓰지 않는다

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
└── agents/            # (선택) Sub-Agent 프롬프트: Claude가 필요 시 생성
    └── agent-<역할>.md
```

- `scripts/`, `references/`, `assets/`는 `create`가 만든다. `agents/`는 `--with-agents` 또는 수동으로 만든다

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

## 5. Body 작성의 5원칙

### 5.1 Progressive Disclosure (3단계 로딩)

| 단계 | 컨텐츠 | 항상 로드? |
|------|--------|-----------|
| Frontmatter | `description`, `allowed-tools`, `model` | 항상 |
| Body | SKILL.md의 `---` 이후 본문 | 트리거 시 로드 |
| References | `references/` 하위 파일 | 명시적 참조 시 로드 |

### 5.2 Description vs Body 역할 분리

- Description = **언제 사용할지** (트리거만)
- Body = **무엇을/어떻게 할지** (절차만). Body 첫머리에 "이 스킬은 ~할 때 사용합니다" 같은 트리거 설명을 반복하지 않는다

### 5.3 500줄의 법칙

Body는 **500줄 이하**. 초과하면 상세 절차·예시를 `references/`로 분리하고 body에는 링크만 둔다.

### 5.4 개념 설명 금지

Claude가 이미 아는 개념(JSON, REST API, kubectl, Docker 등)은 설명하지 않는다.
**프로젝트 고유 값**(엔드포인트, 토큰 경로, 클러스터명)만 포함.

| 자유도 | 처리 방식 |
|--------|-----------|
| Low (절차 고정) | 코드 블록으로 명시 |
| High (Claude 판단) | 지침/원칙만 제시 |

### 5.5 검증 루프 심기

워크플로우 마지막에 검증 Step을 반드시 둔다. 실패 시 에러 메시지별 수정 방법(예: `error: missing field` → 필드 추가 후 재실행)을 쓴다.

"항상" 대신 "MUST" 또는 "반드시"를 쓴다(validate가 warning을 낸다).

### 5.6 관심사 분리

| 분리 대상 | Before (나쁜 예) | After (좋은 예) |
|-----------|-----------------|----------------|
| 반복 실행 bash (3줄 이상) | SKILL.md body에 inline bash | `scripts/env-init.sh` 추출, `allowed-tools`에 등록 |
| 출력 템플릿 (15줄 이상) | SKILL.md body에 markdown 템플릿 | `assets/template.md`로 분리, Read로 참조 |
| Raw 시스템 명령 | `Bash(brew *)` in allowed-tools | `Bash(bash .../scripts/init.sh *)` 래핑 |
| Agent 인라인 프롬프트 (10줄 이상) | SKILL.md body에 멀티라인 Agent 프롬프트 | `agents/agent-<역할>.md`로 분리, body에서 Read 참조 |

**agents/ 디렉토리 규칙**:
- 파일 명명: `agent-{역할}.md` (lowercase, hyphen-case), 예: `agent-notion-reader.md`, `agent-transcript-parser.md`
- 프롬프트 내 동적 값: `{변수명}` placeholder 사용, 예: `{date}`, `{yesterday_note_path}`
- SKILL.md body에서 Read로 참조 후 변수 치환 지시 작성
- `allowed-tools` frontmatter에 `- Agent` 추가

**허용 패턴** (allowed-tools):
- `Bash(python3 /abs/path/scripts/*.py *)`: Python 스크립트 호출
- `Bash(bash /abs/path/scripts/*.sh *)`: Shell 스크립트 호출
- `Bash(kubectl *)`: kubectl은 예외적으로 직접 허용
- `Read`, `Write`, `Edit`, `Glob`, `Grep`: 비-Bash 도구

## 6. SKILL.md Body 구조

타입별 골격은 `references/templates.md`를 따른다. 섹션 헤더는 한국어(`## 핵심 원칙`, `## 주의사항`), Step은 `### Step N: 한국어 설명`.

## 7. 스킬 타입 선택 가이드

| 타입 | 사용 시점 | 예시 |
|------|-----------|------|
| `workflow` | 외부 API 호출 + 여러 단계 자동화 | `notion:add-engineering-note`, `daily:start`, `git:commit` |
| `reference` | 도메인 지식 + 쿼리/분석 | `aws:instance-guide` |
| `tool` | 단순 파일/데이터 처리, CLI 래퍼 | `slack:send` |

## 8. 언어 규칙

- 설명·주의사항은 한국어, 코드·명령·JSON 키·변수명은 영어
