# 리소스 종류별 프로비저닝 가이드

Riiid Terraform 코드베이스에서 사용하는 리소스 유형별 필수 정보, 기본값, 참조 파일 경로입니다.

## 공통 사항

### 디렉터리 구조

새 리소스 생성 시 반드시 아래 파일 세트를 포함합니다:

```
src/{sphere}/{circle}/{env}/{resource_type}/
├── conf.terraform.tf    # Provider + Backend + Version
├── conf.locals.tf       # identifier 등 로컬 변수
├── conf.variables.tf    # sphere, circle, environment 변수
├── terraform.tfvars     # 변수 값
└── {resource}.tf        # 리소스 정의
```

### conf.terraform.tf 템플릿

```hcl
locals {
  default_tags = {
    Sphere             = var.sphere
    Circle             = var.circle
    Environment        = var.environment
    Identifier         = local.identifier
    ManagedByTerraform = "true"
  }
}

provider "aws" {
  region = "ap-northeast-1"
  default_tags {
    tags = local.default_tags
  }
}

terraform {
  required_version = ">= 1.6.5"
  backend "s3" {
    bucket  = "riiid-terraform-state"
    key     = "{sphere}/{circle}/{env}/{resource_type}/terraform.tfstate"
    region  = "ap-northeast-1"
    encrypt = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

### conf.locals.tf 템플릿

```hcl
locals {
  identifier    = "${var.sphere}-${var.circle}-${var.environment}"
  secret_prefix = join("/", [var.sphere, var.circle, var.environment])
}
```

### conf.variables.tf 템플릿

```hcl
variable "sphere" {
  type = string
}

variable "circle" {
  type = string
}

variable "environment" {
  type = string
}
```

### terraform.tfvars 템플릿

```hcl
sphere      = "{sphere}"
circle      = "{circle}"
environment = "{env}"
```

---

## S3 버킷

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| Sphere | Yes | — |
| Circle | Yes | — |
| 환경 | Yes | — |
| 퍼블릭 여부 | No | private |
| 버저닝 | No | disabled |
| CORS | No | 없음 |

### 기본 설정

```hcl
resource "aws_s3_bucket" "this" {
  bucket = local.identifier  # {sphere}-{circle}-{env}
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}
```

### CloudFront 연동 시 추가

```hcl
resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.cloudfront_oac.json
}

data "aws_iam_policy_document" "cloudfront_oac" {
  statement {
    sid    = "Allow CloudFront OAC"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.this.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.this.arn]
    }
  }
}
```

### 참조 파일

| 파일 | 특징 |
|------|------|
| `src/socraai/domain/dev/s3/s3.tf` | 기본 S3 + CORS |
| `src/k6/domain/prod/cdn/s3.tf` | CloudFront 연동 (ACL 없음) |
| `src/santa/domain/prod/cdn/s3.tf` | 복잡한 접근 패턴 (ACL + public prefix) |

---

## CloudFront

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| Sphere | Yes | — |
| Circle | Yes | — |
| 환경 | Yes | — |
| 오리진 종류 | No | S3 |
| 커스텀 도메인 | No | CloudFront 기본 도메인 |
| 접근 제어 방식 | No | OAC (Origin Access Control) |
| CORS 정책 | No | 없음 |
| WAF | No | 없음 |

### 방식 A: 직접 리소스 관리 (socraai 스타일)

OAC + 직접 `aws_cloudfront_distribution` 사용:

```hcl
resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${local.identifier}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "this" {
  origin {
    domain_name              = data.aws_s3_bucket.this.bucket_regional_domain_name
    origin_id                = data.aws_s3_bucket.this.id
    origin_access_control_id = aws_cloudfront_origin_access_control.this.id
  }
  # ... 캐시 정책, 응답 헤더 정책 등
}
```

### 방식 B: 커뮤니티 모듈 (santa/k6 스타일)

`terraform-aws-modules/cloudfront/aws` 모듈 사용:

```hcl
module "cloudfront" {
  source  = "terraform-aws-modules/cloudfront/aws"
  version = "3.4.0"

  aliases             = [local.cf_host]
  comment             = "CDN for ${var.sphere} project (${var.circle})"
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = "PriceClass_200"
  # ...
}
```

### 참조 파일

| 파일 | 특징 |
|------|------|
| `src/socraai/domain/prod/cloudfront/cloudfront.tf` | OAC + CORS + 직접 관리 |
| `src/socraai/domain/dev/cloudfront/cloudfront.tf` | dev 환경 (WAF 없음) |
| `src/santa/domain/prod/cdn/cloudfront.tf` | Signed URL + Trusted Key Groups |
| `src/k6/domain/prod/cdn/cloudfront.tf` | 커뮤니티 모듈 사용 |

---

## RDS Aurora

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| Sphere | Yes | — |
| Circle | Yes | — |
| 환경 | Yes | — |
| 엔진 | Yes | aurora-postgresql |
| 엔진 버전 | Yes | — (최신 LTS 사용) |
| 인스턴스 타입 | Yes | — |
| 인스턴스 수 | No | dev=1, prod=2 |
| AZ | No | dev=single, prod=multi |
| 백업 보존 기간 | No | dev=1, prod=7 |
| 데이터베이스 이름 | No | sphere_circle |
| SG 인바운드 | Yes | EKS SG + 필요시 VPN/Databricks |

### 기본 설정

```hcl
resource "aws_rds_cluster" "aurora_cluster" {
  cluster_identifier  = local.identifier
  engine              = "aurora-postgresql"
  engine_version      = "16.4"
  database_name       = "app"
  master_username     = "admin"
  master_password     = random_password.master.result

  vpc_security_group_ids = [aws_security_group.aurora.id]
  db_subnet_group_name   = aws_db_subnet_group.aurora.name

  backup_retention_period = var.environment == "prod" ? 7 : 1
  preferred_backup_window = "19:00-20:00"  # UTC (KST 04:00-05:00)

  skip_final_snapshot = var.environment != "prod"
}

