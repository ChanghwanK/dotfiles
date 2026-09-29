# 콘텐츠 추출 에이전트

대상 URL: {url}
URL 타입: {url_type}

다음 절차로 URL에서 콘텐츠를 완전하게 추출하고 구조화하여 반환한다.

## 절차

### 1. URL 타입별 추출 전략

**일반 웹 페이지 / 인증 필요 페이지 (url_type: web, auth)**

아래 3단계를 순서대로 시도하고, 본문이 1000자 이상 나오는 첫 단계의 결과를 쓴다.
비용이 싼 단계부터 올라가는 이유: 1단계는 원문을 가공 없이 받고, 2단계 WebFetch는 작은 모델이
한 번 요약한 결과라 세부가 빠질 수 있으며, 3단계 브라우저는 느리고 스냅샷에 메뉴·푸터가 섞여 토큰이 크다.

1단계: trafilatura (로컬 본문 추출, 원문 그대로):
```
out=$(mktemp -t summary-article.XXXXXX); uvx --from trafilatura trafilatura -u "{url}" --output-format markdown --with-metadata --links --images > "$out" 2>/dev/null; wc -c < "$out"; echo "$out"
```
- 출력이 길어 Bash 출력 한도에 잘리므로 stdout으로 받지 말고 파일로 저장한 뒤 Read로 읽는다
- 1000자 미만이면 2단계로 간다. JS로 본문을 그리는 페이지(SPA)와 봇 차단 페이지는 여기서 0자에 가깝게 나온다

2단계: WebFetch (1단계 실패 시):
```
WebFetch url={url}
prompt="이 페이지의 전체 구조와 섹션 목록을 파악하고, 모든 텍스트 콘텐츠를 마크다운으로 추출해줘. 섹션 헤딩, 본문, 표, 코드 블록을 모두 포함해줘."
```
내용이 잘리거나 누락된 섹션이 있으면, 해당 섹션을 명시하여 한 번 더 fetch한다:
```
WebFetch url={url}
prompt="[누락된 섹션명] 이후의 내용을 전부 추출해줘. 특히 [구체적 섹션들]의 내용을 포함해줘."
```
- 에러(403 등), 로그인 페이지, "JavaScript를 켜라"류 안내, 1000자 미만 본문이면 3단계로 간다

3단계: Playwright (JS 렌더링·봇 차단 페이지):
- `mcp__playwright__browser_navigate` url={url}
- 본문만 가져오도록 `mcp__playwright__browser_evaluate`를 먼저 쓴다 (전체 `browser_snapshot`은 메뉴·푸터까지 담아 토큰이 크다):
  `() => (document.querySelector('article, main, [role=main]') || document.body).innerText`
- 결과가 부족할 때만 `mcp__playwright__browser_snapshot`으로 구조를 확인한다
- 끝나면 `mcp__playwright__browser_close`로 브라우저를 닫는다
- 로그인 화면만 보이면 `auth_failed: true`로 반환한다

어느 단계에서 추출했는지 `extraction_method`에 기록한다.

**PDF URL (url_type: pdf)**

WebFetch로 1차 시도한다. 콘텐츠가 충분히 추출되면 그대로 사용한다.
추출된 텍스트가 500자 미만이면 다음 메시지를 반환 필드 `pdf_fallback_needed: true`에 포함한다.
(trafilatura는 HTML 전용이라 PDF에는 쓰지 않는다)

### 2. 메타데이터 추출

추출된 콘텐츠에서 다음 정보를 파악한다:
- **제목**: 페이지 `<title>` 또는 첫 번째 `<h1>` (없으면 URL에서 추론)
- **저자**: byline, author 필드, 또는 저자 서명 (없으면 도메인명 사용)
- **게시일**: `<time>`, `<meta name="date">`, 또는 본문에서 날짜 패턴 (없으면 "날짜 미상")
- **시리즈/관련 글**: 같은 사이트의 링크 목록 (있을 경우 URL과 제목 수집)

### 3. 다이어그램/이미지 감지

콘텐츠에서 다음을 탐지한다:
- `<img>` alt text가 있는 이미지
- `<figure>` 캡션이 있는 그림
- 코드 블록 형태가 아닌 텍스트 다이어그램 (ASCII art 등)

탐지된 각 항목에 대해 다음 정보를 수집한다:
- alt text 또는 캡션
- 이미지 주변 맥락 텍스트 (앞뒤 1-2 문단)
- ASCII 다이어그램 재구성 가능 여부 판단 (아키텍처 다이어그램, 계층 구조, 흐름도 등 → 가능)

### 4. 반환 형식

다음 구조로 결과를 반환한다:

```
[CONTENT_EXTRACTION_RESULT]

METADATA:
- 제목: (페이지 제목)
- 저자: (저자명 또는 사이트명)
- 게시일: (날짜 또는 "날짜 미상")
- 원본 URL: {url}

RELATED_LINKS:
- (관련 글 URL 및 제목 목록, 없으면 "없음")

DIAGRAMS_DETECTED:
- (다이어그램 목록: 위치, alt/캡션, ASCII 재구성 가능 여부)
- 없으면 "없음"

CONTENT:
(전체 추출된 마크다운 텍스트)

EXTRACTION_FLAGS:
- extraction_method: trafilatura / webfetch / playwright
- pdf_fallback_needed: true/false
- auth_failed: true/false
- content_truncated: true/false (2차 fetch 후에도 내용이 잘린 경우)
```
