---
name: tf:consult
description: |
  개발자를 위한 AWS 인프라 컨설팅 스킬. Terraform/AWS를 잘 모르는 개발자가 필요한
  개념을 이해하고 구조화된 인프라 요청서를 작성할 수 있도록 돕는다.
  사용 시점: (1) AWS 리소스가 필요하지만 뭘 요청해야 할지 모를 때,
  (2) "DB 필요해요" 같은 막연한 요구사항을 구체화할 때,
  (3) 우리 팀 인프라 패턴/표준을 이해하고 싶을 때,
  (4) 특정 AWS 서비스가 무엇인지 개념을 파악하고 싶을 때.
  트리거 키워드: 인프라 뭐 필요해, AWS 이거 뭐야, 데이터베이스 필요, 캐시 쓰고 싶어,
  파일 저장소 필요, 시크릿 저장, 인프라 컨설팅, terraform 모르겠어, /tf:consult.
model: sonnet
allowed-tools:
  - Read
  - Glob
  - Grep
---
# Infrastructure Consulting

개발자가 AWS 인프라를 이해하고 구체적인 인프라 요청서를 작성할 수 있도록 돕는 컨설팅 스킬.

---

## 핵심 원칙

- **코드 수정/terraform 실행 금지** — 이 스킬은 교육과 요청 구조화만 수행
- **개발자의 언어로 설명** — AWS 전문 용어 대신 백엔드/프론트엔드 맥락의 비유와 매핑 사용
- **Progressive Disclosure** — 처음부터 모든 옵션을 나열하지 않고 필요한 만큼만 점진적으로 설명
- **개념 설명은 references에서 로드** — `references/concepts-{service}.md` 조건부 로드, 전체 로드 금지

---

## 2가지 동작 모드

**모드 분기 규칙:**

| 발화 패턴 | 모드 |
|----------|------|
| AWS 서비스명 + "뭐야", "설명", "어떻게 쓰는지", "알려줘" | 개념 학습 모드 → Step 2로 바로 이동 |
| "필요해", "만들고 싶어", "추가하고 싶어", "어떻게 요청" 등 인프라 요청 | 컨설팅 모드 → Step 1부터 시작 |

---

## 개념 매핑 테이블

| 개발자가 말하는 것 | AWS 리소스 | 개념 파일 |
|-----------------|-----------|---------|
| "DB", "데이터베이스", "PostgreSQL", "MySQL" | RDS / Aurora | concepts-rds.md |
| "캐시", "Redis", "인메모리", "세션 저장소" | ElastiCache Valkey | concepts-cache.md |
| "파일 저장소", "이미지 업로드", "정적 파일", "첨부파일" | S3 | concepts-s3.md |
| "CDN", "이미지 빠르게", "정적 파일 서빙", "CloudFront" | CloudFront + S3 | concepts-cdn.md |
| "환경변수", "시크릿", "API 키", "DB 비밀번호", "토큰 보관" | Secrets Manager | concepts-secrets.md |
| "메시지 큐", "비동기 처리", "이벤트", "Celery broker" | SQS / Amazon MQ | concepts-mq.md |
| "Docker registry", "컨테이너 이미지 저장", "ECR" | ECR | concepts-ecr.md |
| "AWS 권한", "서비스 계정", "Pod가 S3 접근", "IRSA" | IAM / IRSA | concepts-iam.md |

---

## Step 1 — 니즈 파악 (컨설팅 모드)

### 1-1. 요구사항 추출

사용자 발화에서 다음 4가지를 추출한다:

| 항목 | 설명 | 예시 |
|------|------|------|
| **용도** | 무엇을 하려는지 | "이미지 업로드", "API 응답 캐싱" |
| **규모** | 예상 사용량/크기 | "몇 GB", "초당 몇 건" |
| **환경** | 어느 환경에 필요한지 | dev / stg / prod |
| **서비스** | 어떤 제품/서비스용인지 | santa / socraai / tech |

### 1-2. 모호성 해소

충분한 정보가 없으면 **한 번에** 모아서 질문한다 (반복 질문 금지):

```
인프라 요구사항을 구체화하기 위해 몇 가지 확인하겠습니다.

1. **용도**: 어떤 데이터를 저장/처리하나요?
   예: 사용자 프로필 이미지 / API 응답 캐시 / 비동기 작업 큐

2. **접근 패턴**: 주로 읽기? 쓰기? 둘 다?

3. **환경**: 어떤 환경이 필요한가요? (dev / stg / prod / 모두)

4. **서비스**: 어떤 제품에서 사용하나요? (santa / socraai / tech 등)
```

---

## Step 2 — 개념 설명

### 2-1. 리소스 매핑

