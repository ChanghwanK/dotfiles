# VictoriaMetrics 운영 가이드

## 아키텍처

### vmsingle (dev/stg/idc)

단일 바이너리로 수집, 저장, 쿼리 모두 처리. 소규모 환경에 적합.

```
vmagent → vmsingle ← vmselect (Grafana)
              ↓
         로컬 디스크/PVC
```

### vmcluster (prod)

분산 아키텍처로 고가용성과 수평 확장 지원.

```
vmagent → vminsert → vmstorage ← vmselect (Grafana)
            (LB)    (sharding)    (merge)
```

**컴포넌트:**
- **vminsert**: 데이터 수집 및 sharding
- **vmstorage**: 시계열 데이터 저장
- **vmselect**: 쿼리 처리 및 결과 병합

## 메모리 튜닝

### vmsingle

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `-memory.allowedPercent` | 60 | 시스템 메모리 중 사용할 비율 |
| `-search.maxUniqueTimeseries` | 300000 | 단일 쿼리 최대 시계열 수 |
| `-search.maxSamplesPerQuery` | 1000000000 | 단일 쿼리 최대 샘플 수 |

### vmselect (vmcluster)

| 파라미터 | 설명 |
|---------|------|
| `-search.maxConcurrentRequests` | 동시 쿼리 수 제한 |
| `-search.maxUniqueTimeseries` | 단일 쿼리 최대 시계열 |

### 메모리 부족 시 조치

1. **카디널리티 확인**: `mcp__victoriametrics-prod__tsdb_status`
2. **고카디널리티 메트릭 식별**: label 조합 수가 많은 메트릭
3. **relabeling으로 불필요 label 제거**: vmagent relabeling config
4. **쿼리 최적화**: 시간 범위 축소, 집계 함수 활용

## Retention 관리

```bash
# retention 설정 확인
# mcp__victoriametrics-prod__flags → retentionPeriod
```

| 환경 | 권장 retention | 비고 |
|------|--------------|------|
| prod | 90d | 비용과 디스크 밸런스 |
| stg/dev | 30d | 최소 유지 |
| idc | 30d | Ceph 스토리지 제한 (40Gi) |

## 쿼리 최적화

### 느린 쿼리 식별

```bash
# 활성 쿼리 확인
# mcp__victoriametrics-prod__active_queries

# 상위 쿼리 확인
# mcp__victoriametrics-prod__top_queries
```

### 쿼리 최적화 팁

1. **시간 범위 축소**: `[5m]` > `[1h]` > `[1d]` (짧을수록 빠름)
2. **Label 필터 추가**: `{namespace="..."}` 등 범위 제한
3. **subquery 회피**: nested subquery는 메모리 사용량 급증
4. **recording rule 활용**: 자주 사용하는 복잡 쿼리는 recording rule로 사전 계산
5. **rollup 함수**: `avg_over_time`, `max_over_time` 등 활용

### 카디널리티 관리

```promql
# 카디널리티 높은 메트릭 Top 10
topk(10, count by (__name__)({__name__!=""}))

# 특정 메트릭의 label 카디널리티
count(count by (label_name) (metric_name))
```

## 백업/복구

### vmsingle 백업

```bash
# vmbackup 사용 (S3)
vmbackup -storageDataPath=/path/to/data -dst=s3://bucket/path
```

### vmcluster 백업

각 vmstorage 노드별로 개별 백업 필요.

## 모니터링 (자체 모니터링)

```promql
# VM 프로세스 메모리
process_resident_memory_bytes{job=~".*victoriametrics.*"}

# 수집 rate
vm_rows_inserted_total

# 쿼리 지연
vm_request_duration_seconds

# 디스크 사용량
vm_data_size_bytes
```
