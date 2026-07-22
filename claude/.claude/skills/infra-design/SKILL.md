---
name: infra-design
description: |
  인프라 설계 제안 스킬. 공식 문서·권위 소스(T1/T2)만으로 근거를 조사하고(커뮤니티 배제), devops-wiki로 현재 인프라 컨텍스트를 파악한 뒤, 트레이드오프 분석과 공식 문서 인용을 필수로 포함한 설계안을 제안한다.
  사용 시점: (1) AWS 네트워크 설계(VPC, PrivateLink 등), (2) K8s 클러스터 토폴로지 구성, (3) 데이터 인프라 설계(ClickHouse, Strimzi Kafka 등), (4) 신규 컴포넌트 도입 검토.
  트리거 키워드: "설계해줘", "설계 제안", "아키텍처 제안", "도입 검토", "/infra-design".
model: sonnet
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Agent
  - mcp__aws-pricing
---
# infra-design Skill

공식 문서 기반 근거 조사 + 현재 인프라 컨텍스트 분석을 결합해, 트레이드오프 비교표와 공식 문서 인용이 붙은 인프라 설계안을 제안한다.

---

## 핵심 원칙

- **T1/T2 소스 전용**: 공식 문서(T1) > 권위 사이트·빅테크 엔지니어링 블로그(T2)만 근거로 쓴다. Reddit·Stack Overflow·개인 블로그 등 커뮤니티 소스는 검색 대상에서 배제한다. tier 정의·최신성 판정: `references/source-policy.md`.
- **현재 인프라 컨텍스트 필수**: 설계 제안 전에 반드시 devops-wiki(ADR·context·guardrails)와 실제 배포 구성을 파악한다. wiki는 리포별로 3개(kubernetes: EKS·GitOps, k8s-on-premise: IDC·GPU, terraform: AWS IaC)이며 설계 주제에 따라 선택한다 (`references/domain-doc-map.md`의 "Wiki 소스 선택" 표). 일반론이 아니라 "우리 인프라에서" 성립하는 설계를 제안한다.
- **트레이드오프 분석 필수**: 설계안은 반드시 2개 이상 옵션을 성능/비용/운영 부담/복잡도/위험도 축으로 비교하고, 2차 효과(6개월 후)와 one-way door 여부를 명시한 뒤 조건부 추천한다.
- **인용 강제**: 설계 근거가 되는 모든 주장(limit·quota·모범사례·동작 방식)에 인라인 인용 `[n]`을 달고 References에 매핑한다. 출처 없는 설계 근거는 쓰지 않는다.
- **환각 금지**: `WebFetch`로 실제 확인한 내용만 근거로 쓴다. 소스 간 상충 시 어느 소스가 무엇을 말하는지 명시한다.
- **읽기 전용**: 조사·분석·설계 제안까지만 수행한다. 구현(YAML/Terraform 작성, PR)은 별도 flow로 handoff 제안만 한다.

---

## 워크플로우

### Step 1: 설계 요구사항 구체화

요청에서 다음을 확정한다. 불명확한 항목이 있으면 조사 전에 사용자에게 질문한다:

- **대상 영역**: 무엇을 설계하는가 (예: PrivateLink 연동, ClickHouse 클러스터, Strimzi Kafka, K8s CP 구성)
- **목표/동인**: 왜 필요한가 (신규 요구, 비용 절감, 성능, 보안/컴플라이언스)
- **제약**: 규모(트래픽·데이터량), 환경(dev/stg/prod/IDC), 예산 감도, 마감
- **서브질문 분해**: 설계 결정에 필요한 조사 축을 도출한다 (예: 아키텍처 패턴, limit/quota, HA 구성, 비용 모델, 운영 모범사례)

도메인별 공식 문서 seed와 조사 축 예시: `references/domain-doc-map.md`를 Read해서 참조한다.

### Step 2: 병렬 수집 (Sub-Agent fan-out)

**단일 메시지에서 아래 에이전트를 동시 호출한다** (독립 작업이므로 병렬):

1. **context-collector** (subagent_type: `general-purpose`, model: `sonnet`, 1개)
   - `references/domain-doc-map.md`의 "Wiki 소스 선택" 표로 설계 주제에 맞는 wiki 경로를 고른다 (kubernetes wiki 기본 포함, IDC·GPU·온프레미스 주제면 k8s-on-premise wiki, AWS 네트워크·IaC 주제면 terraform wiki 추가)
   - `agents/agent-context-collector.md`를 Read하고 `{design_topic}`, `{focus_areas}`, `{wiki_paths}`를 치환해 프롬프트로 전달
   - 선택된 wiki들(ADR·context·guardrails) + 실제 배포 구성에서 현재 상태·기존 결정·제약을 수집

2. **doc-researcher** (subagent_type: `general-purpose`, model: `sonnet`, 서브질문 그룹당 1개, 최대 4개)
   - `agents/agent-doc-researcher.md`를 Read하고 `{domain}`, `{sub_questions}`, `{official_domains}`를 치환해 전달
   - `{official_domains}`는 `references/domain-doc-map.md`의 해당 도메인 seed를 사용
   - 서브질문이 2개 이하면 researcher 1개로 묶는다. 도메인이 이질적일 때만 분할한다 (예: AWS 네트워크 + Kafka 혼합 설계)

### Step 3: 수집 결과 검증

에이전트 결과를 통합하기 전에 점검한다:

