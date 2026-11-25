---
name: work:tracking
description: |
  작업 트래킹 스킬. 하루 동안 한 일을 세션 로그와 PR에서 모아 한 일·이어서 할 일·고민·어려움 네 트리로 정리하고,
  지난 기록의 할 일이 끝났는지 이어지는지 대조한다. 결과는 날짜별 페이지로 게시하고 기록을 남겨 다음 날 이어 쓴다.
  사용 시점: (1) 하루 작업 정리, (2) 진행 상황과 이월 추적.
  트리거 키워드: "작업 트래킹", "하루 정리해줘", "작업 정리 트리", "work tracking", "/work:tracking".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/work:tracking/scripts/collect.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/work:tracking/scripts/render.py *)
  - Read
  - Write
  - Edit
  - Artifact
---
# work:tracking

하루를 네 질문으로 정리한다: 무엇을 했나, 이어서 할 일, 어떤 고민을 했나, 어떤 어려움이 있었나.
수집과 화면은 스크립트가 맡고, Claude는 내용 정리만 한다. 날짜별 기록을 남겨 다음 날 이월을 대조한다.

## 핵심 원칙

- **사실이 우선이다.** 세션 로그와 PR이 회고 문서·기억과 다르면 로그와 PR을 따른다. 측정 없는 원인 주장은 "(원인 미확인)"으로 쓴다
- **직접과 추론을 나눈다.** 어려움은 사용자가 직접 말한 것(발화 인용과 시각)과 로그로 추론한 것(근거 명시)을 칩으로 구분한다
- **형식은 고정이다.** 화면 구조와 스타일은 `render.py`와 `assets/tree.css`가 정한다. 페이지 HTML을 손으로 고치지 않고 JSON만 고친다
- **쓰기는 기록 저장소에만 한다.** `~/.claude/work-tracking/` 밖의 파일, Notion, Jira, GitHub에는 쓰지 않는다
- 이모지와 em dash(U+2014)를 쓰지 않는다. `render.py`가 em dash를 거부한다

## 파일

| 경로 | 역할 |
|------|------|
| `scripts/collect.py` | 재료 수집 → `~/.claude/work-tracking/raw/<날짜>.json` |
| `scripts/render.py` | 기록 JSON → `~/.claude/work-tracking/<날짜>.html` |
| `assets/example.json` | 스키마 겸 실제 예시(2026-11-24). 기록을 쓰기 전에 Read한다 |
| `assets/tree.css` | 확정 디자인(가로 트리, 단일 라이트 테마) |
| `~/.claude/work-tracking/<날짜>.json` | 그날의 기록. 다음 회고의 이월 원천 |

## 워크플로우

### Step 1: 수집

날짜를 말하지 않으면 오늘(KST)이다. "어제"면 어제 날짜를 넘긴다.

```bash
python3 /Users/changhwan/.claude/skills/work:tracking/scripts/collect.py --date YYYY-MM-DD
```

- stdout 요약(세션 수, PR 수, 이월 후보 수, 오류)을 보고, `path`의 raw JSON을 Read한다
- 세션은 그날과 활동 구간이 겹치는 것만 들어온다. `spans_days: true` 세션은 다른 날 메시지가 섞여 있으니 내용으로 그날 몫을 가른다
- `existing_record`가 있으면 같은 날 다시 돌리는 것이다. 그 JSON을 Read해 고칠 부분만 바꾸고 `artifact_url`을 유지한다
- `errors`가 있으면 그 소스를 빼고 진행하되 Step 5 콘솔 응답에 한 줄로 알린다

### Step 2: 이월 대조

`carry_candidates`(지난 기록의 이어서 할 일) 각각을 그날 증거로 판정해 `carryover`에 쓴다.

- `done`: 그날 세션·PR에 끝낸 증거가 있다. 그 일은 1번 트리에 넣는다
- `carried`: 아직 남았다. 2번 트리에 **같은 `id`와 `since`**로 다시 넣는다. 화면에 "이월 N일째"가 자동으로 붙는다
- `dropped`: 사용자가 그만두기로 했거나 더 필요 없다는 증거가 있다
- 항목마다 `evidence`에 판정 근거 한 줄(세션 제목, PR 번호, 발화)을 쓴다. 증거가 없으면 `carried`로 둔다
- 새로 생긴 할 일은 `id`를 `<날짜>-n<두 자리 번호>`로, `since`를 그날로 준다

