---
name: devops:observability-ops
description: |
  VictoriaMetrics, Loki, Alloy, OpenTelemetry 등 모니터링/로깅 스택 운영 스킬.
  메트릭 수집 파이프라인 이슈, 저장소 관리, 쿼리 성능, 알림 규칙 운영을 커버.
  사용 시점: (1) VictoriaMetrics 메모리/디스크 이슈, (2) Loki 로그 수집 실패,
  (3) 메트릭 누락/지연, (4) 알림 규칙 관리 (VMRule/PrometheusRule),
  (5) Alloy/OTel 수집 파이프라인 이슈, (6) Grafana 대시보드 쿼리 최적화.
  트리거 키워드: "VictoriaMetrics", "VM", "Loki", "로그 수집", "메트릭 누락",
  "알림 규칙", "VMRule", "Alloy", "OpenTelemetry", "observability",
  "Grafana 느림", "메트릭 안 나옴", "로그 안 보임".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(kubectl *)
  - mcp__victoriametrics-prod__query
  - mcp__victoriametrics-prod__query_range
  - mcp__victoriametrics-prod__labels
  - mcp__victoriametrics-prod__label_values
  - mcp__victoriametrics-prod__series
  - mcp__victoriametrics-prod__metric_statistics
  - mcp__victoriametrics-prod__active_queries
  - mcp__victoriametrics-prod__tsdb_status
  - mcp__victoriametrics-prod__flags
  - mcp__victoriametrics-prod__alerts
  - mcp__victoriametrics-prod__rules
  - mcp__victoriametrics-prod__documentation
  - mcp__grafana__query_prometheus
  - mcp__grafana__query_loki_logs
  - mcp__grafana__list_datasources
  - mcp__grafana__list_alert_rules
  - mcp__grafana__get_alert_rule_by_uid
---

# Observability Stack Operations

VictoriaMetrics, Loki, Alloy 등 모니터링/로깅 스택 운영 진단 및 최적화.

## 참조 문서 (필요 시 Read)

- `kubernetes/claude-code/02-context/infra-guide.md` → 환경별 정책, 모니터링 구성
- `kubernetes/src/observability/` → 모니터링 컴포넌트 GitOps 소스

## 스택 구성

### EKS 클러스터 (prod/stg/dev/global)

| 컴포넌트 | 네임스페이스 | 역할 |
|---------|-------------|------|
| VictoriaMetrics (vmcluster) | observability-victoriametrics | 메트릭 저장/쿼리 (prod) |
| VictoriaMetrics (vmsingle) | observability-victoriametrics | 메트릭 저장/쿼리 (dev/stg) |
| Loki | observability-loki | 로그 수집/저장/쿼리 |
| Alloy | observability-alloy | 메트릭/로그 수집 에이전트 |
| Grafana | observability-grafana | 시각화 |
| vmalertmanager | observability-victoriametrics | 알림 라우팅 |
| vmagent | observability-victoriametrics | 메트릭 scrape & remote write |

### IDC 클러스터

| 컴포넌트 | 비고 |
|---------|------|
| VictoriaMetrics (vmsingle) | 4Gi RAM, 40Gi Ceph 스토리지 |
| Grafana Datasource UID | `bemfeemok4ge8c` |

---

## VictoriaMetrics 운영

### 상태 확인

```bash
# VM Pod 상태
kubectl --context <ctx> get pods -n observability-victoriametrics

# vmsingle/vmcluster 리소스 사용량
kubectl --context <ctx> top pod -n observability-victoriametrics

# TSDB 상태 (MCP 사용)
# mcp__victoriametrics-prod__tsdb_status
```

### 메모리 이슈

**증상:** vmsingle/vmselect OOMKilled, 쿼리 느림

**진단:**
```promql
# VM 메모리 사용량
process_resident_memory_bytes{job=~".*victoriametrics.*"}

# 활성 쿼리 확인 (MCP)
# mcp__victoriametrics-prod__active_queries
```

