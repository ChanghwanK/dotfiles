# 인벤토리 모드 출력 템플릿

## OSS Helm Chart Inventory ({DATE})

스캔 파일: {N}개 | 불일치: {SKEW_COUNT}개 | 일관: {CONSISTENT_COUNT}개

---

### 환경 간 버전 불일치 ⚠️

| Chart | dev | stg | prod | global | idc | 판정 |
|-------|-----|-----|------|--------|-----|------|
| istiod | 1.28.1 | 1.28.1 | 1.28.1 | **1.28.0** | - | global 미업데이트 |
| external-secrets | 1.0.0 | 1.0.0 | 1.0.0 | **0.9.18** | - | ⚠️ MAJOR gap |
| otel-collector | 0.133.0 | 0.133.0 | **0.129.0** | 0.133.0 | - | prod 뒤처짐 |
| reloader | 2.1.3 | 2.0.0 | 2.0.0 | - | - | dev-first 정상 |

> 판정 기준: dev>stg/prod → "dev-first 정상" / prod만 뒤처짐 → "prod 뒤처짐" / global·idc만 다름 → "{env} 미업데이트" / major 차이 → "⚠️ MAJOR gap"

---

### 버전 일관 ✅ ({CONSISTENT_COUNT} charts)

| Chart | Version | Sphere | 배포 환경 수 |
|-------|---------|--------|-------------|
| cert-manager | 1.18.2 | infra | 6 |
| keda | 2.14.2 | infra | 4 |
| sealed-secrets | 2.15.2 | infra | 6 |
| kyverno | 3.2.8 | infra | 3 |
| loki | 6.20.0 | observability | 3 |
| victoria-metrics-single | 0.14.5 | observability | 3 |
| ... | | | |

---

### 비 GitOps 관리 컴포넌트

| 컴포넌트 | 관리 방식 | 현재 버전 | 확인 방법 |
|----------|-----------|-----------|-----------|
| ArgoCD | raw manifests | 미추적 | `src/infra/argocd/infra-k8s-global/resources/` |
| Karpenter | Terraform | 1.9.0 | `~/workspace/riiid/terraform` |
| arc-systems | 수동 Helm CLI | 0.10.1 | `src/infra/arc-systems/README.md` |
