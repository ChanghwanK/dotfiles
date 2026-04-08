# Amazon ElastiCache (Valkey) — 개발자를 위한 개념 가이드

## 한줄 요약

`docker-compose`의 `redis` 컨테이너를 AWS가 운영해주는 것.
우리 팀은 Redis 대신 **Valkey** (Redis 오픈소스 포크)를 사용한다.

## 개발자에게 익숙한 비유

로컬에서 쓰는 Redis와 완전히 동일. 접속 방법도 같다:
`redis-cli -h {endpoint} -p 6379`

Valkey는 Redis 7.2와 100% 호환되므로 기존 Redis 클라이언트(`redis-py`, `ioredis` 등)를 그대로 사용할 수 있다.

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **복제 그룹(Replication Group)** | master-replica 구조. 고가용성 | dev는 1노드, prod는 2+ 노드 |
| **노드 타입** | 서버 사양 | `cache.t3.micro` (dev), `cache.r6g.large` (prod) |
| **파라미터 그룹** | `redis.conf` 설정 | `maxmemory-policy` 등 |
| **클러스터 모드** | 샤딩 지원 (대용량) | 일반적으로 비활성화 |
| **Failover** | 마스터 장애 시 복제본이 자동 승격 | Multi-AZ에서 동작 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/valkey/valkey.tf`
- **엔진**: Valkey 8.1 (Redis 호환)
- **Security Group**: `src/{sphere}/{circle}/{env}/valkey/sg.tf` (별도 파일)
- **엔드포인트**: 생성 후 자동으로 Secrets Manager에 저장 (`{sphere}/{circle}/{env}/valkey`)
- **환경별 차이**:

| 설정 | dev | prod |
|------|-----|------|
| 노드 수 | 1 (replica 없음) | 2+ |
| 인스턴스 | `cache.t3.micro` | `cache.r6g.large` 이상 |
| Multi-AZ | false | true (권장) |
| 자동 장애조치 | false | true |

## 결정해야 할 사항 체크리스트

- [ ] 용도: API 응답 캐시 / 세션 스토어 / 작업 큐 / 기타?
- [ ] 예상 메모리: 데이터가 얼마나 쌓일 것 같은지?
- [ ] 영속성 필요 여부: Redis가 재시작되면 데이터 날아가도 되는지?
- [ ] 환경: dev만? 전체?
- [ ] maxmemory 정책: `allkeys-lru` (캐시) / `noeviction` (세션)?

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 Valkey(ElastiCache) 생성
- 용도: {캐시 / 세션 스토어 / 기타}
- 환경: {dev / stg / prod}
- 예상 메모리: {GB 단위 또는 "기본값 사용"}
- 특이사항: {maxmemory 정책, 복제본 수 등}
```