- 모든 주장에 URL + 날짜/버전이 붙어 있는가. 없는 주장은 버리거나 직접 `WebFetch`로 재확인한다
- versioned/아카이브 URL(`/v1.18/`, `archive.` 등)이 남아 있으면 current/latest로 정규화해 재확인한다 (`references/source-policy.md`의 판정 절차)
- 설계를 좌우하는 핵심 수치(limit, quota, 기본값)는 T1 근거인지 확인한다. T2뿐이면 T1로 교차 확인한다
- context-collector 결과 중 설계와 충돌하는 기존 ADR·guardrail이 있으면 명시적으로 목록화한다

### Step 4: 설계 옵션 도출

수집한 근거 + 현재 인프라 컨텍스트를 결합해 **2개 이상의 설계 옵션**을 도출한다:

- 각 옵션은 아키텍처 개요, 핵심 구성요소, 우리 인프라와의 접점(기존 컴포넌트 재사용 여부)을 포함한다
- 옵션이 실질적으로 1개뿐이면(기술 제약으로 대안 부재) 그 사실과 이유를 명시하고 "채택 vs 미채택(현상 유지)"을 옵션으로 세운다
- 기존 팀 표준·ADR과 다른 방식을 제안할 때는 이유를 명시한다

### Step 5: 트레이드오프 분석 (MUST)

옵션을 구조적으로 비교한다. 이 섹션이 없는 설계 제안은 내보내지 않는다:

- **비교표**: 성능 / 비용(월 비용 추정 포함) / 운영 부담 / 복잡도 / 위험도 5축
- **비용 단가 확인 (MUST)**: 단가 근거 없는 월 비용 수치를 표에 넣지 않는다. 단가 확인 우선순위:
  1. aws-pricing MCP가 연결된 세션이면 `ToolSearch`로 스키마를 로드해 단가를 조회한다 (AWS 리소스)
  2. MCP 미연결 또는 비AWS 리소스면 공식 pricing 페이지를 `WebFetch`로 확인한다
  3. 둘 다 실패한 항목만 "추정" 표기하고 산정 가정(인스턴스 타입·수량·전송량)을 병기한다
- **2차 효과**: 각 옵션 선택 시 6개월 후 생기는 문제·부채 (증가율이 선형인지 복리인지)
- **one-way door**: 되돌리기 어려운 결정이면 명시적으로 표시
- **조건부 추천**: "A가 낫습니다"가 아니라 "X 상황이면 A, Y 상황이면 B" + 우리 인프라의 현재 상황이 어느 쪽인지 판단 근거
- **ROI Self-Check**: 신규 리소스·컴포넌트 도입이면 비용/단순성(Managed 대안)/운영 부담/기술 부채 4항을 점검해 결과를 표기한다

### Step 6: 출력 + 검증 + handoff

`assets/output-format.md`를 Read해서 그 템플릿으로 출력한다.

출력 직전 자가 점검(MUST):
- [ ] 현재 인프라 컨텍스트 섹션이 devops-wiki·src 실제 확인 기반인가 (추정이면 "(미확인)" 표기)
- [ ] 옵션이 2개 이상이고 트레이드오프 비교표가 있는가
- [ ] 각 영역의 핵심 설계 근거에 공식 문서(T1) 인용이 최소 1건 이상 있는가
- [ ] 인용 누락 주장이 없는가, References에 URL + tier + 날짜/버전이 있는가
- [ ] 비용 수치마다 단가 출처(aws-pricing MCP / 공식 pricing 페이지 / 추정)가 붙었는가
- [ ] 커뮤니티 소스(T3)가 References에 없는가
- [ ] one-way door 결정이 표시되었는가, 조건부 추천에 판단 근거가 있는가
- [ ] 기존 ADR·guardrail과의 충돌 여부를 명시했는가

점검 통과 후 handoff 제안(자동 실행 금지, 한 줄):
- 설계 확정 전 검증이 필요하면: `💡 /grill-me 로 이 설계를 Socratic 인터뷰로 검증할 수 있습니다.`
- 팀 공유가 필요하면: `💡 /notion:add-engineering-note 로 이 설계를 Notion에 기록할 수 있습니다.`
- 실행 계획화가 필요하면: `💡 /tasks:tech-spec 으로 Tech Spec으로 발전시킬 수 있습니다.`

---

## 주의사항

- 이 스킬은 **설계 제안 전용**이다. 범용 기술 조사는 `research`, 운영사례·커뮤니티 인사이트는 `research`의 blog-insight 모드로 라우팅한다 (이 스킬에서 커뮤니티 소스를 쓰지 않는 이유: 설계 근거는 검증 가능한 공식 자료여야 하기 때문).
- devops-wiki가 없는 환경(다른 머신)에서는 컨텍스트 수집을 건너뛰지 말고 사용자에게 현재 인프라 상태를 질문한다.
- 비용 수치는 Step 5의 단가 확인 우선순위(aws-pricing MCP → 공식 pricing 페이지 → 추정)를 거친 것만 쓴다. "추정"은 최후 수단이며 산정 가정(인스턴스 타입·수량·데이터 전송량)을 반드시 병기한다. AWS 단가는 리전(`ap-northeast-1`)을 명시해 조회한다.
- `WebSearch`는 US 기준 결과를 반환한다. AWS 문서는 리전별 차이(Tokyo `ap-northeast-1` 기준)를 확인한다.
- 에이전트 결과가 비거나 실패하면 해당 축을 직접 `WebSearch`/`WebFetch`로 보완한다. 근거 없이 설계로 진행하지 않는다.
