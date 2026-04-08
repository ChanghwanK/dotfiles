---
name: grill-me
description: |
  설계/계획 문서를 Decision Tree 방식으로 체계적으로 검증하는 Socratic 인터뷰 스킬.
  모든 설계 의사결정을 계층적으로 분해하고 branch별로 질문하여 빈틈을 탐지한다.
  사용 시점: (1) Tech Spec 완성 후 리뷰, (2) 설계 대화 중 의사결정 검증,
  (3) 기존 계획/문서의 스트레스 테스트, (4) 코드베이스 기반 설계 검증.
  트리거 키워드: "grill me", "설계 검증", "계획 검증", "decision review",
  "스트레스 테스트", "의사결정 검증", "/grill-me".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py *)
  - Read
  - Glob
  - Grep
  - Agent
---

# grill-me — 설계 Decision Tree 검증 스킬

설계/계획의 모든 의사결정을 Decision Tree로 분해하고, 각 branch를 끈질기게 검증한다.
빈틈을 탐지하고 SOCRAAI 엔지니어링 원칙과의 정합성을 확인한다.

---

## 핵심 원칙

- **끈질긴 검증자**: 편의적 답변에 만족하지 않는다. "왜?", "대안은?", "영향은?"을 반복
- **Decision Tree 우선**: 설계를 의사결정 계층으로 분해한다 (Root → Child → Leaf)
- **1문 1답**: 질문을 한 번에 하나씩. 답변을 기다린 후 다음으로 진행
- **코드로 검증**: 질문의 답이 코드/설정에서 확인 가능하면 Explore Agent 자동 spawn
- **SOCRAAI 원칙 연결**: 모든 branch에서 생산성 > 비용 > 안정성 트레이드오프 체크

---

## Step 0 — 입력 소스 결정

사용자 메시지와 대화 맥락을 분석하여 입력 소스를 자동 결정한다.

### 소스 감지 규칙

| 조건 | 소스 모드 | 액션 |
|------|----------|------|
| 직전에 `/tasks:tech-spec` 세션이 있었음 | **Conversation 모드** | 대화 맥락에서 설계 의사결정 추출 |
| `/grill-me {검색어}` 또는 "Tech Spec 검증" 언급 | **Tech Spec 모드** | `tech-spec.py search`로 문서 로드 |
| 파일 경로 언급 (예: `~/...yaml`, `kubernetes/src/...`) | **File 모드** | Read 도구로 파일 직접 로드 |
| 그 외 (일반 대화) | **Conversation 모드** | 현재 대화 맥락 분석 |

### Tech Spec 모드 로딩 절차

```bash
# 1. 검색어로 Tech Spec 찾기
python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py search \
  --query "{검색어}"

# 2. 찾은 Tech Spec 섹션별 읽기
python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py read-section \
  --title "{Tech Spec 제목}" \
  --section "왜 이걸 해야 하는가"

python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py read-section \
  --title "{Tech Spec 제목}" \
  --section "현재 상태와 목표"

python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py read-section \
  --title "{Tech Spec 제목}" \
  --section "설계"

python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py read-section \
  --title "{Tech Spec 제목}" \
  --section "왜 이 방법인가"
```

소스 로딩 완료 후, 아래 확인 메시지 출력:

```
📋 입력 소스: {소스 모드}
분석 대상: {Tech Spec 제목 또는 "현재 대화 맥락"}

이 설계에서 {N}개의 의사결정 후보를 발견했습니다.
Decision Tree를 구성할게요. (y/n)
```

---

## Step 1 — 설계 맥락 수집 및 의사결정 추출

로드된 소스에서 **명시적/암묵적 의사결정**을 추출한다.

**추출 대상:**
- "A 대신 B를 선택했다" — 명시적 기술 선택
- "단순하게 유지한다" — 범위 결정
- "비용 절감을 위해..." — 제약 기반 선택
- "향후 확장을 고려해..." — 미래 설계 가정
- "Dev/Stg 환경은 별도로..." — 환경별 전략

**추출 메모 형식:**

```
의사결정 #1: {결정 내용 한 줄}
- 결정 값: {선택한 것}
- 언급된 이유: {명시된 근거 또는 "미명시"}
- 관련 컴포넌트: {영향받는 시스템}
- SOCRAAI 원칙: {생산성/비용/안정성 중 관련 축}
```

---

## Step 2 — Decision Tree 구축 및 제시

추출된 의사결정을 계층 구조로 분류한다.

### 노드 분류 기준

| 노드 타입 | 정의 | 예시 |
|-----------|------|------|
| **Root** | 전체 방향을 결정하는 핵심 선택 (1~3개) | "VictoriaMetrics를 직접 운영 vs AWS Managed" |
| **Child** | Root 결정에 종속된 선택 (2~4개/Root) | "단일 노드 vs 클러스터 모드" |
| **Leaf** | Child 결정에 종속된 구체적 설정 (0~2개/Child) | "retention 기간 30일 설정" |

