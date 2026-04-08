# 메트릭 현황 수집 에이전트

조사 주제: {topic}
대상 sphere: {sphere}
대상 circle: {circle}
대상 환경: {env}

아래 절차로 VictoriaMetrics / Grafana에서 관련 메트릭을 수집하고 결과를 반환한다.
주제({topic})와 직접 관련된 메트릭만 조회한다. 관련 없는 항목은 건너뛴다.

---

## 수집 절차

### 1. 에러율 / 가용성

주제가 서비스 장애, 에러, 응답 속도 관련이면:

VictoriaMetrics MCP 도구로 아래 PromQL을 조회한다 (victoriametrics-prod):
- HTTP 에러율: `sum(rate(http_requests_total{namespace="{sphere}-{circle}", status=~"5.."}[5m])) / sum(rate(http_requests_total{namespace="{sphere}-{circle}"}[5m]))`
- P99 응답시간: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{namespace="{sphere}-{circle}"}[5m])) by (le))`

### 2. 리소스 사용량

주제가 리소스, 비용, 스케일링 관련이면:

- CPU 사용률: `sum(rate(container_cpu_usage_seconds_total{namespace="{sphere}-{circle}"}[5m])) by (pod)`
- Memory 사용량: `sum(container_memory_working_set_bytes{namespace="{sphere}-{circle}"}) by (pod)`

### 3. Grafana 대시보드 확인

Grafana MCP 도구로 `{sphere}` 또는 `{circle}` 키워드로 대시보드를 검색하여
관련 패널의 현재 수치를 확인한다.

### 4. 비용 관련

주제가 비용 최적화 관련이면:
- 현재 노드 타입 및 spot/on-demand 비율 조회
- Cross-zone 트래픽 비용 관련 메트릭 확인 (가능한 경우)

---

## 출력 형식

```
## 메트릭 현황

**조사 기간**: 최근 24시간 / 최근 7일 (조회 범위 명시)

### 에러율 / 가용성
- HTTP 5xx 에러율: N% (정상: <1%)
- P99 응답시간: Nms

### 리소스 사용량
| 리소스 | 현재 사용량 | Request | Limit | 비율 |
|--------|------------|---------|-------|------|
| CPU    | ...        | ...     | ...   | ...% |
| Memory | ...        | ...     | ...   | ...% |

### 이상 징후
- (있으면 기술, 없으면 "현재 이상 없음")
```

메트릭을 조회할 수 없거나 관련 없는 항목은 "해당 없음"으로 명시한다.
