# Amazon S3 — 개발자를 위한 개념 가이드

## 한줄 요약

서버의 `/uploads` 디렉토리를 클라우드로 옮긴 것. HTTP API로 파일을 읽고 쓴다.

## 개발자에게 익숙한 비유

로컬 파일시스템의 클라우드 버전. 단, HTTP API로만 접근하고 용량 제한이 없다.
Spring의 `MultipartFile`을 로컬에 저장하는 대신 S3에 올린다고 생각하면 된다.

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **버킷(Bucket)** | 최상위 폴더. 이름이 전 세계에서 유일해야 함 | `riiid-socraai-domain-dev` |
| **객체(Object)** | 버킷 안의 파일 + 메타데이터 | `images/user/profile.jpg` |
| **버저닝(Versioning)** | Git처럼 파일의 이전 버전 보관 | prod에서 활성화 권장 |
| **수명주기(Lifecycle)** | 오래된 파일 자동 삭제/아카이브 규칙 | 30일 후 Glacier로 이동 |
| **접근 제어(ACL/Policy)** | 누가 이 버킷에 접근 가능한지 | public/private, OAC |
| **CORS** | 브라우저에서 다른 도메인의 S3에 업로드/다운로드 허용 | 프론트엔드 직접 업로드 시 필요 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/s3/s3.tf`
- **이름 규칙**: `riiid-{sphere}-{circle}-{env}` → 예: `riiid-socraai-domain-prod`
- **보안 기본값**: 항상 Public Access Block, BucketOwnerEnforced 설정
- **CloudFront 연동**: 프론트엔드용 파일은 S3 단독 공개 대신 CloudFront OAC 방식 사용
- **환경별 차이**:

| 설정 | dev | prod |
|------|-----|------|
| 버저닝 | Disabled | Enabled |
| 수명주기 | 미설정 | 상황에 따라 |
| CORS | 개발 도메인 허용 | 서비스 도메인만 허용 |

## 결정해야 할 사항 체크리스트

- [ ] 파일 종류: 이미지? 동영상? 문서? 백업?
- [ ] 접근 방식: 백엔드만 접근? 프론트엔드도 직접 업로드?
- [ ] 공개 여부: 누구나 다운로드 가능? (CloudFront 통해서만?)
- [ ] 보관 기간: 영구 보관? 일정 기간 후 삭제?
- [ ] CORS 필요 여부: 브라우저에서 직접 S3 API를 호출하나요?

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 S3 버킷 생성
- 용도: {파일 종류 설명}
- 접근: {백엔드 전용 / CloudFront 연동 / 프론트엔드 직접 업로드}
- CORS: {필요 / 불필요}, 허용 도메인: {도메인 목록}
- 환경: {dev / stg / prod}
```
