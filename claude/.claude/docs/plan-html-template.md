# Plan HTML 렌더링 템플릿

Plan 모드 결과를 HTML로 렌더링할 때 아래 구조와 스타일을 사용한다.

## 디자인 토큰

라이트/다크 모드를 `:root` 커스텀 프로퍼티로 정의하고, `@media (prefers-color-scheme: dark)`에서
토큰 값만 재정의한다. 컴포넌트 CSS는 항상 토큰을 참조하며 색상 리터럴을 직접 쓰지 않는다.

| 토큰 | 용도 | 라이트 | 다크 |
|------|------|--------|------|
| `--ink` | 본문 텍스트 | `#171A21` | `#E7E9EE` |
| `--paper` | 배경 | `#F6F7F9` | `#14161B` |
| `--surface` | 카드/콜아웃/코드 배경 | `#FFFFFF` | `#1C1F26` |
| `--line` | 구분선/보더 | `#E1E4E9` | `#2B2F38` |
| `--muted` | 보조 텍스트 | `#5B6472` | `#8A93A3` |
| `--accent` | 구조적 강조(추천 배지·체크박스) | `#3A55A6` | `#8DA0EE` |
| `--risk` / `--risk-bg` | 위험 콜아웃(리스크/롤백) | `#B3261E` / `#FBEAEA` | `#F2938D` / `#3A1F20` |
| `--callout` / `--callout-bg` | 일반 콜아웃(정보/분석 결론) | `#9A6700` / `#FFF6E5` | `#FFD98A` / `#3A2E12` |

승인/거부 버튼(초록/빨강)은 accent와 별개의 시맨틱 색이며 라이트/다크 공통 고정값을 쓴다
(승인·거부는 상태 신호이지 디자인 강조색이 아니다).

## CSS

```css
:root {
  --ink: #171A21; --paper: #F6F7F9; --surface: #FFFFFF; --line: #E1E4E9;
  --muted: #5B6472; --accent: #3A55A6; --risk: #B3261E; --risk-bg: #FBEAEA;
  --callout: #9A6700; --callout-bg: #FFF6E5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #E7E9EE; --paper: #14161B; --surface: #1C1F26; --line: #2B2F38;
    --muted: #8A93A3; --accent: #8DA0EE; --risk: #F2938D; --risk-bg: #3A1F20;
    --callout: #FFD98A; --callout-bg: #3A2E12;
  }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  max-width: 68ch;
  margin: 60px auto;
  padding: 0 24px 80px;
  color: var(--ink);
  background: var(--paper);
  line-height: 1.65;
  font-size: 15px;
}
h1, h2, h3 { text-wrap: balance; letter-spacing: -0.01em; }
h1 { font-size: 1.5rem; font-weight: 700; margin: 0 0 12px 0; }
.tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tag { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
       padding: 2px 10px; font-size: 0.78rem; color: var(--muted);
       font-family: 'SF Mono', 'Consolas', monospace; font-variant-numeric: tabular-nums; }
.title-hr { border: none; border-top: 1px solid var(--line); margin: 0 0 28px 0; }
h2 { font-size: 1.02rem; font-weight: 700; margin: 32px 0 4px 0; }
h3 { font-size: 0.96rem; font-weight: 700; margin: 24px 0 8px 0; }
.section-hr { border: none; border-top: 1px solid var(--line); margin: 0 0 14px 0; }
p { margin: 0 0 12px 0; }
code { font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
       background: var(--surface); border: 1px solid var(--line);
       padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
pre { background: var(--surface); border: 1px solid var(--line); padding: 12px 16px;
      border-radius: 6px; overflow-x: auto; font-size: 0.85em; margin: 12px 0; }
pre code { background: none; border: none; padding: 0; }
blockquote { background: var(--callout-bg); border-left: 3px solid var(--callout);
  color: var(--ink); padding: 12px 16px; margin: 14px 0; border-radius: 0 4px 4px 0; font-size: 0.93em; }
blockquote.risk { background: var(--risk-bg); border-left-color: var(--risk); }
blockquote p { margin: 0 0 6px 0; }
blockquote ul { margin: 6px 0 0 0; padding-left: 18px; }
ol, ul { padding-left: 22px; margin: 0 0 12px 0; }
li { margin-bottom: 5px; }
.dod-list { list-style: none; padding-left: 0; }
.dod-list li { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.dod-list input[type="checkbox"] { margin-top: 3px; flex-shrink: 0; accent-color: var(--accent); }
strong { font-weight: 600; }
.table-wrap { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--line); padding: 8px 12px; text-align: left; font-size: 0.9em;
         font-variant-numeric: tabular-nums; }
th { background: var(--surface); font-weight: 600; }
.compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 12px; margin: 12px 0; }
.compare-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; background: var(--surface); }
.compare-card.recommended { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.compare-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.compare-label { font-family: 'SF Mono', 'Consolas', monospace; font-size: 0.78rem; color: var(--muted); }
.compare-badge { font-size: 0.72rem; font-weight: 600; color: var(--accent);
                 border: 1px solid var(--accent); border-radius: 999px; padding: 1px 8px; }
.compare-name { margin: 0 0 8px 0; font-size: 0.95rem; }
.compare-card ul { margin: 0; padding-left: 18px; }
.compare-note { font-size: 0.9em; color: var(--muted); }
.section-risk { border-left: 3px solid var(--risk); background: var(--risk-bg);
                border-radius: 0 6px 6px 0; padding: 10px 16px 2px; }
.section-risk > :last-child { margin-bottom: 8px; }
```

