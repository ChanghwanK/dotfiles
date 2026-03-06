---
name: devops:terraform-request
description: >
  인프라 요청을 분석하여 Terraform 코드 변경을 자동으로 처리하는 스킬.
  요청 텍스트에서 sphere, role type, AWS actions, environment 등을 추출하여
  누락 정보를 식별하고, 충분한 정보가 있으면 Terraform 코드 수정 + plan 검증까지 자동 실행.
  Sonnet(현재 모델)이 분석/설계를 담당하고, Haiku 에이전트가 코드 작성을 수행한다.
  사용 시점: (1) IAM 권한 추가, (2) 리소스 프로비저닝, (3) 설정 변경, (4) 네트워크/보안 변경.
  트리거 키워드: "/terraform-request", "인프라 요청", "terraform request",
  "권한 요청", "리소스 요청".
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Grep
  - Agent
---

# Terraform 인프라 요청 처리

인프라 요청을 분석하고 Terraform 코드 변경을 자동 생성합니다.

**역할 분담:**
- **Sonnet (현재)**: 요청 분석, 파일 탐색, 변경 설계
- **Haiku Agent**: 실제 Terraform 파일 편집 + `terraform fmt` 실행
- **terraform-plan-reviewer Agent**: plan 검증

---

## 처리 워크플로우

### Step 1: 요청 파싱 및 카테고리 분류

아래 키워드 매칭으로 카테고리를 자동 분류합니다.

| 키워드 | 카테고리 |
|--------|---------|
| 권한, permission, role, policy, IAM, action, 접근 허용 | **[A] IAM 권한** |
| 생성, 만들어, 신규, create + 리소스명(S3, RDS, CloudFront 등) | **[B] 리소스 생성** |
| 변경, 수정, 업데이트, CORS, 파라미터, 설정 | **[C] 설정 변경** |
| SG, Security Group, 접근, IP, VPC, 인바운드, 아웃바운드, 포트 | **[D] 네트워크/보안** |

복수 카테고리에 해당하면 가장 구체적인 것을 선택합니다.

---

### Step 2: 정보 추출

요청 텍스트에서 아래 필드를 추출합니다:

- **Sphere**: 프로젝트명 (alias 매핑 적용)
- **Circle**: 서브 컴포넌트 (domain, api 등)
- **Environment**: dev / stg / prod / global
- **Role Type**: okta (콘솔) / irsa (K8s Pod)
- **AWS Actions**: 구체적 액션 목록
- **Resource Scope**: 대상 리소스 ARN 또는 태그 조건
- **Spec**: 리소스 스펙 (인스턴스 타입, 엔진 등)

---

### Step 3: Sphere Alias 매핑

자연어 입력을 terraform sphere 이름으로 변환합니다:

| 자연어 입력 | Terraform Sphere |
|-------------|-----------------|
| socra-ai, 소크라, socraai, SOCRA AI, 소크라아이 | `socraai` |
| 산타, santa, Santa | `santa` |
| AI 산타, ai-santa, AI Santa, ai santa | `ai-santa` |
| 테크, tech, Tech | `tech` |
| 데이터, data-platform, 데이터 플랫폼 | `data-platform` |
| k6, K6, 케이식스 | `k6` |
| 인프라, infra | `infra` |
| 알투비, r-test, R-Test | `r-test` |
| 알인사이드, r-inside | `r-inside` |
| 에어매스, airmath | `airmath` |

---

### Step 4: Terraform 파일 매핑

카테고리와 역할 종류에 따라 수정할 파일 경로를 결정합니다:

| 요청 유형 | 역할 종류 | 파일 경로 |
|-----------|----------|----------|
| [A] IAM - Okta | okta-{sphere} | `src/infra/iam-for-okta/global/{sphere}_iam.tf` |
| [A] IAM - IRSA | {sphere}-{circle}-{env} | `src/{sphere}/{circle}/{env}/irsa/irsa.tf` |
| [B] 리소스 생성 | — | `src/{sphere}/{circle}/{env}/{resource_type}/` |
| [C] 설정 변경 | — | 대상 리소스의 기존 파일 경로 |
| [D] 네트워크/보안 | — | `src/{sphere}/{circle}/{env}/` 내 `sg.tf` 또는 관련 파일 |

---

### Step 5: 코드베이스 탐색 (Sonnet 담당)

Read / Glob / Grep 도구를 사용하여:

