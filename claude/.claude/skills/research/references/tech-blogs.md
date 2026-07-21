# Tech Blogs — 국내외 엔지니어링 블로그 seed + 사례 추출 가이드

`research` 스킬의 **blog-insight 모드**(운영사례/인사이트 조사)가 참조하는 큐레이션 목록과 탐색·추출 패턴.
여기서 엔지니어링 블로그는 공백 보완재(T3)가 아니라 **1차 조사 대상**이다.

---

## 왜 별도 목록인가

표준 tier-cascade는 공식 문서(T1)를 우선하고 블로그(T3)를 낮춰 표기한다.
그러나 "다른 회사는 이 문제를 실제로 어떻게 운영/튜닝/복구했는가"는 공식 문서에 없다.
운영사례·장애 회고·마이그레이션 서사는 대부분 회사 엔지니어링 블로그에만 존재하므로,
이 목록을 seed로 삼아 블로그를 정면으로 탐색한다. (사실 검증은 여전히 T1/T2로 교차 확인)

---

## 국내 엔지니어링 블로그 (seed)

| 회사 | 도메인 | 강점 도메인 |
|------|--------|-------------|
| 우아한형제들 | `techblog.woowahan.com` | JVM/Spring, 대용량 트래픽, MSA, 배포 |
| 토스 | `toss.tech` | 금융 안정성, 대규모 트래픽, SRE, 데이터 |
| 카카오 | `tech.kakao.com` | 검색/추천, 인프라, 대규모 분산 |
| 카카오페이 | `tech.kakaopay.com` | 결제 신뢰성, 트랜잭션, 보안 |
| LINE / LY | `techblog.lycorp.co.jp`, `engineering.linecorp.com` | 글로벌 메신저, 대규모 스토리지, DB |
| 네이버 D2 | `d2.naver.com` | 검색엔진, 컴파일러/런타임, 시스템 |
| 쿠팡 | `medium.com/coupang-engineering` | 커머스 스케일, 물류, 데이터 파이프라인 |
| 당근 | `medium.com/daangn` | 로컬 서비스, 검색/추천, K8s 운영 |
| 마켓컬리 | `helloworld.kurly.com` | 커머스, 주문/재고, 배포 |
| 무신사 | `medium.com/musinsa-tech` | 커머스 트래픽, MSA 전환 |
| 뱅크샐러드 | `blog.banksalad.com` | 금융 데이터, DB, 인프라 |
| 요기요 | `techblog.yogiyo.co.kr` | 배달 실시간, 위치기반 |
| 쏘카 | `tech.socarcorp.kr` | 모빌리티, 데이터, 클라우드 운영 |
| 데브시스터즈 | `tech.devsisters.com` | 게임 인프라, K8s, GitOps, 카오스 |
| 하이퍼커넥트 | `hyperconnect.github.io` | 실시간 미디어, ML 서빙 |
| 오늘의집 | `www.bucketplace.com/post` | 커머스, 이미지/미디어, 스케일 |
| NHN Cloud | `meetup.nhncloud.com` | 클라우드 인프라, DB, 관측성 |
| 스포카 | `spoqa.github.io/tech` | 서비스 백엔드, 배포 |

**국내 애그리게이터(discovery)**: GeekNews `news.hada.io` · awesome-devblog `blog.gaerae.com/2016/02/devblog.html` (RSS 모음)

---

## 국외 엔지니어링 블로그 (seed)

| 회사 | 도메인 | 강점 도메인 |
|------|--------|-------------|
| Netflix | `netflixtechblog.com` | 대규모 스트리밍, 카오스/복원력, 관측성 |
| Uber | `uber.com/blog/engineering` | 분산 시스템, DB(Docstore), 스케줄링 |
| Cloudflare | `blog.cloudflare.com` | 네트워크, 엣지, 장애 회고(post-mortem) |
| Meta | `engineering.fb.com` | 초대규모 인프라, 스토리지, 캐시 |
| AWS Builders' Library | `aws.amazon.com/builders-library` | 운영 우수성 원리(재시도/타임아웃/배포 패턴) |
| Google SRE / Cloud | `sre.google`, `cloud.google.com/blog` | SRE 방법론, SLO, 안정성 |
| Stripe | `stripe.com/blog/engineering` | 결제 신뢰성, API 설계, 멱등성 |
| Dropbox | `dropbox.tech` | 스토리지, 대규모 마이그레이션 |
| Airbnb | `medium.com/airbnb-engineering` | 데이터 인프라, 서비스 전환 |
| Slack | `slack.engineering` | 실시간, 스케일, 배포 |
| Shopify | `shopify.engineering` | 커머스 스케일, Rails, DB 샤딩 |
| LinkedIn | `linkedin.com/blog/engineering` | Kafka 원조, 데이터 파이프라인 |
| DoorDash | `doordash.engineering` | 실시간 물류, 마이크로서비스 |
| Grab | `engineering.grab.com` | 동남아 모빌리티, 데이터 |
| Discord | `discord.com/blog` | 실시간 메시징, DB(ScyllaDB), 스케일 |
| Pinterest | `medium.com/pinterest-engineering` | 스토리지, ML 서빙, K8s |
| Zalando | `engineering.zalando.com` | 커머스, K8s 대규모 운영 |
| Datadog | `datadoghq.com/blog/engineering` | 관측성 내부 구조, 대규모 메트릭 |