### 트리 시각화 출력

```
## 설계 Decision Tree

🌳 Root 1: {결정 내용}
  ├─ 🌿 Child 1-1: {결정 내용}
  │   └─ 🍃 Leaf 1-1-1: {결정 내용}
  └─ 🌿 Child 1-2: {결정 내용}
      ├─ 🍃 Leaf 1-2-1: {결정 내용}
      └─ 🍃 Leaf 1-2-2: {결정 내용}

🌳 Root 2: {결정 내용}
  └─ 🌿 Child 2-1: {결정 내용}

총 {N}개 노드 ({R}개 Root, {C}개 Child, {L}개 Leaf)
```

트리 출력 후 사용자에게 확인:

```
이 순서로 검증을 진행할까요?
특정 branch부터 시작하고 싶으면 번호를 말씀해주세요. (예: "Root 2부터")
```

---

## Step 3 — Branch별 Socratic 인터뷰

각 노드를 순서대로 인터뷰한다. **1문 1답** 원칙 엄수.

### 노드별 질문 구성

**Root 노드 (3개 질문 순서):**

1. **동기(Why)**: "왜 {선택한 것}을 선택했나요? 해결하려는 핵심 문제는 무엇인가요?"
2. **대안(What-if)**: "가장 유력했던 대안은 무엇이었나요? 그것을 선택하지 않은 결정적 이유는?"
3. **영향(Impact)**: "이 선택이 잘못되었다면 어떤 방식으로 문제가 드러날까요? 롤백 전략은?"

**Child 노드 (1~2개 질문):**

1. **정합성(Consistency)**: "이 선택이 Root의 {부모 결정}과 어떻게 연결되나요?"
2. **비용/복잡도(Tradeoff)**: (선택적) "이 설정으로 인한 운영 부담은? 더 단순한 방법은 없었나요?"

**Leaf 노드 (0~1개 질문):**

1. **근거(Evidence)**: (복잡한 Leaf에만) "이 값은 어떻게 결정되었나요? 측정 근거가 있나요?"

### SOCRAAI 원칙 체크 질문

각 Root 인터뷰 완료 후, 관련 원칙을 체크:

```
💡 SOCRAAI 원칙 체크 ({해당 원칙}):
→ {원칙 관련 확인 질문}
```

| 원칙 | 체크 포인트 | 예시 질문 |
|------|------------|----------|
| 생산성 > 비용 > 안정성 | 우선순위 적용이 명시적인가? | "이 결정에서 생산성과 비용 중 어떤 것을 우선했나요?" |
| Self-Service | 제품팀이 인프라 팀 없이 사용 가능한가? | "이 변경 후 제품팀이 자체적으로 뭘 할 수 있게 되나요?" |
| 비용 최적화 | Managed Service vs 오픈소스 비교가 있었나? | "비용 비교 시뮬레이션을 해보셨나요?" |
| 네트워크 최적화 | Cross-zone 통신, NAT GW 회피 고려? | "이 트래픽 경로에서 Cross-zone 비용이 발생하나요?" |
| Dev/Stg 비용 | 비프로덕션 환경이 과도하게 설계되지 않았나? | "Dev/Stg는 Single AZ로 운영하고 있나요?" |

### 코드베이스 탐색 분기

질문에 대한 답이 "현재 코드/설정을 보면 알 수 있다"고 판단되면:

```
잠깐, 이 부분은 현재 코드베이스에서 직접 확인해볼게요.
```

→ `agents/agent-codebase-explorer.md` 프롬프트로 **Explore Agent** spawn:

```
Agent(
  subagent_type: "Explore",
  prompt: agents/agent-codebase-explorer.md 내용 (question, scope 치환)
)
```

Agent 결과를 인터뷰에 통합하여 후속 질문 또는 확인 결과로 제시.

### 탈출 경로 (언제든 사용 가능)

| 키워드 | 동작 |
|--------|------|
| "패스", "pass", "건너뛰" | 이 노드 Skip, 다음으로 이동. Branch 상태: Skipped |
| "충분해", "그만", "enough" | 인터뷰 즉시 종료, Step 4(요약) 진행 |
| "힌트" | 이 결정과 관련된 SOCRAAI 사례 또는 고려 기준 힌트 제공 |
| "코드 확인해줘" | Explore Agent를 명시적으로 spawn |

### Branch 상태 추적

인터뷰 중 각 노드 상태를 내부적으로 기록:

| 상태 | 의미 |
|------|------|
| ✅ Resolved | 근거가 명확히 확인됨 |
| ⚠️ Gap | 근거 불충분 또는 추가 검토 필요 |
| 🔍 Explored | Explore Agent로 코드 확인 완료 |
| ⏭️ Skipped | 사용자가 패스 요청 |

---

