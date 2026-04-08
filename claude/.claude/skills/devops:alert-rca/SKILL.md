---
name: devops:alert-rca
description: |
  Slack 알럿 URL을 입력받아 단일 알럿 심층 RCA를 수행하는 스킬.
  현상파악(Grafana MCP + VictoriaMetrics MCP) → RCA(kubectl) 2단계 구조.
  알럿 카테고리(Pod, Node, Network, Scaling, Storage, DB)별 분기 플로우로 진행.
  해결책 3가지 장/단점 + ROI 분석 후 최선안을 추천한다.
  사용 시점: (1) 특정 알럿 근본 원인 파악, (2) 반복 발생 알럿 심층 분석,
  (3) 해결책 ROI 비교가 필요한 경우.
  트리거 키워드: "알럿 분석", "alert rca", "이 알럿 분석해줘", "/devops:alert-rca".
model: sonnet
allowed-tools:
  - mcp__slack__slack_get_channel_history
  - mcp__slack__slack_get_thread_replies
  - mcp__grafana__get_alert_rule_by_uid
  - mcp__victoriametrics-prod__query
  - mcp__victoriametrics-prod__query_range
  - mcp__victoriametrics-prod__label_values
  - mcp__victoriametrics-prod__labels
  - mcp__victoriametrics-prod__series
  - mcp__victoriametrics-prod__flags
  - mcp__victoriametrics-prod__tsdb_status
  - mcp__victoriametrics-prod__top_queries
  - mcp__victoriametrics-prod__active_queries
  - mcp__victoriametrics-prod__metric_statistics
  - WebFetch
  - Read
  - Bash(kubectl *)
  - Bash(python3 *)
---

# devops:alert-rca Skill

Slack 알럿 URL 하나를 입력받아, 카테고리별 분기 플로우로 현상파악(MCP) + RCA(kubectl)를 수행하고, 해결책 3가지를 ROI 분석과 함께 제안한다.

---

## 핵심 원칙

- **2단계 분리**: 현상파악은 MCP(시계열 메트릭), RCA는 kubectl(K8s 리소스 상태). 둘을 섞지 않는다.
- **카테고리 우선 판별**: 알럿 rule name + labels에서 카테고리(A~F)를 먼저 결정하고, 해당 플로우만 실행한다.
- **false positive 방지**: RCA 전 `claude-code/memory/known-issues.md`를 참조하여 정상 이상현상인지 확인한다.
- **ROI 기반 추천**: 해결책은 팀 원칙(생산성 > 비용 > 안정성)을 반영하여 최선안을 선택한다.
- **애매한 부분은 질문**: 필수 정보(namespace, pod명 등)가 없으면 사용자에게 바로 묻는다.
- **메커니즘 우선 설명**: 현상 나열에 그치지 않고, 해당 한도/제한이 왜 존재하는지(설계 의도), 어떤 순서로 실패가 발생했는지(failure chain), 무엇이 트리거였는지를 반드시 규명한다. "브리핑"이 아닌 "원리 이해"를 목표로 한다.

---

## 워크플로우

### Step 1 — Slack URL 파싱 → 알럿 메시지 읽기

**URL 형식**: `https://app.slack.com/archives/{channel_id}/p{ts_digits}`
- `ts_digits` (예: `1743385200123456`) → `1743385200.123456` 형식으로 변환

```
slack_get_channel_history(channel_id="{channel_id}", limit=5, latest="{ts+1}", oldest="{ts-1}")
```

스레드 답글이 있으면:
```
slack_get_thread_replies(channel_id="{channel_id}", thread_ts="{ts}")
```

### Step 2 — 알럿 메타데이터 추출

메시지에서 아래 항목을 추출한다. 없으면 "알 수 없음"으로 표시 후 계속 진행.

| 항목 | 추출 위치 |
|------|-----------|
| rule name | 알럿 제목 |
| severity | CRITICAL / WARNING / INFO |
| cluster | 라벨 또는 메시지 본문 |
| namespace | 라벨 |
| service / pod | 라벨 |
| firing 시각 | 메시지 타임스탬프 (KST 변환) |
| Grafana source 링크 | 버튼 또는 링크 |

