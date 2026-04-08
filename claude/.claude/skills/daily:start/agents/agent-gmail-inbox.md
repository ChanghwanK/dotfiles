---
allowed-tools:
  - mcp__claude_ai_Gmail__gmail_search_messages
  - mcp__claude_ai_Gmail__gmail_read_message
---

# Agent C: Gmail Inbox 분석

오늘 날짜: {today_date}

## 수집 절차

Gmail MCP 도구를 사용하여 미읽음 메일을 수집하고 분석한다.

### 1단계: 2가지 쿼리로 메일 수집

**Query 1 — Primary 미읽음** (최대 20개):
```
in:inbox is:unread -category:promotions -category:social -category:updates -category:forums
```

**Query 2 — 인프라 알림** (최대 10개):
```
in:inbox is:unread category:updates (from:notifications@github.com OR from:noreply@github.com OR from:hub@artifacthub.io OR from:googleaistudio-noreply@google.com)
```

### 2단계: 중복 제거 및 상세 읽기

- 두 결과를 messageId 기준으로 중복 제거 후 병합
- 전체 15개 초과 시 최신 15개만 선택
- 선택된 각 메일에 대해 `gmail_read_message`로 상세 내용(제목, 본문 첫 300자, 발신자) 읽기

### 3단계: 분류

각 메일을 아래 기준으로 분류한다:

**`infra_actionable`** — 다음 중 하나라도 해당:
- Release / New Version / v[0-9] 포함
- CVE / 보안 취약점 / Security Advisory
- Deprecation / Breaking Change / Action Required / Migration
- 인프라 컴포넌트 언급: Karpenter, Istio, ArgoCD, cert-manager, external-secrets, KEDA, VictoriaMetrics, Loki, Alloy, Grafana, Harbor, CNPG, Rook Ceph, Cluster API, Proxmox, GPU Operator

**`general`** — 그 외 전부

### 4단계: 인프라 적용 가이드 생성

`infra_actionable` 분류 메일에 대해 우리 스택 기준 구체적 액션을 제시한다:
- GitOps 리포 업데이트 경로: `~/workspace/riiid/kubernetes/`
- Helm chart 버전 확인: `~/workspace/riiid/kubernetes-charts/`
- 환경 우선순위: prod → stg → dev 순서로 단계적 적용 권장

## 반환 형식

아래 구분자 사이에 YAML 블록을 반환한다. 코드나 JSON 전체는 반환하지 말 것.

```
GMAIL_RESULT_START
email_summary:
  total_unread: <Query 1 + Query 2 중복 제거 후 총 미읽음 수>
  emails:
    - id: "<messageId>"
      from: "<발신자 이메일>"
      subject: "<제목>"
      date: "<수신일, YYYY-MM-DD>"
      category: "infra_actionable | general"
      summary: "<본문 핵심 1-2문장 요약>"
      infra_guide: "<infra_actionable이면 구체적 액션, general이면 null>"

infra_actions:
  - component: "<컴포넌트명>"
    new_version: "<버전>"
    action: "<GitOps 리포 경로 포함 구체적 액션>"
    priority: "high | medium | low"
    source: "<messageId>"

suggested_tasks:
  - name: "<Task명>"
    priority: "P1 | P2 | P3"
    description: "<설명>"
    source: "<messageId>"
GMAIL_RESULT_END
```

## 오류 처리

- Gmail API 호출 실패 시:
  ```
  GMAIL_RESULT_START
  email_summary: null
  infra_actions: []
  suggested_tasks: []
  GMAIL_RESULT_END
  ```
- 미읽음 메일이 0개이면:
  ```
  GMAIL_RESULT_START
  email_summary:
    total_unread: 0
    emails: []
  infra_actions: []
  suggested_tasks: []
  GMAIL_RESULT_END
  ```

## 주의사항

- raw JSON이나 전체 메일 본문을 반환하지 않는다.
- 광고/소셜 카테고리는 Query 1 검색 조건으로 이미 제외되므로 추가 필터링 불필요.
- 분석 결과는 콘솔 출력과 Obsidian Daily Note에 반영된다. Task는 자동 추가하지 않고 권장만 한다.
