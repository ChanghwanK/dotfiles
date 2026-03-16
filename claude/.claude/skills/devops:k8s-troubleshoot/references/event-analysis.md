# K8s Event 패턴 분석

## Event 수집 방법

```bash
# 전체 Warning events (최근)
kubectl --context <ctx> get events -A --field-selector type=Warning --sort-by='.lastTimestamp'

# 특정 네임스페이스 events
kubectl --context <ctx> get events -n <ns> --sort-by='.lastTimestamp'

# 특정 오브젝트 관련
kubectl --context <ctx> get events -n <ns> --field-selector involvedObject.name=<name>

# JSON 형식 (상세 분석용)
kubectl --context <ctx> get events -n <ns> -o json | jq '.items[] | {time: .lastTimestamp, reason: .reason, message: .message, count: .count}'
```

## Warning Event 분류

### Pod 관련

| Reason | 의미 | 심각도 | 조치 |
|--------|------|--------|------|
| `BackOff` | 컨테이너 재시작 backoff | High | 로그 확인, exit code 분석 |
| `Failed` | Pod 시작 실패 | High | 이미지, 설정, 볼륨 확인 |
| `FailedScheduling` | 스케줄링 실패 | High | 리소스, affinity, taint 확인 |
| `Unhealthy` | Probe 실패 | Medium | liveness/readiness 설정 확인 |
| `Killing` | 컨테이너 종료 | Info | preStop, graceful shutdown 확인 |
| `Preempting` | 선점 발생 | Medium | PriorityClass 확인 |
| `FailedMount` | 볼륨 마운트 실패 | High | PVC, CSI driver 확인 |
| `FailedAttachVolume` | 볼륨 attach 실패 | High | EBS/Ceph 상태 확인 |

### Node 관련

| Reason | 의미 | 심각도 | 조치 |
|--------|------|--------|------|
| `NodeNotReady` | 노드 비정상 | Critical | kubelet, 런타임, 네트워크 확인 |
| `NodeHasDiskPressure` | 디스크 압박 | High | 디스크 정리, 로그 로테이션 |
| `NodeHasMemoryPressure` | 메모리 압박 | High | Pod eviction, 메모리 leak 확인 |
| `NodeHasInsufficientMemory` | 메모리 부족 | Critical | 워크로드 이동, 노드 추가 |
| `Rebooted` | 노드 재부팅 | High | 원인 분석 (OOM, 커널 패닉) |
| `EvictionThresholdMet` | 축출 임계치 도달 | High | 리소스 pressure 원인 분석 |

### Deployment/ReplicaSet 관련

| Reason | 의미 | 심각도 | 조치 |
|--------|------|--------|------|
| `FailedCreate` | Pod 생성 실패 | High | quota, limits, PVC 확인 |
| `ScalingReplicaSet` | 스케일링 발생 | Info | HPA/KEDA 트리거 확인 |
| `DeploymentRollback` | 롤백 발생 | Medium | 이전 배포 실패 원인 확인 |

### HPA/KEDA 관련

| Reason | 의미 | 심각도 | 조치 |
|--------|------|--------|------|
| `FailedComputeMetricsReplicas` | 메트릭 계산 실패 | Medium | metrics-server, VictoriaMetrics 확인 |
| `FailedGetExternalMetric` | 외부 메트릭 조회 실패 | Medium | KEDA ScaledObject 확인 |

---

## 타임라인 재구성 방법론

### Step 1: 시간 범위 설정

문제 발생 시점 기준 전후 30분~1시간의 events를 수집한다.

### Step 2: Event 정렬 및 그룹화

```bash
# 시간순 정렬 + 카운트 포함
kubectl get events -A --sort-by='.firstTimestamp' -o custom-columns=\
'TIME:.firstTimestamp,COUNT:.count,REASON:.reason,KIND:.involvedObject.kind,NAME:.involvedObject.name,NS:.involvedObject.namespace,MESSAGE:.message'
```

### Step 3: 인과 관계 파악

**패턴 1: 노드 장애 → Pod 재스케줄링**
```
T+0  NodeNotReady (node-xyz)
T+1  Killing (pod-a on node-xyz)
T+2  FailedScheduling (pod-a: no available nodes)
T+5  Scheduled (pod-a on node-abc)
```

**패턴 2: 배포 실패 → 롤백**
```
T+0  ScalingReplicaSet (new-rs)
T+1  FailedCreate (new-rs: insufficient cpu)
T+3  DeploymentRollback
T+4  ScalingReplicaSet (old-rs)
```

**패턴 3: 스토리지 문제 → Pod 시작 실패**
```
T+0  FailedAttachVolume (pvc-xyz)
T+0  FailedMount (volume not attached)
T+5  BackOff (container waiting for mount)
```

**패턴 4: 메모리 압박 연쇄**
```
T+0  NodeHasMemoryPressure
T+1  Evicted (pod-a: memory pressure)
T+1  Evicted (pod-b: memory pressure)
T+3  FailedScheduling (pod-a: insufficient memory)
```

### Step 4: 메트릭 상관 분석

Event 타임라인과 다음 메트릭을 시간 축으로 대조:
- CPU/메모리 사용률 변화
- 네트워크 에러율
- API server latency
- 배포 이력 (ArgoCD sync 시점)

```promql
# 특정 시간대의 Pod restart 수
sum(increase(kube_pod_container_status_restarts_total{namespace="<ns>"}[1h]))

# 특정 시간대의 Warning event 수
sum(increase(kubernetes_events_total{type="Warning"}[1h])) by (reason)
```

## Event 기반 이상 탐지

### 반복 패턴 감지

```promql
# 반복 Warning event가 많은 Pod/Node
sum by (involved_object_name, reason) (increase(kubernetes_events_total{type="Warning"}[1h])) > 10
```

### 주의할 정상 패턴

다음은 정상 운영에서도 발생하는 events (false positive 주의):
- `Pulled`: 이미지 pull 완료 (정상)
- `Created`: 컨테이너 생성 (정상)
- `Started`: 컨테이너 시작 (정상)
- `ScalingReplicaSet`: HPA/KEDA에 의한 스케일링 (정상)
- `Killing` + `Pulled` + `Created` + `Started` 순서: 정상 롤링 업데이트