Grafana source 링크에서 UID 추출:
- `/alerting/{uid}/view` → uid 파싱
- `?uid={uid}` 쿼리 파라미터 → uid 파싱

### Step 3 — Grafana 알럿 규칙 조회

```
mcp__grafana__get_alert_rule_by_uid(uid="{uid}")
```

추출 항목:
- `data.data[].model.expr` → PromQL 쿼리
- `data.for` → 지속 시간 (e.g. "5m")
- threshold 값

UID를 추출할 수 없는 경우: Slack 메시지 본문에서 PromQL을 직접 파싱하거나 사용자에게 요청한다.

### Step 4 — 카테고리 판별

rule name + labels + 메시지 내용으로 아래 카테고리 중 하나를 선택한다.

| 카테고리 | 트리거 패턴 |
|----------|-------------|
| A — Pod/Container | `KubePodCrashLooping`, `KubeContainerWaiting`, `KubePodNotReady`, `OOMKilled`, `HighRestartCount` |
| B — Node/인프라 | `KubeNodeNotReady`, `NodeHighCPU`, `NodeHighMemory`, `NodeDiskPressure`, `KarpenterNode*` |
| C — 네트워크/Istio | `HighErrorRate`, `High5xxRate`, `HighLatency`, `IstioProxy*`, `ConnectionRefused` |
| D — 스케일링 | `HPAMaxReplicas`, `KEDAScalerError`, `HighPodPending`, `ReplicaSetFailed` |
| E — 스토리지 | `PVCPending`, `CephHealth*`, `DiskFull`, `PVCBoundFailed` |
| F — DB/CNPG | `CNPGCluster*`, `DBConnectionHigh`, `AuroraFailover`, `PostgresReplicationLag` |
| G — 옵저버빌리티 | `VMAlert*`, `VictoriaMetrics*`, `LokiIngestion*`, `HighCardinality`, `tsdb_*`, `vm_*` |

패턴 매칭이 불명확하면 namespace와 서비스명으로 추가 판단한다.

### Step 5 — [Phase 1] 현상파악 (MCP)

**클러스터별 VM MCP 분기**:
- `prod / stg / dev / global` → `mcp__victoriametrics-prod__query_range` 사용
- `idc / office` → WebFetch 직접 쿼리:
  ```
  GET https://victoriametrics-vmauth-idc.global.riiid.exposed/api/v1/query_range
    ?query={PromQL_encoded}&start={firing_unix-3600}&end={firing_unix+1800}&step=60
  ```

공통 시간 범위: `start = firing 시각 - 1시간`, `end = firing 시각 + 30분`

#### 카테고리 A — Pod/Container

```
query_range: kube_pod_container_status_restarts_total{namespace="{ns}",pod=~"{pod}.*"}
query_range: container_memory_usage_bytes{namespace="{ns}",pod=~"{pod}.*"}
query_range: kube_pod_status_phase{namespace="{ns}",pod=~"{pod}.*"}
```

#### 카테고리 B — Node/인프라

```
query_range: 1 - avg(rate(node_cpu_seconds_total{mode="idle",node="{node}"}[5m]))
query_range: node_memory_MemAvailable_bytes{node="{node}"}
query_range: node_filesystem_avail_bytes{node="{node}",mountpoint="/"}
query_range: kube_node_status_condition{condition="Ready",node="{node}"}
```

#### 카테고리 C — 네트워크/Istio

```
query_range: sum(rate(istio_requests_total{response_code=~"5..",destination_service_name="{svc}"}[5m]))
query_range: histogram_quantile(0.99, rate(istio_request_duration_milliseconds_bucket{destination_service_name="{svc}"}[5m]))
query_range: up{job=~".*istiod.*"}
```

#### 카테고리 D — 스케일링

```
query_range: kube_horizontalpodautoscaler_status_current_replicas{namespace="{ns}"}
query_range: kube_horizontalpodautoscaler_spec_max_replicas{namespace="{ns}"}
query_range: count(kube_pod_status_phase{namespace="{ns}",phase="Pending"})
```

KEDA 관련 시 추가:
```
query_range: keda_scaler_metrics_value{namespace="{ns}"}
```

#### 카테고리 E — 스토리지

