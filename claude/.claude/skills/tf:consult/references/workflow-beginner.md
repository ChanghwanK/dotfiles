# Terraform 초심자 워크플로우 가이드

Terraform/AWS를 처음 접하는 개발자를 위한 단계별 인프라 변경 가이드.
"나는 그냥 DB가 필요한데..." 라는 상황에서 실제 AWS 리소스가 생성되기까지의 전체 여정.

---

## 먼저 알아야 할 핵심 개념 3가지

### 1. Infrastructure as Code (IaC)란?

> **요약**: 인프라(서버, DB, 네트워크)를 코드 파일로 관리하는 방식.

기존 방식:
```
AWS 콘솔 열기 → 버튼 클릭 → DB 생성
→ 나중에 "이거 어떻게 만들었지?" 기억 안 남
→ stg랑 prod 설정이 조금씩 달라짐
```

IaC 방식:
```
.tf 파일 작성 → Plan 확인 → Apply
→ Git에 히스토리 남음
→ dev/stg/prod 모두 동일한 코드 기반
→ 실수를 코드 리뷰 단계에서 잡을 수 있음
```

### 2. State란?

> **요약**: Terraform이 "현재 AWS에 뭐가 있는지" 기억하는 장부.

```
Terraform State (riiid-terraform-state S3 버킷에 저장)
    │
    └── "santa/domain/dev/rds/terraform.tfstate"
         ─ RDS 인스턴스 ID: db-XXXXXX
         ─ 엔드포인트: xxx.us-east-1.rds.amazonaws.com
         ─ 파라미터 그룹: ...
```

State 없이는 Terraform이 "이 코드가 이미 적용됐는지" 알 수 없음.

### 3. Plan & Apply란?

> **요약**: Plan = 배포 미리보기. Apply = 실제 배포.

```
Plan: "이 코드 변경 시 AWS에서 일어날 일 목록"
  + will be created   ← 새로 생김
  ~ will be updated   ← 설정 변경
  - will be destroyed ← 삭제됨 (⚠️ 주의!)

Apply: Plan에서 확인한 변경을 실제 AWS에 적용
```

---

## 전체 워크플로우

```
                    인프라가 필요해졌을 때
                           │
              ┌────────────┴────────────┐
              │                         │
     AWS 개념 잘 모름              이미 알고 있음
              │                         │
              ▼                         │
    ┌─────────────────┐                │
    │  /tf:consult    │                │
    │  (교육 + 요청서) │                │
    └────────┬────────┘                │
             │                         │
             └─────────────┬───────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  STEP 1: 코드 작성       │
              │  /tf:iac                 │
              │                         │
              │  자동 실행:              │
              │    fmt → validate → plan │
              │    tf-code-reviewer (BG) │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  STEP 2: Plan 검토       │
              │  /tf:plan                │
              │                         │
              │  5가지 기준 리뷰:        │
              │    코드 스타일           │
              │    보안 취약점           │
              │    리소스 표준           │
              │    다운타임 위험         │
              │    의존성 영향도         │
              └────────────┬────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
         BLOCKED    NEEDS REVISION    APPROVED
            │              │              │
         수정 필요    경고 검토 후       다음 단계
                      결정                │
                           │              │
                           └──────┬───────┘
                                  ▼
              ┌─────────────────────────┐
              │  STEP 3: 실제 배포       │
              │  /tf:apply               │
              │                         │
              │  "정말 적용하시겠습니까?" │
              │  → yes 입력              │
              │                         │
              │  자동 실행:              │
              │    state 점검            │
              │    결과 리포트           │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  STEP 4: Git 워크플로우  │
              │                         │
              │  git commit              │
              │  → PR 생성               │
              │  → 코드 리뷰             │
              │  → merge                 │
              └─────────────────────────┘
```

---

## STEP 0: /tf:consult (AWS를 모를 때)

