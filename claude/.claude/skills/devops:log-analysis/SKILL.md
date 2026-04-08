---
name: devops:log-analysis
description: |
  파드/네임스페이스의 로그를 수집하여 다차원 분석을 수행하는 범용 RCA 스킬.
  JSON 구조화 로그를 자동 파싱하여 트래픽 추이, 엔드포인트 랭킹,
  슬로우 요청, 에러 패턴, 외부 API 호출, 유저 편향을 분석한다.
  사용 시점: (1) CPU/메모리 스파이크 원인 파악, (2) 500 에러 급증 시 호출 패턴 분석,
  (3) 특정 파드의 트래픽 편향 분석, (4) alert-rca 후속 심층 로그 분석.
  트리거 키워드: "로그 분석", "log analysis", "어떤 호출이", "트래픽 패턴",
  "슬로우 요청", "에러 패턴 분석", "어떤 요청이 무거워", "/devops:log-analysis".
model: sonnet
allowed-tools:
  - Bash(kubectl *)
  - Bash(python3 *)
  - Bash(cat *)
  - Read
---

# devops:log-analysis

파드 로그를 수집하고 6가지 분석 모듈로 RCA 인사이트를 생성하는 범용 스킬.

---

## 핵심 원칙

- **포맷 자동 감지**: JSON 구조화 로그(gunicorn access, FastAPI 등)와 plain text 모두 처리
- **stdlib only**: 외부 패키지 없이 Python 표준 라이브러리만 사용
- **스파이크 자동 감지**: 분당 평균 대비 2배 이상 = SPIKE 자동 마킹
- **path 정규화**: `/api/lesson/1234` → `/api/lesson/{id}` 자동 그룹핑
- **컨텍스트 계승**: `devops:alert-rca` 직후 사용 시 cluster/namespace/pod를 그대로 이어받음

---

## 워크플로우

### Step 1 — 입력 파라미터 확인

아래 정보를 사용자 입력 또는 현재 대화 컨텍스트에서 파악한다. 필수값이 없으면 즉시 질문한다.

| 파라미터 | 필수 | 기본값 | 예시 |
|----------|------|--------|------|
| cluster | 필수 | - | `infra-k8s-prod` |
| namespace | 필수 | - | `k6-domain` |
| pod | 필수 | - | `k6-domain-86748cf95d-jtf88` |
| container | 선택 | 첫 app 컨테이너 | `k6-domain` |
| 시간 범위 | 선택 | `--since=1h` | `--since=2h`, `--tail=1000` |
| 분석 관심사 | 선택 | 전체 | `CPU spike`, `500 에러`, `특정 엔드포인트` |

**cluster → kubectl context 매핑:**
```
infra-k8s-prod   → k8s-prod
infra-k8s-stg    → k8s-stg
infra-k8s-dev    → k8s-dev
infra-k8s-idc    → k8s-idc
infra-k8s-global → k8s-global
```

### Step 2 — 로그 수집

```bash
kubectl --context={ctx} logs {pod} -n {namespace} -c {container} {time_range} 2>&1 \
  | python3 ~/.claude/skills/devops:log-analysis/scripts/analyze-logs.py
```

로그가 너무 크면 (10,000줄+) 분석 구간을 좁혀 재시도:
```bash
# 스파이크 구간에 집중할 경우 --since로 범위 좁히기
kubectl ... --since=30m | python3 ...
```

### Step 3 — 분석 실행 및 결과 해석

스크립트가 6개 모듈 결과를 Markdown으로 출력한다. 각 모듈 결과를 해석하여 아래 인사이트를 도출한다:

**Module A (트래픽 추이)**: SPIKE 마킹 구간 확인 → 언제 시작됐는가?

**Module B (엔드포인트 랭킹)**: avg/max 응답시간이 높은 엔드포인트 → CPU 집약적 작업은?

**Module C (슬로우 요청)**: 특정 엔드포인트 반복 등장? 특정 user_id 집중?

**Module D (에러 패턴)**: 429(rate limit)는 부하 폭증 신호. 401 급증은 세션 만료/토큰 갱신 실패. 5xx는 앱 오류.

**Module E (외부 API)**: OpenAI/LLM 호출이 많으면 → 동기 LLM 호출이 worker를 점유하는 패턴 의심.

**Module F (유저 편향)**: 특정 유저가 특정 파드로 집중되면 → Istio session affinity 또는 consistent hash 라우팅 의심.

### Step 4 — 결과 출력

스크립트 출력을 그대로 사용자에게 제시하고, 마지막에 **종합 인사이트**를 3줄로 요약한다:

```
### 종합 인사이트
1. **스파이크 원인**: {언제, 어떤 엔드포인트, 무슨 이유}
2. **가장 무거운 작업**: {엔드포인트명, 평균 응답시간, 외부 의존성}
3. **권장 조치**: {단기 / 중기 해결책}
```

---

## 출력 형식

```
## 로그 분석 결과

**파드**: {namespace}/{pod} ({container})
**분석 기간**: {start_utc} ~ {end_utc} UTC ({start_kst} ~ {end_kst} KST)
**총 로그**: {N}줄 / HTTP 요청: {M}건 / 로그 포맷: JSON|plaintext

---

### A. 트래픽 추이 (분당)
| UTC   | 요청수 | avg_ms | p95_ms | max_ms | 에러율 | 외부API | 비고 |
...

### B. 엔드포인트 랭킹 TOP 20
| 순위 | 호출수 | avg_ms | max_ms | 에러수 | 엔드포인트 |
...

### C. 슬로우 요청 TOP 20 (>1초)
| 시각(UTC) | 응답시간 | 상태 | user_id | 경로 |
...

### D. 에러 패턴
#### HTTP 상태코드별
| 코드 | 건수 | 주요 엔드포인트 |
...

### E. 외부 API 호출
| 서비스 | 호출수 | 분당 최대 | 에러수 |
...

### F. 유저 편향 분석
| user_id | 요청수 | 주요 엔드포인트 | 재시도 패턴 |
...

---

### 종합 인사이트
1. **스파이크 원인**: ...
2. **가장 무거운 작업**: ...
3. **권장 조치**: ...
```

---

## 주의사항

- **plain text 로그** (istio-proxy 등): Module B/C/F는 스킵, Module A/D/E만 동작
- **kubectl edit/delete 금지**: 조회 명령만 사용 (GitOps 규칙)
- **대화 컨텍스트 계승**: `devops:alert-rca` 직후 호출 시 "이 파드 로그 분석해줘"만으로도 파라미터 자동 파악
- **previous logs**: 파드 재시작 후 크래시 원인 확인 시 `--previous` 플래그 추가
