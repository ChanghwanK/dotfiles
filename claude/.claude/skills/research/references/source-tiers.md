# Source Tiers — 소스 공신력 tier 정의 + 검색 패턴

`research` 스킬이 tier cascade 검색 시 참조하는 소스 분류와 쿼리 구성 가이드.

---

## Tier 정의

| Tier | 이름 | 포함 소스 | 신뢰도 | 언제 쓰나 |
|------|------|-----------|--------|-----------|
| **T1** | 공식 문서 | 프로젝트 공식 docs 사이트, RFC/W3C/IETF 등 표준, 공식 GitHub repo·release notes·design proposal(KEP/PEP 등) | 최상 (1차 출처) | 항상 먼저. 정의·스펙·API·버전 변화의 기준 |
| **T2** | 권위 사이트 | Wikipedia, MDN, 표준 기술 레퍼런스, 벤더 공식 엔지니어링 블로그, 학술/피어리뷰 자료 | 높음 (검증된 2차) | T1이 없거나 개괄·배경·용어 정리가 필요할 때 |
| **T3** | 커뮤니티 | 개인/회사 기술 블로그, Reddit, Stack Overflow, Hacker News, Dev.to, Medium | 보통 (경험·의견) | 실무 함정, 최신 릴리스 반응, 상세 트러블슈팅, 사용자 경험 |

**판정 원칙**: 같은 사실을 여러 tier가 말하면 상위 tier를 인용한다. tier는 아래 "주장별 신뢰 등급"의 시작값이 된다.

---

## Starter 권위 도메인 (seed)

LLM이 대상 기술의 공식 도메인을 추론할 때의 출발점. 여기 없어도 기술명 + "official docs"로 공식 도메인을 먼저 찾는다.

| 도메인/기술 | T1 공식 docs |
|-------------|--------------|
| Kubernetes | `kubernetes.io`, `github.com/kubernetes` |
| Python | `docs.python.org`, `peps.python.org` |
| 웹 표준/JS/CSS | `developer.mozilla.org`, `w3.org`, `whatwg.org` |
| React | `react.dev` |
| Go | `go.dev` |
| Rust | `doc.rust-lang.org` |
| AWS | `docs.aws.amazon.com` |
| GCP | `cloud.google.com/docs` |
| Azure / MS | `learn.microsoft.com` |
| Terraform | `developer.hashicorp.com` |
| Docker | `docs.docker.com` |
| PostgreSQL | `postgresql.org/docs` |
| Istio | `istio.io` |
| Prometheus | `prometheus.io/docs` |
| RFC/IETF | `datatracker.ietf.org`, `rfc-editor.org` |

**T2 공통**: `en.wikipedia.org`
**T3 공통**: `reddit.com`, `stackoverflow.com`, `news.ycombinator.com`

---

## WebSearch 쿼리 구성 패턴

- **연도 주입**: 쿼리 끝에 현재 연도를 붙여 최신 결과를 유도. 예: `Kubernetes ValidatingAdmissionPolicy GA 2026`
  - **단, 공식 docs 검색에는 역효과 주의**: 공식 문서 본문에는 연도 문자열이 거의 없어, 연도 쿼리가 canonical 문서를 탈락시키고 연도가 박힌 블로그류만 남길 수 있다. T1 검색은 연도 대신 **버전 번호 또는 `release notes` / `changelog` / `what's new` 키워드**를 우선하고, 결과가 빈약하면 연도를 빼고 재검색한다. 연도 주입은 T3(블로그·커뮤니티)·뉴스성 검색에서 효과적이다.
- **allowed_domains로 tier 강제**: T1 검색 시 공식 도메인만 허용.
  ```
  WebSearch(query="Kubernetes Mutating Admission Policy 2026",
            allowed_domains=["kubernetes.io", "github.com"])
  ```
- **blocked_domains로 노이즈 제거**: 콘텐츠팜·SEO 스팸·번역 스크랩 사이트를 제외.
- **버전 명시**: 버전 의존 주제는 버전을 쿼리에 포함. 예: `Istio 1.22 ambient mode 2026`
- **표준/스펙 조회**: RFC/PEP/KEP 번호를 알면 직접 검색해 1차 출처로.

---

## 버전드 공식 문서 함정 (versioned docs trap)

검색엔진은 **아카이브된 구버전 공식 문서를 최신 문서보다 높게 랭킹**하는 경우가 많다 (구버전 URL이 오래 존재해 백링크가 많음). T1 도메인이라는 이유로 그대로 인용하면 "공식 문서인데 틀린 정보"가 된다. fetch 전/후에 URL과 본문을 반드시 점검한다.

