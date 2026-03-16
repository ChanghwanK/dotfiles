# 알림 규칙 관리 (VMRule / PrometheusRule)

## VMRule 구조

SOCRAAI는 VictoriaMetrics Operator의 VMRule CRD를 사용하여 알림 규칙을 관리한다.

### GitOps 경로

```
src/observability/victoriametrics/
├── infra-k8s-prod/resources/
│   ├── vmrule.kubernetes-system-api-server.yaml
│   ├── vmrule.kubernetes-system-kubelet.yaml
│   ├── vmrule.node-exporter.yaml
│   └── vmrule.custom-*.yaml
├── infra-k8s-stg/resources/
│   └── ...
└── infra-k8s-idc/resources/
    └── ...
```

### VMRule 기본 템플릿

```yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: <descriptive-name>
  namespace: observability-victoriametrics
  labels:
    app: victoriametrics
spec:
  groups:
    - name: <group-name>
      interval: 30s  # 평가 주기 (선택)
      rules:
        - alert: AlertName
          expr: |
            <PromQL expression>
          for: 5m  # 지속 시간 (flapping 방지)
          labels:
            severity: warning  # warning | critical
            team: devops       # 라우팅용
          annotations:
            summary: "{{ $labels.namespace }}/{{ $labels.pod }}: 간결한 설명"
            description: |
              상세 설명.
              현재 값: {{ $value }}
            runbook_url: "https://..."  # 대응 문서 (선택)
```

## severity 레벨 가이드

| Level | 의미 | 대응 | Slack 채널 |
|-------|------|------|-----------|
| `critical` | 즉시 대응 필요, 서비스 영향 | 5분 내 확인 | #notification_infra |
| `warning` | 주의 필요, 잠재적 문제 | 업무 시간 내 확인 | #notification_infra |

## `for` Duration 가이드

| 시나리오 | 권장 `for` | 이유 |
|---------|-----------|------|
| Pod CrashLoopBackOff | 5m | 일시적 재시작 필터링 |
| 높은 에러율 | 5m | 스파이크 필터링 |
| 디스크 사용률 | 15m | 느린 변화, 급한 대응 불필요 |
| Node NotReady | 5m | 일시적 네트워크 glitch 필터링 |
| 인증서 만료 | 0m (instant) | 이미 긴 시간 전 감지 (30d 전) |
| 메모리 사용률 > 90% | 10m | 일시적 peak 필터링 |

## 알림 규칙 작성 팁

### PromQL 표현식

```yaml
# 비율 기반 (rate 사용)
- alert: HighErrorRate
  expr: |
    sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
    / sum(rate(http_requests_total[5m])) by (service)
    > 0.05
  for: 5m

# 임계치 기반
- alert: HighMemoryUsage
  expr: |
    container_memory_working_set_bytes{container!=""}
    / container_memory_limit_bytes{container!=""}
    > 0.9
  for: 10m

# 부재 기반 (absent)
- alert: TargetDown
  expr: up{job="my-service"} == 0
  for: 5m

# 변화율 기반 (predict)
- alert: DiskWillFillIn4Hours
  expr: |
    predict_linear(node_filesystem_avail_bytes[1h], 4*3600) < 0
  for: 30m
```

### 피해야 할 패턴

1. **너무 민감한 알림**: `for: 0m` + 순간 spike 메트릭 → 과도한 알림
2. **너무 느슨한 알림**: `for: 1h` → 대응 지연
3. **카디널리티 폭발**: `by (pod, container, instance)` → 알림 수 폭증
4. **하드코딩된 임계치**: 환경별 다른 기준 필요 → 변수화 고려

## 알림 테스트

### VictoriaMetrics MCP로 사전 검증

```
# 규칙의 PromQL이 올바른지 확인
mcp__victoriametrics-prod__query → expr 실행

# 테스트 규칙 실행
mcp__victoriametrics-prod__test_rules
```

### 검증 체크리스트

- [ ] PromQL 문법 오류 없음
- [ ] 실제 메트릭이 존재함 (`up{job="..."}` 확인)
- [ ] `for` duration이 적절함
- [ ] severity가 올바름
- [ ] annotations의 template 변수가 유효함
- [ ] 예상 알림 수가 합리적 (수십 개 이상이면 재검토)

## 알림 라우팅

### vmalertmanager 설정

알림은 vmalertmanager를 통해 Slack으로 라우팅된다:
- `#notification_infra`: 모든 severity
- 환경별 분기: prod 알림은 별도 채널 가능

### 알림 억제 (Silence)

긴급 작업 중 알림 억제가 필요한 경우:
- Grafana UI → Alerting → Silences → 새 Silence 생성
- matcher로 특정 알림만 억제
- 종료 시간 반드시 설정 (무기한 억제 금지)
