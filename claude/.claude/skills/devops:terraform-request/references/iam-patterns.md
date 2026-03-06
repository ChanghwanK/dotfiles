# IAM 정책 패턴 가이드

Riiid Terraform 코드베이스에서 사용하는 IAM 정책 패턴 레퍼런스입니다.

## 1. Okta IAM (콘솔 접근)

### 파일 위치

```
src/infra/iam-for-okta/global/{sphere}_iam.tf
```

### 모듈 구조

모든 Okta IAM은 `terraform-aws-iam-for-okta` 모듈을 사용합니다:

```hcl
module "okta_{sphere}" {
  source = "github.com/riiid/terraform-aws-iam-for-okta?ref=v0.1.1"

  identifier = "okta-{sphere}"
  providers = {
    aws = aws
  }

  additional_policy_arns = [
    "arn:aws:iam::aws:policy/ReadOnlyAccess",  # 기본 읽기 권한
    aws_iam_policy.okta_{sphere}.arn,            # 커스텀 정책
    aws_iam_policy.okta_{sphere}_s3.arn,         # S3 정책 (별도 분리)
  ]
}
```

### 정책 정의 패턴

```hcl
resource "aws_iam_policy" "okta_{sphere}" {
  name = "okta-{sphere}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Statement 목록
    ]
  })
}
```

## 2. 태그 기반 스코핑 (주요 패턴)

### SecretsManager — 태그 조건

```hcl
{
  "Action" : [
    "secretsmanager:Describe*",
    "secretsmanager:List*",
    "secretsmanager:GetSecretValue",
    "secretsmanager:PutSecretValue"
  ],
  "Effect" : "Allow",
  "Resource" : "*",
  "Condition" : {
    "StringEquals" : {
      "secretsmanager:ResourceTag/Sphere" : "{sphere}"
    }
  }
}
```

복수 sphere 접근 시:
```hcl
"secretsmanager:ResourceTag/Sphere" : ["ai-santa", "santa"]
```

### CloudFront — 태그 조건

```hcl
{
  "Action" : [
    "cloudfront:CreateInvalidation",
    "cloudfront:GetInvalidation",
    "cloudfront:ListInvalidations",
    "cloudfront:GetDistribution"
  ],
  "Effect" : "Allow",
  "Resource" : "*",
  "Condition" : {
    "StringEquals" : {
      "aws:ResourceTag/Sphere" : "{sphere}"
    }
  }
}
```

### SSM Parameter Store — 경로 기반

```hcl
{
  "Action" : [
    "ssm:GetParameter",
    "ssm:GetParameters",
    "ssm:GetParametersByPath",
    "ssm:PutParameter",
    "ssm:DeleteParameter"
  ],
  "Effect" : "Allow",
  "Resource" : "arn:aws:ssm:*:*:parameter/{sphere}/*"
}
```

### SSM Session Manager — 인스턴스 태그 조건

```hcl
{
  "Effect" : "Allow",
  "Action" : ["ssm:StartSession"],
  "Resource" : "arn:aws:ec2:*:*:instance/*",
  "Condition" : {
    "StringLike" : {
      "ssm:resourceTag/Sphere" : ["{sphere}"],
      "ssm:resourceTag/Name" : ["{instance-name}"]
    }
  }
},
{
  "Effect" : "Allow",
  "Action" : [
    "ssm:TerminateSession",
    "ssm:ResumeSession"
  ],
  "Resource" : "arn:aws:ssm:*:*:session/$${aws:username}-*"
}
```

## 3. S3 스코핑 패턴

### 패턴 A: 접두어 기반 (가장 일반적)

```hcl
{
  "Action" : [
    "s3:ListBucket",
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject"
  ],
  "Effect" : "Allow",
  "Resource" : [
    "arn:aws:s3:::{sphere}-*",
    "arn:aws:s3:::{sphere}-*/*"
  ]
}
```

### 패턴 B: Deny + Allow (제한적)

santa, ai-santa에서 사용 — 다른 sphere 버킷 접근을 명시적으로 차단:

