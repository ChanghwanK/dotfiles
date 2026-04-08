---
name: devops:k8s-troubleshoot
description: |
  EKS/IDC 클러스터 전반의 Kubernetes 문제 진단, Root Cause Analysis, 개선 플랜 설계 스킬.
  Pod lifecycle 에러(CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending 등),
  클러스터 인프라 문제(API server 과부하, etcd 지연, scheduler 장애, node 이슈),
  K8s event 기반 이상 탐지, 메트릭 상관 분석을 통한 근본 원인 규명.
  RCA 완료 후 재발 방지를 위한 개선 플랜(모니터링 강화, 리소스 조정, 아키텍처 개선) 설계.
  사용 시점: (1) Pod 비정상 상태 진단, (2) 클러스터 레벨 알림 분석 (KubeAPITerminatedRequests 등),
  (3) K8s event 이상 탐지, (4) 장애 RCA 및 개선 플랜 작성, (5) 노드/스케줄링 문제 진단.
  트리거 키워드: CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending, Evicted,
  "Pod 에러", "event 분석", "스케줄링 실패", "API server", "etcd",
  "RCA", "근본 원인", "개선 플랜", "장애 분석", "K8s 문제", "troubleshoot".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(kubectl *)
  - mcp__awslabs_eks-mcp-server__list_k8s_resources
  - mcp__awslabs_eks-mcp-server__get_pod_logs
  - mcp__awslabs_eks-mcp-server__get_k8s_events
  - mcp__victoriametrics-prod__query
  - mcp__victoriametrics-prod__query_range
  - mcp__grafana__query_prometheus
  - mcp__grafana__get_alert_rule_by_uid
  - mcp__grafana__list_alert_rules
---

# Kubernetes Troubleshoot & RCA

EKS/IDC 클러스터의 Pod lifecycle 에러, 클러스터 인프라 문제, K8s event 이상을 체계적으로 진단하고,
근본 원인을 규명한 뒤, 재발 방지를 위한 개선 플랜을 설계한다.

## 클러스터 컨텍스트 매핑

| Context | 클러스터 | Grafana Datasource |
|---------|----------|--------------------|
| `k8s-prod` | infra-k8s-prod | `prometheus` (VictoriaMetrics) |
| `k8s-stg` | infra-k8s-stg | `prometheus` |
| `k8s-dev` | infra-k8s-dev | `prometheus` |
| `k8s-global` | infra-k8s-global | `prometheus` |
| `k8s-idc` | infra-k8s-idc | `bemfeemok4ge8c` |

## 참조 문서 (필요 시 Read)

- `kubernetes/claude-code/02-context/infra-guide.md` → DR 플레이북, 환경별 정책, 장애 대응
- `kubernetes/claude-code/03-guardrails/k8s-standards.md` → Health probe 표준, 리소스 Tier 분류
- `kubernetes/claude-code/02-context/karpenter-guide.md` → NodePool, 스케줄링 실패 시 확인

---

## Stage 1: 증거 수집 (Evidence Collection)

### 1.1 증상 분류

문제를 **Pod 레벨** vs **클러스터 인프라 레벨**로 먼저 분류한다:

**Pod 레벨 증상:**
- 특정 Pod/Deployment의 비정상 상태 (CrashLoopBackOff, ImagePullBackOff, Pending 등)
- 특정 서비스의 에러율 증가, 지연 증가
- 단일 네임스페이스/워크로드에 국한된 문제

**클러스터 인프라 레벨 증상:**
- 다수 네임스페이스에 걸친 광범위한 영향
- API server, etcd, scheduler, controller-manager 관련 알림
- 노드 NotReady, 디스크 압박, 메모리 압박
- KubeAPITerminatedRequests, KubeAPIErrorBudgetBurn 등 시스템 알림

### 1.2 Pod 레벨 증거 수집

```bash
# Pod 상태 확인
kubectl --context <ctx> get pod <pod-name> -n <ns> -o yaml

# Pod events 확인
kubectl --context <ctx> describe pod <pod-name> -n <ns>

# 현재 로그
kubectl --context <ctx> logs <pod-name> -n <ns> --tail=100

# 이전 컨테이너 로그 (crash 시 필수)
kubectl --context <ctx> logs <pod-name> -n <ns> --previous --tail=100

# 리소스 사용량
kubectl --context <ctx> top pod <pod-name> -n <ns>
```

**상태별 상세 진단:** `references/pod-status-errors.md` 참조

### 1.3 클러스터 인프라 레벨 증거 수집

```bash
# 노드 상태
kubectl --context <ctx> get nodes -o wide
kubectl --context <ctx> describe node <node-name>

# 시스템 컴포넌트 상태
kubectl --context <ctx> get componentstatuses 2>/dev/null
kubectl --context <ctx> get pods -n kube-system

# 전체 Warning events (최근 1시간)
kubectl --context <ctx> get events --all-namespaces --field-selector type=Warning --sort-by='.lastTimestamp'
```

