---
name: devops:infra-pm
description: |
  인프라 품질 6차원(Reliability, Security, Operability, Observability, Cost, Scalability)
  평가 및 개선 관리 PM 스킬. North Star 목표 대비 현재 상태를 Assessment Agent로 자동 수집하고,
  Gap 기반 개선 백로그를 생성/관리한다.
  사용 시점: (1) 인프라 품질 평가 실행, (2) 개선 백로그 관리,
  (3) 스프린트 계획, (4) 임팩트 측정, (5) 인프라 품질 대시보드 확인.
  트리거 키워드: "인프라 평가", "인프라 PM", "assessment", "infra-pm",
  "품질 점수", "인프라 품질", "/devops:infra-pm".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py *)
  - Read
  - Write
  - Agent
  - AskUserQuestion
---

# devops:infra-pm

인프라 품질을 6개 차원으로 정량 평가하고, North Star 목표 대비 Gap을 관리하는 **목표 지향 인프라 PM 스킬**.

순수 Orchestrator: 모든 데이터 수집과 클러스터 접근은 Assessment Agent에게 위임한다.

---

## 핵심 원칙

- **Goal-Driven**: "고친다"가 아니라 "목표에 얼마나 가까운가"를 측정한다.
- **Agent Delegation**: kubectl/API 직접 호출 없음. Assessment Agent가 모든 수집을 담당.
- **Parallel Execution**: 여러 클러스터/차원 동시 평가로 속도 최적화.
- **Notion Persistence**: 모든 Assessment 결과는 Notion DB에 저장하여 추이 추적.
- **Gap Engine**: North Star 목표 대비 Gap을 자동 계산하여 우선순위를 결정한다.
- **Backlog 모드**: Gap 기반 improvement_items를 Notion Task DB에 자동 적재 (중복 스킵).

---

## 모드 분기

사용자 입력에서 아래 모드를 감지한다:

| 입력 패턴 | 모드 |
|-----------|------|
| `assess`, `평가`, `assessment` | `assess` |
| `dashboard`, `대시보드`, `점수` | `dashboard` |
| `backlog`, `백로그` | `backlog` |
| `gap`, `gap-report` | `gap` |
| `sprint` | Phase 3 예정 — 안내 메시지 출력 |
| `complete` | Phase 3 예정 — 안내 메시지 출력 |

플래그 파싱:
- `--cluster`: `prod` | `idc` | `global` | `all` (기본: `prod`)
- `--dimension`: `reliability` | `operability` | `all` (기본: `all`)

클러스터명 → kubectl context 매핑:
- `prod` → `k8s-prod` (infra-k8s-prod)
- `idc` → `k8s-idc` (infra-k8s-idc)
- `global` → `k8s-global` (infra-k8s-global)

---

## assess 모드

### Step 1 — 입력 파싱

`--cluster`와 `--dimension` 플래그를 파싱한다.

```
cluster=all  → clusters = [prod, idc, global]
cluster=prod → clusters = [prod]

dimension=all          → dimensions = [reliability, operability]
dimension=reliability  → dimensions = [reliability]
dimension=operability  → dimensions = [operability]
```

### Step 2 — Agent 프롬프트 로드 및 치환

각 (cluster, dimension) 조합에 대해:

1. `Read agents/agent-assess-{dimension}.md` 로 프롬프트 로드
2. 프롬프트 내 `{cluster}` → 실제 kubectl context명 (k8s-prod, k8s-idc, k8s-global)
3. 프롬프트 내 `{cluster_name}` → 표시용 이름 (infra-k8s-prod 등)

### Step 3 — Agent 병렬 실행

최대 3개씩 배치로 병렬 실행:

```
assess --cluster all --dimension all 의 경우 (6개 조합):

Batch 1: [prod-reliability, prod-operability, idc-reliability]
Batch 2: [idc-operability, global-reliability, global-operability]
```

각 Agent:
- Type: `general-purpose`
- Prompt: cluster/dimension 치환된 agent 프롬프트
- 반환: 구조화된 AssessmentResult (아래 포맷 참고)

**AssessmentResult 포맷** (Agent가 마지막에 반드시 출력):
```
ASSESSMENT_RESULT_START
dimension: reliability
cluster: infra-k8s-prod
score: 82
metrics:
  pod_restart_rate_1h: 0.3
  argocd_healthy_pct: 96.5
  non_running_pods: 2
  single_replica_deployments: 3
findings:
  - "[WARN] socraai-celery-worker: 12회 재시작 (지난 24h)"
  - "[WARN] 3개 Deployment가 single replica로 운영 중"
  - "[INFO] ArgoCD 전체 96.5% Healthy"
improvement_items:
  - title: "celery-worker 재시작 원인 조사 및 PDB 설정"
    priority: P2
    dimension: reliability
  - title: "prod single-replica Deployment에 replicas=2 적용"
    priority: P2
    dimension: reliability
ASSESSMENT_RESULT_END
```

### Step 4 — 결과 파싱

