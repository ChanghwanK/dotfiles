---
name: tasks:tech-spec
description: |
  인프라/DevOps Tech Spec 스킬. Quick mode(즉시 생성)와 Standard mode(Phase 1-3 대화형) 지원.
  Quick mode: 대화 맥락을 분석하여 한 번에 Tech Spec 생성. Standard mode: 문제 분석 → 목표 설정 → 계획 설계.
  확정한 스펙은 Notion 업무 노트(notion:add-engineering-note 템플릿)에 저장한다. Obsidian에는 저장하지 않는다.
  사용 시점: (1) 인프라 변경 계획 수립, (2) 설계 의사결정 구조화, (3) 새 프로젝트 킥오프, (4) 대화 내용을 빠르게 스펙 정리,
  (5) notion:add-engineering-note가 grill-me 인터뷰 뒤 호출(eng-note 모드).
  트리거 키워드: "tech spec", "기술 스펙", "스펙 문서", "tech-spec 작성", "/tasks:tech-spec", "/work:tech-spec".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/notion:add-engineering-note/scripts/notion-eng-note.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py read-page *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py update-why *)
  - Skill
  - Write
  - Edit
  - Agent
---

# tasks:tech-spec: Tech Spec 스킬

Tech Spec을 만들고, 확정한 내용을 Notion Engineering DB 업무 노트에 저장한다. Quick mode(즉시)와
Standard mode(대화형) 두 가지 모드를 지원한다.

**저장 위치**: Notion 업무 노트. 템플릿 구조·sections 키·저장 명령의 단일 출처는
`notion:add-engineering-note` SKILL.md의 "템플릿 구조와 sections 키"와 Step 3~5다.
Obsidian(`03. Resources/tech-specs/`) 저장은 2026-09-27에 제거했다. 기존 Obsidian 스펙을 다루는
`tasks:tech-spec-ops`와 `tech-spec.py`는 과거 문서용으로만 남아 있다.

---

## Step 0: 호출 경로와 연결 Task 확인

### eng-note 모드 (notion:add-engineering-note에서 호출)

args에 eng-note 모드, 연결할 Task page_id, grill-me 인터뷰 결과가 들어온다.

- grill-me에서 확정된 결정·Before/After·Goals는 **다시 묻지 않고** Phase 1~3 초안에 바로 반영한다.
  남은 Gap만 해당 Phase에서 다룬다.
- 기본은 Standard mode다. 사용자가 인터뷰 생략을 명시해 넘어온 경우만 Quick mode로 진행한다.
- 저장은 "공통: 저장 워크플로우"를 따른다.

### 직접 호출 (/tasks:tech-spec)

- 연결할 Task를 확인한다: "이 스펙을 연결할 Task가 있나요?" 대화에 Task 링크나 page_id가 있으면 묻지 않는다.
- 연결할 Task가 없는데 실제 업무라면 `tasks:capture`로 먼저 Task를 만든다(제목은 스펙 제목과 같게).
- 작업 워크플로우는 **grill-me로 작업 파악 → tech-spec으로 작성 → 업무 노트 반영**이다. 직접 호출이어도 이 순서를 지킨다.
  이 세션에서 grill-me 인터뷰가 아직 없었다면 Task 확인 직후 `grill-me`를 Skill 도구로 호출한다(args: eng-note 모드,
  Task page_id, `notion-task.py read-page`로 읽은 Task 본문 요약). 인터뷰 결과를 받아 아래 eng-note 모드와 같이 진행한다.
- 이미 grill-me 인터뷰를 마친 세션이면 다시 인터뷰하지 않는다. 사용자가 "인터뷰 생략"을 명시한 경우만 건너뛰고 Quick mode로 간다.

---

## 모드 분기

| 조건 | 모드 |
|------|------|
| `/work:tech-spec` 또는 "빠르게 스펙 정리", "스펙으로 정리해줘" | **Quick mode** |
| `/tasks:tech-spec` 또는 기본 | **Standard mode** |

