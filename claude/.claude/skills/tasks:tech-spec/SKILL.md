---
name: tasks:tech-spec
description: |
  인프라/DevOps Tech Spec 스킬. Quick mode(즉시 생성)와 Standard mode(Phase 1-3 대화형) 지원.
  Quick mode: 대화 맥락을 분석하여 한 번에 Tech Spec 생성. Standard mode: 문제 분석 → 목표 설정 → 계획 설계.
  사용 시점: (1) 인프라 변경 계획 수립, (2) 설계 의사결정 구조화, (3) 새 프로젝트 킥오프, (4) 대화 내용을 빠르게 스펙 정리.
  트리거 키워드: "tech spec", "기술 스펙", "스펙 문서", "tech-spec 작성", "/tasks:tech-spec", "/work:tech-spec".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py create-task *)
  - Write(/tmp/tech-spec-content.json)
  - Edit
  - Agent
---

# tasks:tech-spec — Tech Spec 스킬

Tech Spec 문서를 Obsidian에 생성한다. Quick mode(즉시)와 Standard mode(대화형) 두 가지 모드 지원.

**저장 경로**: `03. Resources/tech-specs/`
**운영 스킬**: Phase 4(실행)·5(측정)는 `tasks:tech-spec-ops` 스킬에서 수행.

---

## Step 0 — Notion Task Capture (선택적)

Tech Spec 생성 시작 전, 다음 질문을 사용자에게 한다:

> **"Notion Task도 함께 생성할까요? (y/n)"**

### Yes 선택 시

1. Tech Spec 제목을 먼저 결정한다 (모드 분기 이전에 제목 파악).
   - Quick mode: 대화 맥락에서 제목 추출
   - Standard mode: 사용자에게 간단히 주제/제목 확인
2. 결정된 제목으로 Notion Task 생성:

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py create-task \
  --name "<Tech Spec과 동일한 제목>" \
  --priority P2 \
  --category WORK
```

3. Notion Task 생성 완료 확인 후 Tech Spec 생성 플로우 진행.

### No 선택 시

바로 아래 모드 분기로 진행 (Tech Spec만 생성).

### 제목 통일 규칙

- Notion Task `이름` = Tech Spec `title` (동일 문자열 필수)
- 이를 통해 사용자가 두 문서를 개념적으로 연결할 수 있다.
- 검색 시 동일 제목으로 Notion Task와 Tech Spec을 함께 찾을 수 있다.

---

## 모드 분기

| 조건 | 모드 |
|------|------|
| `/work:tech-spec` 또는 "빠르게 스펙 정리", "스펙으로 정리해줘" | **Quick mode** |
| `/tasks:tech-spec` 또는 기본 | **Standard mode** |

---

## Quick Mode — 즉시 생성

Phase 1-3 대화 없이 **현재 대화 맥락을 분석하여 한 번에 모든 섹션을 채운다**.

### Step 1 — 대화 맥락 분석 + 유형 판단

대화에서 다음을 파악한다:
- 작업 주제와 동기
- **운영 변경**(ConfigMap 변경, 스케일링, 마이그레이션 등)인지 **인프라 설계**(새 클러스터, VPC, 신규 서비스 등)인지
- **스펙 유형 판단**: 어떤 Machine-Readable 스펙이 변경되는가?
  - 운영 변경(ops-change)이면 스펙 아티팩트 섹션 생략
  - 인프라 설계면 스펙 아티팩트 테이블 필수 작성
- 핵심 의사결정과 대안
- 실행 계획과 영향 범위

### Step 2 — 제목과 태그 결정

- **제목**: 작업을 간결하게 설명, **하이픈(`-`) 사용 금지** — 단어 구분은 공백으로
- **태그**: 아래 태그 체계 참조. 원래 이름으로 전달하면 스크립트가 `domain/` 형식으로 자동 정규화

**참조 태그 목록** (Quick mode에서 자주 사용):

| 카테고리 | 태그 |
|----------|------|
| 인프라 | `Kubernetes`, `AWS`, `Terraform`, `Infra`, `Network` |
| 서비스 메시 | `Istio`, `Envoy`, `ServiceMesh` |
| 관측가능성 | `Observability`, `Grafana`, `Prometheus`, `Loki`, `Tracing` |
| AI/ML | `AI`, `Agent`, `LLM`, `ML` |
| 보안 | `Security` |
| 데이터베이스 | `Database`, `Aurora`, `RDS` |
| On-Premise | `GPU`, `OnPremise` |

위 테이블에 없는 구체적 기술 키워드(서비스명, 도구명 등)도 추가 가능.

### Step 3 — 템플릿 채우기

아래 템플릿 구조에 맞춰 모든 섹션을 한 번에 작성:
- **운영 변경**: `## 설계` 섹션 생략 가능. `## 실행 계획`과 `## 임팩트 측정`에 집중.
- **인프라 설계**: `## 설계` 섹션 상세 작성. 다이어그램, 리소스 스펙, 제약조건 포함.
- **변경 사항 Diff**: `### 변경 사항 (Diff)` 섹션에 변경 대상별 As-Is → To-Be를 테이블 또는 diff 블록으로 작성.

