---
name: devops:deploy-diagnose
description: |
  ArgoCD 배포 문제 자동 진단 스킬. 증거 수집→원인 분류→수정 가이드를 자동화.
  사용 시점: (1) sync 실패 알림 받음, (2) 배포 후 서비스 장애, (3) 카나리/롤아웃 실패,
  (4) OutOfSync 지속, (5) merge 했는데 반영 안 됨.
  트리거 키워드: "배포 문제", "sync 실패", "서비스 죽었어", "배포 안 됨", "OutOfSync",
  "카나리 멈춤", "deploy 실패", "/devops:deploy-diagnose".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Agent
  - Bash(kubectl get *)
  - Bash(kubectl describe *)
  - Bash(kubectl logs *)
  - Bash(kubectl argo rollouts *)
  - Bash(git log *)
  - Bash(git show *)
  - Bash(git diff *)
---

# 배포 문제 자동 진단

ArgoCD 배포 실패, 서비스 장애, Sync 오류를 자동으로 진단하고 수정 가이드를 제공한다.

## 핵심 원칙

- **읽기 전용**: `kubectl get/describe/logs`만 사용. `edit/delete/apply` 절대 금지
- **Git 기반 수정**: 수정은 Git 변경 안내만 제공 (직접 파일 수정 안 함)
- **에스컬레이션 판단**: Write 작업 필요 시 명확하게 Tier 3으로 분류

## 참조 문서

- `references/symptom-routing.md` — 증상 → 진단 경로 매핑, 환경 추론 규칙
- `references/common-fixes.md` — 3-Tier 수정 가이드 (Tier 1: 자체해결, Tier 2: 가이드, Tier 3: 에스컬레이션)

---

## Phase 0: 입력 파싱

입력에서 아래 3가지를 추출한다. `references/symptom-routing.md` Read 후 진단 경로 결정.

1. **서비스명** — circle 이름 (예: `ai-gateway`). 없으면 1회만 질문
2. **환경** — dev/stg/prod. 기본값 `dev`. "프로덕션"/"prod" 언급 시 `prod`
3. **증상** — 아래 5개 경로 중 하나로 분류:

| 경로 | 증상 |
|------|------|
| **Path A** NOT_SYNCING | merge 후 반영 안 됨, sync 안 됨 |
| **Path B** SYNC_FAILED | sync 실패, ArgoCD 에러, helm 렌더 에러 |
| **Path C** SERVICE_DOWN | 서비스 장애, CrashLoop, OOMKilled, 502/503 |
| **Path D** CANARY_STUCK | 카나리 멈춤, AnalysisRun 실패 |
| **Path E** PERSISTENT_OUTOFSYNC | OutOfSync 계속, drift |

파싱 완료 후 출력:
```
## 진단 시작: {circle} ({env})
증상: {증상 설명}
증거를 수집합니다... (30-60초 소요)
```

---

## Phase 1: 병렬 증거 수집

**단일 메시지에 Agent 2개를 동시에 실행** (병렬 처리):

**Agent 1** — `agents/agent-argocd-git.md` 내용을 Read 후 아래 변수를 치환하여 실행:
- `{sphere}` — symptom-routing.md의 Namespace 패턴으로 추론
- `{circle}` — 파싱된 서비스명
- `{env}` — `infra-k8s-{env}` 형식
- `{ctx}` — symptom-routing.md의 context 매핑표 참조
- `{repo_path}` — `/Users/changhwan/workspace/riiid/kubernetes`

**Agent 2** — `agents/agent-pod-logs.md` 내용을 Read 후 아래 변수를 치환하여 실행:
- `{namespace}` — `{sphere}-{circle}` 형식 (symptom-routing.md 참조)
- `{circle}` — 파싱된 서비스명
- `{ctx}` — symptom-routing.md의 context 매핑표 참조

---

## Phase 2: Decision Tree 진단

증거를 바탕으로 해당 Path의 분기를 따른다.

### Path A: NOT_SYNCING

```
ArgoCD sync status == Synced?
  YES → Pod 이미지 태그가 values.yaml과 일치하는가?
         YES → "ArgoCD 동기화 완료. Pod 롤링 업데이트 진행 중입니다 (1-3분 대기)"
         NO  → "ArgoCD는 sync 했지만 Deployment 롤아웃 중. 잠시 후 확인하세요"
  NO  → operationState에 에러 메시지?
         YES → Path B로 분기
         NO  → "ArgoCD가 아직 Git 변경을 처리 중 (1-3분 대기). 이후에도 지속되면 재실행"
```

### Path B: SYNC_FAILED

operationState.message 분석:

