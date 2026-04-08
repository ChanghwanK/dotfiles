# AWS IAM / IRSA — 개발자를 위한 개념 가이드

## 한줄 요약

K8s Pod가 S3, RDS 등 AWS 서비스에 접근하기 위한 권한 설정.
**IRSA**: K8s ServiceAccount와 IAM Role을 연결하는 방식 (우리 팀 표준).

## 개발자에게 익숙한 비유

OAuth2의 서비스 계정 버전:
- **IAM Role** = 권한 묶음 (어떤 작업을 할 수 있는지)
- **IAM Policy** = 구체적인 허용/거부 규칙 (S3 읽기, Secrets Manager 조회 등)
- **IRSA** = K8s ServiceAccount에 IAM Role을 연결하는 설정

```
Pod (K8s ServiceAccount) → IRSA → IAM Role → IAM Policy → AWS 서비스
```

`AWS_ACCESS_KEY_ID` 하드코딩 없이 Pod에서 AWS SDK를 사용할 수 있게 해준다.

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **IAM Role** | 권한 묶음. "이 역할을 가진 주체는 이것을 할 수 있다" | `socraai-domain-prod` |
| **IAM Policy** | 구체적 허용/거부 규칙 | `s3:GetObject`, `secretsmanager:GetSecretValue` |
| **IRSA** | K8s SA + IAM Role 연결. EKS OIDC 기반 | Pod에서 AWS SDK 자동 인증 |
| **Least Privilege** | 최소 권한 원칙. 필요한 것만 허용, 와일드카드(`*`) 금지 | `s3:GetObject` O, `s3:*` X |
| **ARN 스코프** | 어느 리소스까지 허용할지 범위 지정 | 특정 버킷만, 특정 시크릿만 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/irsa/irsa.tf`
- **방식**: `terraform-aws-irsa` 모듈 사용 (v1.0.0)
- **명명**: `{sphere}-{circle}-{env}` → 예: `socraai-domain-prod`
- **ARN 규칙**: `arn:aws:s3:::riiid-{sphere}-{circle}-{env}/*` (sphere 전용 리소스만)

**최소 권한 원칙 (팀 정책):**
```
✅ 올바른 예시:
- s3:GetObject, s3:PutObject (읽기/쓰기만)
- secretsmanager:GetSecretValue (읽기만)
- ecr:GetDownloadUrlForLayer, ecr:BatchGetImage (pull만)

❌ 금지:
- s3:* (전체 권한)
- "*" (모든 서비스)
- secretsmanager:* (전체 권한)
```

## 결정해야 할 사항 체크리스트

- [ ] 어떤 AWS 서비스에 접근해야 하나요?
- [ ] 읽기만? 쓰기도? 삭제도?
- [ ] 특정 리소스만 허용? (특정 버킷, 특정 시크릿 경로만)
- [ ] 어떤 K8s Namespace/ServiceAccount에 연결할 건가요?

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 IRSA(IAM Role) 생성
- 접근할 AWS 서비스:
  - S3: {읽기 / 쓰기}, 대상 버킷: {버킷 이름}
  - Secrets Manager: {읽기}, 경로: {secret prefix}
  - ECR: {pull 권한}
- K8s namespace: {namespace 이름}
- K8s ServiceAccount: {sa 이름}
- 환경: {dev / stg / prod}
```
