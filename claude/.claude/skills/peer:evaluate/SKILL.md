---
name: peer:evaluate
description: |
  동료 평가 스킬. claude-mem에 축적된 과거 작업 기록을 기반으로
  SOCRA AI DevOps 팀 동료 평가 프레임워크에 따른 구조화된 평가를 수행한다.
  사용 시점: (1) 분기별 동료 평가 작성 시, (2) 자기 성장 점검 시,
  (3) 특정 기간의 업무 성과를 정리하고 싶을 때.
  트리거 키워드: "동료 평가", "peer evaluate", "peer review", "평가해줘",
  "성과 평가", "자기 평가", "/peer:evaluate".
model: sonnet
allowed-tools:
  - Read
  - mcp__plugin_claude-mem_mcp-search__search
  - mcp__plugin_claude-mem_mcp-search__get_observations
  - mcp__plugin_claude-mem_mcp-search__timeline
---
# Peer Evaluate — SOCRA AI DevOps 동료 평가

claude-mem에 축적된 과거 작업 기록을 기반으로 SOCRA AI DevOps 팀 동료 평가
프레임워크에 따른 구조화된 평가를 수행한다.

---

## 핵심 원칙

- **증거 기반**: 기억이나 추측이 아닌 claude-mem에 기록된 실제 작업 증거를 사용한다
- **정직한 한계 표기**: claude-mem에 기록되지 않은 작업은 "증거 부족"으로 명시한다
- **진정성 있는 동료 피드백**: 기계적 체크리스트가 아닌 진정성 있는 동료 관점으로 작성한다
- **정량적 근거 우선**: 복구 시간, 비용 절감액, 장애 감소 횟수 등 수치 근거를 포함한다
- **STAR 구조 서술**: Situation → Task → Action → Result 형태로 사례를 구성한다

---

## Step 0 — 평가 범위 확인

세션 시작 시 평가 기간을 확인한다.

- 사용자가 이미 기간을 명시했으면 이 단계를 건너뛴다
- 기본값: 최근 3개월
- 확인 후 진행 선언: `평가 기간 {N}개월, 프레임워크 로드 후 증거 수집을 시작합니다.`

---

## Step 1 — 프레임워크 로드

아래 파일을 읽어 5개 영역, 21개 질문, 평가 척도를 파악한다.

```
Read ~/workspace/riiid/socra-devops-cc-system/peer-evaluation-framework.md
```

- 5개 영역: 기술 코드/설계(25%), 기술 운영(30%), 플랫폼 임팩트(20%), 커뮤니케이션(15%), 문화 & 성장(10%)
- 평가 척도: 1~5점 (5=Role Model, 4=기대 초과, 3=On-track, 2=개선 필요, 1=집중 지원 필요)

---

## Step 2 — 증거 수집 (핵심)

5개 영역에 대해 claude-mem `search` 를 영역당 2~3개 쿼리로 호출한다.
**가능한 한 병렬로 호출하여 수집 속도를 높인다.**

### 영역별 검색 쿼리

| 영역 | 검색 쿼리 (각각 별도 search 호출) |
|------|----------------------------------|
| 기술 운영 (30%) | `"incident alert recovery"`, `"troubleshooting root cause"`, `"automation toil"` |
| 기술 코드/설계 (25%) | `"terraform jsonnet architecture"`, `"cost optimization efficiency"`, `"security IAM"` |
| 플랫폼 임팩트 (20%) | `"self-service deploy helm"`, `"requirement proposal alternative"`, `"open source cost"` |
| 커뮤니케이션 (15%) | `"change notification communication"`, `"PR review documentation"` |
| 문화 & 성장 (10%) | `"learning knowledge sharing"`, `"standard convention"` |

### 2차 상세 조회

1차 검색에서 관련성 높은 observation ID를 식별하면 `get_observations`로 상세 내용을 확인한다.

### 타임라인 보조 조회 (선택)

평가 기간이 명확할 경우 `timeline`으로 기간 내 활동 흐름을 파악한다.

---

## Step 3 — 영역별 분석 및 점수 산정

프레임워크의 각 질문을 순회하며 아래 기준으로 분석한다.

### 질문별 처리

1. **Yes/No 판단**: 해당 질문에 Yes로 답할 수 있는 증거가 claude-mem에 있는가?
2. **증거 매핑**: Yes인 경우 구체적 observation을 연결하고 STAR 구조로 재구성
3. **증거 부족 표기**: 증거가 없으면 "증거 미발견 (claude-mem 기록 범위 밖일 수 있음)"으로 표기

### 점수 산정 기준

| 점수 | 기준 |
|------|------|
| 5 | 모든 질문에 구체적 증거 + 정량적 결과 |
| 4 | 70%+ 질문에 구체적 증거 |
| 3 | 50%+ 핵심 질문에 증거 |
| 2 | 일부만 증거, 나머지 부족 |
| 1 | 대부분 증거 없음 |

---

## Step 4 — 평가 리포트 출력

`references/evaluation-output-template.md` 형식으로 최종 리포트를 출력한다.

### 출력 구성

- **헤더**: 평가 대상, 기간, 평가자 (Claude AI Peer)
- **영역별 섹션 ×5**: 점수 + Yes 질문 (STAR) + No 질문 (기대 사항)
- **종합 평가**: 가중 점수 집계표, 가장 큰 기여 2~3가지, 성장 집중 영역 2~3가지, 한 가지 바람
- **푸터**: 분석한 observation 건수, 데이터 한계 면책 문구

### 톤 가이드라인

- "~하면 좋겠습니다" 형태의 기대 표현 사용
- 기계적 체크리스트가 아닌 동료 관점의 진정성 있는 서술
- 증거가 불충분한 영역은 정직하게 "증거 부족"으로 표기
- 개선 기대 사항은 비판이 아닌 성장 기대로 표현

---

## Step 5 — 사용자 피드백 (선택)

리포트 출력 후 아래 옵션을 안내한다:

```
리포트가 완성되었습니다.
→ "보완 요청": 추가 증거를 제시하면 해당 영역을 재평가합니다.
→ "완료": 리포트를 확정합니다.
→ 특정 영역에 대한 추가 질문도 이어서 진행 가능합니다.
```

- 사용자가 추가 증거를 제시하면 해당 영역만 재분석하여 점수와 서술을 업데이트한다
- "완료" 시 리포트 확정 선언으로 종료한다

---

## 주의사항

- claude-mem에 기록되지 않은 작업(구두 소통, 외부 회의 등)은 반영 불가
- 점수는 claude-mem 기록 기반이므로 실제 업무 기여도와 차이가 있을 수 있음
- 데이터 한계를 리포트 하단에 반드시 명시한다
- 평가 기간 외 작업이 검색될 경우 해당 증거는 사용하지 않는다