**목표 섹션 작성 시 — 경량 Goal Challenge**:

대화형 질문 없이 진행하되, `## 현재 상태와 목표` 섹션의 Non-Goals 또는 성공 기준 작성 시 아래를 자동으로 반영한다:

- 대화 맥락에서 ROI가 불명확하면 → 성공 기준에 "왜 이 수치인가?" 근거 한 줄 추가
- 비가역적 변경(삭제, 마이그레이션)이 포함되면 → Non-Goals에 롤백 시나리오 명시
- 네트워크/비용 영향이 감지되면 → Diff 테이블에 해당 항목 행 추가
- Quick mode 완료 후 출력 하단에 제안이 있으면 `> 💡 참고:` 블록으로 1-2개 병기

### Step 4 — 저장 전 자동 검증 (경고만, 차단 안 함)

아래 검증 항목을 체크하되, **실패해도 저장을 진행**한다. 경고만 사용자에게 알린다.

### Step 4-R — Tech Spec 리뷰 Agent 실행

자동 검증 직후, 저장 전에 리뷰 Agent(F)를 실행한다. 아래 "공통: Tech Spec 리뷰" 섹션 참조.

### Step 5 — 저장 워크플로우 실행

아래 "저장 워크플로우" 섹션과 동일. content.json → 스크립트 실행 → 결과 출력.

---

## Standard Mode — Phase 1-3 (대화형)

Claude와 함께 문제를 분석 → 목표 설정 → 계획 설계하여 구조화된 Tech Spec 문서를 만든다.

### Phase 1: 문제 분석 — "왜 해야 하는가?"

대화 맥락이 충분하면 바로 분석 결과를 제시. 부족하면 질문으로 파악한다.

**파악할 것:**
- 어떤 문제를 해결해야 하는가?
- 문제 발생 배경과 근본 원인
- 현재 영향 (장애, 비용, 생산성)
- 왜 지금 해야 하는가? (긴급도, 의존성)

**현재 상태 조사 — 필요한 Agent만 선택적으로 실행**

대화 맥락에서 `{sphere}`, `{circle}`, `{env}`를 추출한다. 불명확하면 "unknown"으로 대체한다.
아래 판단 기준에 따라 필요한 Agent만 선택하여 실행한다. 선택된 것이 여러 개면 **동시에** spawn한다.

| Agent | 실행 조건 |
|-------|----------|
| **A — 클러스터 현재 상태** | sphere/circle이 특정되고, 현재 Pod/Deployment 상태를 모를 때 |
| **B — 메트릭 현황** | 에러율, 응답시간, 리소스 사용량, 비용 관련 수치가 필요할 때 |
| **C — 코드베이스 탐색** | 현재 values.yaml, chart 버전, 설정값을 확인해야 할 때 |