## Step 4 — 검증 요약

모든 branch 인터뷰 완료(또는 "충분해" 종료) 시 아래 형식으로 요약.

### 요약 출력 형식

```
## Grill-Me 검증 결과: {설계 제목}

### Decision Tree 결과 테이블

| # | 의사결정 | 타입 | 상태 | 비고 |
|---|----------|------|------|------|
| R1 | {결정 내용 요약} | Root | ✅ Resolved | {한 줄 요약} |
| C1 | {결정 내용 요약} | Child | ⚠️ Gap | {문제 요약} |
| L1 | {결정 내용 요약} | Leaf | 🔍 Explored | {확인 결과} |
| R2 | {결정 내용 요약} | Root | ⏭️ Skipped | — |

### 발견된 Gap 목록

| # | Gap 설명 | 심각도 | 권고 액션 |
|---|----------|--------|----------|
| 1 | {구체적인 빈틈} | 🔴 High / 🟡 Mid / 🟢 Low | {해결 방향} |

**심각도 기준:**
- 🔴 High: 배포 전 반드시 해결 (보안, 데이터 손실, 비용 급증 리스크)
- 🟡 Mid: 1주 내 해결 권고 (운영 부담, 확장성 우려)
- 🟢 Low: 나중에 개선 가능 (문서 부재, 최적화 여지)

### SOCRAAI 원칙 정합성

| 원칙 | 평가 | 코멘트 |
|------|------|--------|
| 생산성 우선 | ✅ / ⚠️ / ❌ | {한 줄 평가} |
| Self-Service | ✅ / ⚠️ / ❌ | {한 줄 평가} |
| 비용 최적화 | ✅ / ⚠️ / ❌ | {한 줄 평가} |
| 네트워크 효율 | ✅ / ⚠️ / ❌ | {한 줄 평가} |
| Dev/Stg 비용 | ✅ / ⚠️ / ❌ | {한 줄 평가} |

### 권고 변경사항

{Gap이 있는 경우만 작성. 없으면 "특이사항 없음."}

1. {구체적 변경 제안 — 파일 경로 또는 설정값 포함}
2. {구체적 변경 제안}
```

---

## Step 5 — 후속 액션 제안

요약 출력 후, 아래 후속 옵션을 제안한다:

```
다음 중 어떻게 진행할까요?

A) Gap을 Tech Spec에 반영 → /tasks:tech-spec-ops 로 업데이트
B) 권고 변경사항 즉시 구현 → 관련 파일 직접 수정
C) 결과를 Obsidian에 저장 → 나중에 참고
D) 종료
```

### Option A: Tech Spec 반영

사용자가 A를 선택하면:
1. 발견된 Gap과 권고 변경사항을 정리
2. "이 내용을 Tech Spec의 `## 설계` 및 `## 실행 계획` 섹션에 반영하려면 `/tasks:tech-spec-ops`를 사용하세요." 안내

---

## 인터뷰 진행 예시

```
[사용자] /grill-me VictoriaMetrics 도입 스펙

[Claude] 📋 입력 소스: Tech Spec 모드
분석 대상: "VictoriaMetrics 단독 운영 전환"
3개의 의사결정 후보를 발견했습니다. Decision Tree를 구성할게요. (y/n)

[사용자] y

[Claude] ## 설계 Decision Tree
🌳 Root 1: AWS Managed Prometheus 대신 VictoriaMetrics 직접 운영
  ├─ 🌿 Child 1-1: 단일 노드 모드 선택 (클러스터 모드 미사용)
  │   └─ 🍃 Leaf 1-1-1: 30일 retention 설정
  └─ 🌿 Child 1-2: KEDA 기반 scrape 간격 조정 없음

🌳 Root 2: Dev/Stg에도 동일 스펙 적용
  └─ 🌿 Child 2-1: Single AZ 없이 Multi-AZ

총 6개 노드 (2개 Root, 3개 Child, 1개 Leaf)
이 순서로 진행할까요?

[사용자] 응

[Claude] --- Root 1/2 ---
VictoriaMetrics 직접 운영을 선택하셨는데, 해결하려는 핵심 문제가 무엇인가요?
AWS Managed Prometheus의 어떤 한계점이 결정에 영향을 미쳤나요?

[사용자] {답변}
...
```

---

## 검증 (내부용)

인터뷰 시작 전 체크:

- [ ] Step 0 소스 감지가 완료되었는가
- [ ] Decision Tree에 최소 1개 Root 노드가 있는가
- [ ] 사용자가 트리 구조를 확인했는가

인터뷰 종료 후 체크:

- [ ] Step 4 요약에 Decision Tree 결과 테이블이 포함되었는가
- [ ] Gap이 있는 경우 심각도가 분류되었는가
- [ ] SOCRAAI 원칙 정합성 테이블이 작성되었는가
- [ ] Step 5 후속 액션이 제안되었는가
