# 개선 플랜 작성 템플릿

## 구조

개선 플랜은 **즉시 / 단기 / 장기** 3단계로 구분하여 작성한다.

---

## 즉시 조치 (Immediate) — 지금 당장

**목적:** 현재 장애/문제를 해결하여 서비스를 정상 상태로 복구한다.

### 작성 형식

```markdown
### 즉시: [조치 제목]

**변경 내용:**
- 파일: `src/{sphere}/{circle}/infra-k8s-{env}/values.yaml`
- 변경: `resources.limits.memory: 512Mi → 1Gi`

**예상 효과:** OOMKilled 즉시 해소, Pod 정상 가동

**리스크:** 메모리 사용량 증가로 노드 리소스 압박 가능성 (현재 노드 여유: 40%)

**검증 방법:**
- Pod 상태 확인: `kubectl get pod <name> -n <ns>`
- 메모리 사용량 모니터링: `container_memory_working_set_bytes` < 900Mi
```

### 유형별 예시

| 상황 | 즉시 조치 |
|------|----------|
| OOMKilled | memory limit 증가 |
| CrashLoopBackOff (설정 오류) | ConfigMap/Secret 수정 |
| ImagePullBackOff | 이미지 태그 수정, pull secret 확인 |
| Pending (리소스 부족) | replicas 감소 또는 requests 조정 |
| API server 과부하 | 과도한 요청 클라이언트 식별 및 제한 |

---

## 단기 개선 (Short-term) — 1-2주 내

**목적:** 동일 문제의 재발을 방지하는 설정/코드 변경을 적용한다.

### 작성 형식

```markdown
### 단기: [개선 제목]

**변경 내용:**
- 파일: `src/{sphere}/{circle}/common/values.yaml`
- 변경: HPA minReplicas 2 → 3, resource requests 재조정
- 추가: PodDisruptionBudget (minAvailable: 1)

**예상 효과:** 단일 Pod 장애 시에도 서비스 가용성 유지

**리스크:** 리소스 비용 약 30% 증가 (replicas 1개 추가)

**검증 방법:**
- Chaos test: 1개 Pod 강제 삭제 후 서비스 정상 확인
- HPA 동작 확인: 부하 테스트 시 3→5 auto-scale 확인
```

### 유형별 예시

| 상황 | 단기 개선 |
|------|----------|
| 메모리 누수 | 적절한 limit + 모니터링 알림 추가 |
| 스케줄링 실패 | NodePool 설정 조정, affinity 최적화 |
| probe 실패 | probe 파라미터 튜닝 (initialDelay, timeout) |
| 설정 오류 재발 | ConfigMap 검증 로직 추가 |

---

## 장기 개선 (Long-term) — 1-3개월

**목적:** 근본적인 아키텍처, 모니터링, 프로세스를 개선한다.

### 작성 형식

```markdown
### 장기: [개선 제목]

**변경 내용:**
- 아키텍처: 인메모리 캐시 → Redis 외부 캐시로 전환
- 모니터링: 메모리 증가율 기반 선제적 알림 규칙 추가
  - 파일: `src/observability/victoriametrics/infra-k8s-prod/resources/vmrule.{name}.yaml`
- 프로세스: 배포 전 리소스 사용량 벤치마크 자동화

**예상 효과:**
- 메모리 관련 장애 90% 감소
- 배포 전 문제 감지로 프로덕션 장애 예방

**리스크:**
- Redis 도입 시 네트워크 레이턴시 추가 (~1ms)
- 인프라 비용 증가 (ElastiCache 또는 자체 운영)

**검증 방법:**
- 메모리 사용량 추이: 30일간 안정적 유지 확인
- 알림 발생 이력: false positive 비율 < 5%
```

### 유형별 예시

| 상황 | 장기 개선 |
|------|----------|
| 반복 OOM | 애플리케이션 아키텍처 개선 + VPA 도입 검토 |
| API server 과부하 | 클라이언트별 Rate limiting + 캐싱 전략 |
| 노드 장애 빈번 | 노드 health check 강화 + 자동 drain |
| 알림 누락 | 모니터링 커버리지 확대 + SLO 기반 알림 |

---

## GitOps 변경 제안 형식

모든 변경 제안은 GitOps 리포 기준으로 구체적 파일 경로와 diff를 포함한다.

```markdown
**파일:** `src/tech/ai-gateway/infra-k8s-prod/values.yaml`
**변경:**
\`\`\`yaml
# Before
resources:
  limits:
    memory: 512Mi

# After
resources:
  limits:
    memory: 1Gi
\`\`\`
```

---

## 모니터링 강화 방안

개선 플랜에 모니터링 추가가 포함될 경우:

### VMRule 추가 형식

```yaml
# src/observability/victoriametrics/infra-k8s-{env}/resources/vmrule.{name}.yaml
apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: <rule-name>
  namespace: observability-victoriametrics
spec:
  groups:
    - name: <group-name>
      rules:
        - alert: <AlertName>
          expr: <PromQL>
          for: <duration>
          labels:
            severity: <warning|critical>
          annotations:
            summary: "{{ $labels.namespace }}/{{ $labels.pod }}: <설명>"
            description: "<상세 설명>"
```

### Grafana 대시보드

기존 대시보드에 패널 추가 또는 신규 대시보드 생성 시:
- Grafana MCP 도구 활용
- 대시보드 JSON은 GitOps로 관리하지 않음 (Grafana 직접 관리)
