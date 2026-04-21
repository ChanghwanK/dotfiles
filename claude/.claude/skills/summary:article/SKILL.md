---
name: summary:article
description: 웹 URL의 콘텐츠를 fetch하여 심층 분석/인사이트 추가 후 Obsidian 노트로 저장하는 스킬. 병렬 에이전트로 콘텐츠 추출 + 보충 리서치를 동시 수행. 블로그, 기술 문서, 아티클, PDF 등 지원. 사용 시점: (1) 기술 블로그 읽고 정리, (2) 공식 문서 분석 후 노트화, (3) 아티클에서 인사이트 추출. 트리거 키워드: "웹 요약", "아티클 요약", "URL 분석", "web summary", "/summary:article".
model: sonnet
allowed-tools:
  - Agent
  - WebFetch
  - Read
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py *)
---

# Article Summary Skill

웹 URL을 병렬 에이전트로 분석하여 원문 깊이를 유지하면서 보충 인사이트까지 포함한 Obsidian 노트를 생성한다.

## 핵심 원칙

- **병렬 우선**: 콘텐츠 추출과 보충 리서치는 반드시 단일 메시지에서 동시 실행
- **원문 깊이 유지**: 요약이 아닌 정리 — 대화/원문의 모든 내용 포함
- **보충 통합**: Agent B 결과를 별도 섹션이 아닌 본문 흐름에 자연스럽게 통합
- **관련 노트 연결**: obsidian:note 스크립트의 자동 wikilink를 적극 활용

## 워크플로우

### Step 1 — URL 확인 및 분류

사용자가 제공한 URL을 분석한다:

- URL 형식 검증 (http/https 필수)
- URL 타입 분류:
  - `web` — 일반 웹 페이지 (기본값)
  - `pdf` — `.pdf` 확장자 또는 `application/pdf` 반환 예상 URL
  - `auth` — 로그인 페이지, GitHub private repo, Notion 등 인증이 필요한 URL
- 주제 키워드 추출: URL 경로, 도메인, 파라미터에서 핵심 키워드 추론
  - 예: `ssup2.github.io/.../nvidia-gpu-architecture` → `NVIDIA, GPU, Architecture, H100`

### Step 2 — 병렬 에이전트 실행

아래 두 Agent를 **단일 메시지에서 동시에** 실행한다:

**Agent A — 콘텐츠 추출**
Read `/Users/changhwan/.claude/skills/summary:article/agents/agent-content-extractor.md`
변수 치환:
- `{url}` → Step 1에서 확인한 URL
- `{url_type}` → `web` / `pdf` / `auth`

**Agent B — 보충 리서치**
Read `/Users/changhwan/.claude/skills/summary:article/agents/agent-supplementary-research.md`
변수 치환:
- `{url}` → Step 1에서 확인한 URL
- `{topic_keywords}` → Step 1에서 추출한 주제 키워드 (쉼표 구분)

Agent 실패 처리:
- Agent A 실패 → 중단 후 에러 처리 섹션 참조
- Agent B 실패 → Agent A 결과만으로 Step 3 진행 (보충 없이 노트 생성)

### Step 3 — 결과 병합 및 노트 구조화

Agent A + B 결과를 병합하여 **한국어** 마크다운을 생성한다.

#### 노트 구조

```markdown
> **출처**: [페이지 제목](URL) | **저자**: 저자명 | **게시일**: YYYY-MM-DD

## TL;DR
(핵심 내용 불릿 요약. 분량에 따라 3~5개 기준이나 내용이 많으면 더 길어도 됨. 짧은 글은 2개도 허용)

## 핵심 개념
(Why — 이 주제가 왜 중요한지, 어떤 문제를 해결하는지)

## [주제별 본문 섹션들]
(원문 구조 기반, 자유롭게 헤딩 구성)

## SOCRAAI 환경 적용
(Agent B SOCRAAI_RELEVANCE 기반 — 관련 없으면 섹션 생략)

## 더 알면 좋은 것들
(Agent B FURTHER_LEARNING 기반 — 각 항목: 왜 배우면 좋은지 + 리소스 + SOCRAAI 연관성)

## 인사이트
(So what? — 이 아티클이 나에게 의미하는 것, 3-5개 불릿)

## 정리
(핵심 takeaway 3-5개 불릿)
```

#### TL;DR 작성 규칙

- 각 불릿은 **한 문장으로 독립적으로 이해 가능**해야 한다 (다른 섹션 안 읽어도 됨)
- "무엇을 했는가" + "왜/결과가 무엇인가"를 한 문장에 담는다
- 숫자/수치가 있으면 반드시 포함한다 (예: "주당 15시간 → 1.5시간으로 90% 절감")
- 기술 결정/교훈은 별도 불릿으로 뽑는다
- 과도하게 압축하지 않는다 — 불릿 수를 늘리는 것이 내용 손실보다 낫다

