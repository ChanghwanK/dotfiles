---
name: deploy-verify-agent
description: |
  배포 후 ArgoCD sync/health 상태, Pod 헬스, 카나리 진행상황을 병렬로 확인하는 배포 검증 스킬.
  사용 시점: (1) 배포 후 상태 확인, (2) ArgoCD sync 실패/지연, (3) 카나리 진행 중 promote/abort 판단,
  (4) 특정 Pod 상태/로그/env var 확인 (배포 컨텍스트)
  트리거 키워드: "배포 잘 됐어?", "배포 확인", "ArgoCD sync", "카나리", "canary", "env var 확인",
  "/deploy-verify-agent"
model: sonnet
allowed-tools:
  - Bash(kubectl get *)
  - Bash(kubectl describe *)
  - Bash(kubectl logs *)
  - Bash(kubectl argo rollouts *)
  - Bash(git log *)
  - Bash(git show *)
  - Agent
  - Read
  - Glob
  - Grep
---

# Deploy Verify Agent — 배포 상태 검증 스킬

배포 후 ArgoCD sync + Pod 헬스를 병렬로 확인하고, 이상 여부와 카나리 프로모션 권고를 출력한다.

## 클러스터 컨텍스트 매핑

| Context | 클러스터 | 설명 |
|---------|----------|------|
| `k8s-prod` | infra-k8s-prod | 프로덕션 (Tokyo) |
| `k8s-stg` | infra-k8s-stg | 스테이징 (Tokyo) |
| `k8s-dev` | infra-k8s-dev | 개발 (Tokyo) |
| `k8s-global` | infra-k8s-global | 공용 인프라 (Tokyo) |
| `k8s-idc` | infra-k8s-idc | On-Premise GPU (Seoul) |

---

## Phase 0: 입력 파싱

사용자 입력에서 아래를 추출한다:

1. **서비스명 (circle)**: 예: `ai-gateway`, `santa-authentication`. 없으면 1회 질문.
2. **Sphere**: circle 이름과 CLAUDE.md 네임스페이스 맵으로 추론. (예: `ai-gateway` → sphere=`tech`)
3. **Namespace**: `{sphere}-{circle}` 패턴. (예: `tech-ai-gateway`)
4. **환경**: prod/stg/dev 언급 없으면 `prod` 기본값. ctx 결정.
5. **목적 분류**:
   - `DEPLOY_CHECK`: 일반 배포 완료 확인 (기본)
   - `CANARY_CHECK`: 카나리 진행 중 성공률 확인 및 promote/abort 판단
   - `ENV_VAR_CHECK`: 환경변수 주입 확인

파싱 완료 후 출력:
```
배포 검증 시작: {circle} ({namespace}, {ctx})
목적: {목적 설명}
2개 에이전트 병렬 수집 중...
```

---

## Phase 1: 병렬 증거 수집

아래 2개 에이전트 파일을 각각 Read 후 변수를 치환하여 **단일 메시지에서 동시에** 실행한다.

**Agent A** — Read `agents/agent-argocd-status.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context
- `{sphere}` → 파싱된 sphere
- `{env}` → 환경 (예: `prod`)

**Agent B** — Read `agents/agent-pod-health.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context
- `{purpose}` → 목적 분류 (DEPLOY_CHECK / CANARY_CHECK / ENV_VAR_CHECK)

에이전트 실패 처리:
- Agent A 실패 시: 직접 `kubectl get application -n infra-argocd --context {ctx} | grep {circle}` 폴백
- Agent B 실패 시: 직접 `kubectl get pods -n {namespace} --context {ctx}` 폴백

---

## Phase 2: 배포 상태 판정

ARGOCD_STATUS와 POD_STATUS를 종합하여 판정한다.

### 2.1 정상 판정 기준

| 항목 | 정상 조건 |
|------|----------|
| ArgoCD Sync | Synced |
| ArgoCD Health | Healthy |
| Pod Ready | all pods Running & Ready |
| Restarts | 0 (또는 배포 이전과 동일) |
| Rollout (카나리) | Healthy 또는 목표 weight 달성 |

### 2.2 이상 판정 기준

| 증상 | 판정 | 권고 |
|------|------|------|
| OutOfSync + 배포 후 5분 초과 | ArgoCD 동기화 지연 | ArgoCD force sync 또는 원인 확인 |
| Degraded Health | 배포 실패 가능성 | Pod 로그 확인, git revert 고려 |
| Pod CrashLoopBackOff | 신규 버전 앱 오류 | 즉시 git revert 권고 |
| 카나리 AnalysisRun Fail | 카나리 실패 | Abort 권고 |
| 카나리 AnalysisRun Success | 카나리 성공 | Promote 권고 |

### 2.3 카나리 판정 (CANARY_CHECK)

| AnalysisRun 결과 | 판정 | 권고 |
|-----------------|------|------|
| Successful | 성공 | `kubectl argo rollouts promote {circle} -n {namespace}` |
| Failed | 실패 | `kubectl argo rollouts abort {circle} -n {namespace}` |
| Running | 진행 중 | 대기 (예상 완료 시간 안내) |
| Pending | 아직 시작 안함 | 대기 |

---

## Phase 3: 배포 상태 리포트 출력

```markdown
# 배포 검증 리포트: {circle} ({env})

## 현재 상태
| 항목 | 상태 |
|------|------|
| ArgoCD Sync | {Synced/OutOfSync} |
| ArgoCD Health | {Healthy/Degraded/Progressing} |
| Pod Ready | {N}/{total} |
| Pod Restarts | {N}회 |
| 최근 배포 | {커밋 해시} — {커밋 메시지} ({시간}) |

## 판정
**{정상/이상/카나리 진행 중}**

{판정 근거 1-2문장}

## 권고 조치
{권고 내용}

## 다음 단계
{필요 시 추가 확인 사항}
```

이상 감지 시 sre-agent 에스컬레이션 안내:
```
더 깊은 RCA가 필요하면 sre-agent를 사용하세요:
  "{circle} {env} 장애 분석해줘"
```
