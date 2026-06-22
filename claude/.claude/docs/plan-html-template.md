# Plan HTML 렌더링 템플릿

Plan 모드 결과를 HTML로 렌더링할 때 아래 구조와 스타일을 사용한다.

## CSS

```css
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  max-width: 720px;
  margin: 60px auto;
  padding: 0 24px 80px;
  color: #1a1a1a;
  line-height: 1.65;
  font-size: 15px;
  background: #fff;
}
h1 { font-size: 1.45rem; font-weight: 700; margin: 0 0 12px 0; }
.tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tag { background: #f0f0f0; border-radius: 999px; padding: 2px 10px;
       font-size: 0.78rem; color: #555; font-family: 'SF Mono', 'Consolas', monospace; }
.title-hr { border: none; border-top: 1px solid #e0e0e0; margin: 0 0 28px 0; }
h2 { font-size: 1rem; font-weight: 700; margin: 32px 0 4px 0; }
h3 { font-size: 0.95rem; font-weight: 700; margin: 24px 0 8px 0; }
.section-hr { border: none; border-top: 1px solid #e0e0e0; margin: 0 0 14px 0; }
p { margin: 0 0 12px 0; }
code { font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
       background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
pre { background: #f5f5f5; padding: 12px 16px; border-radius: 6px;
      overflow-x: auto; font-size: 0.85em; margin: 12px 0; }
pre code { background: none; padding: 0; }
blockquote, .callout { background: #fffbeb; border-left: 3px solid #d97706;
  padding: 12px 16px; margin: 14px 0; border-radius: 0 4px 4px 0; font-size: 0.93em; }
blockquote p { margin: 0 0 6px 0; }
blockquote ul { margin: 6px 0 0 0; padding-left: 18px; }
ol, ul { padding-left: 22px; margin: 0 0 12px 0; }
li { margin-bottom: 5px; }
.dod-list { list-style: none; padding-left: 0; }
.dod-list li { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.dod-list input[type="checkbox"] { margin-top: 3px; flex-shrink: 0; }
strong { font-weight: 600; }
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
| `## 옵션 비교` | `<h2>옵션 비교</h2><hr class="section-hr">` + `<h3>` per option |
| `## 스텝별 상세 계획` | `<h2>스텝별 상세 계획</h2>` + `<h3>` per step |
| `> blockquote` | `<blockquote>` (amber callout 스타일) |
| 인라인 코드 | `<code>` |
| 코드 블록 | `<pre><code>` |
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

  <!-- blockquote → amber callout -->
  <blockquote>
    <p><strong>사전 분석 결론</strong> — ...</p>
    <ul><li>...</li></ul>
  </blockquote>

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
- 화려한 색상/그라디언트/그림자 없음 — 흰 배경 + 회색 구분선 + amber callout만
- 폰트는 시스템 기본 sans-serif (웹폰트 로드 없음)
- 파일 경로: 플랜 `.md`와 동일 디렉터리, 확장자만 `.html`
