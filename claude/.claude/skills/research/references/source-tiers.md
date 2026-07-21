# Source Tiers — 소스 공신력 tier 정의 + 검색 패턴

`research` 스킬이 tier cascade 검색 시 참조하는 소스 분류와 쿼리 구성 가이드.

---

## Tier 정의

| Tier | 이름 | 포함 소스 | 신뢰도 | 언제 쓰나 |
|------|------|-----------|--------|-----------|
| **T1** | 공식 문서 | 프로젝트 공식 docs 사이트, RFC/W3C/IETF 등 표준, 공식 GitHub repo·release notes·design proposal(KEP/PEP 등) | 최상 (1차 출처) | 항상 먼저. 정의·스펙·API·버전 변화의 기준 |
| **T2** | 권위 사이트 | Wikipedia, MDN, 표준 기술 레퍼런스, 벤더 공식 엔지니어링 블로그, 학술/피어리뷰 자료 | 높음 (검증된 2차) | T1이 없거나 개괄·배경·용어 정리가 필요할 때 |
| **T3** | 커뮤니티 | 개인/회사 기술 블로그, Reddit, Stack Overflow, Hacker News, Dev.to, Medium | 보통 (경험·의견) | 실무 함정, 최신 릴리스 반응, 상세 트러블슈팅, 사용자 경험 |

**판정 원칙**: 같은 사실을 여러 tier가 말하면 상위 tier를 인용한다. T3만 있는 주장은 "커뮤니티 관찰"로 낮춰 표기한다.

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
- **allowed_domains로 tier 강제**: T1 검색 시 공식 도메인만 허용.
  ```
  WebSearch(query="Kubernetes Mutating Admission Policy 2026",
            allowed_domains=["kubernetes.io", "github.com"])
  ```
- **blocked_domains로 노이즈 제거**: 콘텐츠팜·SEO 스팸·번역 스크랩 사이트를 제외.
- **버전 명시**: 버전 의존 주제는 버전을 쿼리에 포함. 예: `Istio 1.22 ambient mode 2026`
- **표준/스펙 조회**: RFC/PEP/KEP 번호를 알면 직접 검색해 1차 출처로.

---

## 최신성 판단 가이드

| 기술 변화 속도 | 예시 | 허용 window(대략) | stale 처리 |
|----------------|------|-------------------|-----------|
| 빠름 | K8s API, 클라우드 신규 기능, JS 프레임워크 | ~12개월 | 초과 시 `stale`, 변경 가능성 명시 |
| 보통 | 데이터베이스, 언어 표준 라이브러리 | ~24개월 | 초과 시 확인 필요 표기 |
| 느림/안정 | 네트워크 프로토콜, 자료구조/알고리즘, RFC | 연식 무관 | 개정판 존재 여부만 확인 |

- publish/updated date가 명시 안 된 소스는 본문에서 대상 버전·연도 단서를 추출해 추정한다.
- deprecated/GA 상태는 반드시 T1(공식 release notes·API reference)로 확정한다.
