# tf:consult References 조건부 로딩 가이드

사용자 발화에 해당 서비스 키워드가 있을 때만 Read로 로드한다. 전체 로드 금지.

| 트리거 키워드 | 로드할 파일 |
|------------|-----------|
| DB, 데이터베이스, PostgreSQL, MySQL, Aurora, RDS | `concepts-rds.md` |
| 캐시, Redis, Valkey, 세션, 인메모리, ElastiCache | `concepts-cache.md` |
| S3, 파일 저장소, 이미지 업로드, 버킷, 첨부파일 | `concepts-s3.md` |
| CDN, CloudFront, 정적 파일 서빙, 이미지 배포 | `concepts-cdn.md` |
| 시크릿, Secrets Manager, 환경변수, API 키 보관 | `concepts-secrets.md` |
| 메시지 큐, SQS, MQ, Amazon MQ, 비동기, Celery | `concepts-mq.md` |
| ECR, Docker registry, 컨테이너 이미지 저장 | `concepts-ecr.md` |
| IAM, IRSA, AWS 권한, 서비스 계정, Pod 권한 | `concepts-iam.md` |

> **기본값**: 로드 없음. 위 표를 보고 해당 파일만 로드한 뒤 개념 설명을 시작한다.
