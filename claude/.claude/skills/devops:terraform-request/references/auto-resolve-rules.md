# Auto-Resolution 규칙

`devops:terraform-request` 스킬의 Step 6에서 누락 정보를 코드베이스에서 자동으로 추론하는 규칙입니다.

**원칙: 물어보기 전에 코드를 먼저 본다**

---

## 카테고리별 자동 추론 규칙

### [A] IAM/Okta 권한 — Okta 역할명 추론

**트리거**: 요청에 sphere는 있지만 Okta 역할명이 없을 때

**추론 방법**:
```
1. Glob으로 파일 탐색: src/infra/iam-for-okta/global/*{sphere}*.tf
2. 파일 발견 시 → 파일명에서 역할명 추출 (예: socraai_iam.tf → okta-socraai)
3. 파일 없을 시 → 기본 패턴: okta-{sphere}
```

**Sphere → Okta 역할 매핑 (코드에서 확인된 매핑)**:
| Sphere | Okta 역할 | 파일 |
|--------|-----------|------|
| socraai | okta-socraai | socraai_iam.tf |
| santa | okta-santa | santa_iam.tf |
| ai-santa | okta-ai-santa | ai_santa_iam.tf |
| tech | okta-tech | tech_iam.tf |
| data-platform | okta-data | data_iam.tf |
| k6 | okta-k6 | k6_iam.tf |
| devops | okta-devops | devops_iam.tf |
| common | okta-common | common_iam.tf |

**추론 성공 시 확인 메시지**:
```
[자동 추론] {sphere} sphere이므로 okta-{sphere} 역할로 판단했습니다.
확인: src/infra/iam-for-okta/global/{sphere}_iam.tf
맞나요? (아니면 올바른 역할명을 알려주세요)
```

---

### [A] IAM/Okta 권한 — 현재 정책 상태 표시

**트리거**: 대상 파일을 찾았을 때 항상 실행

**추론 방법**:
```
1. Read 도구로 src/infra/iam-for-okta/global/{sphere}_iam.tf 읽기
2. Statement 목록에서 현재 허용된 Action + Resource 추출
3. 요청된 Action이 이미 있는지 확인 (중복 방지)
4. 변경 전/후 diff 형태로 표시
```

**출력 형식**:
```
[현재 상태] {sphere} IAM 정책
  S3: s3:GetObject, s3:ListBucket (socraai-*)
  SecretsManager: GetSecretValue (Sphere=socraai 조건)
  CloudFront: CreateInvalidation (Sphere=socraai 조건)

[변경 예정]
  + s3:PutObject 추가 (socraai-domain-* 범위)
```

---

### [A] IAM/Okta 권한 — 리소스 스코프 추론

**트리거**: 리소스 스코프가 명시되지 않았을 때

**추론 규칙 (우선순위 순)**:

1. **S3 버킷**: `{sphere}-*` 패턴 적용
   ```
   Resource: ["arn:aws:s3:::{sphere}-*", "arn:aws:s3:::{sphere}-*/*"]
   ```
   단, 요청에 특정 버킷명이 있으면 해당 버킷으로 한정

2. **SecretsManager**: 태그 기반 스코핑
   ```
   Condition: { StringEquals: { "secretsmanager:ResourceTag/Sphere": "{sphere}" } }
   Resource: "*"
   ```

3. **CloudFront**: 태그 기반 스코핑
   ```
   Condition: { StringEquals: { "aws:ResourceTag/Sphere": "{sphere}" } }
   Resource: "*"
   ```

4. **SSM Parameter Store**: 경로 기반
   ```
   Resource: "arn:aws:ssm:*:*:parameter/{sphere}/*"
   ```

5. **ECR**: 접두어 기반
   ```
   Resource: "arn:aws:ecr:*:*:repository/{sphere}-*"
   ```

**추론 성공 시 확인**:
```
[자동 추론] S3 접근이므로 {sphere}-* 패턴으로 스코핑합니다.
  Resource: arn:aws:s3:::{sphere}-*, arn:aws:s3:::{sphere}-*/*
다른 범위가 필요하면 알려주세요.
```

---

### [C] S3 CORS — 환경별 버킷명 추론

**트리거**: 버킷명 없이 sphere + 용도만 제공될 때

**추론 방법**:
```
1. Glob으로 탐색: src/{sphere}/*/({dev,stg,prod})/s3/s3.*.tf
2. 파일 내에서 bucket = "..." 값 추출
3. 요청 키워드와 가장 유사한 버킷명 제안
```

**추론 성공 시 확인**:
```
[자동 추론] {sphere} sphere의 S3 버킷 목록:
  - {bucket-name-1} (dev/stg/prod)
  - {bucket-name-2} (prod)

어느 버킷에 CORS를 추가할까요?
```

---

### [C] S3 CORS — 기존 CORS 설정 표시

**트리거**: CORS 추가 요청 시 항상 실행

**추론 방법**:
```
1. 대상 S3 파일 읽기
2. cors_rule 블록 찾기
3. 기존 allowed_origins 목록 추출
4. 추가할 Origin과 함께 변경 전/후 표시
```

**출력 형식**:
```
[현재 CORS 설정] {bucket-name}
  기존 Origins:
    - https://app.existing.com
    - https://staging.existing.com

[변경 예정]
  + https://new-origin.vercel.app 추가
```

---

### [A] IRSA — 대상 파일 추론

**트리거**: IRSA 요청 시 서비스명/네임스페이스만 있을 때

**추론 방법**:
```
1. Glob으로 탐색: src/{sphere}/{circle}/{env}/irsa/irsa.tf
2. circle은 서비스명에서 추론 (celery-worker → domain, http-api → api 등)
3. 파일 발견 시 현재 정책 내용 표시
```

**Namespace → Circle 매핑 추론**:
- 네임스페이스 = `{sphere}/{service}` 형태일 때 service를 circle 후보로 사용
- `src/{sphere}/*/` 디렉터리 목록과 교차 검증

**추론 성공 시**:
```
[자동 추론] socraai/celery-worker → src/socraai/domain/prod/irsa/irsa.tf
현재 정책: s3:GetObject (socraai-domain-*)

변경 예정: s3:PutObject 추가
```

**추론 실패 시**:
```
[추론 불가] {sphere} sphere에서 {service} 서비스의 IRSA 파일을 찾지 못했습니다.
Circle 이름을 알려주시면 진행할 수 있습니다.
(예: domain, api, worker 등)
```

---

## 확인 메시지 표준 포맷

자동 추론이 성공했을 때 사용자에게 보여주는 **통합 확인 메시지**:

```
## 요청 분석 완료

**[분류]** {category} — {sub-type}
**[대상 파일]** {file_path}

**[자동 추론된 정보]**
- Okta 역할: okta-{sphere} ({sphere} sphere 기준)
- 리소스 스코프: arn:aws:s3:::{sphere}-* (S3 접두어 패턴)

**[현재 상태]**
{현재 정책/설정 요약}

**[변경 예정]**
{추가/변경 내용 diff}

---
진행할까요? (수정이 필요하면 알려주세요)
```

---

## 추론 실패 조건 (기존처럼 질문)

아래 경우는 자동 추론이 불가하므로 사용자에게 직접 질문합니다:

1. Sphere 자체를 모르는 경우 (`여러 sphere` 요청 등)
2. Circle 이름이 불명확하고 파일도 없는 경우
3. 새로 생성 요청인데 스펙이 전혀 없는 경우 (RDS 인스턴스 타입 등)
4. 비표준 패턴의 리소스 (코드베이스에 유사 예시 없음)