**URL 정규화 규칙**: 인용 전에 URL에 버전 세그먼트가 있는지 확인하고, current/latest가 아니면 정규화한 URL로 다시 fetch한다. 내용이 다르면 최신 버전을 인용하고 변경 사실을 명시한다.

| 프로젝트 | 구버전 URL 패턴 (함정) | 최신 URL |
|----------|------------------------|----------|
| PostgreSQL | `postgresql.org/docs/<N>/` (예: `/docs/9.1/`) | `postgresql.org/docs/current/` |
| Istio | `istio.io/v<X.Y>/`, `archive.istio.io` | `istio.io/latest/` |
| Kubernetes | `v1-<XX>.docs.kubernetes.io` | `kubernetes.io/docs/` (main = latest) |
| Django | `docs.djangoproject.com/en/<X.Y>/` | `/en/stable/` |
| Read the Docs 계열 | `<proj>.readthedocs.io/en/<tag>/` | `/en/stable/` (없으면 `/en/latest/`) |
| Kafka | `kafka.apache.org/<NN>/documentation` | `kafka.apache.org/documentation` |
| Spring | `docs.spring.io/.../docs/<version>/` | `docs.spring.io/<proj>/reference/` |
| Terraform provider | registry의 특정 버전 경로 | `registry.terraform.io/providers/.../latest/docs` |
| Node.js | `nodejs.org/docs/v<X>/api` | `nodejs.org/docs/latest/api` |

여기 없는 프로젝트도 같은 원리로 판단한다: URL에 `v1.2` / `2.x` / `archive` / `legacy` 세그먼트가 보이면 일단 의심하고 latest 경로를 찾는다.

**본문 배너 감지**: 구버전 문서는 대부분 상단에 "This documentation is for an out-of-date version" / "You are viewing docs for an older release" 류의 배너가 있다. WebFetch 결과에 이 문구가 보이면 그 페이지는 인용 금지, 최신 경로로 재fetch한다.

**GitHub 소스 주의**: `github.com`은 T1이지만 시간축이 없는 상태로 검색된다.
- release note는 `releases/latest` 또는 릴리스 날짜를 확인하고 최신 릴리스 기준으로 인용한다.
- issue/discussion은 작성일과 open/closed 상태를 확인한다. 수년 전 closed issue의 결론은 이후 릴리스에서 바뀌었을 수 있으므로, 동작 관련 주장은 현재 문서·최신 릴리스 노트로 재확인한다.

---

## 최신성 판단 가이드

| 기술 변화 속도 | 예시 | 허용 window(대략) | stale 처리 |
|----------------|------|-------------------|-----------|
| 빠름 | K8s API, 클라우드 신규 기능, JS 프레임워크 | ~12개월 | 초과 시 `stale`, 변경 가능성 명시 |
| 보통 | 데이터베이스, 언어 표준 라이브러리 | ~24개월 | 초과 시 확인 필요 표기 |
| 느림/안정 | 네트워크 프로토콜, 자료구조/알고리즘, RFC | 연식 무관 | 개정판 존재 여부만 확인 |

**최신 버전 anchor (버전 민감 주제 MUST)**: 공식 문서는 게시 날짜가 없는 경우가 많아 날짜 기반 window 판정이 작동하지 않는다. 버전이 결과를 좌우하는 주제(K8s API, Istio 기능, DB 파라미터 등)는 조사 초반에 **공식 releases/changelog 페이지를 1회 fetch해 "현재 최신 버전 + 릴리스 날짜"를 anchor로 확정**한다. 이후 모든 소스는 달력 날짜가 아니라 "어느 버전을 다루는 문서인가"를 anchor와 비교해 stale 여부를 판정한다. anchor를 모델 내부 지식으로 단정하지 않는다 (모델 지식 자체가 stale일 수 있음). deprecated/GA 상태도 반드시 T1(공식 release notes·API reference)로 확정한다.

### 게시일/대상 버전 판정 우선순위

소스의 시점을 아래 순서로 확정한다. 상위 신호가 있으면 하위는 참고만 한다.

1. 페이지에 명시된 publish/updated date
2. URL 경로의 날짜 (`/2024/03/...`) 또는 버전 세그먼트
3. 본문이 다루는 대상 버전 → 그 버전의 릴리스 시기로 환산 (anchor 확정 시 changelog에서 확인 가능)
4. 검색 스니펫에 붙은 날짜 (약한 신호, 단독 사용 금지)
5. 전부 실패 → `(날짜 미상)` 표기. 날짜 미상 소스는 시간 가변 주장(아래)의 근거로 쓰지 않는다.

