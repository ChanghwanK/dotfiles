---
name: wiki:capture
description: |
  대화 중 생성된 기술 인사이트·분석·아키텍처 결정을 04. Wiki/engineering/에 즉시 filing.
  LLM Wiki 패턴의 "good answers filed back into the wiki" 워크플로우를 구현한다.
  사용 시점: 원인 분석, 디버깅 해결책, 아키텍처 결정, 패턴 발견 후.
  트리거 키워드: "/wiki:capture", "위키에 저장", "노트로 저장해", "wiki에 남겨".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Bash(pwd)
  - Bash(git -C * rev-parse --show-toplevel)
  - Read
  - Edit
  - Agent
---

# Wiki Capture Skill

대화 중 생성된 인사이트를 `04. Wiki/engineering/`에 filing하는 스킬.
`/obsidian:note`와 차이: 사용자가 주제를 제공하는 게 아니라 **Claude가 대화에서 직접 추출**한다.

## 호출 방식

| 호출 | 동작 |
|------|------|
| `/wiki:capture` | 현재 대화 전체에서 가장 핵심 인사이트를 추출 |
| `/wiki:capture [주제]` | 지정 주제에 집중하여 추출 |

---

## Step 1: 작업 컨텍스트 파악

현재 작업 디렉토리를 확인하여 태그 추론에 활용한다:

```bash
pwd
```

디렉토리 → 태그 매핑:
| 경로 패턴 | 우선 태그 |
|----------|----------|
| `*/kubernetes/*` | `domain/kubernetes` |
| `*/terraform/*` | `domain/aws` |
| `*/infra-k8s-*` | `domain/kubernetes` |
| 기타 | 대화 내용에서 추론 |

---

## Step 2: 인사이트 추출

대화에서 다음 중 가장 가치 있는 내용을 추출한다:

**우선순위 (높은 것부터):**
1. **원인 분석** — "왜 X가 발생하는가"에 대한 명확한 설명
2. **디버깅 해결책** — 재현 가능한 문제 해결 패턴
3. **아키텍처 결정** — 트레이드오프를 포함한 설계 선택
4. **개념 설명** — 기술 개념의 내부 동작 원리
5. **패턴 발견** — 반복 적용 가능한 구성 패턴

`/wiki:capture [주제]` 호출 시: 해당 주제와 관련된 대화 내용만 집중 추출.

---

## Step 3: 노트 타입 결정

| 산출물 성격 | `--type` | 저장 경로 |
|------------|----------|----------|
| 개념 설명·원리·아키텍처 | `learning-note` | `04. Wiki/engineering/` |
| 디버깅 과정·에러 해결 | `troubleshooting` | `03. Resources/troubleshooting/` |
| 운영 절차·명령어 시퀀스 | `runbook` | `03. Resources/runbooks/` |
| 장애 분석·post-mortem | `incident` | `04. Wiki/incidents/` |

**`incident` 타입 선택 기준**: 실제 발생한 장애/알럿을 분석한 대화일 때. 단순 개념 설명이나 디버깅 연습이 아닌, 프로덕션/스테이징 환경의 실제 이벤트여야 한다.

`incident` 타입의 노트 본문은 아래 섹션을 포함한다:
- `## Summary` — 알럿명, severity, 서비스, 발생 시각
- `## 현상` — 메트릭/증상 요약
- `## Root Cause` — 5 Whys 또는 원인 체인
- `## 해결책` — 적용한 또는 추천 해결책
- `## 재발 방지` — 후속 조치 및 모니터링 포인트

---

## Step 4: 노트 본문 생성

아래 구조로 노트 본문을 작성한다. `---` 수평선 사용 금지. H1(`#`) 사용 금지.

```markdown
## Summary

- (핵심 포인트 1 — 가장 중요한 takeaway)
- (핵심 포인트 2)
- (핵심 포인트 3)
- (핵심 포인트 4)
- (핵심 포인트 5)

## (주요 섹션 1)

(대화에서 다룬 내용을 구조화하여 서술)

## (주요 섹션 2)

(코드·설정·명령어가 있으면 언어 태그 포함한 코드블록으로)

```bash
# 예시
kubectl get pods -n infra
```

## 핵심 takeaway

(이 노트에서 가장 중요한 1-2문장 요약)
```

**Summary 규칙**: 정확히 5-7개 bullet. 더 많거나 적으면 안 됨.
**코드블록**: 언어 태그 필수 (` ```bash `, ` ```yaml `, ` ```go ` 등).

---

## Step 5: obsidian-note.py 호출

본문을 임시 파일에 저장 후 create 호출:

```bash
# 본문을 임시 파일로 저장
cat > /tmp/wiki_capture_content.md << 'CONTENT'
{생성한 본문}
CONTENT

# 노트 생성
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "{제목}" \
  --tags "{domain1},{domain2}" \
  --aliases "{alias1},{alias2},{alias3}" \
  --type "{learning-note|troubleshooting|runbook}" \
  --content-file /tmp/wiki_capture_content.md
```

결과 JSON에서 `filepath`와 `filename` 추출.

---

## Step 6: Note Reviewer 실행

저장된 노트를 `agent-note-reviewer`로 품질 검증한다.

```
Agent(
  subagent_type: "sonnet",
  prompt: agent-note-reviewer.md 내용을 참조하여,
    filepath: {결과 filepath}
    title: {제목}
    aliases: {aliases 리스트}
    tags: {tags 리스트}
    related_slugs: {related 노트 slugs}
  로 리뷰 수행
)
```

리뷰 결과 `overall_score < 70`이면 `top_actions`를 사용자에게 보여주고 즉시 적용 여부를 묻는다.
`overall_score >= 70`이면 리뷰 결과는 내부적으로만 반영하고 사용자에게 요약만 표시.

---

## Step 7: _index.md 및 _log.md 업데이트

```bash
VAULT="/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"
INDEX="$VAULT/04. Wiki/_index.md"
LOG="$VAULT/04. Wiki/_log.md"
```

**_index.md**: 적절한 섹션(태그 기반)에 항목 추가:
```
- [[{slug}|{title}]] — {한 줄 설명}
```

**_log.md**: 맨 아래에 append:
```
## [2026-04-20] capture | {제목}
- 출처: /wiki:capture ({컨텍스트 요약 한 줄})
- 저장: [[{slug}]]
```

---

## Step 8: 완료 출력

```
✅ Wiki에 저장되었습니다
   📄 [[{slug}|{title}]]
   📁 {저장 경로}
   🏷️  {tags}
   📊 리뷰 점수: {overall_score}/100
```

---

## aliases 선정 기준 (3개)

- **Role A** — 영문 약어·공식명 (예: `IRSA`, `mTLS`, `NLB`)
- **Role B** — 한국어 개념 (예: `파드 권한`, `로드밸런서 헬스체크`)
- **Role C** — 대안 진입점·유사 개념 (예: `AWS 권한 위임`, `Istio 트래픽`)