실행 방법: 해당 agent 파일을 Read한 뒤 placeholder를 대화 맥락으로 치환하여 실행한다.
- A: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-cluster-status.md`
- B: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-metrics-check.md`
- C: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-codebase-explore.md`

**생략 가능한 경우**: 대화 맥락에 이미 충분한 수치/상태 정보가 있거나, 순수 개념/설계 논의(새 아키텍처 구상, 기술 리서치)일 때는 Agent 전체 생략.

**산출물**: `## 왜 이걸 해야 하는가?` 섹션 초안을 사용자에게 제시.
사용자 확인("좋아", "진행해") → Phase 2로.

### Phase 2: 목표 설정 — "어디까지 할 것인가?"

오버엔지니어링 방지. `생산성 > 비용 > 안정성` 기준으로 범위 정리.

**할 것:**
- 목표를 명확한 문장으로 정의
- Before(현재) → After(목표) 구체화
- **Non-Goals**: 하면 좋지만 이번에는 안 하는 것을 명시 (스코프 통제)
- **성공 기준**: Phase 5에서 검증할 측정 가능한 수치 (예: latency -30%, 비용 $X 절감)
- **변경 사항 Diff**: Before → After 변화를 대상별로 테이블 정리. 코드/설정 수준 변경이 있으면 diff 블록 추가.

---

#### Goal Challenge — 엔지니어링 인사이트 (목표 확정 전 필수)

목표 초안을 작성한 직후, 확정 전에 아래 5가지 관점 중 **해당하는 것만 선택적으로** 제시한다. 모든 관점을 다 물어보지 않는다. Phase 1 맥락을 기반으로 판단한다.

| 관점 | 언제 제시 | 제안/질문 방향 |
|------|-----------|--------------|
| **스코프 적정성** | 범위가 크거나 여러 컴포넌트에 걸칠 때 | "한 번에 끝내기 어려운 크기인가? 먼저 완료 가능한 단위로 쪼갤 수 있는가?" |
| **ROI 검증** | 동기가 불명확하거나 "하면 좋을 것 같아서" 성격일 때 | "안 하면 실제로 어떤 문제가 생기는가? 투입 비용 대비 기대 효과가 충분한가?" |
| **숨은 의존성** | 네트워크/비용/다른 팀 영향이 예상될 때 | "이 변경이 의도치 않게 영향을 미치는 컴포넌트(Cross-zone 트래픽, NAT GW, 다른 팀 서비스)는 없는가?" |
| **더 단순한 대안** | 복잡한 설계나 신규 도입이 포함될 때 | "같은 목표를 더 적은 변경으로 달성할 방법은 없는가? 기존 레거시를 활용할 수 있는가?" |
| **되돌리기 비용** | 비가역적 변경(삭제, 마이그레이션, 외부 의존)이 포함될 때 | "실패 시 롤백이 쉬운가? 되돌리기 어려운 결정이 이번 범위에 포함되어 있는가?" |

**출력 형식 예시**:

```
💡 Goal Challenge — 목표를 확정하기 전에 몇 가지 체크해볼게요.

**[ROI 검증]** 현재 문제가 실제로 얼마나 자주 발생하나요?
장애 빈도나 비용 수치로 표현할 수 있다면 성공 기준이 훨씬 명확해집니다.

**[숨은 의존성]** 이 변경이 Cross-zone 트래픽이나 NAT GW 비용에 영향을 줄 수 있습니다.
해당 비용 항목을 Non-Goals로 명시하거나, 영향도를 Diff에 포함하는 것을 권장합니다.

위 내용을 반영해서 목표를 수정하시겠어요, 아니면 현재 초안으로 확정할까요?
```

사용자가 응답/수정 완료 → 목표 확정 → Phase 3으로 진행.

---

