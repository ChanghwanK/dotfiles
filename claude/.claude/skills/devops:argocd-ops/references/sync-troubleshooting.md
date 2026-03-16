# ArgoCD Sync 실패 유형별 진단 트리

## ComparisonError

**증상:** ArgoCD가 Git과 클러스터 상태를 비교하지 못함.

**주요 원인:**

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| `failed to load initial state of resource` | CRD 미설치 | CRD 먼저 배포 |
| `unable to recognize: no matches for kind` | API 버전 불일치 | apiVersion 수정 |
| `failed to get resource` | RBAC 권한 부족 | ArgoCD SA 권한 추가 |
| `helm template error` | Helm 렌더링 실패 | values.yaml 문법 확인 |
| `kustomize build error` | Kustomize 빌드 실패 | kustomization.yaml 확인 |

**Helm 렌더링 에러 디버깅:**
```bash
# 로컬에서 Helm 렌더링 테스트
cd src/<sphere>/<circle>/infra-k8s-<env>
kustomize build --enable-helm .

# Helm chart 직접 렌더링
helm template <release-name> <chart> -f ../common/values.yaml -f values.yaml
```

## SyncError

**증상:** Git 상태를 클러스터에 적용하지 못함.

**주요 원인:**

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| `is invalid: spec: Forbidden` | immutable field 변경 시도 | 리소스 삭제 후 재생성 (Git에서 제거 → sync → Git에 다시 추가 → sync) |
| `admission webhook denied` | Webhook이 변경 차단 | Webhook 정책 확인, 일시적 비활성화 |
| `namespace not found` | 네임스페이스 미존재 | namespace manifest 추가 또는 ArgoCD CreateNamespace 옵션 |
| `exceeded quota` | ResourceQuota 초과 | quota 조정 또는 리소스 requests 감소 |
| `conflict: Operation cannot be fulfilled` | 동시 수정 충돌 | retry로 해결, 지속 시 직접 변경 소스 확인 |

**Immutable field 해결:**
```bash
# 주의: GitOps이므로 직접 삭제하지 말고 Git에서 처리
# 1. Git에서 해당 리소스 제거
# 2. ArgoCD sync (prune으로 자동 삭제)
# 3. Git에서 새 spec으로 리소스 다시 추가
# 4. ArgoCD sync
```

## Hook 실패

**증상:** PreSync/PostSync/SyncFail hook Job이 실패.

**진단:**
```bash
# Hook Job 상태 확인
kubectl --context <ctx> get jobs -n <ns> -l argocd.argoproj.io/hook

# Hook Job 로그
kubectl --context <ctx> logs job/<hook-job-name> -n <ns>
```

**주요 원인:**
- DB migration 스크립트 실패 (PreSync hook)
- Smoke test 실패 (PostSync hook)
- 이미지 pull 실패
- 리소스 부족으로 Job 스케줄링 불가

## Drift 감지

**증상:** 클러스터 상태가 Git과 다르지만 ArgoCD가 자동 sync하지 못하거나 반복적으로 OutOfSync.

**일반적 원인:**

| 원인 | 설명 | 해결 |
|------|------|------|
| Mutating Webhook | Webhook이 리소스를 자동 수정 | ignoreDifferences 추가 |
| Controller 관리 필드 | Istio, Karpenter 등이 필드 수정 | ignoreDifferences 추가 |
| Defaulting | K8s가 기본값 자동 추가 | 명시적으로 값 설정하거나 ignore |
| 직접 kubectl 수정 | 누군가 직접 수정 | Git에 올바른 상태 커밋 |

**Drift 원인 확인:**
```bash
# 상세 diff 확인
argocd app diff <app-name> --local src/<sphere>/<circle>/infra-k8s-<env>/

# 특정 리소스의 managed-fields 확인
kubectl --context <ctx> get <resource> <name> -n <ns> -o jsonpath='{.metadata.managedFields}' | jq
```

## Degraded 상태

**증상:** Sync는 완료되었지만 리소스가 비정상.

**진단:**
```bash
# Degraded 리소스 식별
argocd app resources <app-name> | grep -v Healthy

# 각 Degraded 리소스 상세 확인
kubectl --context <ctx> describe <kind> <name> -n <ns>
```

**주요 원인:**
- Pod CrashLoopBackOff → `devops:k8s-troubleshoot` 스킬로 전환
- 서비스 endpoint 없음 → selector 불일치 확인
- Ingress/VirtualService 미작동 → 라우팅 설정 확인
- PVC Pending → StorageClass, 용량 확인

## 성능 문제

**증상:** Sync가 매우 느리거나 timeout.

**원인:**
- 대규모 리소스 (100+ 리소스 앱)
- 느린 Helm 렌더링
- API server 과부하
- repo-server 메모리/CPU 부족

**확인:**
```bash
# ArgoCD repo-server 상태
kubectl --context k8s-global get pods -n argocd -l app.kubernetes.io/component=repo-server

# ArgoCD application-controller 상태
kubectl --context k8s-global get pods -n argocd -l app.kubernetes.io/component=application-controller
```
