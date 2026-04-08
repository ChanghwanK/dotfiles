---
name: aws:network-question
description: |
  AWS 네트워크 질문(연결 문제, 비용 분석, DNS, VPN, SG 등)을
  구조화된 워크플로우로 진단하는 스킬.
  사용 시점: (1) 데이터 전송 비용 최적화, (2) 연결 트러블슈팅,
  (3) SG/NACL 이슈, (4) VPN 문제, (5) Cross-region/account 네트워킹, (6) DNS 문제.
  트리거 키워드: "네트워크 질문", "network question", "연결 안됨",
  "데이터 전송 비용", "VPC peering", "VPN 문제", "/aws:network-question".
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Bash(aws *)
  - Bash(dig *)
  - Bash(nslookup *)
  - Bash(host *)
  - mcp__plugin_devops_awslabs_aws-api-mcp-server__call_aws
  - mcp__plugin_devops_awslabs_aws-api-mcp-server__suggest_aws_commands
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__list_vpcs
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__get_vpc_network
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__list_transit_gateways
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__get_tgw
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__get_tgw_routes
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__find_ip_address
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__get_eni_details
  - mcp__plugin_devops_awslabs_aws-network-mcp-server__get_vpc_flow_logs
---
# aws:network-question Skill

AWS 네트워크 질문을 구조화된 워크플로우로 진단하여 빠르고 정확한 답변을 도출한다.

---

## 핵심 원칙

- **Context First**: 제네릭 답변 금지. 반드시 실제 AWS 리소스를 먼저 확인한다.
- **Existing First**: 신규 리소스 제안 전 기존 VPC Peering, TGW, Route Table을 선조회한다.
- **AWS CLI First, MCP Second**: `aws ec2/rds/route53` CLI 우선. MCP는 CLI가 불편하거나 실패할 때만 사용.
- **Active Questioning**: 부족한 정보를 질문할 때 **확인 방법**(콘솔 경로, CLI 명령)도 함께 안내한다.
- **Verify Pricing**: 리전 쌍별 실제 요금을 반드시 확인. 추정치로 답변하지 않는다.

---

## 카테고리 분류

사용자 입력에서 카테고리를 판별한다:

| 키워드 | 카테고리 | 실행할 Agent |
|--------|---------|-------------|
| 비용, cost, 데이터 전송, data transfer, 요금, 청구 | `cost` | network-investigator + cost-analyzer |
| 연결, 접속, reach, connect, timeout, 안됨, 실패 | `connectivity` | network-investigator |
| SG, security group, 보안 그룹, NACL, 인바운드, 아웃바운드 | `security` | network-investigator |
| VPN, 오피스, IDC, 터널, site-to-site | `vpn` | network-investigator |
| DNS, resolve, nslookup, dig, 도메인 | `dns` | network-investigator |
| cross-region, cross-account, peering, 다른 계정, 다른 리전 | `cross-network` | network-investigator + cost-analyzer |

---

## 워크플로우

### Step 1 — 컨텍스트 수집

사용자 입력에서 아래 정보를 추출한다. 부족한 항목은 `AskUserQuestion`으로 질문하되,
**해당 정보를 확인하는 방법도 함께 안내**한다.

#### 수집 대상

```
[Source]
- 위치: EKS Pod / EC2 / RDS / IDC / Office / 외부
- 리전: ap-northeast-1 / ap-northeast-2 / 기타
- 구체 리소스: 인스턴스 ID / DNS / IP

[Destination]
- 위치: 같은 VPC / 다른 VPC / 다른 계정 / 외부 / S3
- 리전: 동일 / 다른 리전
- 구체 리소스: 인스턴스 ID / DNS / IP

[증상]
- 유형: 연결 불가 / 비용 이상 / 설정 확인
- 상세: 에러 메시지, 비용 금액, 연결 문자열
```

#### 질문 시 확인 방법 안내 예시

```
다음 정보가 필요합니다:

1. **RDS 엔드포인트** — AWS 콘솔 > RDS > Databases > 해당 DB > Connectivity & security 탭,
   또는: `aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,Endpoint.Address]' --region <region>`

2. **EC2 인스턴스 ID 및 서브넷** — AWS 콘솔 > EC2 > Instances > 해당 인스턴스 > Networking 탭,
   또는: `aws ec2 describe-instances --filters "Name=tag:Name,Values=<name>" --query 'Reservations[*].Instances[*].[InstanceId,SubnetId,PrivateIpAddress]'`

