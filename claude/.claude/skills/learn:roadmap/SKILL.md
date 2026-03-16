---
name: learn:roadmap
description: |
  특정 도메인의 체계적 학습 로드맵 설계. 101 모드(Level 0→10 전문가 커리큘럼) / Gap 모드(자가 진단 기반 약점 집중).
  Obsidian에 체크박스 기반 living document로 저장하여 진행 추적 가능.
  사용 시점: (1) 새 도메인을 0부터 체계적으로 학습하고 싶을 때, (2) 약점 파악 후 맞춤 학습 계획 수립.
  트리거: "/learn:roadmap", "로드맵 만들어줘", "101 커리큘럼", "학습 계획", "커리큘럼 설계", "roadmap".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py *)
  - Write(/tmp/roadmap-content.json)
  - Read
---
# learn:roadmap 스킬

특정 도메인의 체계적 학습 로드맵을 설계하고 Obsidian에 living document로 저장한다.
101 모드(Level 0~10 전문가 커리큘럼)와 Gap 모드(자가 진단 기반 맞춤 로드맵) 2가지를 지원한다.

---

## 핵심 원칙

- **성장 촉진자**: 정답을 바로 제시하지 않는다. 스스로 생각하고 사고하여 성장할 수 있도록 돕는 것이 주 역할
- **Socratic Questioning**: 핵심 포인트마다 3가지 질문(명확화 / 가정 탐색 / 관점 전환)을 제시하여 깊은 이해를 유도
- **모드 판별**: 사용자가 "101", "처음부터", "입문", "0부터"를 언급하면 **101 모드**, 나머지는 **Gap 모드**
- **SOCRAAI 연결**: 각 학습 항목에 SOCRAAI 인프라 환경 연결점 명시 (Karpenter, Istio mTLS, VictoriaMetrics 등)
- **기존 노트 활용**: 이미 학습한 내용은 `[x]`로 표시 → 로드맵이 현재 상태 반영
- **living document**: 저장 후에도 `update-progress`로 지속 업데이트 가능

---

## 모드 1: 101 모드 (Level 0→10 전문가 커리큘럼)

**트리거**: "101", "처음부터", "입문", "0부터"

### Step 1 — 도메인 확인

사용자로부터 확인:
- 학습 주제 (예: Kubernetes, Istio, VictoriaMetrics)
- 학습 목적 (운영/트러블슈팅/설계/인터뷰 준비 중 선택)

### Step 1.5 — Socratic Pre-Design (로드맵 설계 전 사고 유도)

기존 노트 탐색 전에, 사용자가 스스로 학습 우선순위를 먼저 생각하게 한다:

```
로드맵을 설계하기 전에, 잠깐 생각해볼 질문들입니다.
(바로 설계를 원하시면 "바로 설계해줘"라고 말씀해주세요)

1. [명확화] {domain}을 배우려는 가장 큰 이유를 한 문장으로 표현한다면?
2. [가정 탐색] 이 도메인에서 "이건 꼭 알아야 한다"고 생각하는 핵심 개념이 있다면 무엇인가요?
3. [관점 전환] 6개월 후 이 로드맵을 완주했을 때, SOCRAAI 팀에서 어떤 역할을 더 잘할 수 있게 되길 바라나요?
```

사용자 답변을 로드맵 설계 시 반영한다. "바로 설계해줘" 시 즉시 Step 2로 진행한다.

### Step 2 — 기존 노트 탐색

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py search-notes --domain "{domain}"
```

결과를 보고 이미 학습한 항목을 `[x]`로 표시할 준비를 한다.

### Step 3 — 커리큘럼 설계

아래 **Level 0~10 체계**에 따라 각 레벨에 2~4개 구체적 항목 배치:

| Level | 단계 | 학습 목표 |
|-------|------|----------|
| 0 | 왜 존재하는가 | 이 기술이 해결하는 문제를 설명할 수 있다 |
| 1 | 첫 경험 | 공식 퀵스타트 완료 |
| 2 | 기본 개념 | 핵심 용어와 컴포넌트를 정확히 설명 |
| 3 | 동작 원리 | 내부 아키텍처와 데이터 흐름 설명 |
| 4 | 실무 적용 | SOCRAAI 환경에서 설정/운영 |
| 5 | 트러블슈팅 | 일반 장애 독립 진단/해결 |
| 6 | 대안 비교 | 경쟁 기술과 trade-off 설명 |
| 7 | 최적화 | 성능/비용/안정성 튜닝 |
| 8 | 엣지 케이스 | 소스코드 레벨 분석 |
| 9 | 설계 판단 | 아키텍처 적합성 판단 |
| 10 | 전문가 | 가르치기, 커뮤니티 기여 |

**항목 형식**: 각 항목에 `/learn {topic}` 명령 포함, SOCRAAI 연결점 주석 추가

**이미 학습한 항목**: Step 2 결과를 참조하여 `- [x]` 로 표시

### Step 4 — Obsidian 저장

**문서 형식** (`/tmp/roadmap-content.json` 에 JSON 작성):

```json
{
  "blocks": "## 로드맵 개요\n\n| 도메인 | 모드 | 총 항목 | 예상 기간 | SOCRAAI 연결 |\n...\n\n## Level 0 — 왜 존재하는가\n\n> 목표: 이 기술이 해결하는 문제를 설명할 수 있다\n\n- [ ] 0.1 {주제} → `/learn {topic}`\n  - SOCRAAI: {환경 연결점}\n..."
}
```

**체크박스 상태** (Obsidian Tasks 호환):
- `- [ ]` 미시작
- `- [/]` 진행중
- `- [x]` 완료

**저장 실행**:

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py create \
  --title "{domain} 101 Roadmap" \
  --tags "{domain}" \
  --content-file /tmp/roadmap-content.json \
  --mode 101
```

