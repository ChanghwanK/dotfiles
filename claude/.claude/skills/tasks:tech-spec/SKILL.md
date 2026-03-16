---
name: tasks:tech-spec
description: |
  인프라/DevOps Tech Spec 스킬. Quick mode(즉시 생성)와 Standard mode(Phase 1-3 대화형) 지원.
  Quick mode: 대화 맥락을 분석하여 한 번에 Tech Spec 생성. Standard mode: 문제 분석 → 목표 설정 → 계획 설계.
  사용 시점: (1) 인프라 변경 계획 수립, (2) 설계 의사결정 구조화, (3) 새 프로젝트 킥오프, (4) 대화 내용을 빠르게 스펙 정리.
  트리거 키워드: "tech spec", "기술 스펙", "스펙 문서", "tech-spec 작성", "/tasks:tech-spec", "/work:tech-spec".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py *)
  - Write(/tmp/tech-spec-content.json)
  - Edit
  - Agent
---

# tasks:tech-spec — Tech Spec 스킬

Tech Spec 문서를 Obsidian에 생성한다. Quick mode(즉시)와 Standard mode(대화형) 두 가지 모드 지원.

**저장 경로**: `03. Resources/tech-specs/`
**운영 스킬**: Phase 4(실행)·5(측정)는 `tasks:tech-spec-ops` 스킬에서 수행.

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

### Step 4 — 저장 전 자동 검증 (경고만, 차단 안 함)

아래 검증 항목을 체크하되, **실패해도 저장을 진행**한다. 경고만 사용자에게 알린다.

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
- 필요시 **Explore Agent** spawn → 현재 상태 조사 (kubectl, Grafana 쿼리, 코드 탐색 등)

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

**산출물**: `## 현재 상태와 목표` 섹션 초안 (변경 사항 Diff, Non-Goals, 성공 기준 포함) → 사용자 확인 후 Phase 3.

### Phase 3: 계획 설계 — "어떻게 할 것인가?"

Phase 1-2 결과를 바탕으로 설계를 협업 방식으로 구체화한다. 3단계로 진행.

---

#### Step 3-1: 설계 브리핑 (Claude → 사용자)

Phase 1-2 결과를 기반으로 아래 내용을 브리핑한다:

- **기술 접근 방식**: 어떤 컴포넌트를 어떻게 변경할지 요약
- **대안 후보 2-3개**: 각 대안의 트레이드오프 (생산성 / 비용 / 안정성 기준)
- **스펙 아티팩트 후보**: 이 작업에서 변경될 파일 목록 (Git 경로 포함 예시)
- **SOCRAAI 표준 초기 검증 결과**:

| 항목 | 확인 내용 |
|------|----------|
| 우선순위 | 생산성 > 비용 > 안정성 가중치 부합? |
| 네트워크 | Cross-zone 통신 지양, VPC Endpoint, NAT GW 회피? |
| 비용 | 오픈소스 우선 vs Managed Service 비용 비교? |
| Dev/Stg | 비용 최적화 (Single AZ)? Prod과 불필요한 동일 스펙 아닌지? |

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
# {제목}

## 왜 이걸 해야 하는가?           ← Phase 1 / Quick Step 3
현재 문제/동기/배경

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
## 실행 계획                       ← Phase 3 / Quick Step 3
- [ ] Phase 1 — {Phase 제목}
- [ ] Phase 2 — {Phase 제목}
- [ ] ...

### Phase 1. {Phase 제목}
- Action 1-1: {구체적 액션}
- Action 1-2: {구체적 액션}

### Phase 2. {Phase 제목}
- Action 2-1: {구체적 액션}

## 임팩트 측정                     ← Phase 3 / Quick Step 3

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
  "blocks": "# 제목\n\n## 왜 이걸 해야 하는가?\n..."
}
```

### Step 2 — 스크립트 실행

```bash
python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py create \
  --title "제목" \
  --tags "Kubernetes,AWS" \
  --spec-type "helm-chart,k8s-manifest" \
  --content-file /tmp/tech-spec-content.json
```

태그는 원래 이름으로 전달 → 스크립트가 `domain/` 형식으로 자동 정규화.
aliases도 제목+본문에서 자동 추출.

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