### Step 3: 정리 (기록 JSON 쓰기)

`assets/example.json`을 Read해 같은 스키마로 `~/.claude/work-tracking/<날짜>.json`을 Write한다.

- **트리 구조**: `trees.{done,next,thoughts,hard}` 각각 `root`, `caption`, `groups`. 노드는 `name`, `chip`, `sub`, `detail`, `kids`
  - 상위 주제는 목적 단위로 묶는다(작업 이름이 아니라 같은 목표). 트리당 5개 이하, 상위 주제당 항목 5개 이하, 깊이는 루트 포함 4단계까지
  - `sub`: 카드에 늘 보이는 설명 1~2문장(무엇을, 결과가 어떤지). `detail`: + 로 펼치는 불릿 2~7개(PR 번호, 수치, 확정값, 미확인 항목)
  - 상위 주제 노드에도 `sub`를 준다(이 묶음이 무엇인지)
- **칩**(`chip.kind`): `g` 완료·결론, `y` 진행·대기, `r` 오늘, `z` 날짜 지정·미확인, `d` 직접, `i` 추론
  - 1번: g/y/z, 2번: r/y/z(끝난 것은 g), 3번: g(결론)/y(열림), 4번: d/i
- **3번 고민**은 고민의 성격(설계 트레이드오프, 운영 경계, 문서와 소통, 일하는 방식 등)으로, **4번 어려움**은 원인 성격(AI 협업 품질, 작업 구조, 인지 부하, 도구·환경 등)으로 묶는다
- **Overview**: `lead`(하루 한 문장), `stats` 4개(머지 PR, 작업 세션, 근무 시간, 남은 결정 등 그날 의미 있는 수), `overview` 4개 문단(섹션마다 2~3문장)
- **PR**: `prs`는 collect의 PR을 그대로 쓰고 `group`만 1번 트리의 상위 주제 이름으로 붙인다. push만 하고 PR이 없는 브랜치는 `open_branches`
- `span`(첫·마지막 세션 시각), `sources`(근거 한 문장)를 채운다. 문체는 격식체 명사형·문장형을 섞되 em dash 없이 쓴다

### Step 4: 렌더와 게시

```bash
python3 /Users/changhwan/.claude/skills/work:tracking/scripts/render.py --data ~/.claude/work-tracking/YYYY-MM-DD.json
```

- `error`가 나오면 JSON을 고쳐 다시 렌더한다
- 출력 `path`를 Artifact로 게시한다
  - 기록에 `artifact_url`이 있으면 그 `url`로 갱신한다(같은 날 재실행)
  - 없으면 새로 게시한다(`icon: "tree"`, `description`: "<날짜> 작업을 한 일·할 일·고민·어려움 트리로 정리한 기록")
- 게시가 끝나면 받은 URL을 기록 JSON의 `artifact_url`에 Edit로 써 둔다

### Step 5: 콘솔 응답

세 줄로 끝낸다.
1. 결론 한 줄(그날의 `lead`)
2. 이월 요약 한 줄(예: "지난 기록의 할 일 12건: 완료 3, 이월 8, 중단 1"). 이월 후보가 없으면 "첫 기록입니다"
3. Artifact 링크

## 주의사항

- `collect.py`는 `daily:start/scripts/extract-work.py`를 호출만 한다. 그 스크립트는 handoff:pause 등도 쓰므로 고치지 않는다
- PR 수집 범위는 `riiid` 조직, 작성자 본인, 그날(KST) 머지된 PR이다
- 페이지 디자인을 바꾸라는 요청은 `assets/tree.css`와 `render.py`를 고치고 `assets/example.json`으로 렌더해 기존 구조(카드, 상세, Overview, PR 목록)가 유지되는지 확인한다