resource "aws_rds_cluster_instance" "aurora_instances" {
  count              = var.environment == "prod" ? 2 : 1
  identifier         = "${local.identifier}-${count.index}"
  cluster_identifier = aws_rds_cluster.aurora_cluster.id
  instance_class     = "db.r6g.large"
  engine             = aws_rds_cluster.aurora_cluster.engine
  engine_version     = aws_rds_cluster.aurora_cluster.engine_version
}
```

### Security Group 패턴

```hcl
resource "aws_security_group" "aurora" {
  name   = "${local.identifier}-sg"
  vpc_id = data.aws_vpc.main.id
}

# EKS에서 접근
resource "aws_security_group_rule" "eks_ingress" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = data.aws_security_group.eks.id
  security_group_id        = aws_security_group.aurora.id
}
```

### 참조 파일

| 파일 | 특징 |
|------|------|
| `src/socraai/domain/prod/rds/rds.tf` | Aurora PostgreSQL + RDS Proxy 포함 |
| `src/socraai/domain/prod/rds/sg.tf` | SG 규칙 (EKS + Databricks + VPN) |
| `src/socraai/domain/prod/rds/iam.tf` | RDS Proxy IAM |

---

## Security Group

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| 대상 리소스 | Yes | — |
| 소스 | Yes | — (SG ID 또는 CIDR) |
| 포트 | Yes | — |
| 프로토콜 | No | tcp |
| 방향 | No | ingress |

### 패턴

```hcl
# SG 기반 인바운드
resource "aws_security_group_rule" "from_eks" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = data.aws_security_group.eks.id
  security_group_id        = aws_security_group.target.id
}

# CIDR 기반 인바운드
resource "aws_security_group_rule" "from_vpn" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = ["10.100.0.0/16"]  # Seoul VPC (VPN)
  security_group_id = aws_security_group.target.id
}
```

### 자주 사용하는 소스

| 소스 | CIDR / SG | 용도 |
|------|-----------|------|
| EKS Prod | SG (태그 lookup) | Pod → RDS/ElastiCache |
| VPN | `10.100.0.0/16` | 개발자 로컬 접근 |
| Databricks | SG (태그 lookup) | 데이터 파이프라인 |
| Tokyo VPC | `10.0.0.0/16` | 같은 VPC 내부 통신 |

---

## ElastiCache (Valkey/Redis)

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| Sphere | Yes | — |
| 환경 | Yes | — |
| 엔진 | No | valkey (신규) / redis (기존) |
| 노드 타입 | No | cache.t4g.micro (dev) / cache.r7g.large (prod) |
| 클러스터 모드 | No | disabled |
| 레플리카 수 | No | dev=0, prod=1 |

---

## IRSA (K8s Service Account)

### 필수 정보

| 필드 | 필수 | 기본값 |
|------|------|--------|
| Sphere | Yes | — |
| Circle | Yes | — |
| 환경 | Yes | — |
| 네임스페이스 | No | {sphere}-{circle} |
| 권한 (Statement) | Yes | — |

### 참조 파일

| 파일 | 특징 |
|------|------|
| `src/socraai/domain/prod/irsa/irsa.tf` | S3 full access |
| `src/socraai/domain/dev/irsa/irsa.tf` | dev 환경 IRSA |

---

## 데이터 소스 (공통으로 자주 사용)

```hcl
# VPC
data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = ["main"]
  }
}

# Private Subnets
data "aws_subnets" "main_private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }
  filter {
    name   = "tag:subnetType"
    values = ["private"]
  }
}

# EKS Security Group
data "aws_security_group" "eks" {
  filter {
    name   = "tag:aws:eks:cluster-name"
    values = ["infra-k8s-${var.environment}"]
  }
}

# ACM Certificate (us-east-1 for CloudFront)
data "aws_acm_certificate" "this" {
  domain   = "*.${var.environment}.riiid.cloud"
  statuses = ["ISSUED"]
  provider = aws.virginia
}

# OIDC Provider (for IRSA)
data "aws_iam_openid_connect_provider" "this" {
  url = "https://oidc.eks.ap-northeast-1.amazonaws.com/id/CLUSTER_ID"
}
```

---

## 환경별 기본값 가이드

| 설정 | dev | stg | prod |
|------|-----|-----|------|
| AZ | Single | Single | Multi |
| RDS 인스턴스 수 | 1 | 1 | 2+ |
| RDS 인스턴스 타입 | db.t4g.medium | db.r6g.large | db.r6g.large+ |
| 백업 보존 | 1일 | 3일 | 7일 |
| 삭제 보호 | false | false | true |
| WAF | 없음 | 없음 | 있음 (선택) |
| ElastiCache 레플리카 | 0 | 0 | 1 |
