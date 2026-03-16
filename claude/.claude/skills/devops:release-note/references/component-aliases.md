# Component Aliases Reference

scan-versions.py 스크립트에 내장된 컴포넌트 별칭 매핑 참조 문서.

## 사용법

```bash
# 다양한 별칭으로 같은 컴포넌트 조회 가능
python3 scan-versions.py scan --component istio
python3 scan-versions.py scan --component istiod
python3 scan-versions.py scan --component vm          # victoriametrics
python3 scan-versions.py scan --component eso         # external-secrets
python3 scan-versions.py scan --component cnpg        # cloudnative-pg
```

## 별칭 → Circle 매핑 테이블

| 입력 키워드 | → Circle(s) | Sphere |
|------------|-------------|--------|
| `istio`, `istiod` | `istio-system`, `istio-ingressgateway`, `istio-egressgateway` | infra |
| `istio-ingressgateway` | `istio-ingressgateway` | infra |
| `istio-egressgateway` | `istio-egressgateway` | infra |
| `cert-manager`, `certmanager`, `jetstack` | `cert-manager` | infra |
| `victoriametrics`, `vm`, `victoria-metrics` | `victoriametrics` | observability |
| `loki` | `loki` | observability |
| `alloy` | `alloy` | observability |
| `grafana` | `grafana` | observability |
| `jaeger` | `jaeger` | observability |
| `tempo` | `tempo` | observability |
| `pyroscope` | `pyroscope` | observability |
| `opentelemetry`, `otel` | `opentelemetry` | observability |
| `keda` | `keda` | infra |
| `argo-rollouts`, `argorollouts` | `argo-rollouts` | infra |
| `external-secrets`, `eso` | `external-secrets` | infra |
| `sealed-secrets`, `sealedsecrets` | `sealed-secrets`, `sealed-secrets-web` | infra |
| `cnpg`, `cloudnative-pg`, `cloudnativepg` | `cnpg-system` | infra |
| `gpu-operator`, `gpuoperator` | `gpu-operator` | infra |
| `kyverno` | `kyverno` | infra |
| `external-dns`, `externaldns` | `external-dns` | infra |
| `ebs-csi`, `aws-ebs-csi-driver` | `aws-ebs-csi-driver` | infra |
| `efs-csi`, `aws-efs-csi-driver` | `aws-efs-csi-driver` | infra |
| `s3-csi`, `aws-s3-csi-driver` | `aws-s3-csi-driver` | infra |
| `rook-ceph`, `ceph`, `rook` | `rook-ceph` | infra |
| `harbor` | `harbor` | infra |
| `haproxy` | `haproxy` | infra |
| `metrics-server` | `metrics-server` | infra |
| `goldilocks` | `goldilocks` | infra |
| `velero` | `velero` | infra |
| `reloader` | `reloader` | infra |
| `opencost` | `opencost` | infra |
| `tetragon` | `tetragon` | infra |
| `volcano` | `volcano` | infra |
| `atlantis` | `atlantis` | infra |
| `elastic`, `elasticsearch`, `elastic-system` | `elastic-system` | infra |
| `kube-downscaler`, `downscaler` | `kube-downscaler` | infra |
| `open-feature-operator`, `openfeature` | `open-feature-operator` | infra |
| `qdrant` | `qdrant` | infra |
| `ebpf-exporter` | `ebpf-exporter` | infra |
| `multus` | `multus` | infra |

## 특수 컴포넌트 (Helm 외 관리)

| 컴포넌트 | 관리 방식 | 위치 |
|----------|-----------|------|
| `argocd` | raw K8s manifests | `src/infra/argocd/infra-k8s-global/resources/` |
| `karpenter` | Terraform | `~/workspace/riiid/terraform` |
| `arc-systems` | 수동 Helm CLI | `src/infra/arc-systems/README.md` |

## 별칭 추가 방법

`scan-versions.py` 상단의 `ALIASES` 딕셔너리에 추가:

```python
ALIASES: dict[str, list[str]] = {
    '새키워드': ['circle-name'],
    ...
}
```

새로운 특수 컴포넌트는 `SPECIAL_COMPONENTS` 딕셔너리에 추가:

```python
SPECIAL_COMPONENTS: dict[str, str] = {
    '컴포넌트명': '관리 방식 및 확인 방법 설명',
    ...
}
```
