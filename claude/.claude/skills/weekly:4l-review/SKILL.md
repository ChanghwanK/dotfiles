---
name: weekly:4l-review
description: |
  Daily DB를 분석해 이번 주 한 일을 리스트업하고 4L(Liked/Learned/Lacked/Longed for)
  형식 주간 회고 초안을 화면에 출력한 뒤, 확인을 거쳐 Notion 개인 "주간 리뷰" DB에
  페이지를 생성하는 스킬.
  사용 시점: (1) 주간 4L 회고 작성, (2) Notion 주간 리뷰 DB에 회고 페이지 생성,
  (3) 이번 주 한 일 정리.
  트리거 키워드: "주간 회고", "4L 회고", "4L 리뷰", "회고 노션에 기록",
  "weekly:4l-review", "/weekly:4l-review".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly-review.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly.py *)
  - AskUserQuestion
---

# weekly:4l-review Skill

Daily DB를 분석해 이번 주 한 일을 리스트업하고, 4L(Liked/Learned/Lacked/Longed for) 회고 초안을 화면에 보여준 뒤 확인을 거쳐 Notion "주간 리뷰" DB에 페이지로 남깁니다.

---

## 핵심 원칙

- 스크립트만 호출한다. Notion MCP 도구는 사용하지 않는다 (토큰 효율).
- Daily DB 조회는 이 스킬의 `scripts/notion-weekly.py`를 쓴다 (2026-09-18 weekly:start 제거 시 이관).
- Notion 페이지는 **반드시 사용자 확인 후에만** 생성한다. 초안은 반드시 먼저 화면에 출력한다.
- 같은 기간의 페이지가 이미 존재하면 중복 생성하지 않고 사용자에게 알린다 (이 스킬은 생성 전용이며 기존 페이지 수정은 지원하지 않는다).
- Notion 본문 문장 스타일은 `~/.claude/docs/notion-writing-style.md`를 따른다 (짧고 단순하게, 핵심만). em dash/본문 이모지는 쓰기 스크립트가 자동 정리한다.

---

## 워크플로우

### Step 1: 기간 확인 + 중복 체크

```bash
python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly-review.py find-existing --week current
```

- 대상 주는 기본 `current`(월~금). 사용자가 "지난 주"를 명시하면 `--week previous`.
- 응답의 `exists`가 `true`이면: `📌 이미 "{title}" 페이지가 존재합니다: {url}` 를 출력하고 워크플로우를 종료한다 (덮어쓰기는 이 스킬 범위 밖).
- `exists`가 `false`이면 `period_label`(예: `07.27~07.31`)을 이후 Step에서 그대로 사용한다.

### Step 2: Daily DB 데이터 수집

```bash
python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly.py weekly-daily-summary --week current
```

- Step 1과 동일한 `--week` 값을 사용한다.
- 응답의 `days[].todos.items`(`done: true`인 항목), `days[].note`, `days[].kpt`(일별 K/P/T)를 이후 분석에 사용한다. `days[].kpt`는 기존 daily 스킬이 Keep/Problem/Try 필드로 남긴 원본 데이터이며, 4L 합성 시 참고 소스로만 사용한다(그대로 옮기지 않는다).

### Step 3: 이번 주 했던 일 초안 (화면 출력)

`days[].todos.items` 중 `done: true`인 항목만 모아 리스트업한다. `[Must Have]`/`[Should Have]`/`[Nice to have]` 같은 섹션 라벨 줄과 빈 불릿(`•`만 있는 줄)은 제외한다. 같은 작업이 여러 날 반복되면 하나로 합친다.

```
### 이번 주({period_label}) 한 일
- 항목1
- 항목2
(완료 항목이 없는 날은 생략)
```

### Step 4: 4L 초안 + 짧은 작성 팁 (화면 출력)

Step 2의 일별 `kpt`(K/P/T)와 `note`, Step 3에서 정리한 완료 항목을 종합해 **주간 단위** 4L을 합성한다. 일별 기록을 그대로 나열하지 않고 반복되는 패턴을 묶어 재작성한다.

- **Liked**: 이번 주 좋았던 순간·경험 (일별 Keep + 완료 항목 중 만족스러웠던 것)
- **Learned**: 새로 알게 된 지식·기술·협업에서 얻은 교훈 (사실 기반, 판단 불필요)
- **Lacked**: 부족했던 자원·정보·기술 (일별 Problem과 상당 부분 겹침)
- **Longed for**: 다음 주 안에 실행 가능한 구체적 목표 (일별 Try를 다음 주 단위로 재구성)

출력 포맷은 `assets/4l-draft-template.md`를 Read로 참조해 `{period_label}`을 치환하고, 네 섹션 아래 실제 항목으로 채운다.

### Step 5: 사용자 확인 (AskUserQuestion)

```
AskUserQuestion:
  question: "위 4L 초안을 '{period_label} 주간 리뷰' 페이지로 생성할까요?"
  options:
    - label: "확정"
      description: "초안 그대로 Notion에 생성합니다."
    - label: "수정하기"
      description: "일부 항목을 변경한 뒤 생성합니다."
    - label: "취소"
      description: "생성하지 않고 종료합니다."
```

- **"확정"**: Step 4 초안 그대로 Step 6 진행.
- **"수정하기"**: 자유 텍스트로 변경 사항을 입력받아 반영 후 Step 6 진행.
- **"취소"**: 아무것도 쓰지 않고 종료.

### Step 6: Notion 페이지 생성

```bash
python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly-review.py create \
  --week current \
  --liked "항목1
항목2" \
  --learned "항목1" \
  --lacked "항목1" \
  --longed-for "항목1"
```

- `--liked`/`--learned`/`--lacked`/`--longed-for`는 줄바꿈으로 항목을 구분한다 (한 줄 = 불릿 하나).
- Step 1과 동일한 `--week` 값을 사용해야 동일한 기간 라벨이 생성된다.
- 성공 시 응답의 `url`을 사용자에게 그대로 보여준다.

---

## 결과 출력 형식

```
✅ '{title}' 페이지 생성 완료
{url}
```

---

## 주의사항

- `NOTION_TOKEN` 환경변수 필요: `~/.secrets.zsh`에서 로드.
- 대상 DB는 "주간 리뷰" DB(`27664745-3170-8097-bb54-e1962a8242ff`)이며 title 속성만 가진다 (4L은 본문 H2 섹션으로 기록).
- `scripts/notion-weekly.py weekly-daily-summary`의 응답 형식을 바꾸면 이 스킬의 Step 2/3도 함께 확인해야 한다.
- 페이지 생성은 되돌리기 쉬운 작업(Notion에서 직접 삭제 가능)이지만, 중복 생성을 막기 위해 Step 1 중복 체크를 반드시 거친다.

---

## 검증

```bash
python3 /Users/changhwan/.claude/skills/weekly:4l-review/scripts/notion-weekly-review.py find-existing --week current
```

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 `NOTION_TOKEN` 확인
- `HTTP 400` → `--week` 값 확인, DB 필터 속성명(`이름`) 변경 여부 확인
- `create` 응답에 `success: false` → 에러 메시지 확인 후 재시도
