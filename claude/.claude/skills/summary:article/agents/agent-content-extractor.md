# 콘텐츠 추출 에이전트

대상 URL: {url}
URL 타입: {url_type}

다음 절차로 URL에서 콘텐츠를 완전하게 추출하고 구조화하여 반환한다.

## 절차

### 1. URL 타입별 추출 전략

**일반 웹 페이지 (url_type: web)**

1차 fetch — 전체 구조 파악:
```
WebFetch url={url}
prompt="이 페이지의 전체 구조와 섹션 목록을 파악하고, 모든 텍스트 콘텐츠를 마크다운으로 추출해줘. 섹션 헤딩, 본문, 표, 코드 블록을 모두 포함해줘."
```

2차 fetch — 누락 섹션 보완:
1차 fetch에서 내용이 잘리거나 누락된 섹션이 있으면, 해당 섹션을 명시하여 2차 fetch를 수행한다:
```
WebFetch url={url}
prompt="[누락된 섹션명] 이후의 내용을 전부 추출해줘. 특히 [구체적 섹션들]의 내용을 포함해줘."
```

**PDF URL (url_type: pdf)**

WebFetch로 1차 시도한다. 콘텐츠가 충분히 추출되면 그대로 사용한다.
추출된 텍스트가 500자 미만이면 다음 메시지를 반환 필드 `pdf_fallback_needed: true`에 포함한다.

**인증 필요 페이지 (url_type: auth)**

WebFetch로 1차 시도한다. 에러 또는 로그인 페이지가 반환되면:
- Playwright로 fallback 시도 (mcp__playwright__browser_navigate → browser_snapshot)
- Playwright도 실패하면 `auth_failed: true` 필드에 포함한다.

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
- pdf_fallback_needed: true/false
- auth_failed: true/false
- content_truncated: true/false (2차 fetch 후에도 내용이 잘린 경우)
```
