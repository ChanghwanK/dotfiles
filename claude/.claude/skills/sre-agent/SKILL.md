---
name: sre-agent
description: |
  인프라 전체 스택(Istio, Karpenter, KEDA, ArgoCD, CNPG, Loki 등)과 K8s 레벨에서 발생하는
  모든 문제를 4개 레이어로 병렬 수집하고 교차 분석으로 근본 원인을 찾는 RCA 스킬.
  사용 시점: (1) 알림 발생, service down, CrashLoopBackOff, 503/504 폭증,
  (2) "prod 이상한 거 있어?", "뭔가 이상해 보여", 사전 점검.
  트리거 키워드: "알림 발생", "service down", "CrashLoopBackOff", "503", "504",
  "prod 이상한 거", "뭔가 이상해", "장애", "RCA", "/sre-agent".
model: sonnet
allowed-tools:
  - Bash(kubectl get *)
  - Bash(kubectl describe *)
  - Bash(kubectl logs *)
  - Bash(kubectl top *)
  - Bash(kubectl argo rollouts *)
  - mcp__victoriametrics-prod__query
  - mcp__victoriametrics-prod__query_range
  - mcp__grafana__list_alert_rules
  - mcp__grafana__get_alert_rule_by_uid
  - mcp__grafana__query_loki_logs
  - mcp__grafana__find_error_pattern_logs
  - Agent
  - Read
  - Glob
  - Grep
---

# SRE Agent — 멀티레이어 RCA 스킬

인프라 전체 스택에서 발생하는 문제를 4개 레이어로 병렬 수집하고, 교차 분석으로 근본 원인을 찾는다.

## 클러스터 컨텍스트 매핑

| Context | 클러스터 | 설명 |
|---------|----------|------|
| `k8s-prod` | infra-k8s-prod | 프로덕션 (Tokyo) |
| `k8s-stg` | infra-k8s-stg | 스테이징 (Tokyo) |
| `k8s-dev` | infra-k8s-dev | 개발 (Tokyo) |
| `k8s-global` | infra-k8s-global | 공용 인프라 (Tokyo) |
| `k8s-idc` | infra-k8s-idc | On-Premise GPU (Seoul) |

## 커버 대상 레이어

| 레이어 | 컴포넌트 |
|--------|---------|
| App/Pod | Deployment, Pod lifecycle, CrashLoop, OOMKilled, Pending |
| Service Mesh | Istio, VirtualService, DestinationRule, Envoy 503/504, mTLS |
| Platform | Karpenter NodeClaim, KEDA ScaledObject, ArgoCD sync, kube-system |
| Observability | VictoriaMetrics 알림, Loki 에러 패턴, 메트릭 이상 |

---

## Phase 0: 입력 파싱

사용자 입력에서 아래를 추출한다:

1. **서비스명 (circle)**: 예: `ai-gateway`, `santa-authentication`. 없으면 1회 질문.
2. **Sphere**: circle 이름과 CLAUDE.md 네임스페이스 맵으로 추론. (예: `tech-ai-gateway` → sphere=`tech`)
3. **Namespace**: `{sphere}-{circle}` 패턴. (예: `tech-ai-gateway`)
4. **환경**: prod/stg/dev 언급 없으면 `prod` 기본값. ctx 결정.
5. **증상 분류**:
   - `INCIDENT`: 서비스 장애, 알림 발생, CrashLoop, 503/504
   - `HEALTH_CHECK`: "이상한 거 있어?", 사전 점검, 광범위 스캔

파싱 완료 후 출력:
```
RCA 시작: {circle} ({namespace}, {ctx})
증상: {증상 설명}
4개 레이어 병렬 증거 수집 중... (30-60초 소요)
```

---

## Phase 1: 병렬 증거 수집

아래 4개 에이전트 파일을 각각 Read 후 변수를 치환하여 **단일 메시지에서 동시에** 실행한다.

**Agent A** — Read `agents/agent-app-layer.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context

**Agent B** — Read `agents/agent-platform-layer.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context
- `{sphere}` → 파싱된 sphere
- `{env}` → `infra-k8s-{env}` 형식

