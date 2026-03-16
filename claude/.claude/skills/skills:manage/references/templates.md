# SKILL.md 템플릿 모음

세 가지 스킬 타입별 완성된 SKILL.md 템플릿.
새 스킬 작성 시 해당 타입 템플릿을 기반으로 수정하세요.

---

## 타입 1: Workflow (순차 자동화)

**적합한 경우**: API 호출, 파일 처리, 다단계 자동화 (eng-note, start-daily, commit 스타일)

```markdown
---
name: my-workflow
description: |
  Notion/GitHub/외부 API를 호출하는 자동화 워크플로우 스킬.
  사용 시점: (1) 특정 조건에서 자동 실행, (2) 반복 작업 자동화.
  트리거 키워드: "키워드1", "키워드2", "/my-workflow".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/my-workflow/scripts/main.py *)
  - Write(/tmp/my-workflow-data.json)
---

# My Workflow Skill

TODO: 핵심 동작 한 문장 (트리거 설명 X — description과 중복 금지)

---

## 핵심 원칙

- **데이터 수집 후 처리**: 필요한 정보를 먼저 모은 다음 작업한다.
- 스크립트만 호출한다. 직접 API 호출 금지.
- 토큰은 1Password 런타임 fetch.
- 완료 후 결과 URL 또는 확인 메시지를 반드시 출력한다.

---

## 워크플로우

### Step 1 — 입력 수집

사용자에게 필요한 정보를 확인한다 (대화에서 이미 명확하면 생략):
- **제목** (필수)
- **카테고리** — 기본값: `default`

### Step 2 — 데이터 준비

```bash
# /tmp/my-workflow-data.json 작성 (Write 도구 사용)
{
  "title": "제목",
  "category": "default"
}
```

### Step 3 — 스크립트 실행

```bash
TOKEN=$(op read "op://Employee/vault/item/field") \
python3 /Users/changhwan/.claude/skills/my-workflow/scripts/main.py create \
  --title "제목" \
  --data /tmp/my-workflow-data.json
```

### Step 4 — 결과 출력

```
작업 완료.
- 제목: {title}
- URL: {url}
```

---

## 주의사항

- 토큰이 없으면 스크립트가 실패한다. 1Password 로그인 상태 확인.
- 중복 실행 방지: 같은 제목으로 두 번 생성하지 않는다.
```

---

## 타입 2: Reference (도메인 지식)

**적합한 경우**: 특정 도메인 전문 지식을 Claude에게 주입 (gpu-analysis 스타일)

```markdown
---
name: my-reference
description: |
  특정 도메인의 분석/진단/설계를 지원하는 레퍼런스 스킬.
  사용 시점: (1) 도메인 분석 요청, (2) 관련 도구 쿼리.
  트리거 키워드: "분석", "진단", "현황", "/my-reference".
model: sonnet
allowed-tools:
  - Bash(kubectl *)
  - Bash(python3 /Users/changhwan/.claude/skills/my-reference/scripts/query.py *)
---

# My Reference Skill

도메인 X의 현황 분석 및 진단을 수행하는 스킬.

---

## 도메인 지식

### 핵심 개념

<!-- Claude가 이미 아는 범용 개념은 생략. 프로젝트 고유 용어/값만 기술 -->
| 개념 | 설명 |
|------|------|
| 개념 A | A에 대한 설명 |
| 개념 B | B에 대한 설명 |

### 인프라 컨텍스트

- 환경: prod / staging / dev
- 주요 엔드포인트: ...

---

## 분석 워크플로우

### Step 1 — 현황 데이터 수집 (병렬 실행)

```bash
# 명령 1
kubectl get nodes -o wide

# 명령 2
python3 /Users/changhwan/.claude/skills/my-reference/scripts/query.py metrics
```

### Step 2 — 데이터 해석

수집된 데이터를 기반으로 다음을 분석한다:
1. 항목 A 상태
2. 항목 B 이상 여부

### Step 3 — 권고 사항 도출

분석 결과에 따른 조치 권고:
- 정상: "현재 상태 양호"
- 이상 감지: 구체적인 조치 방법 제시

---

## 출력 형식

```
=== 분석 결과 ===

