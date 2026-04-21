---
name: devops:alert-rca
description: |
  Slack 알럿 URL을 입력받아 단일 알럿 심층 RCA를 수행하는 스킬.
  현상파악(Grafana + VictoriaMetrics MCP) → RCA(kubectl) → 5 Whys 2단계 구조.
  카테고리 7개(Pod/Node/Network/Scaling/Storage/DB/Observability) 분기 플로우.
  known-issues.md 체크로 false positive 방지 후 해결책 3가지 ROI 분석 및 후속 조치 제안.
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
  - mcp__victoriametrics-prod__flags
  - mcp__victoriametrics-prod__tsdb_status
  - mcp__victoriametrics-prod__top_queries
  - mcp__victoriametrics-prod__active_queries
  - mcp__victoriametrics-prod__metric_statistics
  - WebFetch
  - Read
  - Edit
  - Write
  - Bash(kubectl *)
  - Bash(python3 *)
---

# devops:alert-rca Skill

Slack 알럿 URL 하나를 입력받아, 카테고리별 분기 플로우로 현상파악(MCP) + RCA(kubectl) + 5 Whys를 수행하고, 해결책 3가지를 ROI 분석과 함께 제안한다.

---

## 핵심 원칙

- **2단계 분리**: 현상파악은 MCP(시계열 메트릭), RCA는 kubectl(K8s 리소스 상태). 둘을 섞지 않는다.
- **카테고리 우선 판별**: 알럿 rule name + labels에서 카테고리(A~G)를 먼저 결정하고, 해당 플로우만 실행한다.
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
    ?query={URL-encoded PromQL}&start={firing_unix-3600}&end={firing_unix+1800}&step=60
  ```
  - PromQL 특수문자(`{`, `}`, `|`, `=~`)는 반드시 URL 인코딩 후 사용
  - 401/403 응답 시: IDC 메트릭 접근 불가임을 사용자에게 알리고 kubectl 단계로 진행
  - 5xx/타임아웃 시: IDC VM 응답 없음을 알리고 kubectl 단계로 진행

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

카테고리별 kubectl 조회 명령은 `references/kubectl-playbook.md`를 Read한 후 실행한다.

### Step 6.5 — [선택] 애플리케이션 로그 심층 분석

**트리거 조건**: 아래 중 하나라도 해당되면 자동 실행한다.
- 카테고리 A (Pod/Container): 높은 재시작, CrashLoop, OOMKilled 외 **응답 지연/에러율** 유형
- 카테고리 B (Node): 노드 CPU/메모리 포화 → 어떤 파드/요청이 원인인지 파악 필요 시
- 카테고리 C (Network/Istio): High 5xx 에러율, 높은 레이턴시 → 어떤 엔드포인트/유저 유형

**스킵 조건**: CrashLoop (컨테이너 즉시 종료라 HTTP 로그 없음), 카테고리 E/F/G

**실행 방법**:

```bash
kubectl --context={ctx} logs {pod} -n {ns} -c {main-container} --since=2h 2>&1 \
  | python3 /Users/changhwan/.claude/skills/devops:log-analysis/scripts/analyze-logs.py
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

### Step 6.7 — 5 Whys RCA 구조화

증거 수집이 완료된 후, 수집한 근거를 기반으로 5 Whys 기법으로 근본 원인을 추적한다.

**규칙**:
- 각 "Why"는 반드시 수집된 증거(메트릭 값, kubectl 출력, 이벤트 등)에 근거해야 한다.
- "왜?"의 답변이 "알 수 없음"이면 추가 조사가 필요한 항목으로 표시하고 Step 8에서 처리한다.
- 5번 반복이 목표이지만, 근본 원인이 3번째에서 특정되면 거기서 멈춰도 된다.
- 마지막 "Why"의 답변이 **시스템적 원인**(설정 누락, 용량 미계획, 프로세스 결함 등)이어야 한다.

5 Whys 체인 형식 → `references/output-template.md` 참조.

### Step 7 — 결과 출력

`references/output-template.md`를 Read한 후 해당 형식에 맞춰 대화창에 출력한다.

### Step 8 — 후속 조치 제안

결과 출력 후 아래 3가지를 사용자에게 제안한다.

1. **추천안 적용 경로**: Option A가 GitOps 변경이면 "values.yaml 수정 PR" 경로 안내, 즉각 조치이면 실행 단계 안내
2. **재발 방지 아카이브** (해당 케이스에 따라 선택):
   - 정상 이상현상으로 판정 → `known-issues.md` 업데이트 제안
   - 새 실패 패턴 발견 → `task-patterns.md` 또는 `failure-lessons.md` 업데이트 제안
3. **추가 조사 분기**: Step 6.7에서 "알 수 없음" Why가 있으면 "추가 정보 수집 후 Step 2부터 재시작" 제안

### Step 8B — Incident 노트 저장

**"incident 노트로 저장할까요? [Y/n]"** 를 묻고, Y이면 아래를 실행한다.

#### 노트 본문 구성 (Step 7 출력 기반)

```markdown
## Summary

- 알럿: {rule_name} ({severity})
- 클러스터 / 네임스페이스: {cluster} / {namespace}
- 서비스: {service}
- 발생 시각: {firing_time KST}
- 해결책: {추천 옵션 한 줄}

## 현상

{Step 5 현상파악 요약 — 메트릭 수치 포함}

## Root Cause

{Step 6.7 5 Whys 체인 요약}

## 해결책

{Step 7 추천 옵션 A/B/C 상세}

## 재발 방지

{재발 방지 조치 및 추가 모니터링 포인트}
```

#### 저장 실행

```bash
# 1. 본문 임시 저장
python3 -c "
content = '''...노트 본문...'''
open('/tmp/rca_incident.md', 'w').write(content)
"

# 2. 노트 생성 (04. Wiki/incidents/ 에 저장됨)
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py create \
  --title "{rule_name} — {service} {현상 한줄 요약}" \
  --tags "domain/{주요 도메인}" \
  --aliases "{service},{rule_name},{cluster}" \
  --type "incident" \
  --content-file /tmp/rca_incident.md
```

#### _index.md 및 _log.md 업데이트

```
VAULT="/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"
INDEX="$VAULT/04. Wiki/_index.md"
LOG="$VAULT/04. Wiki/_log.md"
```

**_index.md**: `## Incidents` 섹션에 항목 추가:
```
- [[{slug}|{title}]] — {severity} / {service} / {firing_date}
```

**_log.md**: 맨 아래에 append:
```
## [{YYYY-MM-DD}] incident | {제목}
- 출처: devops:alert-rca
- 저장: [[{slug}]]
```

---

## 주의사항

- **IDC PromQL**: `mcp__victoriametrics-idc__*` MCP 없음 → WebFetch로 `victoriametrics-vmauth-idc.global.riiid.exposed` 직접 호출 (URL 인코딩 필수, 4xx/5xx 시 kubectl 단계로 fallback)
- **Grafana UID 추출 실패 시**: 사용자에게 Grafana 알럿 규칙 URL 또는 PromQL을 직접 요청
- **kubectl edit/delete 금지**: GitOps 규칙 — 조회 명령만 사용
- **카테고리 불명확 시**: 가장 근접한 카테고리로 시작하고 진행 중 사용자에게 알림
- **MCP 토큰**: wrapper 스크립트 자동 주입 — 별도 인증 불필요
