# Plan HTML 렌더링 계약

Plan 모드 결과를 HTML로 렌더링하는 파이프라인의 **계약 문서**입니다.
CSS/JS 본문은 여기에 복제하지 않습니다.

> **정본**
> - 스타일: `~/.claude/scripts/assets/plan.css`
> - 동작: `~/.claude/scripts/assets/plan.js`
> - 마크업: `~/.claude/scripts/plan-to-html.py`
>
> 과거에는 이 문서가 CSS 전문을 바이트 단위로 복제하고 있었습니다. 한쪽만 고치면
> 조용히 어긋나므로 복제를 제거하고, 이 문서는 **토큰 계약과 셀렉터 계약만** 규정합니다.

## 파이프라인

| 훅 | 스크립트 | 모드 | 액션 버튼 |
|----|----------|------|-----------|
| `PreToolUse(ExitPlanMode)` | `plan-preview.sh` → `plan-approval-server.py` | `server` | 승인 / 논의 / 거부 |
| `PostToolUse(ExitPlanMode)` | `notify-plan-done.sh` → `convert()` | `static` | 없음 (오프라인 아카이브) |
| `Stop` | `plan-text-preview.sh` → `convert()` | `static` | 없음 (읽기 전용 뷰어) |

렌더러가 마크업을 소유하고, 서버는 `mode="server"`를 요청한 뒤 `__CSRF__` 토큰만 치환합니다.
서버가 HTML을 문자열 치환으로 조립하지 않습니다 (과거 `replace('<body>', ...)` 방식은
렌더러가 바뀌면 조용히 깨졌습니다).

## 디자인 토큰

컴포넌트 CSS는 항상 토큰을 참조하며 색상 리터럴을 직접 쓰지 않습니다.

| 토큰 | 용도 | 라이트 | 다크 |
|------|------|--------|------|
| `--ink` | 본문 텍스트 | `#171A21` | `#E7E9EE` |
| `--paper` | 배경 | `#F6F7F9` | `#14161B` |
| `--surface` | 카드/콜아웃/코드/사이드바 배경 | `#FFFFFF` | `#1C1F26` |
| `--line` | 구분선/보더 | `#E1E4E9` | `#2B2F38` |
| `--muted` | 보조 텍스트 | `#5B6472` | `#8A93A3` |
| `--accent` | 구조적 강조(추천 배지·체크박스·진행률) | `#3A55A6` | `#8DA0EE` |
| `--risk` / `--risk-bg` | 위험 콜아웃(리스크/롤백) | `#B3261E` / `#FBEAEA` | `#F2938D` / `#3A1F20` |
| `--callout` / `--callout-bg` | 일반 콜아웃(정보/분석 결론) | `#9A6700` / `#FFF6E5` | `#FFD98A` / `#3A2E12` |
| `--ok` | 답변 완료 표시 | `#16733C` | `#6FCF97` |
| `--sidebar-w` | 사이드바 폭 | `268px` | 동일 |

승인/거부 버튼(초록 `#16a34a` / 빨강 `#dc2626`)은 토큰이 아닌 고정 시맨틱 색입니다.
되돌릴 수 없는 액션의 의미가 테마에 따라 흔들리면 안 되기 때문입니다.

### 테마는 반드시 3블록

```
/* 1 */  :root { ...라이트 토큰... }
/* 2 */  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ...다크... } }
/* 3 */  :root[data-theme="dark"] { ...다크... }
```

`:not([data-theme="light"])`가 **load-bearing**입니다. 이게 없으면
"시스템은 다크인데 사용자가 라이트를 선택한" 경우가 조용히 다크로 남습니다.
다크 토큰 블록이 중복되는 것은 이 때문이며, 의도된 중복입니다.

`<head>`의 인라인 부트스트랩 스크립트가 스타일시트보다 먼저
`document.documentElement.dataset.theme`를 세팅합니다. 본문 끝에서 읽으면 FOUC가 발생합니다.

## 셀렉터 계약 (불변)

`plan.js`가 질의하는 셀렉터입니다. 렌더러를 리팩터링할 때 하나라도 빠지면 아래 증상이 납니다.

