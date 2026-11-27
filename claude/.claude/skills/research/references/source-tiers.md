# Source Tiers: tier 정의, 최신성 판정, 신뢰 등급

## Tier 정의

| Tier | 포함 소스 | 언제 쓰나 |
|------|-----------|-----------|
| **T1** 공식 문서 | 공식 docs, RFC/W3C/IETF 등 표준, 공식 GitHub repo·release notes·design proposal(KEP/PEP 등) | 항상 먼저. 정의·스펙·API·버전 변화의 기준 |
| **T2** 권위 사이트 | Wikipedia, MDN, 표준 기술 레퍼런스, 벤더 공식 엔지니어링 블로그, 학술/피어리뷰 자료 | T1이 없거나 개괄·배경·용어가 필요할 때 |
| **T3** 커뮤니티 | 개인/회사 기술 블로그, Reddit, Stack Overflow, Hacker News, Dev.to, Medium | 실무 함정, 최신 릴리스 반응, 트러블슈팅, 사용자 경험 |

같은 사실을 여러 tier가 말하면 상위 tier를 인용한다.

## Starter T1 도메인

여기 없으면 기술명 + "official docs"로 공식 도메인부터 찾는다. RFC/PEP/KEP 번호를 알면 직접 검색한다.

| 기술 | T1 | 기술 | T1 |
|------|----|------|----|
| Kubernetes | `kubernetes.io`, `github.com/kubernetes` | AWS | `docs.aws.amazon.com` |
| Python | `docs.python.org`, `peps.python.org` | GCP | `cloud.google.com/docs` |
| 웹 표준/JS/CSS | `developer.mozilla.org`, `w3.org`, `whatwg.org` | Azure / MS | `learn.microsoft.com` |
| React | `react.dev` | Terraform | `developer.hashicorp.com` |
| Go | `go.dev` | Docker | `docs.docker.com` |
| Rust | `doc.rust-lang.org` | PostgreSQL | `postgresql.org/docs` |
| Istio | `istio.io` | Prometheus | `prometheus.io/docs` |
| RFC/IETF | `datatracker.ietf.org`, `rfc-editor.org` | | |

T2 공통: `en.wikipedia.org`. T3 공통: `reddit.com`, `stackoverflow.com`, `news.ycombinator.com`.

## 버전드 공식 문서 함정 (versioned docs trap)

검색엔진은 아카이브된 구버전 공식 문서를 최신보다 높게 랭킹하는 경우가 많다. URL에 버전 세그먼트가 있으면 아래처럼 정규화해 다시 fetch하고, 내용이 다르면 최신을 인용하며 변경 사실을 쓴다.

| 프로젝트 | 구버전 패턴 | 최신 |
|----------|-------------|------|
| PostgreSQL | `postgresql.org/docs/<N>/` | `/docs/current/` |
| Istio | `istio.io/v<X.Y>/`, `archive.istio.io` | `istio.io/latest/` |
| Kubernetes | `v1-<XX>.docs.kubernetes.io` | `kubernetes.io/docs/` |
| Django | `docs.djangoproject.com/en/<X.Y>/` | `/en/stable/` |
| Read the Docs 계열 | `<proj>.readthedocs.io/en/<tag>/` | `/en/stable/` (없으면 `/en/latest/`) |
| Kafka | `kafka.apache.org/<NN>/documentation` | `kafka.apache.org/documentation` |
| Spring | `docs.spring.io/.../docs/<version>/` | `docs.spring.io/<proj>/reference/` |
| Terraform provider | registry 특정 버전 경로 | `registry.terraform.io/providers/.../latest/docs` |
| Node.js | `nodejs.org/docs/v<X>/api` | `nodejs.org/docs/latest/api` |

표에 없어도 `v1.2`, `2.x`, `archive`, `legacy` 세그먼트는 의심하고 latest 경로를 찾는다.