3. **월간 데이터 전송량** — AWS 콘솔 > Billing > Cost Explorer > Group by: Usage Type > 필터: DataTransfer
```

### Step 2 — 빠른 가설 (토폴로지 기반)

Agent 실행 전, Orchestrator(Claude)가 직접 수행한다.

1. `Read /Users/changhwan/.claude/skills/aws:network-question/references/aws-network-architecture.md` 로 토폴로지 로드
2. Source/Dest의 IP/CIDR로 소속 판별:

| CIDR | 소속 |
|------|------|
| 10.0.x.x | Tokyo VPC (우리 계정) |
| 10.1.x.x | Legacy Peering: qms-qualson-dev |
| 10.2.x.x | Legacy Peering: qualson-realclass-public |
| 10.3.x.x | Legacy Peering: qms-qualson-prod |
| 10.4.x.x | Legacy Peering: qualson-dms |
| 10.10.x.x | Tokyo Secondary VPC |
| 10.100.x.x | Seoul VPC (우리 계정) |
| 172.16.x.x | Office 네트워크 |
| 172.0.x.x | Client VPN |

3. Source → Destination 예상 경로를 문서 기반으로 추론
4. 가설을 사용자에게 공유:

```
## 빠른 가설 (토폴로지 기반)

**예상 경로:** Source ({source_desc}) → {hop1} → {hop2} → Destination ({dest_desc})
**예상 비용 구성요소:** (cost 카테고리인 경우)
**가설:** {초기 가설 1줄}

이 가설을 검증하기 위해 실제 AWS 리소스를 조사하겠습니다.
```

### Step 3 — Agent 병렬 조사

카테고리에 따라 Agent를 선택적으로 실행한다.

| 카테고리 | Agent 1 | Agent 2 |
|---------|---------|---------|
| `cost` | network-investigator | cost-analyzer |
| `connectivity` | network-investigator | — |
| `security` | network-investigator (SG 집중) | — |
| `vpn` | network-investigator (VPN 집중) | — |
| `dns` | network-investigator (DNS 집중) | — |
| `cross-network` | network-investigator | cost-analyzer |

#### Agent 호출 패턴

Agent 프롬프트를 Read로 로드한 뒤 placeholder를 치환하여 실행한다.

**Agent A — Network Investigator**
Read `/Users/changhwan/.claude/skills/aws:network-question/agents/agent-network-investigator.md`
치환: `{source_info}`, `{dest_info}`, `{category}`, `{hypothesis}`, `{source_region}`, `{dest_region}`
모델: sonnet

**Agent B — Cost Analyzer** (cost / cross-network 카테고리만)
Read `/Users/changhwan/.claude/skills/aws:network-question/agents/agent-cost-analyzer.md`
치환: `{source_info}`, `{dest_info}`, `{source_region}`, `{dest_region}`, `{confirmed_path}`, `{estimated_monthly_gb}`
모델: sonnet

2개 Agent를 사용하는 경우 반드시 **병렬 실행** (단일 메시지에서 2개 Agent tool call).

#### Agent 결과 파싱

각 Agent는 `INVESTIGATION_RESULT_START` ~ `INVESTIGATION_RESULT_END` 블록으로 결과를 반환한다.

### Step 4 — 결과 종합

Agent 결과를 아래 형식으로 종합하여 출력한다:

```
## AWS 네트워크 진단 결과

### 1. 질문 요약
- 카테고리: {category}
- Source: {source} → Destination: {dest}
- 확인된 경로: {actual_path}

### 2. Findings
| 상태 | 내용 |
|------|------|
| ✅ CONFIRMED | {확인된 사실} |
| ❌ ISSUE | {발견된 문제} |
| ℹ️ INFO | {참고 정보} |

### 3. 비용 분석 (cost 카테고리)
| 항목 | 단가 | 추정 월 트래픽 | 월 비용 |
|------|------|-------------|---------|
| {항목} | ${단가}/GB | {GB} | ${금액} |
| **합계** | | | **${금액}** |

### 4. 권고 사항 (우선순위순)

#### [P1] {즉시 조치}
- **구체적 액션**: {AWS CLI 명령 또는 Terraform 파일 경로}
- **예상 효과**: {정량적 효과}

#### [P2] {단기 개선}
- **구체적 액션**: ...
```

### Step 5 — 검증 방법 제시

권고 사항 적용 후 확인할 수 있는 CLI 명령을 반드시 포함한다:

```
### 5. 검증 방법
- Route Table 확인: `aws ec2 describe-route-tables --filters "Name=vpc-id,Values={vpc_id}" --query ...`
- DNS 확인: `dig +short {hostname}`
- 연결 테스트: `aws ec2 describe-network-insights-analyses ...`
```

---

## 주의사항

- 리전 쌍별 데이터 전송 요금은 **AWS Pricing API로 런타임 조회** — 하드코딩 금지 (cost-analyzer agent의 Step 0 참조)
- Terraform 변경이 필요한 경우 파일 경로 안내: `terraform/src/infra/network/global/`
- `kubectl edit/delete` 금지 — GitOps 워크플로우 보호
- 다른 계정(Qualson 등)의 리소스는 직접 확인 불가 — 확인 요청용 CLI 명령만 제공