---

## Quick Mode: 즉시 생성

Phase 1-3 대화 없이 **현재 대화 맥락을 분석하여 한 번에 모든 섹션을 채운다**.

### Step 1: 대화 맥락 분석 + 유형 판단

대화에서 다음을 파악한다:
- 작업 주제와 동기
- **운영 변경**(ConfigMap 변경, 스케일링, 마이그레이션 등)인지 **인프라 설계**(새 클러스터, VPC, 신규 서비스 등)인지
- **스펙 유형 판단**: 어떤 Machine-Readable 스펙이 변경되는가?
  - 운영 변경(ops-change)이면 스펙 아티팩트 섹션 생략
  - 인프라 설계면 스펙 아티팩트 테이블 필수 작성
- 핵심 의사결정과 대안
- 실행 계획과 영향 범위

**파악한 내용으로 바로 Step 2로 가지 않는다.** "공통: 문제 검증 게이트"(G1~G4)를 먼저 통과시킨다.
Quick mode는 사용자 확인 단계가 없어 잘못된 문제 정의가 그대로 저장되므로, 이 게이트가 유일한 가드다.

### Step 2: 제목 결정

- **제목**: 작업을 간결하게 설명, 단어 구분은 공백으로. 연결된 Task가 있으면 Task 제목과 개념적으로 대응되게 짓는다.

### Step 3: 템플릿 채우기

아래 템플릿 구조에 맞춰 모든 섹션을 한 번에 작성:
- **운영 변경**: `## 설계` 섹션 생략 가능. `## 실행 계획`과 `## 임팩트 측정`에 집중.
- **인프라 설계**: `## 설계` 섹션 상세 작성. 다이어그램, 리소스 스펙, 제약조건 포함.
- **변경 사항 Diff**: `### 변경 사항 (Diff)` 섹션에 변경 대상별 As-Is → To-Be를 테이블 또는 diff 블록으로 작성.

**목표 섹션 작성 시, 경량 Goal Challenge**:

대화형 질문 없이 진행하되, `## 현재 상태와 목표` 섹션의 Non-Goals 또는 성공 기준 작성 시 아래를 자동으로 반영한다:

- 대화 맥락에서 ROI가 불명확하면 → 성공 기준에 "왜 이 수치인가?" 근거 한 줄 추가
- **ROI 분류**: [work-definition-framework.md](~/workspace/riiid/kubernetes/devops-wiki/01-decisions/work-definition-framework.md)의 6유형 중 하나로 분류 + L1/L2/L3/보류 레벨을 산출해 성공 기준 옆에 괄호로 표기 (예: "latency -30% (L2·기술 부채형)").
- 비가역적 변경(삭제, 마이그레이션)이 포함되면 → Non-Goals에 롤백 시나리오 명시
- 네트워크/비용 영향이 감지되면 → Diff 테이블에 해당 항목 행 추가
- Quick mode 완료 후 출력 하단에 제안이 있으면 `> 💡 참고:` 블록으로 1-2개 병기

### Step 4: 저장 전 자동 검증 (경고만, 차단 안 함)

아래 검증 항목을 체크하되, **실패해도 저장을 진행**한다. 경고만 사용자에게 알린다.

### Step 4-R: Tech Spec 리뷰 Agent 실행

자동 검증 직후, 저장 전에 리뷰 Agent(F)를 실행한다. 아래 "공통: Tech Spec 리뷰" 섹션 참조.

### Step 5: 저장 워크플로우 실행

아래 "저장 워크플로우" 섹션과 동일. content.json → 스크립트 실행 → 결과 출력.

---

## Standard Mode: Phase 1-3 (대화형)

Claude와 함께 문제를 분석 → 목표 설정 → 계획 설계하여 구조화된 Tech Spec 문서를 만든다.

### Phase 1: 문제 분석 ("왜 해야 하는가?")

대화 맥락이 충분하면 바로 분석 결과를 제시. 부족하면 질문으로 파악한다.

