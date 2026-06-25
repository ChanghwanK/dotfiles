# kubectl Context 매핑

| Context | 클러스터 | 환경 | 비고 |
|---------|----------|------|------|
| `k8s-prod` | infra-k8s-prod | 프로덕션 | Tokyo |
| `k8s-stg` | infra-k8s-stg | 스테이징 | Tokyo |
| `k8s-dev` | infra-k8s-dev | 개발 | Tokyo |
| `k8s-global` | infra-k8s-global | 공용 인프라 | Tokyo |
| `k8s-idc` | infra-k8s-idc | On-Premise GPU | Seoul (Proxmox) |
| `k8s-office` | — | 오피스 테스트 | Seoul (Proxmox) |

# 핵심 네임스페이스 맵

GitOps 리포 구조: `kubernetes/src/<sphere>/` = 네임스페이스 단위

| Sphere | 주요 서비스 | 설명 |
|--------|------------|------|
| `santa` | gateway, http-api, grpc-api, backoffice, keycloak, n8n | Santa 제품 (TOEIC/TOEFL) |
| `socraai` | domain, celery-worker, celery-beat | SOCRAAI 제품 (AI 튜터) |
| `infra` | argocd, istio, keda, cnpg, cert-manager, external-secrets, velero, kyverno | 플랫폼 인프라 컴포넌트 |
| `observability` | victoriametrics, loki, alloy, tempo, grafana, pyroscope, opentelemetry | 모니터링/로깅/트레이싱 |
| `data-platform` | — | 데이터 파이프라인 |
| `tech` | — | 기술 공통 |

# 주요 리포지토리

Base path: `~/workspace/riiid`

| 리포 | 경로 | 용도 |
|------|------|------|
| kubernetes | `~/workspace/riiid/kubernetes` | ArgoCD GitOps (K8s 매니페스트, Jsonnet) |
| terraform | `~/workspace/riiid/terraform` | AWS 인프라 IaC |
| kubernetes-charts | `~/workspace/riiid/kubernetes-charts` | Helm chart 저장소 |
| k8s-on-premise | `~/workspace/riiid/k8s-on-premise` | IDC/Office 클러스터 부트스트랩 |

# 배포 워크플로우

1. `kubernetes/src/<sphere>/<app>/` 에서 Jsonnet/YAML 수정
2. PR 생성 → 리뷰 → 머지
3. ArgoCD가 자동 감지 → Sync (수동 Sync 필요 시 ArgoCD UI 또는 `argocd app sync`)