**GitHub**: release note는 `releases/latest`나 릴리스 날짜로 최신 기준인지 확인한다. issue/discussion은 작성일과 open/closed를 확인하고, 오래된 closed issue의 동작 결론은 현재 문서·최신 릴리스 노트로 재확인한다.

## 최신성

| 변화 속도 | 예시 | window(대략) |
|-----------|------|--------------|
| 빠름 | K8s API, 클라우드 신규 기능, JS 프레임워크 | ~12개월 |
| 보통 | 데이터베이스, 언어 표준 라이브러리 | ~24개월 |
| 느림/안정 | 네트워크 프로토콜, 자료구조/알고리즘, RFC | 연식 무관(개정판 존재만 확인) |

공식 문서는 날짜가 없는 경우가 많으므로 버전 민감 주제는 "어느 버전을 다루는가"를 버전 anchor와 비교한다. anchor와 deprecated/GA 상태는 모델 지식으로 단정하지 않고 T1로 확정한다.

**시점 판정 우선순위**: 명시된 publish/updated date → URL의 날짜·버전 세그먼트 → 본문 대상 버전(릴리스 시기로 환산) → 검색 스니펫 날짜(단독 사용 금지) → 모두 실패하면 `(날짜 미상)`(시간 가변 주장의 근거로 쓰지 않는다). updated date는 최근인데 본문이 구버전만 다루면 버전 단서를 우선한다(SEO 날짜 자동 갱신).

**주장 단위 분류**: stale 판정은 소스가 아니라 주장 단위로 내린다.

| 분류 | 예시 | 취급 |
|------|------|------|
| 시간 가변 | 기본값·파라미터, API/필드 스펙, GA/deprecated, 가격·쿼터·한도, 성능 수치, UI 절차 | 등급 `낮음`이면 T1 재확인 전 인용 금지 |
| 시간 불변 | 동작 원리·아키텍처 개념, 알고리즘, 트레이드오프 논리, 프로토콜 스펙(개정 확인 후) | `낮음`이어도 등급 표기 후 인용 가능 |

### stale 3단계 판정

window 밖은 의심 신호일 뿐이다. changelog/release notes로 그 내용이 이후 바뀌었는지 확인해 라벨을 정한다.

| 라벨 | 조건 | 행동 |
|------|------|------|
| `stale-confirmed` | 이후 변경이 확인됨 | 인용 금지, 최신 소스로 대체. 변경 서사가 필요하면 "구버전 X, 현행 Y"로 신구를 함께 인용 |
| `stale-suspect` | 변경 여부 확인 불가 | 시간 가변 주장 근거 금지. 시간 불변 주장만 낮은 신뢰 + "이후 변경 가능성" |
| `dated-valid` | 변경 없음 확인 | 정상 인용, 날짜만 표기 |

핵심 주장의 근거가 `stale-suspect` 이하뿐이면 `<기술> changelog`, `<기능> deprecated`, 버전 번호로 1회 재검색하고, 그래도 없을 때만 라벨과 함께 인용한다. References에는 날짜 뒤에 라벨을 붙인다(예: `(T3, 2023-05, stale-suspect)`, fresh는 생략).

## 주장별 신뢰 등급 (confidence grade)

점수가 아니라 결정 규칙이다.

1. 시작 = tier: T1 `높음`, T2 `중간`, T3 `낮음`
2. +1(최대 높음): **독립** 소스 2개 이상 수렴. 서로 인용·번역·스크랩 관계인 소스는 1개로 센다
3. -1씩(최저 낮음): `stale-suspect` 또는 `(날짜 미상)`, 벤더가 자사 우위·경쟁 비교를 주장(독립 소스로 확인되면 해제)
4. `dated-valid`는 하향 없음. `stale-confirmed`는 산정 대상이 아니라 인용 금지

`높음`은 생략하고 `중간`/`낮음`만 사유와 함께 쓴다. 예: `- 기본 idleTimeout은 1h [3] (신뢰 낮음: T3 단일)`