| 셀렉터 | 의미 | 생산자 | 깨졌을 때 |
|--------|------|--------|-----------|
| `body[data-mode]` | `static` \| `server` | 렌더러 | 액션 버튼 표시 오류 |
| `body[data-plan-key]` | localStorage 네임스페이스 (제목+스텝 제목의 sha1 앞 12자) | 렌더러 | 체크 상태 유실 |
| `section.sec[id^="sec-"]` | H2 섹션 단위 | 렌더러 | scroll-spy·`j`/`k` 이동 죽음 |
| `#plan-toc a[data-target]` | TOC 링크 | 렌더러 | 목차 활성 표시 죽음 |
| `#plan-actions` | 액션 폼 주입 지점 (static에선 빈 div) | 렌더러 | 승인 불가 |
| `#plan-form` | 결정 폼 (server 전용) | 렌더러 | 승인 불가 (서버가 stderr 경고) |
| `input.chk[data-key]` | `step:N` 또는 `dod:<hash>` | 렌더러 | 진행률·영속화 오류 |
| `input.chk[data-seed="done"]` | frontmatter `todos:` 기준 완료 | 렌더러 | localStorage가 셸 상태를 이김 |
| `details.step-detail[data-step]` | 스텝 상세 아코디언 | 렌더러 | 양방향 링크·접기 죽음 |
| `#quiz .quiz-answer[name^="quiz_"]` | 이해 점검 답변 | 렌더러 | 논의 페이로드 누락 |
| `input[name^="quizq_"]` | 문항 원문 (hidden) | 렌더러 | 서버가 답변에 라벨을 못 붙임 |
| `#discuss` | 논의 입력 | 렌더러 | 논의 텍스트 누락 |

본문 textarea들은 사이드바의 폼 밖에 있으므로 `form="plan-form"` 속성으로 연결합니다.
정적 HTML에는 그 폼이 없으므로 이 속성은 무해한 no-op입니다.

### 상태 우선순위

`data-seed="done"` > localStorage. frontmatter는 `/plan:check`가 관리하는 셸 측 진실이고,
브라우저가 조용히 다른 값을 주장하면 statusline과 어긋납니다.
DoD 체크박스는 frontmatter에 대응물이 없으므로 localStorage 전용이며,
항목 재정렬 시 상태가 밀리지 않도록 **내용 해시**로 키를 만듭니다.

`data-plan-key`도 `plan_id`가 아니라 **내용 해시**입니다. 프리뷰는 frontmatter가 없는
임시 파일에서, 아카이브는 frontmatter가 있는 파일에서 렌더되므로, `plan_id`를 쓰면
같은 플랜인데 네임스페이스가 갈라집니다.

## 마크다운 매핑

| 마크다운 | 출력 |
|----------|------|
| 첫 `# ` | `<h1>` + `.tags` + `.title-hr` |
| `## X` | `<section class="sec" id="sec-N">` + `<h2>` + `.section-hr` |
| `## Steps` (번호 목록) | `ol.steps-list` + 체크박스 + 상세 점프 링크 |
| `## 스텝별 상세 계획`의 `### Step N` | `details.step-detail` (기본 열림) |
| `## 옵션 비교`의 `### Option X:` | `.compare-grid` / `.compare-card` (+ `.recommended`) |
| `## 이해 점검`의 `### Qn (레벨):` | `.quiz-item` + textarea + `details.quiz-model` |
| 제목에 리스크 키워드 | `.section-risk` 래핑 |
| `- [ ]` / `- [x]` 연속 런 | `ul.dod-list` + 체크박스 |

**폴백 원칙**: 전용 렌더러는 섹션이 예상 형태가 아니면 `None`을 반환하고 일반 렌더러로
떨어집니다. 내용이 소리 없이 사라지는 경로를 만들지 않습니다.

**펜스 인식**: 섹션 분할과 `### Step N` / `### Qn` 탐지는 코드펜스 안을 건너뜁니다.
플랜이 마크다운 제목을 코드블록으로 인용하면 섹션이 조기 종료되던 버그가 있었습니다.

**DoD 판정 범위**: 체크박스 여부는 현재 위치에서 시작하는 **연속된 불릿 런**만 봅니다.
이후 10줄을 훑던 방식은 근처에 DoD가 있다는 이유로 무관한 목록을 체크박스로 만들었습니다.

## 아코디언은 기본 열림