**PromQL 쿼리로 메트릭 수집:** `references/promql-queries.md` 참조
**클러스터 인프라 문제 상세:** `references/cluster-infra-issues.md` 참조

### 1.4 K8s Event 타임라인 재구성

```bash
# 네임스페이스별 최근 events
kubectl --context <ctx> get events -n <ns> --sort-by='.lastTimestamp' | tail -30

# 특정 오브젝트 관련 events
kubectl --context <ctx> get events -n <ns> --field-selector involvedObject.name=<name>
```

**Event 패턴 분석:** `references/event-analysis.md` 참조

---

## Stage 2: Root Cause Analysis (RCA)

### 2.1 타임라인 정렬

수집된 모든 증거를 시간 순으로 정렬한다:

```
[시간] [소스] [내용]
─────────────────────────
HH:MM  event   Node NotReady 발생
HH:MM  metric  API server latency 급증
HH:MM  log     Pod OOMKilled
HH:MM  event   Pod rescheduled
```

### 2.2 인과 관계 추론

1. 문제의 **최초 발생 시점** 식별 (첫 번째 이상 신호)
2. 이전 변경 사항 확인 (배포, 설정 변경, 스케일링)
3. 영향 범위 파악 (단일 Pod → 단일 노드 → 클러스터 전체?)
4. 연쇄 반응 추적 (A → B → C 인과 체인)

### 2.3 근본 원인 분류

| 분류 | 예시 | 주요 증거 |
|------|------|----------|
| **Application** | 코드 버그, 메모리 누수, 잘못된 설정 | 앱 로그, exit code, OOM events |
| **Platform** | 리소스 부족, 스케줄링 실패, 노드 장애 | node conditions, scheduler events |
| **Infrastructure** | API server 과부하, etcd 지연, 네트워크 | 시스템 메트릭, component status |
| **Configuration** | 잘못된 limits/requests, probe, 이미지 태그 | Pod spec, describe output |

### 2.4 5 Whys 적용

```
1. Why: Pod가 CrashLoopBackOff 상태인가?
   → OOMKilled (exit code 137)
2. Why: OOM이 발생했는가?
   → 메모리 사용량이 limit(512Mi)을 초과
3. Why: 메모리 사용량이 급증했는가?
   → 새 버전에서 캐시 크기가 무한 증가하는 버그
4. Why: 캐시 크기 제한이 없는가?
   → maxSize 설정이 누락된 채 배포
5. Why: 설정 누락이 감지되지 않았는가?
   → 설정 검증 테스트 미비
```

**RCA 방법론 상세:** `references/rca-methodology.md` 참조

---

## Stage 3: 개선 플랜 설계 (Improvement Plan)

### 3.1 시간 축 기반 분류

| 구분 | 기간 | 목적 |
|------|------|------|
| **즉시 조치 (Immediate)** | 지금 | 현재 문제 해결 |
| **단기 개선 (Short-term)** | 1-2주 | 재발 방지 |
| **장기 개선 (Long-term)** | 1-3개월 | 근본적 아키텍처/프로세스 개선 |

### 3.2 각 항목 작성 형식

```markdown
### [즉시/단기/장기] 제목

- **변경 내용**: 구체적 수정 사항 (GitOps 파일 경로 포함)
- **예상 효과**: 정량적/정성적 기대 효과
- **리스크**: 변경으로 인한 부작용 가능성
- **검증 방법**: 변경 후 확인할 메트릭/로그/상태
```

### 3.3 GitOps 변경 제안

개선 플랜의 구체적 변경은 GitOps 리포 기준으로 제안한다:
- `src/{sphere}/{circle}/common/values.yaml` — 공통 설정 변경
- `src/{sphere}/{circle}/infra-k8s-{env}/values.yaml` — 환경별 설정 변경
- `src/{sphere}/{circle}/infra-k8s-{env}/resources/` — 추가 K8s 매니페스트
- `src/observability/` — 모니터링/알림 규칙 추가

**개선 플랜 템플릿:** `references/improvement-plan-template.md` 참조

---

## 출력 포맷

```markdown
# [서비스명] 진단 리포트

## 1. 증상 요약
- 발생 시간: YYYY-MM-DD HH:MM
- 영향 범위: [Pod/Node/Cluster]
- 심각도: [Critical/Warning/Info]

## 2. 타임라인
| 시간 | 소스 | 이벤트 |
|------|------|--------|

## 3. Root Cause Analysis
- 근본 원인 분류: [Application/Platform/Infrastructure/Configuration]
- 5 Whys 분석: ...
- 결론: ...

## 4. 개선 플랜
### 즉시 조치
### 단기 개선
### 장기 개선
```

---

## 검증

진단 완료 후 반드시 확인:
1. 증거 수집이 충분한가? (로그, 이벤트, 메트릭 모두 확인했는가?)
2. RCA가 증거 기반인가? (추측이 아닌 데이터에 근거하는가?)
3. 개선 플랜이 구체적인가? (GitOps 파일 경로와 변경 내용이 명시되었는가?)
4. 즉시 조치로 현재 문제가 해결되는가?