**SEO 날짜 갱신 함정**: updated date는 최근인데 본문이 구버전만 다루는 페이지가 있다 (날짜만 자동 갱신). 날짜와 본문 버전 단서가 상충하면 **버전 단서를 우선**한다.

### 주장 단위 분류: 시간 가변 vs 시간 불변

stale 판정은 소스 단위가 아니라 **주장 단위**로 내린다. 오래된 소스도 불변 주장은 유효할 수 있다.

| 분류 | 예시 | 취급 (신뢰 등급과 접속) |
|------|------|------------------------|
| **시간 가변** | 기본값·파라미터, API/필드 스펙, GA/deprecated 상태, 가격·쿼터·한도, 성능 수치, UI 조작 절차 | 등급 `낮음`이면 **T1 재확인 전 인용 금지** |
| **시간 불변** | 동작 원리·아키텍처 개념, 알고리즘, 트레이드오프 논리, 프로토콜 스펙(개정 확인 후) | `낮음`이어도 등급 표기 후 인용 가능 |

### stale 3단계 판정

window를 벗어났다는 것은 **의심 신호이지 확정이 아니다**. anchor·changelog로 실제 변경 여부를 확인해 세 라벨 중 하나로 확정한다.

1. 소스의 대상 버전/날짜를 식별한다 (위 우선순위).
2. window 내면 fresh, 판정 종료.
3. window 밖이면 changelog/release notes에서 **해당 내용이 그 후 바뀌었는지** 확인한다:

| 라벨 | 조건 | 행동 |
|------|------|------|
| `stale-confirmed` | 이후 변경이 changelog로 확인됨 | 인용 금지, 최신 소스로 대체. 변경 서사 자체가 필요하면 "구버전에서는 X, 현행은 Y" 형태로 신구 소스를 함께 인용 |
| `stale-suspect` | window 밖 + 변경 여부 확인 불가 | 시간 가변 주장의 근거 금지. 시간 불변 주장만 낮은 신뢰로 인용 + "이후 변경 가능성" 명시 |
| `dated-valid` | window 밖이지만 해당 내용의 변경 없음이 확인됨 | 정상 인용, 날짜만 표기 (stale 아님) |

**재검색 규칙**: 핵심 주장의 근거가 `stale-suspect` 이하뿐이면 표기만 하고 끝내지 않는다. `<기술> changelog` / `<기능> deprecated` / 버전 번호로 **1회 재검색**해 더 새로운 소스 또는 변경 확인 근거를 찾는다. 그래도 없으면 그때 라벨과 함께 인용한다.

**References 표기**: 날짜 뒤에 라벨을 붙인다. 예: `(T3, 2023-05, stale-suspect)` / `(T1, 2022-11, dated-valid)`. fresh는 라벨 생략.

---

## 주장별 신뢰 등급 (confidence grade)

tier·freshness·수렴도·이해관계의 신뢰 신호를 주장 단위의 단일 등급 `높음/중간/낮음`으로 합성한다. 가중합 점수가 아니라 **결정 규칙**이다 (LLM이 산출하는 숫자 점수는 보정이 안 되므로 쓰지 않는다).

1. **시작 등급 = 소스 tier**: T1 → `높음`, T2 → `중간`, T3 → `낮음`
2. **상향 (+1단계, 최대 높음)**: **독립** 소스 2개 이상이 같은 주장에 수렴
   - 독립 = 서로 인용·번역·스크랩 관계가 아닌 소스. 같은 원문을 재인용한 N개는 1개로 센다
3. **하향 (-1단계씩, 최저 낮음)**: 해당하는 것마다 적용
   - freshness가 `stale-suspect` 또는 `(날짜 미상)`
   - **벤더 이해관계**: 벤더 소스가 자사 제품 우위·경쟁 제품 비교를 주장할 때 (독립 소스로 교차 확인되면 하향 해제)
4. `dated-valid`는 하향 없음. `stale-confirmed`는 등급 산정 대상이 아니라 인용 금지 (stale 3단계 판정 참조)

**게이트 접속**: 시간 가변 주장이 `낮음`이면 T1 재확인 전 인용 금지. 시간 불변 주장은 `낮음`이어도 등급 표기 후 인용 가능.

**표기**: `높음`은 생략(기본값). `중간`/`낮음`만 주장 뒤에 사유와 함께 표기한다.
예: `- 기본 idleTimeout은 1h [3] (신뢰 낮음: T3 단일)` / `- ... [1][4] (신뢰 중간: T3 2건 수렴)`