**산출물**: `## 현재 상태와 목표` 섹션 초안 (변경 사항 Diff, Non-Goals, 성공 기준 포함) → Goal Challenge 통과 후 사용자 확인 → Phase 3.

### Phase 3: 계획 설계 — "어떻게 할 것인가?"

Phase 1-2 결과를 바탕으로 설계를 협업 방식으로 구체화한다. 3단계로 진행.

---

#### Step 3-1: 설계 브리핑 (Claude → 사용자)

Phase 1-2 결과를 기반으로 아래 내용을 브리핑한다.
필요한 경우 Agent를 선택적으로 spawn하여 재료를 보충한다.

| Agent | 실행 조건 |
|-------|----------|
| **D — 설계 대안 조사** | 접근 방식이 아직 불분명하거나, 대안이 2개 이상 있어 비교가 필요할 때 |
| **E — SOCRAAI 표준 검증** | 네트워크 구조 변경, 신규 AWS 서비스 도입, 멀티 환경 설정이 포함될 때 |

실행 방법: 해당 agent 파일을 Read한 뒤 Phase 1-2 결과로 placeholder를 치환하여 실행한다.
선택된 것이 여러 개면 **동시에** spawn한다.
- D: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-design-research.md`
- E: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-standard-validation.md`

**생략 가능한 경우**: Phase 1-2 대화에서 접근 방식과 대안이 이미 합의되었거나, ops-change처럼 설계 선택지가 없을 때는 Agent 생략 후 직접 브리핑 작성.

Agent 결과(또는 Phase 1-2 맥락)를 종합하여 아래 내용을 브리핑한다:

- **기술 접근 방식**: 어떤 컴포넌트를 어떻게 변경할지 요약
- **대안 후보 2-3개**: Agent D 결과 (각 대안의 트레이드오프 생산성 / 비용 / 안정성 기준)
- **스펙 아티팩트 후보**: Agent D 결과 (변경될 파일 목록, Git 경로 포함)
- **SOCRAAI 표준 검증 결과**: Agent E 결과 (4개 항목 ✅/⚠️/❌ 판정)

브리핑 후 사용자에게 확인 요청: **"이 방향으로 진행할까요? 수정할 부분이 있으면 알려주세요."**

---

#### Step 3-2: 핑퐁 설계 (사용자 ↔ Claude)

사용자 피드백을 반영하여 설계를 구체화한다:

- 사용자가 대안 선택, 범위 조정, 추가 요구사항 제시 가능
- Claude는 피드백을 반영하여 설계를 업데이트하고 다시 요약 제시
- 사용자가 "좋아", "확정", "진행해" 등으로 합의를 표시하면 Step 3-3으로 이동

---

#### Step 3-3: 산출물 확정

합의된 설계를 바탕으로 최종 섹션을 작성한다:

- **스펙 아티팩트 식별** (Spec Driven)
  - 이 작업의 "계약"이 될 Machine-Readable 스펙은 무엇인가?
  - 스펙 유형 결정 (아래 스펙 유형 테이블 참조)
  - `## 설계` 섹션 내에 `### 스펙 아티팩트` 테이블 작성 (Git 경로 포함)
  - **운영 변경**: `ops-change` 유형 → 스펙 아티팩트 섹션 생략 가능

**산출물**: `## 설계`, `## 왜 이 방법인가?`, `## 실행 계획`, `## 임팩트 측정` 섹션 → 저장 전 자동 검증으로 이동.

**실행 계획 작성 원칙**:
- **Phase 단위**: 독립적으로 완료 가능한 작업 묶음. 각 Phase는 명확한 산출물(artifact)을 가진다.
  - Phase 간 순서는 의존성 기준으로 결정 (병렬 가능한 경우 같은 Phase에 묶기)
- **Action item 단위**: 실행 가능한 **최소 단위** — PR 1개, 명령어 1회, 파일 1개 수정 수준.
  - `- [ ] N. {동사 + 목적어}` 형식 (예: `- [ ] 2. values.yaml에 replica 설정 추가`)
  - Phase 내 action item은 위에서 아래로 순차 진행 가능하도록 의존성 순서로 정렬

