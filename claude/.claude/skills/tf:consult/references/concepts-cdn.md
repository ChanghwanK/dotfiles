# Amazon CloudFront — 개발자를 위한 개념 가이드

## 한줄 요약

nginx의 reverse proxy + 캐시를 전세계에 깔아놓은 것.
S3의 파일을 사용자에게 가장 가까운 서버(Edge)에서 빠르게 제공한다.

## 개발자에게 익숙한 비유

S3 앞에 nginx CDN을 붙인 구조:
`사용자 브라우저 → CloudFront(캐시) → S3(원본)`

CloudFront 없이 S3를 직접 공개하면 보안 위험이 있고 느리다. CloudFront를 통하면:
- 전세계 Edge에서 캐시 제공 (빠름)
- S3 버킷을 인터넷에 직접 노출하지 않아도 됨 (안전)
- HTTPS 자동 지원

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **Distribution** | CloudFront 설정 1개 = CDN 엔드포인트 1개 | `d1abc.cloudfront.net` |
| **Origin** | 원본 서버 (S3 버킷 또는 API) | `riiid-socraai-domain-dev.s3.ap-northeast-1.amazonaws.com` |
| **OAC (Origin Access Control)** | CloudFront만 S3에 접근하도록 제한하는 인증 | 최신 방식 (OAI 대체) |
| **Cache Behavior** | URL 패턴별 캐시 규칙 | `/api/*`는 캐시 안 함 |
| **Custom Domain** | `cdn.example.com` 같은 도메인 연결 | ACM 인증서 필요 |
| **CORS** | 브라우저에서 다른 도메인의 CloudFront에 요청 허용 | 헤더 포워딩으로 처리 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/cloudfront/cloudfront.tf`
- **패턴**: S3 버킷은 `data "aws_s3_bucket"` 으로 참조 (별도 state)
- **OAC**: 항상 OAC 방식 사용 (레거시 OAI 사용 금지)
- **S3 버킷 정책**: CloudFront OAC + 백엔드 IAM을 `source_policy_documents`로 결합
- **환경별 차이**:

| 설정 | dev | prod |
|------|-----|------|
| 커스텀 도메인 | 없음 (CloudFront 기본 도메인) | 서비스 도메인 연결 |
| ACM 인증서 | 불필요 | us-east-1 리전에서 발급 필요 |
| 가격 클래스 | All (또는 100) | All (전세계) |

## 결정해야 할 사항 체크리스트

- [ ] S3 버킷이 이미 있나요? (없으면 먼저 S3 생성 필요)
- [ ] 커스텀 도메인 필요 여부: `cdn.example.com` 형태?
- [ ] CORS 설정 필요 여부: 브라우저에서 직접 다운로드?
- [ ] 캐시 TTL: 파일이 얼마나 자주 변경되나요?
- [ ] 프라이빗 콘텐츠: 인증된 사용자만 접근 가능해야 하나요? (Signed URL 필요)

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 CloudFront Distribution 생성
- Origin S3 버킷: {버킷 이름 또는 "새로 생성 필요"}
- 커스텀 도메인: {도메인 / 없음}
- CORS: {허용할 도메인 목록 / 없음}
- 프라이빗 콘텐츠: {필요 / 불필요}
- 환경: {dev / stg / prod}
```
