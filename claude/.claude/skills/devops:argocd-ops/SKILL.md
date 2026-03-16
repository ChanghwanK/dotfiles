---
name: devops:argocd-ops
description: |
  ArgoCD Application sync 실패, Drift 감지, OutOfSync 상태 진단 스킬.
  ApplicationSet 기반 GitOps 배포에서 발생하는 다양한 sync 문제를 체계적으로 분석.
  사용 시점: (1) ArgoCD sync 실패 원인 분석, (2) OutOfSync/Degraded 상태 진단,
  (3) Drift 감지 및 원인 파악, (4) Application health 이상 분석.
  트리거 키워드: "ArgoCD", "sync 실패", "OutOfSync", "Degraded", "Drift",
  "배포 실패", "ArgoCD 에러".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(kubectl *)
  - Bash(argocd *)
  - mcp__awslabs_eks-mcp-server__list_k8s_resources
  - mcp__awslabs_eks-mcp-server__get_k8s_events
---

# ArgoCD Operations & Troubleshooting

ArgoCD Application sync 실패, Drift, OutOfSync, Degraded 상태를 체계적으로 진단하고 해결한다.

## 참조 문서 (필요 시 Read)

- `kubernetes/.claude/rules/architecture.md` → ApplicationSet 구조, 환경 구성
- `kubernetes/.claude/rules/patterns.md` → GitOps 패턴, Canary ignoreDifferences
- `kubernetes/src/applicationset.libsonnet` → 표준 ApplicationSet 템플릿

## ArgoCD 접근

```bash
# ArgoCD CLI (k8s-global 클러스터에 설치)
argocd app list
argocd app get <app-name>

# Application 이름 패턴: {circle}.{env}
# 예: ai-gateway.infra-k8s-prod, authentication.infra-k8s-dev
```

---

## 진단 워크플로우

### Step 1: Application 상태 확인

```bash
# Application 상태 요약
argocd app get <app-name>

# 주요 확인 항목:
# - Sync Status: Synced / OutOfSync
# - Health Status: Healthy / Degraded / Progressing / Missing / Unknown
# - Conditions: 에러/경고 조건
# - Sync Result: 마지막 sync 결과
```

### Step 2: Sync 실패 유형 분류

| Sync Status | Health Status | 의미 | 진단 방향 |
|-------------|---------------|------|----------|
| OutOfSync | Healthy | Git ≠ 클러스터, 서비스 정상 | Diff 확인, 의도적 변경 여부 |
| OutOfSync | Degraded | Git ≠ 클러스터, 서비스 비정상 | 즉시 sync 또는 롤백 검토 |
| Synced | Degraded | Git = 클러스터, 서비스 비정상 | Pod 레벨 문제 진단 |
| OutOfSync | Missing | 리소스 미생성 | 권한, namespace, CRD 확인 |
| Unknown | Unknown | 연결 문제 | 클러스터 연결, 네임스페이스 존재 확인 |

### Step 3: Sync 에러 분석

```bash
# Sync 에러 상세 확인
argocd app get <app-name> --show-operation

# 리소스별 상태 확인
argocd app resources <app-name>

# Diff 확인 (Git vs 클러스터)
argocd app diff <app-name>
```

**주요 Sync 에러 유형:** `references/sync-troubleshooting.md` 참조

### Step 4: ApplicationSet → Application 체인 검증

```bash
# ApplicationSet 확인
kubectl --context k8s-global get applicationsets -n argocd

# Jsonnet으로 ApplicationSet 렌더링 확인
jsonnet src/<sphere>/<circle>/applicationset.jsonnet

# Application이 올바르게 생성되었는지 확인
argocd app list | grep <circle>
```

### Step 5: 해결 방안 적용

| 상황 | 조치 |
|------|------|
| 일시적 네트워크 에러 | `argocd app sync <app-name> --retry-limit 3` |
| 캐시 불일치 | `argocd app get <app-name> --hard-refresh` |
| ignoreDifferences 필요 | ApplicationSet jsonnet에 ignoreDifferences 추가 |
| CRD 미설치 | CRD 먼저 설치 후 sync |
| 권한 부족 | ArgoCD ServiceAccount RBAC 확인 |
| Webhook 차단 | Webhook 로그 확인, 임시 비활성화 |

---

## 주요 주의사항

### ignoreDifferences (Canary 배포)

Argo Rollouts를 사용하는 앱은 VirtualService weight와 DestinationRule label이 동적으로 변경되므로
ignoreDifferences를 반드시 설정해야 한다:

```jsonnet
ignoreDifferences: [
  {
    group: 'networking.istio.io',
    kind: 'VirtualService',
    jqPathExpressions: ['.spec.http[].route[].weight'],
  },
  {
    group: 'networking.istio.io',
    kind: 'DestinationRule',
    jqPathExpressions: ['.spec.subsets[].labels["rollouts-pod-template-hash"]'],
  },
]
```

### Prune 정책

모든 앱이 `syncPolicy.automated.prune: true`를 사용하므로, Git에서 리소스를 삭제하면
클러스터에서도 자동 삭제된다. 의도하지 않은 리소스 삭제에 주의.

### Sync Wave

복잡한 앱은 sync-wave 어노테이션으로 배포 순서를 제어한다:
```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"  # 낮은 숫자 먼저 배포
```

---

## 출력 포맷

```markdown
# ArgoCD 진단 리포트: [app-name]

## 상태
- Sync Status: [Synced/OutOfSync]
- Health Status: [Healthy/Degraded/...]
- Last Sync: [시간]

## 문제 분석
[에러 유형, 원인, 영향 범위]

## 해결 방안
[구체적 조치 단계]
```
