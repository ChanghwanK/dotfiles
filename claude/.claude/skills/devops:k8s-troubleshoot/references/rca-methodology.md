# RCA (Root Cause Analysis) 수행 가이드

## 핵심 원칙

1. **증거 기반 판단**: 추측이 아닌 데이터(로그, 메트릭, 이벤트)에 근거한다
2. **인과 관계 구분**: 상관 관계(correlation)와 인과 관계(causation)를 구분한다
3. **시간 순서 준수**: 결과는 반드시 원인 이후에 발생한다
4. **완전성 확인**: 모든 증거가 일관되게 설명되는지 확인한다

---

## 5 Whys 기법

### 적용 방법

1. 관찰된 증상을 첫 번째 "Why"로 시작
2. 각 답변에 대해 "왜 그런가?"를 반복 질문
3. 기술적 근본 원인에 도달할 때까지 진행 (보통 3-7회)
4. 근본 원인은 **변경 가능한 것**이어야 한다

### 좋은 5 Whys 예시

```
1. Why: 사용자가 503 에러를 경험한다
   → Istio VirtualService가 트래픽을 healthy Pod로 라우팅하지 못함
2. Why: healthy Pod가 없는가?
   → 모든 Pod가 CrashLoopBackOff 상태
3. Why: Pod가 crash하는가?
   → OOMKilled (exit code 137), 메모리 limit 512Mi 초과
4. Why: 메모리 사용량이 limit을 초과하는가?
   → 새 배포 버전에서 인메모리 캐시가 TTL 없이 무한 증가
5. Why: 캐시 TTL이 설정되지 않았는가?
   → 환경변수 CACHE_TTL이 ConfigMap에서 누락됨

→ 근본 원인: ConfigMap에 CACHE_TTL 환경변수 누락
→ 조치: ConfigMap 수정 + 설정 검증 CI 추가
```

### 나쁜 5 Whys (피해야 할 패턴)

- "사람이 실수했다" → 프로세스/시스템 레벨 원인으로 파고들어야 함
- 순환 논리 (A→B→A)
- 너무 추상적 ("시스템이 복잡해서")

---

## 타임라인 분석

### 구성 요소

타임라인은 3가지 소스를 통합한다:

| 소스 | 수집 방법 | 정보 |
|------|----------|------|
| K8s Events | `kubectl get events --sort-by` | 리소스 생명주기 변화 |
| 메트릭 | PromQL / Grafana | CPU, 메모리, 에러율, 레이턴시 |
| 로그 | `kubectl logs`, Loki | 애플리케이션 에러, 스택 트레이스 |

### 타임라인 작성 형식

```
시간          소스     이벤트
──────────────────────────────────────────
14:20:00     deploy   ArgoCD sync: ai-gateway v2.1.5 → v2.1.6
14:20:30     event    ScalingReplicaSet: new ReplicaSet created
14:21:00     event    Pulled: image harbor.../ai-gateway:v2.1.6
14:21:10     event    Started: container main
14:21:15     log      ERROR: Connection refused to redis:6379
14:21:20     metric   error_rate spike: 0.1% → 45%
14:21:25     event    Unhealthy: readiness probe failed
14:21:30     event    BackOff: container restarting
14:22:00     event    Killing: container failed liveness probe
```

### 분기점 식별

타임라인에서 **정상 → 비정상** 전환 시점을 식별한다:
- 배포 시점 (ArgoCD sync)
- 설정 변경 시점 (ConfigMap/Secret 변경)
- 스케일링 이벤트 (HPA/KEDA 트리거)
- 인프라 변경 (노드 추가/제거, NodePool 변경)
- 외부 의존성 변화 (DB, Redis, 외부 API)

---

## 인과 관계 추론

### 증거 일치성 검증

RCA 결론이 올바른지 다음을 확인한다:

1. **시간적 일치**: 원인이 결과보다 먼저 발생하는가?
2. **범위 일치**: 원인의 영향 범위가 관찰된 증상 범위와 일치하는가?
3. **메커니즘 설명**: 원인이 결과를 일으키는 기술적 메커니즘이 설명 가능한가?
4. **반증 부재**: 결론을 반박하는 증거가 없는가?

### 대안 가설 검증

근본 원인을 확정하기 전에 다른 가능한 원인을 배제한다:

```
가설 A: 새 배포 버전의 메모리 누수
- 시간적 일치: ✅ 배포 후 30분부터 메모리 증가
- 범위 일치: ✅ 새 버전 Pod만 영향
- 이전 버전 비교: ✅ 이전 버전은 안정적 메모리 사용

가설 B: 트래픽 증가로 인한 메모리 증가
- 시간적 일치: ❌ 트래픽은 평소 수준
- 기각
```

---

## 근본 원인 분류 프레임워크

### 4계층 분류

| 계층 | 범위 | 예시 | 해결 주체 |
|------|------|------|----------|
| **Application** | 앱 코드/설정 | 메모리 누수, 잘못된 쿼리, 설정 오류 | 제품팀 |
| **Platform** | K8s/Helm | 리소스 limit, probe, HPA 설정 | DevOps |
| **Infrastructure** | 노드/네트워크 | API server 과부하, 노드 장애, 네트워크 | DevOps |
| **Configuration** | GitOps 설정 | 이미지 태그, 환경변수, 시크릿 | DevOps/제품팀 |

### 분류 기준

- **단일 Pod/서비스에 국한**: Application 또는 Configuration
- **다수 서비스에 영향**: Platform 또는 Infrastructure
- **배포 직후 발생**: Application 또는 Configuration
- **점진적 악화**: Application (리소스 누수) 또는 Infrastructure (용량)
- **갑작스러운 장애**: Infrastructure (노드/네트워크) 또는 Platform (설정 변경)