`details.step-detail`은 `open`으로 렌더합니다. 접힌 `<details>`는 Ctrl+F로 찾을 수 없고
인쇄에도 안 나옵니다. 일괄 접기는 사이드바 버튼이 담당하고, 상태는 첫 상호작용 이후부터
localStorage에 저장합니다.

목록 복귀 링크는 `<summary>` **밖**(본문 안)에 둡니다. `<summary>` 안의 `<a>`는 클릭 시
disclosure를 토글해 버립니다.

## 보안

- `inline_md()`는 **이스케이프를 먼저** 수행합니다. 프리뷰 페이지는 상태를 바꾸는
  엔드포인트를 호스팅하므로, 주입된 스크립트가 읽지도 않은 플랜을 승인시킬 수 있습니다.
- `escape()`는 `"`도 처리합니다. 속성값(`value="{질문}"`)에 그대로 들어가기 때문입니다.
- 서버는 CSRF 토큰 + Origin 검사를 요구하고 `GET /approve` 같은 부작용 있는 GET을 두지 않습니다.
  토큰 없는 로컬 GET 엔드포인트는 사용자가 열어둔 아무 웹페이지나 `fetch`로 호출할 수 있습니다.
- CSP는 인라인 스크립트를 막지 못하지만(`unsafe-inline` 필요) `default-src 'none'` +
  `form-action 'self'`로 **유출 경로**를 닫습니다.

## 결정 경로

승인/논의/거부는 JS 없이 동작하는 **form POST**입니다. `plan.js`는 이제 페이지에서 가장 큰
구성 요소이고, 문법 오류 하나면 모든 리스너가 함께 죽습니다. 플랜을 승인하는 경로만은
그 사고에서 살아남아야 합니다.

`stdout`은 한 단어(`approve|pause|reject|timeout`) 전용 채널로 유지합니다. 논의 텍스트는
`--pause-out` 파일로 나갑니다. `plan-preview.sh`의 `case`에는 catch-all(터미널 프롬프트
fallback)이 있어서, stdout에 구분자 프로토콜을 얹으면 파싱 오류가 승인을 조용히
"훅이 아무 것도 안 함"으로 바꿔버립니다.

**타임아웃 불변식**: `SERVER_TIMEOUT(840) + 60 <= settings.json 훅 timeout(900)`.
서버가 항상 먼저 죽어야 셸이 JSON을 낼 여유가 생깁니다.
타임아웃이 파괴적이지 않도록 논의·답변 입력은 localStorage에 드래프트로 자동 저장됩니다.

## 제약

- 출력은 **단일 오프라인 파일**입니다. CSS/JS는 렌더 시점에 인라인되며 외부 요청이 없습니다
  (웹폰트·CDN·이미지 금지). JS 인라인 시 `</script>`를 이스케이프합니다.
- 이모지 금지, 장식용 그라디언트·섀도 금지. 색은 의미가 있을 때만 사용합니다.
- 시스템 폰트만 사용합니다.
- 에셋 파일이 없어도 페이지는 떠야 합니다 (fallback CSS). 세 호출 경로가 모두 에러를
  삼키므로, 없으면 무스타일 페이지가 조용히 뜹니다.
- 출력 경로: 플랜 `.md`와 같은 디렉터리, 확장자만 `.html`.

## 검증

```bash
# 전 플랜 렌더 + 외부 요청 없음
for f in ~/.claude/plans/*.md; do python3 ~/.claude/scripts/plan-to-html.py "$f"; done
grep -nE '(src|href)="(https?:|//)' ~/.claude/plans/*.html   # 비어 있어야 함

# 정의되지 않은 var() 없음
comm -13 <(grep -oE '^\s*--[a-z-]+' ~/.claude/scripts/assets/plan.css | tr -d ' ' | sort -u) \
         <(grep -oE 'var\(--[a-z-]+' ~/.claude/scripts/assets/plan.css | sed 's/var(//' | sort -u)

# 이 문서가 CSS를 다시 복제하고 있지 않은지
grep -c '^:root {' ~/.claude/docs/plan-html-template.md   # 0

# 서버 단독 실행 (브라우저 없이)
python3 ~/.claude/scripts/plan-approval-server.py <plan.md> --no-open --port 17999 --pause-out /tmp/p.txt
```
