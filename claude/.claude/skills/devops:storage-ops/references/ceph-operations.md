# Ceph 운영 가이드

## Ceph 상태 진단

### ceph status 해석

```
  cluster:
    id:     <uuid>
    health: HEALTH_OK

  services:
    mon: 3 daemons          # Monitor (합의, 메타데이터)
    mgr: 1 daemon active    # Manager (모니터링, 대시보드)
    osd: N osds: N up, N in # OSD (데이터 저장)

  data:
    pools:   X pools, Y pgs
    objects: N objects, X GiB
    usage:   X GiB used, Y GiB avail
    pgs:     Z active+clean
```

### 정상 상태 조건

- `health: HEALTH_OK`
- 모든 OSD: `up` + `in`
- 모든 PG: `active+clean`
- mon 3개 이상

## OSD 관리

### OSD 상태 확인

```bash
# OSD tree (호스트별 OSD 매핑)
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd tree

# OSD 사용량
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd df

# OSD 성능 (최근 perf 통계)
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd perf
```

### OSD 문제

| 상태 | 의미 | 조치 |
|------|------|------|
| `down` + `in` | OSD 프로세스 비정상, 데이터 보존 | 프로세스 재시작, 로그 확인 |
| `down` + `out` | OSD가 클러스터에서 제외됨 | 디스크 교체 또는 OSD 재생성 |
| `nearfull` | 디스크 85% 이상 | 데이터 정리, 리밸런싱, OSD 추가 |
| `full` | 디스크 95% 이상 (write 차단!) | 긴급 데이터 삭제 또는 OSD 추가 |

### OSD 디스크 임계치

| 비율 | 상태 | 동작 |
|------|------|------|
| < 85% | 정상 | - |
| 85% | nearfull | 경고 |
| 90% | backfillfull | 리밸런싱 중단 |
| 95% | full | write 차단! |

## PG (Placement Group) 관리

### PG 상태 확인

```bash
# PG 요약
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph pg stat

# 비정상 PG 확인
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph pg dump_stuck
```

### PG 상태 해석

| 상태 | 의미 | 조치 |
|------|------|------|
| `active+clean` | 정상 | - |
| `active+degraded` | 복제본 부족 | OSD 복구 대기 (자동) |
| `active+recovering` | 복구 중 | 대기 (자동) |
| `inactive` | I/O 불가 | 긴급 — OSD 상태 확인 |
| `stale` | PG 상태 업데이트 안 됨 | Mon/OSD 연결 확인 |

## 용량 계획

### 사용 가능 공간 계산

```
가용 용량 = 총 raw 용량 × (1 / 복제 수) × 0.85 (nearfull 여유)
```

예: OSD 3개 × 1TB NVMe, 복제 수 3
- Raw: 3TB
- 실 사용 가능: 3TB × (1/3) × 0.85 = **850GB**

### 용량 모니터링

```promql
# Ceph 전체 사용률
ceph_cluster_total_used_bytes / ceph_cluster_total_bytes

# Pool별 사용량
ceph_pool_bytes_used

# OSD별 사용률
ceph_osd_stat_bytes_used / ceph_osd_stat_bytes
```

## Rook Operator

### Rook Pod 확인

```bash
# Rook operator
kubectl --context k8s-idc get pods -n rook-ceph -l app=rook-ceph-operator

# Ceph 도구 (toolbox)
kubectl --context k8s-idc get pods -n rook-ceph -l app=rook-ceph-tools

# Mon
kubectl --context k8s-idc get pods -n rook-ceph -l app=rook-ceph-mon

# OSD
kubectl --context k8s-idc get pods -n rook-ceph -l app=rook-ceph-osd
```

### CephCluster CR 확인

```bash
kubectl --context k8s-idc get cephcluster -n rook-ceph
kubectl --context k8s-idc describe cephcluster -n rook-ceph
```