```
query_range: kube_persistentvolumeclaim_status_phase{namespace="{ns}"}
query_range: ceph_cluster_total_used_bytes / ceph_cluster_total_bytes * 100
query_range: ceph_health_status
```

#### 카테고리 F — DB/CNPG

```
query_range: cnpg_pg_replication_lag{namespace="{ns}"}
query_range: cnpg_backends_total{namespace="{ns}"}
query_range: changes(cnpg_pg_postmaster_start_time{namespace="{ns}"}[1h])
```

### Step 5.5 — 메커니즘 분석 (한도/트리거 규명)

현상파악 결과를 바탕으로 아래 3가지 질문에 반드시 답한다. 이 단계를 건너뛰면 "브리핑"에 그친다.

**Q1. 이 한도/임계값은 왜 존재하는가?**
- 어떤 자원(메모리/CPU/연결수/처리량)을 보호하기 위한 설계인가?
- 한도를 초과할 경우 시스템에 어떤 연쇄 영향이 생기는가?

**Q2. 실패는 어떤 순서로 발생했는가? (failure chain)**
- 정상 상태 → 이상 발생 → 한도 초과 → 시스템 차단/에러 → 알럿 순서로 재구성

**Q3. 이번 실패를 유발한 직접 트리거는 무엇인가?**
- 특정 쿼리 / 배포 / 설정 변경 / 트래픽 증가 / 메트릭 누적 중 어느 것인가?
- 언제부터 시작되었는가?

#### 카테고리 G — 옵저버빌리티 심층 쿼리

```
flags           → maxUniqueTimeseries, retention, 메모리 한도 등 설정 확인
tsdb_status     → 전체 series 수, top cardinality metrics, top label values
top_queries     → 가장 많은 series를 조회한 쿼리 특정 (트리거 후보)
active_queries  → 현재 실행 중인 쿼리 (hang/폭주 쿼리 확인)
metric_statistics → 특정 메트릭의 series 수 및 쿼리 횟수 (사용 여부 판단)
```

### Step 6 — [Phase 2] RCA (kubectl)

**kubectl context 결정**:

| 알럿 클러스터 | --context |
|---------------|-----------|
| infra-k8s-prod | k8s-prod |
| infra-k8s-stg | k8s-stg |
| infra-k8s-dev | k8s-dev |
| infra-k8s-idc | k8s-idc |
| infra-k8s-global | k8s-global |

**먼저 false positive 확인**:
```
Read: /Users/changhwan/workspace/riiid/kubernetes/claude-code/memory/known-issues.md
```
정상 이상현상이면 RCA 중단 후 사용자에게 즉시 알린다.

#### 카테고리 A — Pod/Container

```bash
kubectl --context={ctx} -n {ns} describe pod {pod}
kubectl --context={ctx} -n {ns} logs {pod} --previous --tail=150
kubectl --context={ctx} -n {ns} get events \
  --field-selector involvedObject.name={pod} --sort-by=.lastTimestamp
```

OOMKilled 의심 시:
```bash
kubectl --context={ctx} -n {ns} top pod {pod} --containers
```

#### 카테고리 B — Node/인프라

```bash
kubectl --context={ctx} describe node {node}
kubectl --context={ctx} get pods -A --field-selector spec.nodeName={node} | sort -k4 -r | head -20
kubectl --context={ctx} get events -A \
  --field-selector involvedObject.name={node} --sort-by=.lastTimestamp | tail -20
```

Karpenter 관련 시:
```bash
kubectl --context={ctx} -n infra-karpenter logs \
  -l app.kubernetes.io/name=karpenter --tail=100 --since=1h
```

참조: `claude-code/02-context/karpenter-guide.md`

#### 카테고리 C — 네트워크/Istio

```bash
kubectl --context={ctx} -n {ns} logs {pod} -c istio-proxy --tail=100
kubectl --context={ctx} -n {ns} get virtualservice,destinationrule -o yaml
kubectl --context={ctx} -n istio-system get pods
kubectl --context={ctx} -n {ns} exec {pod} -c istio-proxy \
  -- pilot-agent request GET /stats \
  | grep -E "upstream_rq_5xx|upstream_cx_connect_fail|upstream_cx_overflow"
```

