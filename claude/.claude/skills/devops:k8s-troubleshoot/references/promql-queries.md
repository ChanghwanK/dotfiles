# PromQL 쿼리 모음

## Grafana MCP 사용법

```
mcp__grafana__query_prometheus 또는 mcp__victoriametrics-prod__query 사용
datasource UID: prometheus (EKS), bemfeemok4ge8c (IDC)
```

---

## Pod 리소스

### CPU

```promql
# Pod CPU 사용량 (cores)
sum(rate(container_cpu_usage_seconds_total{namespace="<ns>", pod=~"<pod-prefix>.*", container!=""}[5m])) by (pod)

# CPU throttling 비율
sum(rate(container_cpu_cfs_throttled_seconds_total{namespace="<ns>", pod=~"<pod-prefix>.*"}[5m])) by (pod)
/ sum(rate(container_cpu_usage_seconds_total{namespace="<ns>", pod=~"<pod-prefix>.*"}[5m])) by (pod)

# CPU request 대비 사용률
sum(rate(container_cpu_usage_seconds_total{namespace="<ns>", pod=~"<pod-prefix>.*", container!=""}[5m])) by (pod)
/ sum(kube_pod_container_resource_requests{namespace="<ns>", pod=~"<pod-prefix>.*", resource="cpu"}) by (pod)
```

### Memory

```promql
# Pod 메모리 사용량 (working set)
sum(container_memory_working_set_bytes{namespace="<ns>", pod=~"<pod-prefix>.*", container!=""}) by (pod)

# 메모리 limit 대비 사용률
sum(container_memory_working_set_bytes{namespace="<ns>", pod=~"<pod-prefix>.*", container!=""}) by (pod)
/ sum(kube_pod_container_resource_limits{namespace="<ns>", pod=~"<pod-prefix>.*", resource="memory"}) by (pod)

# OOM Kill 이력
sum(increase(kube_pod_container_status_last_terminated_reason{namespace="<ns>", reason="OOMKilled"}[24h])) by (pod)
```

### Restart

```promql
# 컨테이너 재시작 횟수 (최근 1시간)
sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>"}[1h])) by (pod, container)

# 재시작 많은 Pod Top 10
topk(10, sum(increase(kube_pod_container_status_restarts_total[1h])) by (namespace, pod))
```

---

## API Server

```promql
# 요청 rate by verb
sum(rate(apiserver_request_total[5m])) by (verb)

# 에러율 (5xx)
sum(rate(apiserver_request_total{code=~"5.."}[5m])) / sum(rate(apiserver_request_total[5m]))

# P99 latency by verb (WATCH 제외)
histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb!~"WATCH|CONNECT"}[5m])) by (le, verb))

# 종료된 요청
sum(rate(apiserver_request_terminations_total[5m])) by (component)

# Inflight requests
apiserver_current_inflight_requests

# Webhook 지연
histogram_quantile(0.99, sum(rate(apiserver_admission_webhook_admission_duration_seconds_bucket[5m])) by (le, name))
```

---

## etcd

```promql
# 리더 변경 횟수
changes(etcd_server_is_leader[1h])

# WAL fsync P99
histogram_quantile(0.99, sum(rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])) by (le))

# Backend commit P99
histogram_quantile(0.99, sum(rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])) by (le))

# DB 크기
etcd_mvcc_db_total_size_in_bytes

# DB 사용률
etcd_mvcc_db_total_size_in_bytes / etcd_server_quota_backend_bytes * 100

# Proposal 실패
rate(etcd_server_proposals_failed_total[5m])
```

---

## Node

```promql
# 노드 CPU 사용률
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)

# 노드 메모리 사용률
1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

# 노드 디스크 사용률
1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})

# 노드 네트워크 에러
rate(node_network_receive_errs_total[5m])
rate(node_network_transmit_errs_total[5m])

# kubelet PLEG 지연
histogram_quantile(0.99, sum(rate(kubelet_pleg_relist_duration_seconds_bucket[5m])) by (le, instance))
```

---

## Scheduler

```promql
# Scheduling 지연
histogram_quantile(0.99, sum(rate(scheduler_scheduling_algorithm_duration_seconds_bucket[5m])) by (le))

# 스케줄링 시도 결과
sum(rate(scheduler_schedule_attempts_total[5m])) by (result)

# Pending Pods
scheduler_pending_pods
```

---

## 서비스 레벨 (HTTP)

```promql
# 에러율 (5xx) by service
sum(rate(istio_requests_total{response_code=~"5.*", destination_service_namespace="<ns>"}[5m])) by (destination_service_name)
/ sum(rate(istio_requests_total{destination_service_namespace="<ns>"}[5m])) by (destination_service_name)

# P99 latency by service
histogram_quantile(0.99, sum(rate(istio_request_duration_milliseconds_bucket{destination_service_namespace="<ns>"}[5m])) by (le, destination_service_name))

# 요청 rate by service
sum(rate(istio_requests_total{destination_service_namespace="<ns>"}[5m])) by (destination_service_name)
```

---

## Karpenter

```promql
# 노드 프로비저닝 시간
histogram_quantile(0.99, sum(rate(karpenter_provisioner_scheduling_duration_seconds_bucket[5m])) by (le))

# 프로비저닝된 노드 수
karpenter_nodes_total

# NodePool별 노드 수
karpenter_nodepools_allowed_disruptions

# Spot interruption
sum(increase(karpenter_interruption_received_messages_total[1h])) by (message_type)
```

---

## HPA/KEDA

```promql
# HPA 현재/원하는/최대 replicas
kube_horizontalpodautoscaler_status_current_replicas{namespace="<ns>"}
kube_horizontalpodautoscaler_status_desired_replicas{namespace="<ns>"}
kube_horizontalpodautoscaler_spec_max_replicas{namespace="<ns>"}

# KEDA scaled object 활성 상태
keda_scaledobject_ready{namespace="<ns>"}
```