Agent 반환값에서 `ASSESSMENT_RESULT_START` ~ `ASSESSMENT_RESULT_END` 블록을 추출한다.
파싱 실패 시 해당 (cluster, dimension) 결과를 `score: null`로 기록하고 계속 진행.

### Step 5 — Notion 저장

각 AssessmentResult를 Notion Assessment DB에 저장:

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  save-assessment --data '<json>'
```

`--data` JSON 형식:
```json
{
  "dimension": "reliability",
  "cluster": "infra-k8s-prod",
  "score": 82,
  "metrics": {"pod_restart_rate_1h": 0.3, ...},
  "findings": ["[WARN] ..."],
  "improvement_items": [{"title": "...", "priority": "P2"}]
}
```

### Step 6 — 결과 출력

콘솔에 아래 형식으로 출력:

```
## 인프라 품질 Assessment 결과
평가 시간: 2026-03-16 12:30 KST

### 점수 요약

| 차원          | infra-k8s-prod | infra-k8s-idc | infra-k8s-global |
|---------------|:--------------:|:-------------:|:----------------:|
| Reliability   | 82 / 100       | 75 / 100      | 90 / 100         |
| Operability   | 71 / 100       | 68 / 100      | 85 / 100         |

### 주요 Findings (심각도순)

[infra-k8s-prod · Reliability]
- [WARN] socraai-celery-worker: 12회 재시작 (지난 24h)
- [WARN] 3개 Deployment가 single replica로 운영 중

[infra-k8s-idc · Operability]
- [WARN] PDB 미적용 Deployment: 8개
...

### Improvement Items (우선순위순)

1. [P1] celery-worker 재시작 원인 조사 (reliability)
2. [P2] prod single-replica → replicas=2 적용 (reliability)
...

Notion Assessment DB에 {N}건 저장 완료.
```

---

## dashboard 모드

Notion Assessment DB에서 최근 assessment 조회:

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  dashboard
```

반환 JSON을 파싱하여 클러스터별 최근 점수 테이블로 출력한다.

---

## gap 모드

### Step 1 — Gap 리포트 조회

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  gap-report
```

### Step 2 — 결과 출력

반환 JSON의 `gaps` 배열을 Gap 큰 순으로 테이블 출력:

```
## 인프라 품질 Gap 리포트
North Star 목표 대비 현재 상태

| 차원 | 클러스터 | 현재 점수 | 목표 | Gap | 등급 |
|------|--------|:---------:|:----:|:---:|------|
| Operability | infra-k8s-idc | 68 | 85 | -17 | ⚠️ Fair |
| Reliability  | infra-k8s-idc | 75 | 90 | -15 | ✅ Good |
...

Gap이 큰 순서로 우선순위 개선 대상 상위 3개:
1. [Gap -17] infra-k8s-idc Operability → PDB 커버리지 개선 필요
2. [Gap -15] infra-k8s-idc Reliability → ...
```

점수 등급: ⭐ Excellent (90-100) / ✅ Good (75-89) / ⚠️ Fair (60-74) / 🚨 Poor (0-59)

---

## backlog 모드

### Step 1 — 최근 improvement_items 수집

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  list-improvements --limit 12
```

### Step 2 — Dry-run 미리보기 (선택)

`--dry-run` 플래그가 있으면 실제 생성 없이 미리보기만 출력:

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  create-backlog --items '<json>' --dry-run
```

### Step 3 — Notion Task DB 적재

```bash
python3 /Users/changhwan/.claude/skills/devops:infra-pm/scripts/notion-infra-pm.py \
  create-backlog --items '<json>'
```

**적재 규칙:**
- Task 이름 형식: `[{cluster_short}] {improvement_item_title}`
  - 예: `[prod] celery-worker 재시작 원인 조사 및 PDB 설정`
- Priority: P1 → `P1 - Must Have`, P2/P3 → `P2 - Nice to Have`
- Group: `WORK`
- Due Date: 다음 월요일 (기본값)
- **중복 방지**: 제목 앞 25자로 Task DB 검색 → 이미 존재하면 스킵

### Step 4 — 결과 출력

```
## 인프라 PM 백로그 적재 결과

Notion Task DB에 {N}건 생성, {M}건 스킵(중복).

### 생성된 Task
1. [P1] [prod] celery-worker 재시작 원인 조사
2. [P2] [prod] Single Replica Deployment replicas=2 적용
...

### 스킵 (중복)
- [idc] PDB 미적용 Deployment 개선 (기존 Task 존재)
```

---

## Phase 3+ 모드 안내

`sprint`, `complete` 모드 요청 시:

> Phase 3에서 구현 예정입니다. 현재는 `assess`, `dashboard`, `gap`, `backlog` 모드를 지원합니다.

---

## 오류 처리

- **kubectl 접근 실패**: Agent가 접근 불가 클러스터를 만나면 `score: null` + `findings: ["[ERROR] 클러스터 접근 실패"]` 반환
- **Notion 저장 실패**: stderr 출력 후 콘솔 결과는 정상 출력
- **NOTION_TOKEN 없음**: 1Password `op read` 실패 시 명확한 에러 메시지 출력
