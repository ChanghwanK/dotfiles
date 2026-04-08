---
name: aws:instance-guide
description: |
  AWS 인스턴스 타입 분석, 비교, 추천 및 Q&A 스킬.
  현재 사용 중인 인스턴스 utilization 분석과 right-sizing 제안,
  신규 인스턴스 선택 가이드, 최신 인스턴스 패밀리 정보를 제공한다.
  사용 시점: (1) EC2/RDS/ElastiCache 인스턴스 타입 비교,
  (2) 비용 최적화를 위한 right-sizing, (3) 신규 서비스 인스턴스 선정,
  (4) Graviton/Intel/AMD 비교, (5) 현재 인프라 인스턴스 사용 현황 분석.
  트리거 키워드: 인스턴스 타입, instance type, right-sizing, 인스턴스 비교,
  RDS 인스턴스, ElastiCache 노드, Graviton, 인스턴스 추천, /aws:instance-guide.
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - WebFetch
  - WebSearch
  - Bash(aws *)
  - mcp__plugin_devops_awslabs_aws-api-mcp-server__call_aws
  - mcp__plugin_devops_awslabs_aws-api-mcp-server__suggest_aws_commands
---
# aws:instance-guide Skill

AWS 인스턴스 타입 질문을 3개 병렬 Agent(spec-explorer, usage-analyzer, knowledge-advisor)로
분석하여 데이터 기반 추천과 right-sizing 제안을 도출한다.

---

## 핵심 원칙

- **Data-Driven**: 추정치 금지 — AWS API/Pricing API로 실제 스펙/가격을 런타임 조회
- **Context First**: 현재 사용 중인 리소스를 먼저 확인한 뒤 권장사항 제시
- **Trade-off Explicit**: 생산성 > 비용 > 안정성 가중치 명시적 반영 (CLAUDE.md 준수)
- **Parallel Investigation**: 3 Agent 병렬 실행으로 빠른 결과 도출

---

## 카테고리 분류

사용자 입력에서 카테고리를 판별한다:

| 키워드 | 카테고리 | 실행 Agent |
|--------|---------|-----------|
| EC2, 컴퓨팅, EKS, Karpenter, 노드 | `ec2` | spec-explorer + usage-analyzer + knowledge-advisor |
| RDS, Aurora, PostgreSQL, MySQL, DB | `rds` | spec-explorer + usage-analyzer + knowledge-advisor |
| ElastiCache, Valkey, Redis, 캐시, MemoryDB | `cache` | spec-explorer + usage-analyzer + knowledge-advisor |
| MQ, RabbitMQ, AmazonMQ, 메시지 큐 | `mq` | spec-explorer + knowledge-advisor |
| 비교, compare, vs, 차이, 어떤 게 나아 | `compare` | spec-explorer + knowledge-advisor |
| right-sizing, 최적화, 오버스펙, 과다, 낭비 | `rightsizing` | spec-explorer + usage-analyzer + knowledge-advisor |
| Graviton, T4g, ARM, ARM64, M7g, R7g | `graviton` | spec-explorer + knowledge-advisor |

---

## 워크플로우

### Step 1 — 요청 파싱 및 정보 수집

사용자 입력에서 아래 정보를 추출한다. 부족한 항목은 `AskUserQuestion`으로 질문한다.

```
[서비스 타입]  EC2 / RDS / ElastiCache / MQ / 복합
[목적]        신규 선정 / right-sizing / 비교 / Q&A
[대상 Sphere] socraai / santa / tech / infra / 전체
[환경]        prod / stg / dev / 전체
[현재 타입]   (있으면) 현재 사용 중인 인스턴스 타입
[요구 조건]   특정 vCPU, Memory, 네트워크, 스토리지 요구 등
[리전]        ap-northeast-1 (기본값)
```

#### 정보 부족 시 질문 예시

```
다음 정보가 필요합니다:

1. **서비스 타입** — EC2/RDS/ElastiCache/MQ 중 어떤 서비스인가요?
2. **목적** — 신규 인스턴스 선정인가요, 기존 인스턴스 최적화인가요?
3. **대상 Sphere** — socraai/santa/tech 등 어떤 서비스의 인스턴스인가요?

현재 사용 중인 타입을 모르면 아래 명령으로 확인할 수 있습니다:
- RDS: `aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass]' --profile okta-devops --region ap-northeast-1`
- ElastiCache: `aws elasticache describe-cache-clusters --query 'CacheClusters[*].[CacheClusterId,CacheNodeType]' --profile okta-devops --region ap-northeast-1`
```

---

### Step 2 — Agent 병렬 디스패치

카테고리에 따라 Agent를 선택하고 **단일 메시지에서 병렬 실행**한다.

#### Agent 로드 및 placeholder 치환 패턴

```
1. Read /Users/changhwan/.claude/skills/aws:instance-guide/agents/agent-spec-explorer.md
2. Read /Users/changhwan/.claude/skills/aws:instance-guide/agents/agent-usage-analyzer.md
3. Read /Users/changhwan/.claude/skills/aws:instance-guide/agents/agent-knowledge-advisor.md