---

## 공통: 저장 전 자동 검증

Phase 3 완료 또는 Quick mode Step 4에서 전체 Tech Spec을 보여주고 자동 검증:

| 검증 항목 | 실패 시 |
|-----------|---------|
| 필수 H2 섹션 4개 존재 (왜 이걸 해야 하는가?, 현재 상태와 목표, 실행 계획, 임팩트 측정) | 누락 안내 |
| 임팩트에 숫자 or Before/After 패턴 | 경고 |
| 실행 계획에 롤백 언급 | 경고 |
| domain/ 태그 ≥ 1 | 추천 |
| 스펙 아티팩트 참조 (spec_type ≠ ops-change) | 경고 |

경고는 저장을 막지 않되, 사용자에게 알린다. 사용자가 "저장해" 하면 진행.

---

## 공통: Tech Spec 리뷰 (저장 전)

저장 전 자동 검증 통과 후, 저장 워크플로우 실행 전에 리뷰 Agent(F)를 실행한다.

### 실행 방법

`/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-spec-review.md`를 Read한 뒤,
아래 placeholder를 치환하여 Agent F를 실행한다:

- `{tech_spec_content}` → 작성된 전체 Tech Spec 마크다운 본문 (H1 제목 포함)
- `{spec_type}` → Phase 3 또는 Quick mode에서 판단한 스펙 유형 (예: `helm-chart`, `ops-change`)

### 리뷰 결과 처리

Agent F 결과를 사용자에게 제시한 후:

1. **❌ (Issue) 항목이 있으면**: 해당 부분 수정을 권고한다. 사용자가 수정 의사를 밝히면 스펙을 함께 수정 후 다시 리뷰를 실행한다.
2. **⚠️ (Concern) 항목만 있으면**: 수정 여부를 사용자에게 확인한다. "이대로 진행"도 허용.
3. **사용자가 확정("저장해", "이대로 진행", "OK" 등)하면** → 저장 워크플로우로 이동한다.

---

## 공통: 태그 체계

`domain/` 네임스페이스 사용. 스크립트가 자동 정규화.

| 입력 | 변환 결과 |
|------|----------|
| `Kubernetes`, `kubernetes` | `domain/kubernetes` |
| `AWS`, `CloudFront`, `Route53` | `domain/aws` |
| `Istio`, `Envoy`, `Network` | `domain/networking` |
| `Observability`, `Grafana`, `Loki` | `domain/observability` |
| `Terraform` | `domain/terraform` |
| `Database`, `Aurora`, `RDS` | `domain/database` |
| `GPU`, `on-premise` | `domain/on-premise` |
| `AI`, `Agent`, `LLM`, `ML` | `domain/ai` |
| `Security` | `domain/security` |

> `Issue`, `Design`, `Architecture` 등은 도메인이 아닌 분류 태그 → 매핑되지 않고 자동 drop.

---

## 공통: 스펙 유형 (Spec Driven)

| spec_type | Spec Layer | 대표 경로 |
|-----------|------------|----------|
| `terraform` | 인프라 | `terraform/modules/...` |
| `k8s-manifest` | 워크로드 | `kubernetes/src/<sphere>/...` |
| `k8s-crd` | 워크로드 | CRD 정의 |
| `helm-chart` | 워크로드 | `kubernetes-charts/charts/...` |
| `jsonnet` | 워크로드 | `kubernetes/src/<sphere>/*.jsonnet` |
| `kyverno-policy` | 정책 | `kubernetes/src/infra/kyverno/...` |
| `alert-rule` | 관측 | VMRule/PrometheusRule YAML |
| `api-spec` | 인터페이스 | OpenAPI, Protobuf |
| `ops-change` | 운영 변경 | 스펙 아티팩트 해당 없음 |

---