**국외 애그리게이터(discovery)**: Hacker News `news.ycombinator.com` · InfoQ `infoq.com` · lobste.rs

---

## 탐색(discovery) 쿼리 패턴

- **도메인 배치 강제**: seed 도메인을 `allowed_domains`로 묶어 검색.
  ```
  WebSearch(query="Kafka consumer lag 운영 <현재 연도>",
            allowed_domains=["techblog.woowahan.com","toss.tech","d2.naver.com","medium.com"])
  WebSearch(query="Kafka consumer lag production incident <현재 연도>",
            allowed_domains=["netflixtechblog.com","uber.com","engineering.linkedin.com"])
  ```
  연도는 최신 글 우선 유도용이며, 결과가 빈약하면 연도를 빼고 재검색한다 (좋은 사례 글은 수년 전 게시가 많음).
- **관심 축 키워드 조합**: 기술 + 축을 붙인다. 국내는 한국어, 국외는 영어로.
  - 운영: `운영 / 튜닝 / 안정화` · `production / operating / tuning`
  - 장애: `장애 / 회고 / 트러블슈팅` · `incident / postmortem / outage`
  - 전환: `마이그레이션 / 도입기 / 전환` · `migration / adopting / moving to`
  - 스케일: `대용량 / 트래픽 / 스케일` · `at scale / high throughput`
- **애그리게이터 우회**: seed에 없는 회사 사례는 GeekNews/HN에서 `<기술> 사례`로 발굴 후 원문 도메인으로 fetch.
- **노이즈 제외**: 번역 스크랩·SEO 요약·콘텐츠팜은 `blocked_domains`로 제거하고 반드시 원문(1차 게시)으로 인용.

---

## 사례 카드 추출 필드 (WebFetch로 확인한 것만)

각 사례 글에서 아래를 추출한다. 본문에 없는 필드는 `(미상)`으로 남기고 지어내지 않는다.

| 필드 | 내용 |
|------|------|
| **회사/출처** | 어느 회사의 어느 글인가 (국내/국외 표기) |
| **규모/맥락** | 트래픽·데이터 규모, 스택, 왜 이 문제가 생겼나 |
| **문제** | 해결하려던 구체적 문제 (증상/제약) |
| **접근/해결** | 실제로 취한 방법 (설정값·아키텍처 변경 등 구체적으로) |
| **결과** | 개선 수치·효과 (있으면), 남은 한계 |
| **교훈** | 글이 강조한 재사용 가능한 원칙 |

---

## 인사이트 종합 기준 (사례 카드 → 교차 분석)

여러 사례 카드를 모은 뒤 아래 축으로 종합한다. 단순 요약 반복 금지.

- **공통 패턴**: 여러 회사가 동일하게 수렴한 접근 (강한 신호 → 검증된 모범사례)
- **접근 차이 = 트레이드오프**: 같은 문제를 다르게 푼 경우, 무엇이 그 선택을 갈랐나 (규모/비용/팀 역량)
- **반복되는 함정(안티패턴)**: 여러 사례가 공통으로 겪은 실수·후회 포인트
- **우리 인프라 적용 시사점**: SOCRA AI(K8s GitOps, dev/stg/prod, 비용 우선) 맥락에서 채택·주의할 점 한두 줄

**신뢰도 표기**: `references/source-tiers.md`의 confidence grade를 쓴다. 블로그 사례는 T3이므로 단일 사례 인사이트는 `낮음`, 독립 사례 2건 이상 수렴은 `중간`, T1/T2 교차 확인까지 되면 `높음`. 사유에 사례 수를 적는다. 예: `(신뢰 중간: 3건 수렴)` / `(신뢰 낮음: 단일 사례)`.