각 파일의 placeholder를 치환:
- {service_type} → 판별된 서비스 타입 (ec2/rds/cache/mq)
- {requirements} → 사용자가 명시한 요구 조건
- {compare_targets} → 비교 대상 인스턴스 타입들 (예: db.r7g.large vs db.r6g.large)
- {region} → ap-northeast-1 (또는 사용자 지정 리전)
- {target_sphere} → 대상 Sphere (socraai/santa/tech/전체)
- {purpose} → 신규선정/right-sizing/비교/Q&A
- {workload_description} → 사용자가 설명한 워크로드 특성
```

#### 카테고리별 Agent 선택

| 카테고리 | spec-explorer | usage-analyzer | knowledge-advisor |
|---------|:---:|:---:|:---:|
| `ec2`, `rds`, `cache` | ✅ | ✅ | ✅ |
| `rightsizing` | ✅ | ✅ | ✅ |
| `mq`, `compare`, `graviton` | ✅ | — | ✅ |

**2~3개 Agent를 실행하는 경우 반드시 단일 메시지에서 병렬로 Agent tool call 실행.**

---

### Step 3 — 결과 파싱

각 Agent는 `INSTANCE_GUIDE_RESULT_START` ~ `INSTANCE_GUIDE_RESULT_END` 블록으로 결과를 반환한다.

파싱 실패 시 해당 Agent 결과를 "데이터 없음"으로 처리하고 다른 Agent 결과로 종합한다.

---

### Step 4 — 결과 종합 및 추천

아래 형식으로 종합 리포트를 출력한다:

```
## AWS 인스턴스 가이드 결과

### 1. 요청 요약
- 서비스: {service_type} | 목적: {purpose} | 대상: {sphere}/{env}
- 요구 조건: {requirements}

### 2. 인스턴스 스펙 비교

| 인스턴스 타입 | vCPU | Memory | 네트워크 | 시간당 가격 | 월 비용 | 프로세서 |
|-------------|:----:|:------:|:-------:|:---------:|:------:|:-------:|
| {type}      | {n}  | {n}GB  | {n}Gbps | ${price}  | ${monthly} | {proc} |

### 3. 현재 사용 현황 (usage-analyzer 결과)

| 리소스 | 현재 타입 | 환경 | CPU 평균 | 메모리 | 판정 | 제안 타입 |
|-------|---------|------|:-------:|:-----:|:---:|:--------:|
| {name} | {type} | {env} | {pct}% | {pct}% | ⚠️과다/✅적정/🔴부족 | {suggested} |

예상 절감액: ${savings}/월 ({pct}% 절감)

### 4. 추천

#### 🏆 최종 추천: {recommended_type}
**이유**: {reasoning}

**Trade-off 분석**:
- ✅ 장점: {pros}
- ⚠️ 고려사항: {cons}
- 💰 비용 영향: {cost_impact}

#### 대안 옵션
| 옵션 | 타입 | 적합한 경우 |
|-----|------|----------|
| A   | {type} | {scenario} |
| B   | {type} | {scenario} |

### 5. 베스트 프랙티스 핵심 요약
- {practice_1}
- {practice_2}

### 6. 검증 방법
{verification_commands}
```

---

### Step 5 — 추천 인스턴스 가용성 확인

추천 인스턴스가 해당 리전에서 실제로 사용 가능한지 확인한다.

#### EC2 인스턴스 타입 가용성

```bash
aws ec2 describe-instance-type-offerings \
  --location-type availability-zone \
  --filters "Name=instance-type,Values={recommended_type}" \
  --region ap-northeast-1 \
  --profile okta-devops \
  --query 'InstanceTypeOfferings[*].Location'
```

#### RDS 인스턴스 클래스 가용성

```bash
aws rds describe-orderable-db-instance-options \
  --engine aurora-postgresql \
  --db-instance-class {recommended_class} \
  --region ap-northeast-1 \
  --profile okta-devops \
  --query 'OrderableDBInstanceOptions[*].{Class:DBInstanceClass,AZ:AvailabilityZone,MultiAZ:MultiAZCapable}'
```

가용성이 확인되면 최종 추천에 ✅ 표시. 미제공 시 대안 제시.

---

## 주의사항

- 가격 정보는 **AWS Pricing API 런타임 조회** — 하드코딩 금지 (spec-explorer agent 담당)
- Dev/Stg 환경은 Single AZ, Prod 환경은 Multi-AZ 구성 권장 (CLAUDE.md 원칙 준수)
- Graviton(ARM64) 권장 시 반드시 컨테이너 이미지 ARM64 호환 여부 확인 안내
- Terraform 변경이 필요한 경우 파일 경로 안내: `terraform/src/{sphere}/domain/{env}/rds/` 또는 `ec2/`
- `kubectl edit/delete` 금지 — GitOps 워크플로우 보호
- AWS profile: `okta-devops` (모든 CLI 명령에 `--profile okta-devops` 포함)