1. **대상 파일 읽기**: 매핑된 파일의 현재 전체 내용 확인
2. **유사 패턴 참조**: 다른 sphere의 동일 유형 구성을 탐색하여 일관성 확인
3. **참조 파일 활용**: `references/iam-patterns.md`, `references/resource-patterns.md`
4. **변경 설계 완료**: 추가할 Statement / 리소스 블록을 완전히 작성해둔다

---

### Step 6: 누락 정보 검증

카테고리별 필수 필드를 검증합니다. **누락 시 코드 작업 전에 사용자에게 질문합니다.**

#### [A] IAM 권한

| 필드 | 필수 | 누락 시 질문 |
|------|------|-------------|
| 역할 종류 | Yes | "콘솔 접근용(okta)인가요, K8s Pod용(irsa)인가요?" |
| AWS 액션 | Yes | "어떤 작업이 필요한지 알려주시면 액션을 추천드립니다" |
| 리소스 스코프 | Yes | 기본: 태그 기반 `aws:ResourceTag/Sphere`, 특수 경우 확인 필요 |
| 환경 | No | Okta → global (기본값), IRSA → 환경 확인 필요 |

#### [B] 리소스 생성

| 필드 | 필수 | 누락 시 질문 |
|------|------|-------------|
| Sphere | Yes | "어느 프로젝트(sphere)에 필요한가요?" |
| 환경 | Yes | "dev/stg/prod 중 어느 환경인가요?" |
| 스펙 | 조건부 | RDS: "인스턴스 타입과 엔진 버전을 알려주세요" / S3: 기본값 적용 가능 |

#### [C] 설정 변경

| 필드 | 필수 |
|------|------|
| 대상 리소스 | Yes |
| 변경 내용 (구체적 값) | Yes |
| 환경 | Yes |

#### [D] 네트워크/보안

| 필드 | 필수 |
|------|------|
| 대상 SG 또는 리소스 | Yes |
| 소스 IP/CIDR/SG, 포트, 프로토콜 | Yes |
| 환경 | Yes |

---

### Step 7: 코드 변경 — Haiku 에이전트 위임

Step 5에서 설계한 변경 내용을 Haiku 에이전트에 위임합니다.

위임 시 프롬프트에 반드시 포함할 내용:

```
- 수정할 파일의 절대 경로
- 현재 파일에서 수정할 위치 (기존 Statement 이름, 리소스 블록명 등)
- 추가/수정할 완성된 HCL 코드
- terraform fmt 실행할 디렉터리 경로
```

에이전트 호출 예시:

```
Agent(
  subagent_type: "general-purpose",
  model: "haiku",
  prompt: |
    아래 Terraform 파일을 수정하고 포맷팅을 적용해주세요.

    ## 대상 파일
    {absolute_file_path}

    ## 수행할 변경
    {exact_hcl_change}

    ## 규칙
    - 기존 코드 스타일(들여쓰기, 따옴표 방식)을 그대로 유지할 것
    - 수정 후 반드시 `terraform fmt {dir_path}` 실행할 것
    - /src/infra/k8s/ 는 절대 수정 금지
)
```

---

### Step 8: Plan 검증 (독립 검증 단계)

코드 변경 완료 후 `terraform-plan-reviewer` 에이전트로 plan을 검증합니다.

```
Agent(subagent_type: "terraform-plan-reviewer")
```

검증 확인 항목:
- 의도한 리소스만 변경되는지 확인
- 예상치 못한 destroy / replace 없는지 확인
- 변경 사항이 요청 내용과 일치하는지 확인

---

## 출력 형식

### 처리 완료

```
## 요청 분석

- 카테고리: [A] IAM 권한
- Sphere: {sphere}
- 역할: {role}
- 추가 액션: {actions}
- 리소스 스코프: {scope}

## 코드 변경 완료

파일: {file_path}
변경: {변경 요약}

## Plan 검증 결과

(terraform-plan-reviewer 결과 요약)
```

### 정보 부족 — 확인 필요

```
## 요청 분석

- 카테고리: {category} (추정)
- Sphere: {sphere}
- 파악된 정보: {identified_info}

## 확인이 필요한 사항

1. {질문 1}
2. {질문 2}
```

---

## 주의사항

- `/src/infra/k8s/`는 절대 수정하지 않습니다 (ArgoCD GitOps 전용)
- IAM 정책은 최소 권한 원칙을 적용합니다
- Okta IAM은 태그 기반 스코핑(`aws:ResourceTag/Sphere`)을 기본으로 적용합니다
- 새 리소스 디렉터리 생성 시 `conf.*.tf` 파일 세트를 반드시 포함합니다 (`references/resource-patterns.md` 참조)
- Step 8 plan 검증은 코드 변경 후 반드시 실행합니다
