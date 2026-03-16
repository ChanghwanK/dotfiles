# Loki 운영 가이드

## 아키텍처

### 수집 파이프라인

```
Pod stdout/stderr
    ↓
Alloy DaemonSet (각 노드에서 로그 tail)
    ↓
Loki (Ingester → Compactor → S3)
    ↓
Grafana (LogQL 쿼리)
```

### 컴포넌트

| 컴포넌트 | 역할 |
|---------|------|
| **Distributor** | 로그 수신, tenant 라우팅 |
| **Ingester** | 메모리 버퍼, 청크 생성 |
| **Querier** | LogQL 쿼리 실행 |
| **Compactor** | 인덱스 압축, retention 적용 |
| **Index Gateway** | 인덱스 캐시 |

## 로그 수집 실패 진단

### Alloy 문제

```bash
# Alloy DaemonSet 상태
kubectl --context <ctx> get ds -n observability-alloy
kubectl --context <ctx> get pods -n observability-alloy -o wide

# Alloy 로그 확인 (수집 에러)
kubectl --context <ctx> logs -n observability-alloy <pod-name> --tail=50
```

**주요 원인:**
- DaemonSet Pod가 노드에 스케줄링 안 됨 (toleration 누락)
- 로그 파일 경로 변경 (/var/log/pods)
- 라벨링 규칙 에러
- Loki endpoint 연결 실패

### Loki Ingester 문제

```bash
# Ingester 상태
kubectl --context <ctx> get pods -n observability-loki -l app.kubernetes.io/component=ingester

# Ingester 메모리 사용량
kubectl --context <ctx> top pod -n observability-loki -l app.kubernetes.io/component=ingester
```

**OOM 방지:**
- `ingester.chunk-encoding: snappy` (압축으로 메모리 절약)
- `limits_config.ingestion_rate_mb` 조정
- `limits_config.max_streams_per_user` 제한

### S3 저장소 문제

**증상:** Compactor 에러, 오래된 로그 조회 실패

**진단:**
```bash
# Compactor 로그
kubectl --context <ctx> logs -n observability-loki -l app.kubernetes.io/component=compactor --tail=50
```

**주요 원인:**
- S3 버킷 권한 (IRSA 설정)
- S3 endpoint 연결 (VPC Endpoint 확인)
- 버킷 용량/비용

## LogQL 쿼리 최적화

### 기본 원칙

1. **Stream selector 먼저**: `{namespace="...", app="..."}` — 검색 범위 제한
2. **Line filter 다음**: `|= "error"` (contains) > `|~ "err.*"` (regex)
3. **Parser 마지막**: `| json` 또는 `| logfmt`

### 효율적인 쿼리 패턴

```logql
# 좋음: label로 범위 제한 후 line filter
{namespace="tech-ai-gateway", container="main"} |= "error" |= "timeout"

# 나쁨: 너무 넓은 범위
{namespace=~".*"} |~ "error|warning|critical"

# 좋음: 파싱 후 필터
{namespace="tech-ai-gateway"} | json | level="error" | status >= 500

# 집계 쿼리
sum(rate({namespace="tech-ai-gateway"} |= "error" [5m])) by (container)
```

### 쿼리 성능 팁

- **시간 범위**: 가능하면 1h 이내, 최대 24h
- **Label 매처**: exact match(`=`) > regex match(`=~`)
- **Line filter**: `|=` (contains) > `|~` (regex)
- **Parallel query**: Loki가 자동으로 시간 분할 병렬 처리

## Rate Limiting

### 주요 제한 파라미터

| 파라미터 | 설명 | 기본값 |
|---------|------|--------|
| `ingestion_rate_mb` | 초당 수집 MB | 4 |
| `ingestion_burst_size_mb` | 버스트 수집 MB | 6 |
| `max_streams_per_user` | 최대 스트림 수 | 10000 |
| `max_entries_limit_per_query` | 쿼리당 최대 엔트리 | 5000 |

### Rate Limit 초과 시

```bash
# Distributor 로그에서 rate limit 에러 확인
kubectl --context <ctx> logs -n observability-loki -l app.kubernetes.io/component=distributor --tail=50 | grep -i "rate"
```

**해결:**
- 불필요한 로그 필터링 (Alloy에서 drop)
- 로그 레벨 조정 (DEBUG → INFO)
- Rate limit 값 증가 (values.yaml)

## Retention

```yaml
# Loki retention 설정
compactor:
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

limits_config:
  retention_period: 30d  # 기본 retention
```
