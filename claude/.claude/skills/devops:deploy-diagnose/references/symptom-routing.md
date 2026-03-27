# 증상 라우팅 테이블

개발자/DevOps 자연어를 5가지 진단 경로(Path A~E)로 매핑한다.

---

## 입력 파싱 규칙

### 필수 정보 추출

| 정보 | 추출 방법 | 기본값 |
|------|-----------|--------|
| **서비스명** | "ai-gateway", "authentication" 등 circle 이름 | 없으면 1회 질문 |
| **환경** | "dev/stg/prod" 명시 또는 키워드 추론 | `dev` |
| **증상** | 아래 라우팅 테이블 참조 | 없으면 Path B (SYNC_FAILED) 시도 |

### 환경 추론 규칙

| 키워드 | 추론 환경 |
|--------|-----------|
| "prod", "프로덕션", "운영" | `infra-k8s-prod` |
| "stg", "스테이징" | `infra-k8s-stg` |
| "dev", "개발" 또는 명시 없음 | `infra-k8s-dev` |
| "global" | `infra-k8s-global` |
| "idc" | `infra-k8s-idc` |

### kubectl context 매핑

| 환경 | kubectl context | short key |
|------|----------------|-----------|
| infra-k8s-prod | k8s-prod | prod |
| infra-k8s-stg | k8s-stg | stg |
| infra-k8s-dev | k8s-dev | dev |
| infra-k8s-global | k8s-global | global |
| infra-k8s-idc | k8s-idc | idc |

---

## 증상 → 진단 경로 매핑

### Path A: NOT_SYNCING — "배포했는데 반영이 안 됨"

트리거 키워드:
- "merge 했는데 변화 없어", "반영이 안 됨", "배포 안 됨", "PR 머지했는데"
- "argocd에 업데이트 안 됨", "이미지 태그가 안 바뀜", "sync 안 됨"
- ArgoCD 상태가 `Synced`인데 클러스터에 변경사항이 없는 경우

**진단 포인트**: ArgoCD가 최신 Git 상태를 반영했는지, Pod가 새 이미지로 교체되었는지

### Path B: SYNC_FAILED — "Sync 실패/에러"

트리거 키워드:
- "sync 실패", "sync error", "Slack에서 실패 알림 받음"
- "helm render 에러", "template 에러", "ArgoCD 에러"
- "배포 실패", "Failed", ArgoCD Health/Sync 상태가 `Degraded`/`Error`

**진단 포인트**: operationState 에러 메시지 분석, 최근 Git 변경 파악

### Path C: SERVICE_DOWN — "배포 후 서비스 장애"

트리거 키워드:
- "서비스 죽었어", "앱 크래시", "재시작 반복", "CrashLoopBackOff"
- "502", "503", "500 에러", "서비스 응답 없음"
- "OOMKilled", "메모리 부족", "프로세스 종료됨"
- "ImagePullBackOff", "이미지 못 가져옴"

**진단 포인트**: Pod 상태, 종료 코드, 에러 로그 패턴

### Path D: CANARY_STUCK — "카나리/롤아웃 문제"

트리거 키워드:
- "카나리 멈춤", "롤아웃 실패", "롤아웃 진행 안 됨"
- "AnalysisRun 실패", "카나리 에러", "canary 문제"
- "argo rollouts", "weight 변경 안 됨"

**진단 포인트**: Rollout 상태, AnalysisRun 결과, 카나리 Pod 로그

### Path E: PERSISTENT_OUTOFSYNC — "OutOfSync 계속 뜸"

트리거 키워드:
- "OutOfSync 계속", "sync 해도 다시 OutOfSync", "계속 drift"
- "ArgoCD가 계속 변경 감지", "수동 sync 반복"
- VirtualService/DestinationRule weight 관련 OutOfSync

**진단 포인트**: 어떤 리소스가 OutOfSync인지, 외부 컨트롤러가 수정하는 리소스인지

---

## Disambiguation 규칙

### 애매한 입력 처리

| 입력 | 해석 |
|------|------|
| "배포가 안 돼" | ArgoCD 상태 먼저 확인 → Synced면 Path A, 에러면 Path B |
| "서비스가 이상해" | Pod 상태 먼저 확인 → CrashLoop이면 Path C, Sync 에러면 Path B |
| "뭔가 잘못됐어" | ArgoCD 상태 + Pod 상태 동시 확인 후 분류 |
| ArgoCD 상태 정보 직접 제공 | 해당 상태에 맞는 Path로 바로 라우팅 |

### ArgoCD Application 이름 패턴

```
# 표준 패턴 (대부분의 circle)
{circle}.infra-k8s-{env}
예: ai-gateway.infra-k8s-prod, authentication.infra-k8s-dev

# 일부 circle은 sphere prefix 포함
{sphere}.{circle}.infra-k8s-{env}
예: tech.core-api.infra-k8s-prod
```

**에이전트 실행 시**: 두 패턴 모두 시도. `kubectl get application -n argocd --context {ctx} | grep {circle}` 로 정확한 이름 확인

### Namespace 패턴

```
# 기본 패턴
{sphere}-{circle}
예: tech-ai-gateway, santa-authentication

# IDC는 환경 suffix 포함
{sphere}-{circle}-{env}
예: ai-santa-toefl-model-ckt-dev
```