참조: `claude-code/02-context/istio-service-mesh.md`, `claude-code/03-guardrails/istio-troubleshooting.md`

#### 카테고리 D — 스케일링

```bash
kubectl --context={ctx} -n {ns} describe hpa
kubectl --context={ctx} -n {ns} get pods | grep -E "Pending|ContainerCreating"
kubectl --context={ctx} -n {ns} describe pod {pending-pod}
kubectl --context={ctx} get nodes -o wide
```

KEDA 관련 시:
```bash
kubectl --context={ctx} -n {ns} get scaledobject -o yaml
kubectl --context={ctx} -n {ns} describe scaledobject {name}
```

참조: `claude-code/02-context/karpenter-guide.md`

#### 카테고리 E — 스토리지

```bash
kubectl --context={ctx} -n {ns} describe pvc {pvc}
kubectl --context={ctx} -n {ns} get events \
  --field-selector involvedObject.kind=PersistentVolumeClaim --sort-by=.lastTimestamp
```

IDC Ceph인 경우:
```bash
kubectl --context=k8s-idc -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph status
kubectl --context=k8s-idc -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph df
kubectl --context=k8s-idc -n rook-ceph exec -it deploy/rook-ceph-tools -- ceph health detail
```

참조: `claude-code/03-guardrails/incident-playbooks.md`

#### 카테고리 F — DB/CNPG

```bash
kubectl --context={ctx} -n {ns} get cluster -o yaml
kubectl --context={ctx} -n {ns} describe cluster {cluster-name}
kubectl --context={ctx} -n {ns} get pods -l cnpg.io/cluster={cluster-name}
kubectl --context={ctx} -n {ns} logs {primary-pod} --tail=150
```

참조: `claude-code/02-context/database-operations.md`

### Step 6.5 — [선택] 애플리케이션 로그 심층 분석

**트리거 조건**: 아래 중 하나라도 해당되면 자동 실행한다.
- 카테고리 A (Pod/Container): 높은 재시작, CrashLoop, OOMKilled 외 **응답 지연/에러율** 유형
- 카테고리 B (Node): 노드 CPU/메모리 포화 → 어떤 파드/요청이 원인인지 파악 필요 시
- 카테고리 C (Network/Istio): High 5xx 에러율, 높은 레이턴시 → 어떤 엔드포인트/유저 유형

**스킵 조건**: CrashLoop (컨테이너 즉시 종료라 HTTP 로그 없음), 카테고리 E/F/G

**실행 방법**:

```bash
# 1. 파드 이름 결정 (kubectl top 또는 describe 결과에서 가져옴)
# 2. 로그 수집 + 분석 스크립트 파이프
kubectl --context={ctx} logs {pod} -n {ns} -c {main-container} --since=2h 2>&1 \
  | python3 .claude/skills/devops:log-analysis/scripts/analyze-logs.py
```

**컨테이너 이름 결정 규칙**:
- 앱 컨테이너 이름 = pod 이름에서 ReplicaSet suffix 제거 후 첫 번째 컨테이너
- istio-proxy, statsd, alloy는 제외
- 모르면 `kubectl --context={ctx} get pod {pod} -n {ns} -o jsonpath='{.spec.containers[*].name}'`로 확인

**결과 해석 포인트**:
- **Module A (트래픽 추이)**: SPIKE 구간과 알럿 firing 시각이 일치하는가?
- **Module B (엔드포인트 랭킹)**: max_ms > 3000ms 엔드포인트가 스파이크 직접 원인인가?
- **Module C (슬로우 요청)**: 특정 user_id 반복 등장 시 → Istio session affinity 트래픽 편향 의심
- **Module D (에러 패턴)**: 429는 부하 폭증, 5xx는 앱 오류, 401 급증은 세션 만료
- **Module E (외부 API)**: OpenAI/LLM 동기 호출 폭증 → worker 점유로 CPU 포화 유발 가능

### Step 7 — 결과 출력

대화창에 아래 형식으로 출력한다.

---

## 결과 출력 형식