**파악할 것:**
- 어떤 문제를 해결해야 하는가?
- 문제 발생 배경과 근본 원인. 측정으로 확정한 원인만 사실로 쓴다. 원인이 미확인이면 원인 가설 단계를 거친다
  (CLAUDE.md Hypothesis-First): 후보 둘 이상 + 그 외, 후보별로 보여야 할 것, 후보를 가르는 변별 증거, 측정 결과
- 현재 영향 (장애 건수, 복구 시간, 변경 실패율, 비용)
- 왜 지금 해야 하는가? (긴급도, 의존성)

**"대화 맥락이 충분하면 바로 제시"는 충분성(정보의 양)만 보는 조건이다.** 타당성(그게 증상인지
메커니즘인지)은 "공통: 문제 검증 게이트"(G1~G4)로 별도 확인한 뒤 산출물을 제시한다.

**현재 상태 조사: 필요한 Agent만 선택적으로 실행**

대화 맥락에서 `{sphere}`, `{circle}`, `{env}`를 추출한다. 불명확하면 "unknown"으로 대체한다.
아래 판단 기준에 따라 필요한 Agent만 선택하여 실행한다. 선택된 것이 여러 개면 **동시에** spawn한다.

| Agent | 실행 조건 |
|-------|----------|
| **A: 클러스터 현재 상태** | sphere/circle이 특정되고, 현재 Pod/Deployment 상태를 모를 때 |
| **B: 메트릭 현황** | 에러율, 응답시간, 리소스 사용량, 비용 관련 수치가 필요할 때 |
| **C: 코드베이스 탐색** | 현재 values.yaml, chart 버전, 설정값을 확인해야 할 때 |

실행 방법: 해당 agent 파일을 Read한 뒤 placeholder를 대화 맥락으로 치환하여 실행한다.
- A: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-cluster-status.md`
- B: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-metrics-check.md`
- C: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-codebase-explore.md`

**생략 가능한 경우**: 대화 맥락에 이미 **조회로 확보된** 수치/상태 정보가 있거나, 순수 개념/설계 논의(새 아키텍처 구상, 기술 리서치)일 때는 Agent 전체 생략. **단, 그 수치가 이번 세션에서 Claude 자신이 쓴 요약 문장이면 생략 근거가 되지 않는다** (자기 인용은 측정이 아니다). 또한 Agent A/B/C는 알럿이 지목한 sphere/circle로 조사 범위를 좁히므로, 같은 메커니즘이 **다른 네임스페이스에 만든 여파**는 별도로 조회한다 (게이트 G2).

**산출물**: `## 왜 이걸 해야 하는가?` 섹션 초안을 사용자에게 제시.
사용자 확인("좋아", "진행해") → Phase 2로.

### Phase 2: 목표 설정 ("어디까지 할 것인가?")

오버엔지니어링 방지. `안정성 > 비용 > 가용성 수준` 기준으로 범위를 정리한다.
**줄이는 대상은 가용성 수준**(9의 개수, 이중화 범위, replica 수)이지 안정성(가드레일, 복구성,
correctness 가드)이 아니다. 안정성은 목적이고 가용성 수준은 비용에 맞춰 조절하는 변수다.

**할 것:**
- 목표를 명확한 문장으로 정의
- Before(현재) → After(목표) 구체화
- **Non-Goals**: 하면 좋지만 이번에는 안 하는 것을 명시 (스코프 통제)
- **성공 기준**: 완료 후 "작업 결과"에서 검증할 측정 가능한 수치 (예: latency -30%, 비용 $X 절감). `## 임팩트 측정 > 증명 기준`과 같은 지표를 쓴다
- **변경 사항 Diff**: Before → After 변화를 대상별로 테이블 정리. 코드/설정 수준 변경이 있으면 diff 블록 추가.

---

#### Goal Challenge: 엔지니어링 인사이트 (목표 확정 전 필수)