**언제**: AWS 서비스가 뭔지, 뭘 써야 할지 모를 때

**하는 일**:
1. 개발자 언어로 AWS 서비스 개념 설명
2. 필요한 정보 수집 (용도, 환경, 서비스명)
3. 인프라 요청서 생성
4. 자동으로 `/tf:iac`에 전달

**대화 예시**:
```
개발자: "파일 업로드 기능에 스토리지가 필요해"

tf:consult:
  → S3 = "서버의 /uploads 디렉토리를 클라우드로 옮긴 것"
  → 몇 가지 확인:
     1. 어떤 파일을? (이미지/동영상/문서)
     2. 브라우저에서 직접 업로드? (CORS 필요 여부)
     3. dev/stg/prod 중 어디에?
     4. socraai 서비스용?

개발자: "이미지, 브라우저 직접 업로드, dev부터, socraai"

tf:consult:
  → 요청서 생성 → 확인 요청 → /tf:iac 자동 호출
```

**몰라도 되는 것**: AWS 콘솔, Terraform 문법, 네이밍 규칙

---

## STEP 1: /tf:iac (코드 작성)

**언제**: AWS 리소스 타입과 Sphere/Circle/Environment를 알 때

**하는 일**:
1. 기존 코드 패턴 분석
2. Terraform 코드 파일 생성
3. fmt → validate → plan 자동 실행
4. tf-code-reviewer 백그라운드 실행

**요청 예시**:
```
# tf:consult를 통해 자동 전달되거나
# 직접 요청:
"socraai/domain/dev에 S3 버킷 생성해줘.
 이미지 업로드용, CORS 필요, CloudFront 연동"
```

**생성되는 파일 구조**:
```
src/socraai/domain/dev/s3/
├── conf.terraform.tf   ← S3 backend + provider 설정
├── conf.locals.tf      ← identifier = "socraai-domain-dev"
├── conf.variables.tf   ← sphere, circle, environment 선언
├── terraform.tfvars    ← 변수 값
└── s3.tf               ← 실제 S3 리소스 코드
```

**Sphere/Circle/Environment 규칙**:
```
src/{sphere}/{circle}/{environment}/{resource}/

sphere    = 프로덕트 단위  (socraai, santa, tech, infra)
circle    = 서브 컴포넌트  (domain, backoffice, k8s, iam)
environment = 배포 환경   (dev, stg, prod, global)

예: src/socraai/domain/dev/s3/
    src/santa/backoffice/prod/rds/
    src/tech/core-api/global/ecr/
```

---

## STEP 2: /tf:plan (Plan 검토)

**언제**: 코드 작성 후 실제 배포 전

**하는 일**: 코드 품질 5가지 기준 리뷰 + 실제 Plan 출력 분석

**Verdict 해석**:

| Verdict | 의미 | 다음 행동 |
|---------|------|---------|
| ✅ APPROVED | 모든 검사 통과 | `/tf:apply` 바로 실행 |
| ⚠️ NEEDS REVISION | 경고 있음 (WARNING 2건 이상) | 경고 내용 확인 후 수정하거나 수용 |
| 🚫 BLOCKED | 심각한 문제 (보안 위험, 파괴적 변경) | 반드시 수정 후 재실행 |

**Plan 결과 읽는 법**:
```
# Plan 출력 예시
Terraform will perform the following actions:

  # aws_s3_bucket.this will be created
  + resource "aws_s3_bucket" "this" {
      + bucket = "riiid-socraai-domain-dev"
      ...
    }

Plan: 1 to add, 0 to change, 0 to destroy.
       ─────────────────────────────────────
       ↑ 새로 생김  ↑ 수정됨   ↑ 삭제됨
                           ⚠️ 이게 있으면 주의!
```

**초심자가 반드시 확인할 것**:
- `to destroy`가 0인지 (예상치 못한 삭제 없는지)
- `to add` 리소스 이름이 올바른지
- BLOCKED면 이유 읽고 수정

