# Amazon RDS / Aurora — 개발자를 위한 개념 가이드

## 한줄 요약

`docker-compose`의 `postgres` 컨테이너를 AWS가 운영해주는 것.
백업, 패치, 장애조치를 AWS가 자동으로 처리한다.

## 개발자에게 익숙한 비유

로컬 개발에서 쓰는 PostgreSQL과 완전히 동일한 DB. 단, 서버 관리를 AWS가 해준다.
접속 방법도 동일하다: `psql -h {endpoint} -U {user} -d {dbname}`

**Aurora vs RDS 단일 인스턴스:**
- `aurora postgresql`: 고성능 클러스터 버전. 읽기 복제본 추가가 쉬움. prod 권장
- `rds mysql/postgres`: 단순한 단일 인스턴스. 비용이 더 저렴

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **인스턴스 클래스** | 서버 사양 (CPU/RAM) | `db.t3.micro` (dev), `db.r7g.large` (prod) |
| **파라미터 그룹** | `postgresql.conf` 설정 파일 | `max_connections`, `log_min_duration` |
| **서브넷 그룹** | DB를 어느 네트워크에 배치할지 | private subnet (인터넷 직접 접근 불가) |
| **스냅샷** | DB 백업. 특정 시점으로 복원 가능 | 자동 스냅샷 (7일 보관) |
| **읽기 복제본** | 읽기 전용 복사본. 읽기 부하 분산용 | Aurora에서 쉽게 추가 가능 |
| **RDS Proxy** | DB 연결 풀링. 서버리스/Lambda 환경에서 유용 | socraai prod에서 사용 중 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/{env}/rds/`
- **엔진**: Aurora PostgreSQL 15+ 주로 사용 (socraai, santa 등)
- **비밀번호**: `random_password`로 자동 생성 → Secrets Manager에 자동 저장
- **prod에만 RDS 있는 경우가 많음** (dev/stg는 비용 절약을 위해 생략하기도 함)
- **환경별 차이**:

| 설정 | dev | prod |
|------|-----|------|
| 인스턴스 | `db.t3.micro` | `db.r7g.large` 이상 |
| Multi-AZ | false | 상황에 따라 |
| 자동 백업 | 최소 | 7일 이상 |
| RDS Proxy | 미사용 | 사용 권장 |

## 결정해야 할 사항 체크리스트

- [ ] DB 엔진: PostgreSQL / MySQL?
- [ ] 환경: dev만? prod만? 모두?
- [ ] 예상 데이터 크기: 초기 수 GB / 수십 GB 이상?
- [ ] 읽기 트래픽: 읽기 복제본이 필요할 만큼 많은가?
- [ ] 연결 방식: K8s Pod에서 접근? Lambda에서 접근? (RDS Proxy 필요 여부)

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 RDS 생성
- 엔진: Aurora PostgreSQL / RDS MySQL
- 환경: {dev / stg / prod}
- 인스턴스 크기: {요구사항 또는 "기본값 사용"}
- RDS Proxy: {필요 / 불필요}
- 특이사항: {읽기 복제본 필요, 특정 파라미터 등}
```