목표 초안을 작성한 직후, 확정 전에 아래 5가지 관점 중 **해당하는 것만 선택적으로** 제시한다. 모든 관점을 다 물어보지 않는다. Phase 1 맥락을 기반으로 판단한다.

| 관점 | 언제 제시 | 제안/질문 방향 |
|------|-----------|--------------|
| **스코프 적정성** | 범위가 크거나 여러 컴포넌트에 걸칠 때 | "한 번에 끝내기 어려운 크기인가? 먼저 완료 가능한 단위로 쪼갤 수 있는가?" |
| **ROI 검증** | 동기가 불명확하거나 "하면 좋을 것 같아서" 성격일 때 | "안 하면 실제로 어떤 문제가 생기는가? 투입 비용 대비 기대 효과가 충분한가?" → [work-definition-framework.md](~/workspace/riiid/kubernetes/devops-wiki/01-decisions/work-definition-framework.md)의 6유형 중 하나로 분류하고 L1/L2/L3/보류 레벨을 산출한다 |
| **숨은 의존성** | 네트워크/비용/다른 팀 영향이 예상될 때 | "이 변경이 의도치 않게 영향을 미치는 컴포넌트(Cross-zone 트래픽, NAT GW, 다른 팀 서비스)는 없는가?" |
| **더 단순한 대안** | 복잡한 설계나 신규 도입이 포함될 때 | "같은 목표를 더 적은 변경으로 달성할 방법은 없는가? 기존 레거시를 활용할 수 있는가?" |
| **되돌리기 비용** | 비가역적 변경(삭제, 마이그레이션, 외부 의존)이 포함될 때 | "실패 시 롤백이 쉬운가? 되돌리기 어려운 결정이 이번 범위에 포함되어 있는가?" |

**출력 형식 예시**:

```
💡 Goal Challenge: 목표를 확정하기 전에 몇 가지 체크해볼게요.

**[ROI 검증]** 현재 문제가 실제로 얼마나 자주 발생하나요?
장애 빈도나 비용 수치로 표현할 수 있다면 성공 기준이 훨씬 명확해집니다.
→ 유형: 기술 부채형, 레벨: L2

**[숨은 의존성]** 이 변경이 Cross-zone 트래픽이나 NAT GW 비용에 영향을 줄 수 있습니다.
해당 비용 항목을 Non-Goals로 명시하거나, 영향도를 Diff에 포함하는 것을 권장합니다.

위 내용을 반영해서 목표를 수정하시겠어요, 아니면 현재 초안으로 확정할까요?
```

사용자가 응답/수정 완료 → 목표 확정 → Phase 3으로 진행.

---

**산출물**: `## 현재 상태와 목표` 섹션 초안 (변경 사항 Diff, Non-Goals, 성공 기준 포함) → Goal Challenge 통과 후 사용자 확인 → Phase 3.

### Phase 3: 계획 설계 ("어떻게 할 것인가?")

Phase 1-2 결과를 바탕으로 설계를 협업 방식으로 구체화한다. 3단계로 진행.

---

#### Step 3-1: 설계 브리핑 (Claude → 사용자)

Phase 1-2 결과를 기반으로 아래 내용을 브리핑한다.
필요한 경우 Agent를 선택적으로 spawn하여 재료를 보충한다.

| Agent | 실행 조건 |
|-------|----------|
| **D: 설계 대안 조사** | 접근 방식이 아직 불분명하거나, 대안이 2개 이상 있어 비교가 필요할 때 |
| **E: SOCRAAI 표준 검증** | 네트워크 구조 변경, 신규 AWS 서비스 도입, 멀티 환경 설정이 포함될 때 |