---

## STEP 3: /tf:apply (실제 배포)

**언제**: Plan이 APPROVED (또는 NEEDS REVISION 수용) 후

**하는 일**:
1. Plan 결과 재확인
2. "정말 적용하시겠습니까?" 확인 요청
3. `terraform apply` 실행
4. 적용된 State 점검
5. 결과 리포트 출력

**중요한 점**:
```
Apply = 실제 AWS에 변경이 일어남 = 비용 발생 가능
→ 항상 Plan 결과를 먼저 확인하고 진행

"yes" 입력 = 배포 시작 (되돌리기 어려울 수 있음)
→ BLOCKED 상태에서는 tf:apply가 진행 거부
```

**결과 리포트**:
```
✅ SUCCESS
  적용된 리소스:
    + aws_s3_bucket.this (riiid-socraai-domain-dev)
    + aws_s3_bucket_versioning.this
    + aws_s3_bucket_public_access_block.this

  다음 단계: git commit → PR 생성
```

---

## STEP 4: Git 워크플로우

**왜 필요한가**: IaC의 핵심 = "인프라 변경도 코드 변경 = PR로 관리"

**순서**:
```bash
# 1. 변경된 파일 확인
git status

# 2. 커밋 (커밋 메시지 자동 생성)
/git:commit

# 3. PR 생성 후 코드 리뷰
# → 브랜치 규칙: feat/{feature-name} 또는 config/{env}/{component}/{change}
```

**커밋 메시지 규칙**:
```
feat(socraai/domain): add S3 bucket for image uploads
fix(santa/domain): fix RDS parameter group max_connections
chore(tech/core-api): update provider version
```

---

## 빠른 참조: 어떤 명령어를 쓰나?

```
상황                              → 명령어
─────────────────────────────────────────────────────
AWS 개념 모름, 뭘 써야 할지 모름   → /tf:consult
코드 직접 작성 요청               → /tf:iac
배포 전 Plan 검토                 → /tf:plan
실제 배포                         → /tf:apply
커밋                              → /git:commit
어떤 도구를 써야 할지 모름         → /tf:guide
```

---

## 자주 묻는 질문

**Q: 처음인데 뭐부터 시작해야 하나요?**
A: `/tf:consult`에 "무엇이 필요한지" 자연어로 말씀해 주세요. 나머지는 안내해 드립니다.

**Q: Plan 후 Apply를 취소하고 싶으면?**
A: Apply 확인 질문에서 "no"라고 답하거나 Enter 없이 멈추면 됩니다. Apply가 시작되기 전에는 언제든 취소 가능합니다.

**Q: dev에 먼저 만들고 나중에 prod에도 만들고 싶으면?**
A: `/tf:iac` 요청 시 environment를 `dev`로, 나중에 동일 요청에 `prod`로 다시 요청하면 됩니다. 코드 구조가 동일해서 쉽게 복제됩니다.

**Q: 실수로 Apply했는데 되돌리고 싶으면?**
A: 상황에 따라 다릅니다. 리소스 삭제(destroy)가 아닌 단순 생성이면 terraform 코드를 지우고 plan → apply로 삭제할 수 있습니다. 문제가 있으면 인프라 팀에 문의해 주세요.

**Q: AWS 콘솔에서 직접 수정하면 안 되나요?**
A: 가능하지만 권장하지 않습니다. 콘솔에서 수정하면 Terraform State와 실제 AWS가 불일치하게 되어 다음 apply 시 예상치 못한 변경이 발생할 수 있습니다.

**Q: socraai 서비스 인프라를 요청했는데 왜 다른 에이전트가 처리하나요?**
A: socraai sphere는 전용 아키텍트 에이전트(`socraai-terraform-architect`)가 코드 일관성을 보장합니다. `/tf:iac`를 통해 요청하면 자동으로 해당 에이전트로 위임됩니다.