**Agent C** — Read `agents/agent-network-layer.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context

**Agent D** — Read `agents/agent-observability-layer.md` 후 실행
변수 치환:
- `{namespace}` → 파싱된 네임스페이스
- `{circle}` → 서비스명
- `{ctx}` → kubectl context

에이전트 실패 처리:
- Agent 실패 시 해당 레이어는 "수집 실패"로 표시하고 나머지 결과로 RCA 진행
- Agent A(App) 실패 → 직접 `kubectl get pods -n {namespace} --context {ctx}` 실행으로 폴백

---

## Phase 2: 교차 RCA

4개 EVIDENCE를 받아 타임라인 기반 교차 분석을 수행한다.

### 2.1 타임라인 정렬

수집된 이벤트/메트릭/로그를 시간순으로 정렬:

```
[시간] [레이어] [이벤트]
─────────────────────────
HH:MM  Platform  Karpenter: NodeClaim 생성 실패 (insufficient capacity)
HH:MM  App       Pod Pending → 3분 후 OOMKilled
HH:MM  Observ.   alert firing: KubePodCrashLooping
HH:MM  Network   Istio: upstream 503 급증
```

### 2.2 레이어 간 인과 관계 파악

가능한 인과 체인 패턴:

| 체인 | 설명 |
|------|------|
| Platform → App | Karpenter 노드 부족 → Pod Pending → 서비스 과부하 |
| App → Network | CrashLoop → Endpoint 제거 → Istio 503 |
| Platform → Network | KEDA 과스케일 → 노드 압박 → 네트워크 지연 |
| Observability → App | 알림 발화 시점과 에러 로그 시점 일치 확인 |

### 2.3 5 Whys

근본 원인에 도달할 때까지 Why를 반복한다 (최대 5단계).

```
1. Why: 서비스 503이 발생했는가?
   → Istio upstream 연결 실패
2. Why: Upstream 연결이 실패했는가?
   → Pod이 모두 Terminating 상태
3. Why: Pod이 Terminating인가?
   → OOMKilled (exit code 137)
4. Why: OOM이 발생했는가?
   → 메모리 limit 512Mi인데 사용량이 600Mi 도달
5. Why: 메모리 사용량이 급증했는가?
   → 새 버전에서 캐시 초기화 버그
```

### 2.4 근본 원인 분류

| 분류 | 예시 |
|------|------|
| Application | 코드 버그, 메모리 누수, 잘못된 설정 |
| Platform | Karpenter 용량 부족, KEDA 오작동, ArgoCD 동기화 실패 |
| Service Mesh | Istio 설정 오류, mTLS 불일치, 잘못된 VirtualService |
| Infrastructure | 노드 NotReady, 디스크/메모리 압박 |
| Configuration | 잘못된 limits/requests, probe 설정, 이미지 태그 |

---

## Phase 3: RCA 리포트 출력

```markdown
# RCA 리포트: {circle} ({env})

## 현재 상태
| 항목 | 상태 |
|------|------|
| Pod | Running {N}/{total} (재시작 {N}회) |
| ArgoCD | {sync_status} / {health_status} |
| 활성 알림 | {N}개 ({severity}) |
| Istio | {status} |
| Karpenter | {NodeClaim 상태} |

## 타임라인
| 시간 | 레이어 | 이벤트 |
|------|--------|--------|
...

## 근본 원인
**분류**: {Application / Platform / Service Mesh / Infrastructure / Configuration}
**컴포넌트**: {구체적 컴포넌트명}
**원인**: {2-3문장 설명}

## 핵심 증거
```
{에러 메시지 또는 이벤트 1-3줄}
```

## 즉시 조치
{Tier 1: 자체 해결 가능한 조치}

## 단기 개선
{재발 방지를 위한 1-2주 내 작업}

## 장기 개선
{아키텍처/프로세스 개선}
```

---

## 참조 문서

필요 시 Read:
- `claude-code/02-context/istio-service-mesh.md` — Istio 이중 Gateway 구조
- `claude-code/02-context/karpenter-guide.md` — NodePool, NodeClaim, RI 정책
- `claude-code/02-context/observability-stack.md` — VM, Loki, Alloy 아키텍처
- `claude-code/03-guardrails/istio-troubleshooting.md` — 503/504 진단 패턴
- `claude-code/memory/known-issues.md` — 정상 이상현상 베이스라인 (false positive 방지)
- `claude-code/03-guardrails/incident-playbooks.md` — CrashLoop, OOMKilled, Spot 중단 플레이북