## HTML 구조 매핑

| Plan 요소 | HTML 변환 |
|----------|---------|
| 플랜 제목 | `<h1>` → `<hr class="title-hr">` |
| 메타 태그 (env/sphere/버전) | `<div class="tags"><span class="tag">...</span></div>` |
| `## Summary` | `<h2>Summary</h2><hr class="section-hr">` + bullet → `<ul>` |
| `## Goals` | `<h2>Goals</h2><hr class="section-hr">` + `<ul>` |
| `## Non-Goals` (선택적) | `<h2>Non-Goals</h2><hr class="section-hr">` + `<ul>` (존재할 때만 렌더링) |
| `## Steps` | `<h2>Steps</h2><hr class="section-hr">` + `<ol>` |
| `## 완료 조건 (DoD)` | `<h2>완료 조건 (DoD)</h2><hr class="section-hr">` + `<ul class="dod-list">` (checkbox) |
| `## 옵션 비교` | `### Option X: (이름)` 서브섹션들을 `<div class="compare-grid">`의 `<div class="compare-card">` 카드로 렌더링. `**추천**: Option X` 감지 시 해당 카드에 `recommended` 클래스 + `<span class="compare-badge">` 배지 부여. `### Option` 서브섹션이 없으면 일반 리스트로 폴백 |
| `## 스텝별 상세 계획` | `<h2>스텝별 상세 계획</h2>` + `<h3>` per step |
| 리스크/롤백 관련 H2 (`리스크`, `위험`, `롤백` 등 헤딩 키워드 포함) | 섹션 전체를 `<div class="section-risk">`로 감싸 rose 톤 강조 |
| `> blockquote` (Blast radius/실패 시나리오/롤백 방법/rollback 키워드 포함) | `<blockquote class="risk">` (rose 톤) |
| `> blockquote` (그 외) | `<blockquote>` (amber callout 스타일) |
| 인라인 코드 | `<code>` |
| 코드 블록 | `<pre><code>` |
| 표 | `<div class="table-wrap"><table>...</table></div>` |
| `**굵게**` | `<strong>` |

## 메타데이터 태그 추출

플랜 frontmatter 또는 본문 상단에서 아래 패턴을 `.tag`로 추출한다:
- 버전 전환: `0.59.3 → 0.84.0`
- 환경: `infra-k8s-{env}`, `dev`, `stg`, `prod`, `global`, `idc`
- sphere: `observability`, `santa`, `socraai`, `data-platform`, `tech` 등
- 플랜 타입: frontmatter `type:` 값