**작성 원칙:**
- **Summary 설명**과 **근본 원인**은 반드시 `한도/조건 → 현재 상태 → 알럿 발생` 구조로 연결하여 서술한다. 현상을 단순 나열하지 않는다.
  - ✅ "{컴포넌트}는 {한도}까지만 {기능}할 수 있는데, 현재 {비정상 상태}이기 때문에 {결과}가 발생한다."
  - ❌ "{컴포넌트}에서 {수치}를 초과하여 에러가 발생했다." (현상 나열)

```
## 🔍 현상 파악

- **알럿**: {rule_name} | {severity}
- **클러스터**: {cluster} / Namespace: `{namespace}`
- **발생**: {YYYY-MM-DD HH:MM KST} | 지속: N분 (resolved: Y/N)
- **카테고리**: {A~F} — {카테고리명}

### Summary
1. **설명**: {rule_name} 알럿은 {시스템/컴포넌트}가 {정상 동작 조건/한도}인데, 현재 {비정상 상태}이기 때문에 {결과적으로 발생하는 현상}이 생겨 발생하는 알럿이다.

### 메트릭 분석
- **PromQL**: `{query}`
- **임계값**: {threshold}
- **발생 시 값**: {peak_value}
- **추이**: {급등 / 점진 증가 / 반복 / 지속}

---

## 🔎 RCA (Root Cause Analysis)

### 타임라인
- `{HH:MM KST}` — 메트릭 이상 감지 ({value})
- `{HH:MM KST}` — 알럿 firing
- `{HH:MM KST}` — {관련 K8s 이벤트}

### 근본 원인
> {시스템/컴포넌트}는 {정상 동작 조건/한도}까지만 {기능}할 수 있는데, 현재 {비정상 상태}이기 때문에 {결과적으로 발생하는 현상}이 발생한다.

### 메커니즘
```
{선행 조건 / 설계 제한 — 왜 이 한도가 존재하는가}
    ↓
{이상 상태 발생 — 무엇이 축적/증가/변화했는가}
    ↓
{시스템 보호 동작 / 실패 지점 — 어디서 차단/에러가 발생했는가}
    ↓
알럿 발생
```
- **설계 의도**: {이 한도/제한이 존재하는 이유 — 메모리/CPU/연결수 등 어떤 자원 보호}
- **트리거**: {이번 실패를 유발한 직접 원인 — 특정 쿼리 / 배포 / 메트릭 누적 / 트래픽 중 무엇}

### 근거
- {kubectl/메트릭/flags 출력에서 확인된 핵심 증거 1}
- {kubectl/메트릭/flags 출력에서 확인된 핵심 증거 2}

### 한 줄 요약
> {비전문가도 이해할 수 있는 plain-language 설명. 시스템의 행동을 의인화하거나 물리적 비유로 표현한다.}

---

## 💡 해결책 제안

### Option A: {이름} ⭐ 추천
- **요약**: ...
- **장점**: ...
- **단점**: ...
- **ROI**: 효과 {High/Med/Low} / 비용 {High/Med/Low}
- **구현 난이도**: {Easy/Medium/Hard}
- **구현 방법**: `{파일경로}` — {변경 내용 요약}

### Option B: {이름}
- **요약**: ...
- **장점**: ...
- **단점**: ...
- **ROI**: 효과 {High/Med/Low} / 비용 {High/Med/Low}
- **구현 난이도**: {Easy/Medium/Hard}

### Option C: {이름}
- **요약**: ...
- **장점**: ...
- **단점**: ...
- **ROI**: 효과 {High/Med/Low} / 비용 {High/Med/Low}
- **구현 난이도**: {Easy/Medium/Hard}

**최선안**: Option {X} — {팀 원칙(생산성 > 비용 > 안정성) 기준 선택 이유}
```

---

## 주의사항

- **IDC PromQL**: `mcp__victoriametrics-idc__*` MCP 없음 → WebFetch로 `victoriametrics-vmauth-idc.global.riiid.exposed` 직접 호출
- **Grafana UID 추출 실패 시**: 사용자에게 Grafana 알럿 규칙 URL 또는 PromQL을 직접 요청
- **kubectl edit/delete 금지**: GitOps 규칙 — 조회 명령만 사용
- **카테고리 불명확 시**: 가장 근접한 카테고리로 시작하고 진행 중 사용자에게 알림
- **MCP 토큰**: wrapper 스크립트 자동 주입 — 별도 인증 불필요