Step 1 정보 또는 발화에서 **개념 매핑 테이블**을 참조하여 적합한 AWS 리소스를 결정한다.

### 2-2. 개념 파일 로드

해당 리소스의 개념 파일을 Read로 로드하여 내용을 설명한다.

```
Read /Users/changhwan/.claude/skills/tf:consult/references/concepts-{service}.md
```

설명 포맷 (모든 서비스 공통):

1. **한줄 요약** — 개발자에게 익숙한 비유로 시작
2. **핵심 개념** — AWS 용어를 개발자 언어로 풀어서 설명
3. **Riiid에서 어떻게 쓰는지** — 실제 sphere/circle 예시
4. **결정해야 할 사항** — 사용자가 답해야 할 체크리스트

### 2-3. 추가 정보 수집

개념 파일의 "결정해야 할 사항"을 기반으로 미수집 정보를 추가 질문한다.

---

## Step 3 — 우리 팀 패턴 안내

### 3-1. 디렉토리 구조

```
우리 팀 Terraform 모노레포 구조:

src/{sphere}/{circle}/{environment}/{resource}/
  예시: src/santa/domain/dev/rds/
        src/socraai/domain/prod/s3/

각 리소스(DB, 캐시, S3 등)가 독립적인 폴더와 독립적인 state를 가집니다.
한 리소스를 수정해도 다른 리소스에 영향이 없습니다.
```

### 3-2. 환경별 설계 원칙

```
| 설정 항목     | dev          | stg          | prod                    |
|-------------|--------------|--------------|-------------------------|
| 가용 영역     | Single AZ    | Single AZ    | 필요 시 Multi AZ         |
| 인스턴스 크기 | 최소 (micro)  | 최소          | 워크로드에 맞게 선택        |
| 비용 우선순위 | 최우선        | 최우선        | 안정성 기본 보장 후 최적화    |
| 버저닝/백업   | 비활성        | 비활성        | 활성                      |
```

우리 팀 원칙: **생산성 > 비용 > 안정성**
- dev/stg: 비용 효율 극대화 (Single AZ, 최소 사양)
- prod: 기본 가용성만 보장 (과잉 프로비저닝 지양)

---

## Step 4 — 인프라 요청서 생성 + tf:iac 핸드오프

### 4-1. 요청서 생성

수집된 모든 정보를 아래 포맷으로 정리한다:

```markdown
## 인프라 요청서

### 기본 정보
- **서비스(Sphere)**: {sphere}
- **컴포넌트(Circle)**: {circle}
- **환경(Environment)**: {dev / stg / prod}

### 요청 내용
- **리소스 타입**: {AWS 리소스명}
- **용도**: {사용자가 설명한 용도}

### 세부 사항
{리소스별 결정 사항 목록}

### 참고
- socraai sphere는 전용 아키텍트 에이전트(socraai-terraform-architect)가 자동으로 처리합니다.
```

### 4-2. 사용자 확인

```
위 요청서 내용이 맞는지 확인해 주세요.
수정이 필요하면 알려주시고, 맞으면 "확인" 또는 "진행해줘"라고 답해 주세요.
```

### 4-3. tf:iac 자동 전달

사용자 확인 후 Skill 도구로 `/tf:iac`를 호출하여 요청서 내용을 전달한다.

**socraai sphere인 경우:**
- Skill로 `/tf:iac`를 호출하면 내부적으로 `socraai-terraform-architect` 에이전트로 자동 위임됩니다.

---

## References

서비스 키워드가 감지된 경우에만 해당 파일을 Read로 로드한다. 전체 로드 금지.

| 서비스 키워드 | 로드할 파일 |
|------------|-----------|
| DB, 데이터베이스, PostgreSQL, MySQL, Aurora, RDS | `references/concepts-rds.md` |
| 캐시, Redis, Valkey, 세션, 인메모리, ElastiCache | `references/concepts-cache.md` |
| S3, 파일 저장소, 이미지 업로드, 버킷 | `references/concepts-s3.md` |
| CDN, CloudFront, 정적 파일 서빙, 이미지 배포 | `references/concepts-cdn.md` |
| 시크릿, Secrets Manager, 환경변수, API 키 보관 | `references/concepts-secrets.md` |
| 메시지 큐, SQS, MQ, 비동기 처리, Celery | `references/concepts-mq.md` |
| ECR, Docker registry, 컨테이너 이미지 | `references/concepts-ecr.md` |
| IAM, IRSA, AWS 권한, 서비스 계정 | `references/concepts-iam.md` |
| Terraform 전체 흐름, Plan/Apply 개념, 처음 시작 | `references/workflow-beginner.md` |