---

## 모드 2: Gap 모드 (자가 진단 기반 맞춤 로드맵)

**트리거**: 101 키워드 없이 도메인 + "로드맵", "약점", "부족한 것" 언급

### Step 1 — 도메인 + 자가 진단

사용자에게 5개 영역 1~5점 자가 평가 요청:

```
{domain} 역량을 1(전혀 모름)~5(전문가) 로 평가해주세요:
1. 핵심 개념 이해:
2. 동작 원리 (내부 아키텍처):
3. 실무 운영 경험:
4. 트러블슈팅 능력:
5. 설계/아키텍처 판단:
```

### Step 2 — 기존 노트 탐색

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py search-notes --domain "{domain}"
```

### Step 3 — 약점 분석 + 맞춤 로드맵

점수 기반 항목 배정:
- **1~2점** (집중): 2~4개 항목, 기초→원리 순서
- **3점** (보완): 1~2개 항목, 실무/심화
- **4~5점** (생략 또는 심화 1개만)

### Step 4 — Obsidian 저장

101 모드와 동일한 저장 과정. `--mode gap` 지정:

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py create \
  --title "{domain} Gap 로드맵" \
  --tags "{domain}" \
  --content-file /tmp/roadmap-content.json \
  --mode gap
```

---

## 모드 3: Update 모드 (진행 상황 업데이트)

**트리거**: "로드맵 업데이트", "진행 상황", "완료 표시", "체크"

### Step 1 — 기존 로드맵 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py list
```

### Step 2 — 진행률 확인

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py show-progress \
  --filename "{filename}"
```

결과 출력 후 다음 추천 항목 3개 표시.

### Step 3 — 완료 항목 업데이트

사용자로부터 완료 항목 번호 수집 후:

```bash
python3 /Users/changhwan/.claude/skills/learn:roadmap/scripts/roadmap.py update-progress \
  --filename "{filename}" \
  --items "0.1,1.2,2.3" \
  --status done
```

---

## Obsidian 문서 형식 참조

### Frontmatter

```yaml
---
title: "Kubernetes 101 Roadmap"
date: 2026-03-09
last_reviewed: 2026-03-09
status: active
type: roadmap
mode: 101          # 101 | gap
progress: "3/32"   # 완료/전체 (자동 갱신)
tags:
  - domain/kubernetes
aliases:
  - K8s 101
  - Kubernetes 로드맵
---
```

### 본문 구조 (101)

```markdown
## 로드맵 개요

| 도메인 | 모드 | 총 항목 | 예상 기간 | SOCRAAI 연결 |
|--------|------|---------|----------|--------------|
| Kubernetes | 101 | 32개 | 8~12주 | Karpenter, KEDA, Istio |

## Level 0 — 왜 존재하는가

> 목표: 이 기술이 해결하는 문제를 설명할 수 있다

- [ ] 0.1 컨테이너 오케스트레이션 문제 → `/learn 컨테이너 오케스트레이션의 필요성`
  - SOCRAAI: Dev/Stg/Prod 환경의 50+ Pod 관리 복잡성
- [ ] 0.2 VM vs Container vs K8s 트레이드오프 → `/learn VM Container K8s 비교`

## Level 1 — 첫 경험

...

## 학습 자원

| 자원 | 레벨 | 링크/명령 |
|------|------|----------|

## 진행 기록

| 날짜 | 완료 항목 | 메모 |
|------|----------|------|
```

---

## 결과 출력 형식

```
✅ 로드맵 생성 완료

제목: Kubernetes 101 Roadmap
모드: 101 (Level 0~10)
총 항목: 32개 (완료: 3개, 진행률: 9.4%)
태그: domain/kubernetes
저장 경로: 02. Notes/engineering/Kubernetes 101 Roadmap.md
관련 노트: 5개 연결
```

---

## 주의사항

- 항목 번호는 `{level}.{순서}` 형식 (0.1, 1.2, 10.3 등)으로 일관되게 작성해야 `update-progress`가 정상 동작
- 저장 경로는 항상 `02. Notes/engineering/` — 타입이 roadmap이면 resource 디렉토리 불사용
- 기존 로드맵이 있으면 새로 생성하기 전에 기존 로드맵 업데이트를 먼저 제안
