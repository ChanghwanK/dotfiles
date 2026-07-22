# Source Policy: T1/T2 전용

infra-design 스킬의 소스 채택 기준. **커뮤니티 소스(T3)는 검색·인용 모두 배제한다.**

---

## Tier 정의

### T1: 공식 문서 (설계 근거의 기본)

해당 기술의 벤더/프로젝트가 직접 발행한 문서. limit·quota·기본값·동작 방식·모범사례의 유일한 확정 근거.

| 도메인 | T1 도메인 예시 |
|--------|---------------|
| AWS | `docs.aws.amazon.com`, `aws.amazon.com/blogs/architecture`, `aws.amazon.com/blogs/networking-and-content-delivery` |
| Kubernetes | `kubernetes.io/docs`, `github.com/kubernetes` (KEP·공식 리포) |
| ClickHouse | `clickhouse.com/docs` |
| Strimzi / Kafka | `strimzi.io/docs`, `kafka.apache.org/documentation` |
| CNCF 프로젝트 | 각 프로젝트 공식 docs (`istio.io`, `argo-cd.readthedocs.io`, `keda.sh` 등) |
| Terraform | `developer.hashicorp.com/terraform`, `registry.terraform.io` |

AWS 공식 blog(architecture/networking 카테고리)와 Well-Architected Framework는 T1로 취급한다 (벤더 공식 발행물).

### T2: 권위 사이트 + 빅테크 엔지니어링 블로그

T1이 답하지 못한 공백(설계 패턴의 실전 검증, 대규모 운영 수치)을 채울 때만 사용.

- **권위 레퍼런스**: Wikipedia(개념·역사), IETF RFC, CNCF 공식 blog·백서
- **빅테크 엔지니어링 블로그**: Netflix TechBlog, Uber Engineering, Cloudflare Blog, Meta Engineering, Google Cloud Blog, LinkedIn Engineering, Shopify Engineering, Slack Engineering 등 (기업 공식 엔지니어링 조직 발행물만)
- **DB/데이터 벤더 blog**: ClickHouse Blog, Confluent Blog 등은 자사 제품 관련 주장에 이해관계 하향을 적용한다 (경쟁 비교 주장은 인용 금지, 아키텍처 해설은 인용 가능)

### T3: 커뮤니티 (배제)

Reddit, Stack Overflow, 개인 블로그, Medium 개인 계정, HN 코멘트는 **검색 대상에서 제외한다** (`WebSearch` 시 allowed_domains를 T1/T2로 제한). 설계 근거는 검증 가능한 공식 자료여야 하기 때문이다.

---

## 최신성 판정

1. **버전 anchor**: 버전이 설계를 좌우하는 주제(K8s API, ClickHouse 기능, Strimzi CRD)는 공식 releases/changelog를 먼저 fetch해 현재 최신 버전을 확정한다.
2. **versioned URL trap**: URL에 버전 세그먼트(`/v1.18/`, `/docs/9.1/`, `archive.`)가 있으면 구버전 문서다. current/latest 경로로 바꿔 fetch한다. 검색엔진은 구버전 공식 문서를 상위 랭킹하는 경우가 많다.
3. **Rolling docs (버전 체계 없는 문서)**: AWS 문서처럼 버전 세그먼트 없이 조용히 갱신되는 문서는 버전 anchor 비교를 생략하고 현행(latest)으로 간주한다. 단, 기능의 신규성·GA 여부·리전 지원 여부는 본문만으로 단정하지 않고 What's New·release announcement(`aws.amazon.com/new` 등)로 별도 확인한다 (rolling docs는 preview 기능을 이미 서술하거나, 리전별 미지원을 본문에 안 적는 경우가 있다).
4. **stale 판정**: window(빠른 기술 1~2년, 안정 기술 3~5년)를 벗어난 소스는 changelog로 변경 여부를 확인한다:
   - `stale-confirmed`: 이후 변경 확인됨 → 인용 금지, 최신 소스로 대체
   - `stale-suspect`: 변경 여부 미확인 → 핵심 근거로 쓰지 않고 재검색
   - `dated-valid`: 변경 없음 확인 → 정상 인용
5. 본문에 "out-of-date version" 배너가 보이면 인용 금지, 최신 경로로 재fetch.

---

## 인용 규칙

- 각 주장 뒤 인라인 `[n]`, References에 `[n] 제목 · URL · T1/T2 · 날짜(또는 대상 버전)` 매핑
- limit·quota·기본값·비용 단가 등 시간 가변 수치는 T1 근거 필수
- 소스 간 상충 시 양쪽을 명시하고 어느 쪽을 채택했는지 이유를 적는다
- verbatim 확보 원칙: 설정 예시·YAML·수치는 소스 원문 그대로 옮긴다. 직접 조합한 예시는 `구성 예시(문서 미검증)`로 표기한다