총 N개 항목 | 정상 M개 | 이상 K개

[이상 항목]
- 항목명: 문제 설명

[권고 사항]
- 조치 1
```

---

## 참고 자료

- 공식 문서: https://...
- 내부 위키: ...
```

---

## 타입 3: Tool (단순 CLI 래퍼)

**적합한 경우**: 기존 스크립트나 CLI의 단순 래퍼 (send-plan 스타일)

```markdown
---
name: my-tool
description: |
  특정 CLI 또는 스크립트를 Claude 워크플로우에서 쉽게 호출하는 도구.
  사용 시점: (1) 특정 파일/데이터를 외부로 전송, (2) 변환/처리.
  트리거 키워드: "전송", "보내줘", "/my-tool".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/my-tool/scripts/tool.py *)
  - Read
---

# My Tool

특정 파일을 대상 서비스로 전송하거나 처리하는 도구.

---

## 사용법

### 기본 실행

```bash
python3 /Users/changhwan/.claude/skills/my-tool/scripts/tool.py \
  --input /path/to/file \
  --target destination
```

---

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--input` | 입력 파일 경로 | 필수 |
| `--target` | 전송 대상 | - |
| `--dry-run` | 실제 전송 없이 미리보기 | false |

---

## 워크플로우

1. Read 도구로 입력 파일 내용 확인
2. 사용자에게 대상 확인 (필요한 경우)
3. 스크립트 실행
4. 결과 URL 또는 확인 메시지 출력

---

## 출력 예시

성공:
```json
{
  "success": true,
  "url": "https://...",
  "message": "전송 완료"
}
```

---

## 주의사항

- `--input` 경로가 존재해야 한다.
- 대상이 명확하지 않으면 사용자에게 확인한다.
```

---

## 타입 선택 가이드

```
요청 분석
    │
    ├─ 외부 API 호출 + 다단계 처리?  → workflow
    │
    ├─ 도메인 지식 + 쿼리/분석?      → reference
    │
    └─ 단순 파일/데이터 처리?        → tool
```

---

## Agent 사용 시 참고 패턴

Workflow 스킬에서 병렬 데이터 수집이 필요할 때의 확장 패턴.

**판단 기준**: 독립적인 소스(Notion, Obsidian, 외부 API 등)에서 데이터를 동시에 수집해야 하고, 각 수집 로직이 10줄 이상의 프롬프트를 요구할 때 → `agents/` 분리.

### frontmatter 예시 (Agent 포함)

```yaml
---
name: my-workflow
description: |
  여러 소스에서 병렬로 데이터를 수집하는 워크플로우.
  사용 시점: (1) 상황 1, (2) 상황 2.
  트리거 키워드: "키워드", "/my-workflow".
model: sonnet
allowed-tools:
  - Agent
  - Bash(python3 /Users/changhwan/.claude/skills/my-workflow/scripts/main.py *)
  - Read
  - Write
---
```

### agents/ 파일 참조 패턴 (SKILL.md body)

```markdown
### Step 2 — 병렬 데이터 수집

아래 두 Agent를 **동시에** 실행한다:

**Agent A — Notion 데이터 수집**
Read `/Users/changhwan/.claude/skills/my-workflow/agents/agent-notion-reader.md`
변수 치환: `{date}` → 오늘 날짜 (YYYY-MM-DD 형식)

**Agent B — Obsidian 노트 파싱**
Read `/Users/changhwan/.claude/skills/my-workflow/agents/agent-obsidian-parser.md`
변수 치환: `{note_path}` → 어제 Daily Note 경로
```

### agents/ 파일 구조 예시

```markdown
<!-- agents/agent-notion-reader.md -->
# Notion 데이터 수집 에이전트

대상 날짜: {date}

다음 절차로 Notion에서 데이터를 수집한다:

1. ...
2. ...

수집 완료 후 JSON 형태로 결과를 반환한다.
```