```hcl
{
  "Effect" : "Deny",
  "Action" : ["s3:ListBucket", "s3:GetObject", "s3:GetObjectVersion"],
  "NotResource" : [
    "arn:aws:s3:::riiid-{sphere}-*",
    "arn:aws:s3:::riiid-{sphere}-*/*"
  ]
},
{
  "Effect" : "Allow",
  "Action" : ["s3:PutObject", "s3:DeleteObject"],
  "Resource" : [
    "arn:aws:s3:::riiid-{sphere}-*/*"
  ]
}
```

### 패턴 C: 명시적 ARN 목록

data-platform에서 사용 — 공유 버킷이 많아 ARN을 직접 나열:

```hcl
{
  "Effect" : "Allow",
  "Action" : ["s3:*"],
  "Resource" : [
    "arn:aws:s3:::riiid-data-platform-datalake",
    "arn:aws:s3:::riiid-data-platform-datalake/*",
    "arn:aws:s3:::specific-bucket-name",
    "arn:aws:s3:::specific-bucket-name/*"
  ]
}
```

## 4. ECR 접근 패턴

```hcl
{
  "Action" : [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload"
  ],
  "Effect" : "Allow",
  "Resource" : [
    "arn:aws:ecr:*:*:repository/{sphere}-*"
  ]
}
```

> `ecr:GetAuthorizationToken`은 `Resource: "*"`가 필요합니다.

## 5. IRSA (K8s Pod 접근)

### 파일 위치

```
src/{sphere}/{circle}/{env}/irsa/irsa.tf
```

### 모듈 구조

```hcl
module "irsa" {
  source = "github.com/riiid/terraform-aws-irsa?ref=v1.0.0"

  identifier        = local.identifier  # {sphere}-{circle}-{env}
  oidc_provider_arn = data.aws_iam_openid_connect_provider.this.arn
  namespace         = "{sphere}-{circle}"

  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["s3:*"]
        Effect   = "Allow"
        Resource = [
          "arn:aws:s3:::{sphere}-{circle}-*",
          "arn:aws:s3:::{sphere}-{circle}-*/*"
        ]
      }
    ]
  })
}
```

### Okta vs IRSA 차이점

| 항목 | Okta | IRSA |
|------|------|------|
| 사용 주체 | 콘솔 사용자 (사람) | K8s Pod (서비스) |
| 인증 방식 | Okta SAML Federation | OIDC Provider |
| 스코핑 | 태그 기반 Condition | ARN 접두어 기반 |
| 기본 정책 | ReadOnlyAccess 포함 | 최소 권한만 |
| 파일 위치 | 중앙 집중 (iam-for-okta/) | 분산 (각 sphere/) |
| 환경 | global (전체) | 환경별 (dev/stg/prod) |

## 6. 정책 추가 시 체크리스트

### Okta IAM 권한 추가

1. `src/infra/iam-for-okta/global/{sphere}_iam.tf` 열기
2. 기존 `aws_iam_policy` 리소스에 Statement 추가 또는 새 policy 리소스 생성
3. 새 policy 리소스 생성 시 모듈의 `additional_policy_arns`에 추가
4. 태그 기반 Condition 적용 여부 확인
5. `terraform fmt` 실행
6. `terraform plan` 으로 변경 사항 검증

### IRSA 권한 추가

1. `src/{sphere}/{circle}/{env}/irsa/irsa.tf` 열기
2. `policy_json`의 Statement 배열에 항목 추가
3. 새 디렉터리 생성 시 `conf.*.tf` 파일 세트 포함
4. `terraform fmt` 실행
5. `terraform plan` 으로 변경 사항 검증

## 7. 참조 파일

| Sphere | 파일 | 특징 |
|--------|------|------|
| socraai | `socraai_iam.tf` | SecretsManager + CloudFront + S3 (태그 기반) |
| k6 | `k6_iam.tf` | CloudFront invalidation + 태그 조건 |
| tech | `tech_iam.tf` | SSM Session Manager + Parameter Store (복잡) |
| santa | `santa_iam.tf` | ECR + S3 Deny/Allow + CloudWatch |
| ai-santa | `ai_santa_iam.tf` | ECR + S3 Deny/Allow |
| common | `common_iam.tf` | Deny-first 패턴 (제한적 S3) |
| devops | `devops_iam.tf` | 관리자 (`*:*`) |
| data | `data_iam.tf` | 명시적 ARN (Databricks, Airflow) |