#### 마크다운 생성 규칙

- 출력 언어: **한국어**. 기술 용어는 원문 병기 (예: "스트리밍 멀티프로세서(Streaming Multiprocessor)")
- 문장 끊기: 한 문장 = 한 사실/행동. 복문은 불릿으로 분리
- 3가지 이상 나열 → 불릿 목록으로 전환
- `---` 수평선 금지 — 섹션은 `##` 헤딩으로 구분
- 헤딩에 `—` em dash 금지
- 불릿에 `—` em dash 금지 — 부연은 중첩 불릿으로
- 다이어그램: Agent A `DIAGRAMS_DETECTED`에 재구성 가능 항목이 있으면 ASCII 다이어그램 생성
- 표: 비교 데이터는 반드시 마크다운 테이블로 표현
- Agent B 보충 데이터는 해당 본문 섹션에 자연스럽게 통합 (별도 표시 없이)

#### 태그 자동 추론

Agent B `DOMAIN_CLASSIFICATION`을 기반으로 `domain/` 태그를 결정한다:

| 키워드 | 태그 |
|--------|------|
| GPU, CUDA, NVIDIA, ML, LLM, 모델 | `domain/ai` |
| IDC, Proxmox, A100, A6000, bare metal | `domain/on-premise` |
| Kubernetes, Helm, ArgoCD, Karpenter | `domain/kubernetes` |
| AWS, EC2, EKS, VPC, S3, Route53 | `domain/aws` |
| Istio, Envoy, Service Mesh, mTLS | `domain/networking` |
| Prometheus, Grafana, Loki, VictoriaMetrics | `domain/observability` |
| PostgreSQL, Aurora, Redis, CNPG | `domain/database` |
| Terraform, IaC | `domain/terraform` |
| TLS, PKI, IAM, RBAC | `domain/security` |

사용자가 명시적으로 태그를 지정하면 우선 적용한다.

### Step 4 — Obsidian 저장

Step 3에서 생성한 마크다운 본문을 heredoc stdin으로 파이프한다:

```bash
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py create \
  --title "[페이지 제목]" \
  --tags "domain/tag1,domain/tag2" \
  --type "learning-note" \
  --category "engineering" \
  --content-file - << 'OBSIDIAN_CONTENT_EOF'
(Step 3에서 생성한 전체 마크다운 본문)
OBSIDIAN_CONTENT_EOF
```

- 제목: Agent A 메타데이터의 페이지 제목 사용 (없으면 URL에서 추론)
- `success: false`이면 에러 메시지를 사용자에게 전달하고 중단

### Step 5 — 결과 출력

저장 완료 메타데이터와 내용 미리보기를 함께 출력한다:

```
웹 아티클 분석이 Obsidian에 저장되었습니다.
- **제목**: {title}
- **출처**: {url}
- **태그**: {tags} (자동 추론)
- **파일**: {filename}
- **관련 노트**: {related_count}개 링크됨 (0이면 생략)
- **Daily Note**: 📝 Daily Note에 연결됨 (daily_linked: false이면 생략)

---

**주요 내용**
- (TL;DR 섹션의 불릿들을 그대로 출력 — 저장된 노트의 핵심 내용 미리보기)
```

**출력 규칙:**
- TL;DR 불릿은 Step 3에서 생성한 내용에서 그대로 가져온다 (재요약 금지)
- 불릿 앞에 **굵은 키워드**: 형식 사용 권장 (예: `- **PR 머지 조건**: lgtm + approved 필요`)
- aliases는 출력에서 생략 (노이즈가 많음)

시리즈/관련 글이 감지된 경우 (Agent A `RELATED_LINKS` 비어있지 않으면):
```
같은 시리즈의 관련 글이 감지되었습니다:
- [제목](URL)
- [제목](URL)
이 글들도 요약하시겠습니까?
```

## 에러 처리

| 상황 | 대응 |
|------|------|
| WebFetch 실패 (인증/403) | Agent A가 Playwright fallback 시도. 실패 시 "인증이 필요한 페이지입니다. 로컬에 저장 후 경로를 알려주세요." 안내 |
| PDF 콘텐츠 부족 (500자 미만) | "PDF 파싱이 충분하지 않습니다. `! curl -o /tmp/article.pdf {url}` 실행 후 경로를 알려주세요." 안내 |
| 콘텐츠 너무 짧음 (1000자 미만) | "페이지에서 충분한 콘텐츠를 추출하지 못했습니다. 다른 URL을 시도해주세요." 안내 |
| Agent B 리서치 실패 | Agent A 결과만으로 노트 생성. "보충 리서치를 가져오지 못해 원문 기반으로만 정리되었습니다." 메모 추가 |
| Obsidian 저장 실패 | 에러 메시지 전달. 생성된 마크다운 본문을 대화에 출력하여 수동 저장 가능하도록 |