실행 방법: 해당 agent 파일을 Read한 뒤 Phase 1-2 결과로 placeholder를 치환하여 실행한다.
선택된 것이 여러 개면 **동시에** spawn한다.
- D: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-design-research.md`
- E: `/Users/changhwan/.claude/skills/tasks:tech-spec/agents/agent-standard-validation.md`

**생략 가능한 경우**: Phase 1-2 대화에서 접근 방식과 대안이 이미 합의되었거나, ops-change처럼 설계 선택지가 없을 때는 Agent 생략 후 직접 브리핑 작성.

Agent 결과(또는 Phase 1-2 맥락)를 종합하여 아래 내용을 브리핑한다:

- **기술 접근 방식**: 어떤 컴포넌트를 어떻게 변경할지 요약
- **대안 후보 2-3개**: Agent D 결과 (각 대안의 트레이드오프 안정성 / 비용 / 운영 부담 기준)
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
- **Action item 단위**: 실행 가능한 **최소 단위**, PR 1개, 명령어 1회, 파일 1개 수정 수준.
  - `- [ ] N. {동사 + 목적어}` 형식 (예: `- [ ] 2. values.yaml에 replica 설정 추가`)
  - Phase 내 action item은 위에서 아래로 순차 진행 가능하도록 의존성 순서로 정렬

---

## 공통: 문제 검증 게이트 (초안 작성 전 필수)

Quick Step 1과 Standard Phase 1이 모두 이 게이트를 통과한 뒤에 초안을 쓴다.

두 경로 모두 "대화에서 무엇을 파악할지"는 정하지만 **"파악한 그것이 진짜 문제인지"는 검사하지
않는다.** 맥락이 풍부하면 그대로 통과하므로, 정보가 많은데 전부 증상인 경우를 걸러내지 못한다.
초안 작성 전에 아래를 확인하고, 걸리면 **사용자에게 묻기 전에 먼저 조회·측정으로 해소한다.**

| # | 자문 | 걸리면 할 일 |
|---|------|-------------|
| G1 | 알럿·에러 로그·대시보드 이상에서 출발했는가? | 신호가 아니라 **신호를 만든 메커니즘**을 문제로 쓴다. 알럿은 진입점이지 문제의 경계가 아니다 |
| G2 | 영향을 진단 도구의 단위(알럿 발화 횟수, 노드 수, 로그 라인 수)로 세지 않았는가? | **영향받는 대상**(파드, 요청, 배포, 사용자) 단위로 다시 센다 |
| G3 | 근거가 이번 세션에서 내가 쓴 요약 문장인가, 조회 가능한 측정치인가? | 자기 인용이면 재측정한다 |
| G4 | 근거의 표본이 n=1인가? | 일반화하지 않는다. 창을 7일 이상(30일 권장)으로 넓혀 다시 센다 |

**G3은 부정 결론에 특히 강하게 적용한다.** "영향 없음", "문제 없음", "무해함"은
*측정해서 0이었다*와 *찾아보지 않았다*가 겉으로 구분되지 않는다. 그 0을 만든 쿼리를 다시 실행한다.

**정본은 이 파일이 아니다.** kubernetes 레포에서 작업 중이면 이 절차의 단일 출처는
`devops-wiki/03-guardrails/rca-shared-criteria.md` §1이다 (Procedure step 4 + 4-way verdict).
위 G1~G4는 정본이 없는 프로젝트를 위한 이식 가능한 축약본이므로, 정본이 있으면 정본을 따른다.
선행 RCA의 verdict가 `MISMEASURED`이면 `## 왜 이걸 해야 하는가?`는 알럿이 아니라
**메커니즘이 만든 비용**을 문제로 쓴다.

### 게이트 결과 출력 형식 (통과·실패 모두)

초안을 제시할 때 게이트 결과를 아래 형식으로 **항상** 정리해 붙인다. 통과한 항목도 "왜 통과인지"를 한 줄로 남겨,
읽는 사람이 자문 목록을 몰라도 판정 근거를 따라갈 수 있게 한다. 자문 설명(G1~G4가 무엇을 묻는지)은 반복하지 않는다.