**주요 원인:**
- 고카디널리티 쿼리 (label 조합이 너무 많음)
- 긴 시간 범위 쿼리 (30d+ range query)
- 동시 쿼리 과다
- retention 기간 대비 디스크 부족

**해결:**
- `search.maxUniqueTimeseries` 제한 조정
- 카디널리티가 높은 메트릭 식별 및 relabeling
- 쿼리 최적화 (시간 범위 축소, 집계 사용)

### 디스크 이슈

```promql
# VM 디스크 사용량
vm_data_size_bytes

# 저장된 시계열 수
vm_rows_total
```

**상세:** `references/vm-operations.md` 참조

---

## Loki 운영

### 로그 수집 실패

**진단:**
```bash
# Loki Pod 상태
kubectl --context <ctx> get pods -n observability-loki

# Alloy (로그 수집 에이전트) 상태
kubectl --context <ctx> get pods -n observability-alloy

# 특정 Pod 로그가 수집되는지 확인 (Grafana MCP)
# mcp__grafana__query_loki_logs 사용
```

**주요 원인:**
- Alloy DaemonSet Pod 비정상
- Loki ingester 메모리 부족
- S3 저장소 권한/연결 문제
- Rate limiting (per-tenant limits)

### 쿼리 최적화

- **Label 필터 먼저**: `{namespace="tech-ai-gateway"}` → `|= "error"` 순서
- **시간 범위 최소화**: 필요한 기간만 쿼리
- **Line filter 활용**: regex보다 `|=` (contains) 선호
- **Stream selector 활용**: 가능하면 label로 필터링

**상세:** `references/loki-operations.md` 참조

---

## 알림 규칙 관리

### VMRule 구조

```yaml
# src/observability/victoriametrics/infra-k8s-{env}/resources/vmrule.*.yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: <name>
  namespace: observability-victoriametrics
spec:
  groups:
    - name: <group>
      rules:
        - alert: AlertName
          expr: <PromQL>
          for: <duration>
          labels:
            severity: warning|critical
          annotations:
            summary: "..."
            description: "..."
```

### 알림 규칙 확인

```bash
# GitOps에서 모든 VMRule 확인
find src/observability/victoriametrics/ -name 'vmrule.*.yaml'

# 활성 알림 확인 (MCP)
# mcp__victoriametrics-prod__alerts
# mcp__victoriametrics-prod__rules
```

### 알림 규칙 작성 가이드

1. `for` duration: 최소 5m (flapping 방지)
2. severity 레벨: warning (알림만), critical (즉시 대응)
3. annotations: summary (1줄 요약), description (상세), runbook_url (대응 문서)
4. 테스트: `mcp__victoriametrics-prod__test_rules`로 사전 검증

**상세:** `references/alerting-rules.md` 참조

---

## Alloy/OpenTelemetry 수집 파이프라인

### 메트릭 수집 흐름

```
Targets → vmagent (scrape) → VictoriaMetrics (storage)
                ↓
         Alloy (additional scrape/transform)
```

### 로그 수집 흐름

```
Pod stdout/stderr → Alloy (DaemonSet, tail) → Loki (storage)
```

### 수집 누락 진단

```promql
# vmagent target 상태
up{job="<target-job>"}

# Scrape 에러
scrape_series_added{job="<target-job>"}

# vmagent 드롭된 시계열
vm_promscrape_stale_samples_created_total
```

```bash
# vmagent targets 확인
kubectl --context <ctx> port-forward -n observability-victoriametrics svc/vmagent 8429
# http://localhost:8429/targets
```

---

## 출력 포맷

```markdown
# Observability 진단 리포트

## 컴포넌트 상태
| 컴포넌트 | Pod | Status | 비고 |
|---------|-----|--------|------|

## 문제 분석
[증상, 원인, 영향 범위]

## 해결 방안
[구체적 조치]
```