## 공통: 템플릿 구조

```markdown
---
## 왜 이걸 해야 하는가?           ← Phase 1 / Quick Step 3

### 문제
- (어떤 문제가 있는가)

### 배경
- (왜 발생했는가, 히스토리)

## 현재 상태와 목표                ← Phase 2 / Quick Step 3
### Before (현재)
### After (목표)
### 변경 사항 (Diff)

| 대상 | As-Is | To-Be |
|------|-------|-------|
| {파일/설정/리소스명} | {현재 값/상태} | {변경 후 값/상태} |

> 코드/설정 수준의 구체적 변경이 있으면 diff 블록으로 추가:

```diff
- replicas: 2
+ replicas: 4
```

### Non-Goals (이번에는 안 하는 것)
### 성공 기준

## 설계                           ← Phase 3 (인프라 설계만, 운영 변경은 생략 가능)

### 스펙 아티팩트                  ← NEW (인프라 설계 시, ops-change는 생략)
| 스펙 유형 | 경로 | 설명 |
|-----------|------|------|
| helm-chart | `kubernetes-charts/charts/xxx/` | 차트 변경 |
| k8s-manifest | `kubernetes/src/infra/xxx/` | 매니페스트 추가 |

## 왜 이 방법인가?                 ← Phase 3 / Quick Step 3

### 선택 이유
- (이 접근 방식을 선택한 핵심 근거)

### 대안 및 트레이드오프
- (대안 A: 장단점)
- (대안 B: 장단점)

## 실행 계획                       ← Phase 3 / Quick Step 3

| Phase | 제목 | 산출물 |
|-------|------|--------|
| Phase 1 | {Phase 제목} | {예: 인프라 배포 완료} |
| Phase 2 | {Phase 제목} | {예: 서비스 마이그레이션 완료} |
| Phase 3 | {Phase 제목} | {예: 검증 및 완료} |

### Phase 1. {Phase 제목}

- [ ] 1. {구체적 액션}
- [ ] 2. {구체적 액션}
- [ ] 3. {구체적 액션}

### Phase 2. {Phase 제목}

- [ ] 1. {구체적 액션}
- [ ] 2. {구체적 액션}

### Phase 3. {Phase 제목}

- [ ] 1. {구체적 액션}

## 임팩트 측정                     ← Phase 3 / Quick Step 3

### 기대 효과
- (정량적 수치 또는 Before/After)

### 측정 방법
- (어떤 메트릭으로, 어떻게 확인할 것인가)

## 실행 기록                       ← Phase 4 (tasks:tech-spec-ops)
> 실행 시작 후 기록

## 실제 결과 (Outcome)             ← Phase 5 (tasks:tech-spec-ops)
> 완료 후 작성
```

---

## 공통: 저장 워크플로우

### Step 1 — content.json 작성

전체 마크다운 본문(H1 제목 포함)을 `/tmp/tech-spec-content.json`에 저장:

```json
{
  "blocks": "---\n## 왜 이걸 해야 하는가?\n\n### 문제\n- ...\n\n### 배경\n- ..."
}
```

### Step 2 — 스크립트 실행

스크립트 호출 전에 Claude가 이 스펙을 나중에 검색할 때 쓸 핵심 키워드 **3개**를 결정한다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py create \
  --title "제목" \
  --tags "Kubernetes,AWS" \
  --aliases "키워드1,키워드2,키워드3" \
  --spec-type "helm-chart,k8s-manifest" \
  --content-file /tmp/tech-spec-content.json
```

태그는 원래 이름으로 전달 → 스크립트가 `domain/` 형식으로 자동 정규화.

### Step 3 — 결과 출력

```
Tech Spec이 생성되었습니다.
- 제목: {title}
- 태그: {tags}
- aliases: {aliases}
- 상태: 시작전
- 날짜: {date}
- 파일: {filename}
- 관련 스펙: {related_count}개 링크됨
```

---

## 공통: 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