```
**문제 검증 게이트: {통과 N/4 | 걸림 M건}**
| 항목 | 결과 | 근거 / 조치 |
|------|------|-------------|
| G1 알럿 출발 | 해당 없음 | {알럿이 아닌 출발점 한 줄} |
| G2 영향 단위 | 통과 | {센 단위와 그것이 실제 영향 대상인 이유} |
| G3 측정 근거 | 걸림 → 해소 | {자기 인용이던 근거와 다시 측정한 결과·조회 방법} |
| G4 표본 | 걸림 → 미해소 | {표본 수와 미해소 이유, 초안에 (미확인) 표시한 위치} |
```

- 결과 값은 `통과` / `해당 없음` / `걸림 → 해소` / `걸림 → 미해소` 네 가지만 쓴다.
- `걸림 → 미해소`가 있으면 초안의 해당 문장에 `(미확인)`을 붙였는지 확인한다.

---

## 공통: 저장 전 자동 검증

Phase 3 완료 또는 Quick mode Step 4에서 전체 Tech Spec을 보여주고 자동 검증:

| 검증 항목 | 실패 시 |
|-----------|---------|
| 필수 H2 섹션 4개 존재 (왜 이걸 해야 하는가?, 현재 상태와 목표, 실행 계획, 임팩트 측정) | 누락 안내 |
| 임팩트에 숫자 or Before/After 패턴 | 경고 |
| 실행 계획에 롤백 언급 (인프라·설정 변경이 있는 스펙만. 문서·설계만인 스펙은 검사하지 않고 롤백 문장도 쓰지 않는다) | 경고 |
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
- (왜 발생했는가, 히스토리. 측정으로 확정한 원인은 사실로, 미확인이면 `(원인 미확인)` + 원인 후보와 변별 증거)

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

### 해결 가설
- (무엇을 적용하면 위 문제가 해결되는가, 한 문장. 개선 후 사람·팀이 얻는 것을 1~4 불릿으로 덧붙인다)

### 증명 기준
- (무엇이 어느 방향으로 얼마나 바뀌면 해결인가: 지표 현재값 → 목표값, 어떤 메트릭으로 어떻게 확인하는가, 판정 시점)
- (반증 조건: 이 관측이 나오면 가설이 틀린 것. 인프라·prod면 안 바뀔 것도 적는다)

## 실행 기록                       ← 진행 중 notion-task.py append-content --section "실행 기록"
> 실행 시작 후 기록

## 실제 결과 (Outcome)             ← 완료 후 append-content --section "작업 결과"
> 완료 후 작성
```

---

## 공통: 저장 워크플로우

확정된 스펙을 Notion 업무 노트에 저장한다. 절차는 `notion:add-engineering-note` SKILL.md가 단일 출처다.

1. **sections.json 작성**: 위 템플릿 구조의 각 섹션을 `notion:add-engineering-note`의 Step 3 매핑표로 sections 키에
   옮긴다(문제·배경 → `problem`/`root_cause`, 해결 가설·증명 기준 → `value`의 `*가설:*`·`*증명 기준:*` 라벨, Before/After → `before`/`after`,
   Diff → `changes`, 목표·성공 기준 → `goals`, Non-Goals → `non_goals`, 설계 + 왜 이 방법인가 → `design`,
   실행 계획 → `plan`). 매핑표 아래의 Goals·실행 계획 작성 기준을 함께 적용한다.
2. **노트 생성 + Task 동기화**: `notion:add-engineering-note`의 Step 4 명령을 실행한다(`notion-eng-note.py create --task`,
   이어서 `notion-task.py update-why`).
3. **결과 출력**: `notion:add-engineering-note`의 Step 5 형식을 따르고, 스펙 유형(`spec_type`)과 리뷰 Agent F 결과
   요약(❌/⚠️ 건수)을 한 줄씩 덧붙인다.

eng-note 모드에서 호출됐다면 이 단계의 결과를 호출한 스킬로 돌려주고, 호출한 스킬이 결과를 출력한다(중복 출력 방지).

---

## 공통: 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