## 전체 HTML 뼈대

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{plan_title}</title>
  <style>
    /* 위 CSS 삽입 */
  </style>
</head>
<body>
  <h1>{plan_title}</h1>
  <div class="tags">
    <span class="tag">{tag1}</span>
    <span class="tag">{tag2}</span>
  </div>
  <hr class="title-hr">

  <h2>Summary</h2>
  <hr class="section-hr">
  <ul>
    <li><strong>무엇을</strong>: ...</li>
    <li><strong>어떻게</strong>: ...</li>
    <li><strong>범위/주의</strong>: ...</li>
  </ul>

  <h2>Goals</h2>
  <hr class="section-hr">
  <ul>
    <li>...</li>
  </ul>

  <!-- Non-Goals: 선택적. 범위 혼동 우려가 있을 때만 포함 -->
  <h2>Non-Goals</h2>
  <hr class="section-hr">
  <ul>
    <li>...</li>
  </ul>

  <!-- blockquote → amber callout, 위험 키워드 포함 시 rose(class="risk") -->
  <blockquote>
    <p><strong>사전 분석 결론</strong> — ...</p>
    <ul><li>...</li></ul>
  </blockquote>

  <!-- 옵션 비교 → 카드 그리드 -->
  <h2>옵션 비교</h2>
  <hr class="section-hr">
  <div class="compare-grid">
    <div class="compare-card recommended">
      <div class="compare-card-head">
        <span class="compare-label">Option A</span>
        <span class="compare-badge">추천</span>
      </div>
      <h3 class="compare-name">...</h3>
      <ul><li><strong>장점</strong>: ...</li><li><strong>단점</strong>: ...</li></ul>
    </div>
    <div class="compare-card">
      <div class="compare-card-head"><span class="compare-label">Option B</span></div>
      <h3 class="compare-name">...</h3>
      <ul><li><strong>장점</strong>: ...</li><li><strong>단점</strong>: ...</li></ul>
    </div>
  </div>
  <p class="compare-note"><strong>추천</strong>: Option A — ...</p>

  <h2>Steps</h2>
  <hr class="section-hr">
  <ol>
    <li>...</li>
  </ol>

  <h2>완료 조건 (DoD)</h2>
  <hr class="section-hr">
  <ul class="dod-list">
    <li><input type="checkbox"> <span><code>kubectl get ...</code></span></li>
  </ul>

  <!-- 헤딩에 '리스크'/'위험'/'롤백' 등이 포함되면 섹션 전체를 rose 톤으로 강조 -->
  <h2>리스크 / 롤백</h2>
  <hr class="section-hr">
  <div class="section-risk">
    <ul>
      <li><strong>Blast radius</strong>: ...</li>
      <li><strong>롤백</strong>: ...</li>
    </ul>
  </div>

  <h2>스텝별 상세 계획</h2>
  <h3>Step 1 — {제목}</h3>
  <ol><li>...</li></ol>
  <p><strong>대상 파일</strong>: <code>path/to/file</code></p>
  <p><strong>검증</strong>: ...</p>
</body>
</html>
```

## 주의사항

- 이모지 없음 (CLAUDE.md 글로벌 규칙 준수)
- 토큰 기반 절제된 팔레트 — 장식적 색상/그라디언트/그림자 없음. 색상은 위험(rose)·추천(accent)·
  일반 콜아웃(amber) 등 의미가 있는 곳에만 사용한다
- 라이트/다크 모두 지원 (`prefers-color-scheme`) — 새 컴포넌트를 추가할 때도 색상 리터럴 대신
  반드시 토큰을 참조한다
- 폰트는 시스템 기본 sans-serif (웹폰트 로드 없음) — 로컬 오프라인 도구라는 특성상 데이터 URI
  임베딩도 하지 않는다
- 파일 경로: 플랜 `.md`와 동일 디렉터리, 확장자만 `.html`