| 에러 패턴 | 원인 | Fix |
|-----------|------|-----|
| `helm template`, `render`, `yaml` | Helm 렌더링 실패 | T1-C (YAML 문법 에러) |
| `ImagePullBackOff`, `not found`, `registry` | 이미지 없음 | T1-A (이미지 태그 확인) |
| `required field`, `unknown field` | values 필드 오류 | T1-C (values.yaml 수정) |
| `chart.*not found`, `OCI` | Chart version 없음 | T1-E (kustomization.yaml) |
| `immutable` | Immutable 필드 변경 시도 | T2-B |
| 기타 | 불명확 | T3 에스컬레이션 |

### Path C: SERVICE_DOWN

```
CrashLoopBackOff?
  → Step 1: 이전 컨테이너 종료 코드 확인
    - 137 (OOMKilled): T1-B (memory limit 증가)
    - 1 (App error): 에러 로그 분석 → 환경변수 누락이면 T1-D, 코드 버그이면 T3
    - 0 (정상 종료): CMD/Entrypoint 문제 → T3
    - 2 (설정 오류): 환경변수/설정파일 문제 → T1-D
  → Step 2: 종료 코드만으로 원인 불명확하면 describe로 Probe 메시지 확인
    - "Readiness probe failed": probe 경로/포트 설정 오류 → T1-D (값 확인 후 values.yaml 수정)
    - "Liveness probe failed": 앱 응답 느림 또는 데드락 → 에러 로그 추가 분석 → T3
    - "Back-off restarting": 에러 로그에서 원인 확인 필요

ImagePullBackOff?
  → T1-A (이미지 태그 확인)

Pending (1분 이상)?
  → describe Events에서 스케줄링 실패 메시지 확인:
    - "0/N nodes are available", "didn't match node selector": 노드 셀렉터/toleration 문제 → T3
    - "Insufficient cpu/memory": 리소스 부족 → Karpenter 로그 확인
      - "no capacity": EC2 용량 부족 (Spot 경합, AZ 선택 문제) → T3
      - NodeClaim 생성 중: "1-3분 대기 후 재확인"
      - Karpenter 로그 에러 없음: NodePool 선택 기준 검토 → T3
    - "persistentvolumeclaim ... not found": PVC 문제 → T3
```

### Path D: CANARY_STUCK

```
Rollout phase == Paused?
  → "카나리가 수동 대기 상태. promote 또는 abort 필요" → T3

Rollout phase == Degraded?
  → AnalysisRun 실패?
     YES → 성공률 < 95%: "카나리 버전 에러율 높음 ({actual}%). 코드 검토 필요"
           Pod 에러: Path C로 분기
  → T3 에스컬레이션 (promote/abort 필요)
```

### Path E: PERSISTENT_OUTOFSYNC

```
OutOfSync 리소스 종류:
  VirtualService / DestinationRule?
    → "Argo Rollouts가 카나리 weight를 수정하는 정상 현상"
    → T2-A (applicationset.jsonnet ignoreDifferences 추가)

  기타 리소스?
    → T3 에스컬레이션 (외부 컨트롤러 또는 immutable 필드)
```

---

## Phase 3: 진단 결과 출력

`references/common-fixes.md`를 Read하여 해당 Tier의 수정 가이드를 제시.

```markdown
## 배포 진단 결과: {circle} ({env})

### 현재 상태
| 항목 | 상태 |
|------|------|
| ArgoCD Sync | {status} |
| ArgoCD Health | {status} |
| Pod | {running}/{total} Running (재시작 {N}회) |
| 마지막 배포 | {timestamp} |

### 원인
{원인 설명 2-3문장 — 개발자가 이해할 수 있는 언어}

### 핵심 증거
```
{에러 메시지 또는 로그 1-3줄}
```

### 수정 방법
{Tier 1/2/3 가이드}

### 최근 Git 변경
{커밋 목록 — 원인이 된 변경사항 강조}
```

---

## 에스컬레이션 기준 (Tier 3 해당 시)

아래 상황은 즉시 Tier 3 에스컬레이션:
- 인프라 레이어 (노드 압박, Unschedulable, PVC Pending)
- ArgoCD 자체 장애 또는 접근 불가
- Write 작업 필요 (rollout promote/abort, force sync)
- Prod 서비스 다운 5분 이상
- 에러 메시지 패턴 불명확 (위 표에 해당 없음)

**에스컬레이션 Slack 메시지** (`references/common-fixes.md` T3 섹션 템플릿 사용):

```
*배포 문제 진단 결과*
• 서비스: {sphere}/{circle} ({env})
• ArgoCD: {sync} / {health}
• Pod: {running}/{total}, 재시작 {N}회
• 에러: `{핵심 에러 메시지}`
• 최근 변경: {git commit summary}
• 권장 조치: {T3 액션}
```
