# Infra PM — North Star Targets

인프라 품질 6차원의 목표값 정의. Phase 1에서는 Reliability와 Operability만 활성화.

최종 업데이트: 2026-03-16

---

## 차원별 가중치

| Dimension    | Weight | Phase 1 |
|--------------|--------|---------|
| Reliability  | 0.25   | ✅ 활성 |
| Operability  | 0.20   | ✅ 활성 |
| Security     | 0.15   | 🔲 Phase 2 |
| Observability| 0.15   | 🔲 Phase 2 |
| Cost         | 0.15   | 🔲 Phase 2 |
| Scalability  | 0.10   | 🔲 Phase 2 |

---

## Reliability (가중치 0.25)

**목표**: 전체 workload가 안정적으로 실행되며, 예상치 않은 재시작과 비정상 상태가 없는 상태.

| 지표 | 목표 | 현재 (초기) | 측정 방법 |
|------|------|------------|-----------|
| pod_restart_rate_per_hr | < 0.5/hr (클러스터 전체 평균) | - | `kubectl get pods -A -o json \| jq` |
| argocd_healthy_pct | > 95% | - | ArgoCD API |
| non_running_pod_count | 0 (Succeeded 제외) | - | `kubectl get pods -A --field-selector` |
| single_replica_prod_pct | < 5% (prod 기준) | - | `kubectl get deployments -A -o json` |

**Score Formula**:
```
argocd_healthy_pct * 0.40
+ (100 - min(restart_rate_normalized, 100)) * 0.30
+ running_pct * 0.20
+ (100 - single_replica_pct) * 0.10
```

restart_rate_normalized = min(restart_rate_per_hr / 0.5, 1.0) * 100
running_pct = (running_pods / total_pods) * 100 (Succeeded 제외)
single_replica_pct = (single_replica_deployments / total_deployments) * 100

---

## Operability (가중치 0.20)

**목표**: 운영자가 별도의 수동 작업 없이 배포/스케일링/업그레이드를 안전하게 수행할 수 있는 상태.

| 지표 | 목표 | 현재 (초기) | 측정 방법 |
|------|------|------------|-----------|
| pdb_coverage_pct | > 80% (prod Deployment 기준) | - | `kubectl get pdb -A -o json` |
| resource_request_set_pct | > 90% (non-system namespace) | - | `kubectl get pods -A -o json` |
| argocd_drift_count | 0 (OutOfSync) | - | ArgoCD API |
| eol_component_count | 0 (지원 종료 버전 운영 중) | - | kustomization.yaml 스캔 |

**Score Formula**:
```
pdb_coverage_pct * 0.30
+ resource_request_set_pct * 0.30
+ (100 - min(drift_normalized, 100)) * 0.20
+ (100 - min(eol_normalized, 100)) * 0.20
```

drift_normalized = min(drift_count * 5, 100)
eol_normalized = min(eol_count * 20, 100)

---

## Security (가중치 0.15) — Phase 2 예정

| 지표 | 목표 | 측정 방법 (예정) |
|------|------|-----------------|
| privileged_container_count | 0 | securityContext 스캔 |
| network_policy_coverage_pct | > 80% | NetworkPolicy 조회 |
| image_vulnerability_critical | 0 (CRITICAL CVE) | Harbor 스캔 결과 |
| host_path_volume_count | 0 (non-system) | pod spec 스캔 |

---

## Observability (가중치 0.15) — Phase 2 예정

| 지표 | 목표 | 측정 방법 (예정) |
|------|------|-----------------|
| metrics_coverage_pct | > 95% | ServiceMonitor 커버리지 |
| log_collection_pct | > 95% | Alloy/Loki 수집률 |
| tracing_enabled_pct | > 70% (tech sphere) | OTEL annotation 여부 |
| alert_rule_coverage | > 80% (critical path) | VMRule 커버리지 |

---

## Cost (가중치 0.15) — Phase 2 예정

| 지표 | 목표 | 측정 방법 (예정) |
|------|------|-----------------|
| cpu_utilization_avg | > 40% (request 대비) | VictoriaMetrics 쿼리 |
| memory_utilization_avg | > 50% (request 대비) | VictoriaMetrics 쿼리 |
| oversized_deployment_count | 0 (2x+ over-provisioned) | 메트릭 비교 |
| spot_instance_ratio | > 70% (dev/stg) | Karpenter NodeClaim 조회 |

---

## Scalability (가중치 0.10) — Phase 2 예정

| 지표 | 목표 | 측정 방법 (예정) |
|------|------|-----------------|
| hpa_coverage_pct | > 60% (api/worker) | HPA 조회 |
| keda_scaledObject_count | 현황 파악 후 설정 | ScaledObject 조회 |
| node_headroom_pct | > 15% (prod) | Karpenter 빈 슬롯 |
| pvc_capacity_utilization | < 80% | PVC 용량 조회 |

---

## 평가 주기

- **정기 평가**: 매주 월요일 weekly:start 후 실행 권장
- **임시 평가**: 인프라 변경 작업 전후 비교

## 점수 등급

| 점수 | 등급 | 의미 |
|------|------|------|
| 90-100 | ⭐ Excellent | North Star 달성 |
| 75-89  | ✅ Good     | 목표 근접, 소수 개선 필요 |
| 60-74  | ⚠️ Fair     | 개선 작업 필요 |
| 0-59   | 🚨 Poor     | 긴급 개선 필요 |
