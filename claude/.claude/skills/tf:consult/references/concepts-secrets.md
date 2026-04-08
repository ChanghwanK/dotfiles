# AWS Secrets Manager — 개발자를 위한 개념 가이드

## 한줄 요약

`.env` 파일의 클라우드 버전. 값이 암호화 저장되고, 접근 로그가 남고, IAM으로 권한을 통제한다.

## 개발자에게 익숙한 비유

`dotenv`가 로컬 파일에 시크릿을 보관한다면, Secrets Manager는 AWS 서버에 안전하게 보관.
K8s에서는 **External Secrets Operator**가 Secrets Manager의 값을 자동으로 K8s Secret으로 주입해준다.

```
Secrets Manager → External Secrets Operator → K8s Secret → Pod (환경변수)
```

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **Secret** | 하나의 시크릿 항목 (JSON 또는 단순 문자열) | `socraai/domain/prod/rds` |
| **Secret 경로(이름)** | 계층적 이름. `/`로 구분 | `{sphere}/{circle}/{env}/{name}` |
| **버전(Version)** | 값 변경 이력. 이전 버전으로 롤백 가능 | `AWSCURRENT`, `AWSPREVIOUS` |
| **자동 로테이션** | DB 비밀번호 등을 주기적으로 자동 변경 | RDS와 연동 가능 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/secretmanager/secretmanager.tf`
- **이름 규칙**: `{sphere}/{circle}/{env}/{resource-name}`
  - 예: `socraai/domain/dev/rds`, `socraai/domain/dev/valkey`
- **패턴**: `secretmanager/`는 **빈 컨테이너만 생성**. 실제 값은 해당 리소스(RDS, Valkey 등)가 생성 후 채움
- **K8s 연동**: External Secrets Operator가 자동으로 K8s Secret으로 동기화
- **환경별 차이**: 환경별로 각각 생성 (dev/stg/prod 독립)

## 결정해야 할 사항 체크리스트

- [ ] 어떤 시크릿이 필요한가? (DB 비밀번호, API 키, OAuth 토큰 등)
- [ ] 시크릿 이름 목록: `{sphere}/{circle}/{env}/` 이후 경로
- [ ] K8s Pod에서 환경변수로 주입 받을 것인가? (External Secrets Operator 연동)
- [ ] 자동 로테이션 필요 여부 (RDS 비밀번호 등)

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 Secrets Manager 시크릿 생성
- 시크릿 목록:
  - {sphere}/{circle}/{env}/{name1}: {용도 설명}
  - {sphere}/{circle}/{env}/{name2}: {용도 설명}
- K8s 환경변수 주입: {필요 / 불필요}
- 환경: {dev / stg / prod}
```
