# 클러스터 인프라 문제 진단

## API Server 문제

### KubeAPITerminatedRequests

**의미:** API server가 처리 중인 요청을 조기 종료 (503 응답). 보통 API server 과부하, 요청 큐 포화 시 발생.

**진단:**
```promql
# 종료된 요청 비율
sum(rate(apiserver_terminated_watchers_total[5m]))
sum(rate(apiserver_request_terminations_total[5m])) by (component)

# API server request latency
histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb!="WATCH"}[5m])) by (le, verb))

# 현재 inflight requests
apiserver_current_inflight_requests
```

**주요 원인:**
- 과도한 LIST/WATCH 요청 (대규모 리소스 변경 시)
- Webhook 처리 지연 (validating/mutating webhook timeout)
- etcd 지연 전파
- 특정 클라이언트의 과도한 요청 (Argo, Karpenter 등)

**대응:**
1. `apiserver_request_total` 메트릭으로 요청 소스 식별
2. Priority & Fairness 설정 확인
3. Webhook 타임아웃/실패율 확인
4. etcd 상태 확인 (아래 참조)

### KubeAPIErrorBudgetBurn

**의미:** API server SLO 에러 버짓 소진 속도가 임계치 초과.

**진단:**
```promql
# 에러율
sum(rate(apiserver_request_total{code=~"5.."}[5m])) / sum(rate(apiserver_request_total[5m]))

# verb별 에러율
sum(rate(apiserver_request_total{code=~"5.."}[5m])) by (verb, resource)
```

### KubeAPILatencyHigh

**진단:**
```promql
# P99 latency by verb
histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb!~"WATCH|CONNECT"}[5m])) by (le, verb, resource))

# 느린 요청 식별
histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket[5m])) by (le, resource, verb)) > 1
```

---

## etcd 문제

### etcd 리더 변경 (Leader Election)

**의미:** 잦은 리더 변경은 네트워크 불안정 또는 디스크 I/O 지연을 나타냄.

**진단:**
```promql
# 리더 변경 횟수
changes(etcd_server_is_leader[1h])

# 리더 변경 rate
rate(etcd_server_leader_changes_seen_total[5m])
```

### etcd 디스크 지연

**진단:**
```promql
# WAL fsync 지연 (P99)
histogram_quantile(0.99, sum(rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])) by (le))

# Backend commit 지연 (P99)
histogram_quantile(0.99, sum(rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])) by (le))
```

**임계치:**
- WAL fsync: > 10ms 주의, > 100ms 위험
- Backend commit: > 25ms 주의, > 100ms 위험

### etcd 쿼럼 상실

**진단:**
```promql
# 활성 멤버 수
etcd_server_has_leader

# Proposal 실패
rate(etcd_server_proposals_failed_total[5m])
```

### etcd DB 크기

```promql
# DB 크기
etcd_mvcc_db_total_size_in_bytes
etcd_server_quota_backend_bytes  # quota

# DB 사용률
etcd_mvcc_db_total_size_in_bytes / etcd_server_quota_backend_bytes * 100
```

**임계치:** DB 크기가 quota의 80% 초과 시 경고

---

## Scheduler / Controller Manager

### Scheduler 문제

**증상:** Pod가 Pending 상태로 장시간 대기, scheduling 처리 속도 저하.

**진단:**
```promql
# Scheduling 지연
histogram_quantile(0.99, sum(rate(scheduler_scheduling_algorithm_duration_seconds_bucket[5m])) by (le))

# Scheduling 실패
rate(scheduler_schedule_attempts_total{result="error"}[5m])
rate(scheduler_schedule_attempts_total{result="unschedulable"}[5m])

# Pending Pods 수
scheduler_pending_pods
```

### Controller Manager 문제

**진단:**
```promql
# Work queue 깊이 (처리 대기 항목)
workqueue_depth{job="kube-controller-manager"}

# 처리 지연
workqueue_queue_duration_seconds{job="kube-controller-manager"}
```

---

## Node 문제

### Node NotReady

**진단:**
```bash
kubectl describe node <node-name> | grep -A20 "Conditions"
kubectl get events --field-selector involvedObject.name=<node-name> --sort-by='.lastTimestamp'
```

**주요 원인:**
- kubelet 프로세스 비정상
- 컨테이너 런타임 (containerd) 장애
- 네트워크 단절 (API server 연결 불가)
- 디스크 공간 부족
- 메모리 부족 (시스템 프로세스 kill)

**EKS 특이사항:**
- Karpenter 노드: EC2 인스턴스 상태 확인 (spot interruption 등)
- 노드 drain 상태 확인: cordon/drain 여부

**IDC 특이사항:**
- Proxmox VM 상태 확인
- 물리 호스트 하드웨어 상태

### Node 리소스 압박

**진단:**
```promql
# 노드 CPU 사용률
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) by (instance)

# 노드 메모리 사용률
1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

# 노드 디스크 사용률
1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})
```

### Kubelet 문제

```promql
# kubelet 관련 메트릭
kubelet_running_pods
kubelet_running_containers

# PLEG (Pod Lifecycle Event Generator) 지연
histogram_quantile(0.99, sum(rate(kubelet_pleg_relist_duration_seconds_bucket[5m])) by (le, instance))
```
