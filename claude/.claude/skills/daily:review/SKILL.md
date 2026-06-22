---
name: daily:review
description: |
  하루 마무리 스킬. 오늘 업무 일지를 기반으로 회고 진행.
  사용 시점: (1) 하루 종료 시 오늘 한 일 요약, (2) 내일 할 것들 정리,
  (3) KPT 방식 daily 회고, (4) Notion 업데이트.
  트리거 키워드: "하루 마무리", "일지 마무리", "오늘 회고", "KPT", "daily:review".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:review/scripts/extract-work.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:review/scripts/llm-wiki-append.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:review/scripts/obsidian-remind-append.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py *)
  - AskUserQuestion
---

# End-Daily Skill: 하루 마무리 워크플로우

오늘 업무 일지를 읽고 분석해 회고를 진행하고, 내일 할 것들과 KPT를 Notion에 업데이트합니다.

---

## 핵심 원칙

- 스크립트만 호출한다. Notion MCP 도구는 사용하지 않는다 (토큰 효율).
- JSON 응답을 파싱해 구조화된 회고 포맷으로 출력한다.
- 각 단계마다 사용자 확인 후에만 Notion을 업데이트한다.

---

## 워크플로우 (3단계)

### Step 1 — 데이터 수집 (자동, 병렬 실행)

네 소스를 **동시에** 읽는다:

```bash
# (1) Notion 일지 (page_id, tomorrow, kpt 필드 획득용)
python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py read --date today

# (2) Obsidian Daily Note todos (primary todos 소스)
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py today

# (3) 오늘 Claude 대화 세션 로그 (Obsidian에 없는 작업 포착)
python3 /Users/changhwan/.claude/skills/daily:review/scripts/extract-work.py --date today

# (4) Notion Task DB 전체 활성 목록 — 기한 초과 탐지 + Step 2.5 매칭 재사용
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py search-tasks
```

**종합 분석 로직:**

| 소스 | 사용 목적 |
|------|-----------|
| Notion `read` | `page_id`, `tomorrow`, `kpt` 필드 획득 전용 |
| Obsidian `today` → `todos.completed` | **오늘 한 일 유일한 기준** — 세션 로그 보완 없음 |
| Obsidian `today` → `todos.in_progress` | **미완료 항목 primary source** |
| Obsidian `today` → `top3` | 오늘 목표 달성 여부 + `[실행]`/`[탐색]` 태그별 완료율 |
| Obsidian `today` → `notes` | 리마인드 생성 원천 (Step 3.5) |
| Obsidian Daily Note → `## Hypothesis Log` | 가설-실행 사이클 분석 (Growth Feedback용) |
| 세션 로그 `sessions` | KPT·Growth Feedback 보완용 — **오늘 한 일 요약에는 미포함** |
| Notion `search-tasks` → `due_date` | 반복 이월 탐지(Step 2.1) + 미등록 Task 매칭(Step 2.5) 재사용 |

> ⚠️ Notion `todos` 필드는 DB 프로퍼티 컬럼만 읽히므로 실제 todos와 불일치. **Obsidian을 primary source로 사용**한다.

**Hypothesis Log 파싱 (Growth Feedback용):**

Obsidian Daily Note의 `## Hypothesis Log` 섹션을 Read 도구로 파싱한다:
- `### [HH:MM] 이슈명` → 가설 기록 건수
- `결과: H{N}이 맞았다` → 첫 가설(H1) 적중 여부
- `놓친 것:` → 놓친 레이어 집계
- 가설 항목(H1, H2, ...) 개수 → 평균 사이클 횟수

Hypothesis Log가 비어있으면(`-` 한 줄만 있거나 섹션 없음) Growth Feedback에서 가설 관련 항목을 생략한다.

**Top 3 실행율 파싱 (Growth Feedback용):**

Obsidian Daily Note의 `## Top 3 오늘의 목표`에서:
- `[x]`/`[ ]` → 전체 완료율
- `[실행]`/`[탐색]` 태그 → 태그별 완료율 분리

**세션 로그 해석 방법 (KPT·Growth Feedback 보완용):**
- `sessions[].project`로 어떤 리포지토리/프로젝트에서 작업했는지 파악
- `sessions[].user_messages`에서 KPT Problem·Try 작성에 활용할 맥락 추출
- **오늘 한 일 요약에는 포함하지 않는다** — Obsidian `todos.completed`가 유일한 완료 기준

**출력 포맷:**
```
## {YYYY-MM-DD} 하루 마무리

### 오늘 한 일 요약
- 항목1
- 항목2
(완료 항목이 없으면 "없음" 한 줄)

### 미완료 🔄
- 항목 (있을 경우만)

### 메모 / 인사이트 📝
- 메모 (있을 경우만 — Obsidian `## Notes`에서)
```

---

### Step 2 — ROI 분석 + 내일 할 것들 + KPT 초안 (한 번에 제시)

Step 1에서 수집한 전체 작업 맥락 기반으로 **ROI 분석 → 내일 할 것들 → KPT를 동시에 생성해 한 번에 보여준다.**

#### 2.0 ROI 분석

오늘 완료한 작업을 아래 기준으로 분류한다. 스크립트 없이 Claude가 직접 추론한다.
**Top 3 정렬도는 이 섹션에서 단독 계산하며 Growth Feedback은 결과를 참조만 한다** (중복 계산 금지).

**Empty state:** Step 1에서 완료 작업(`todos.completed` + 세션 로그 추가 완료)이 0건이면
ROI 분석 표를 생략하고 `> 오늘 완료 작업 없음 — ROI 분석 생략` 한 줄만 출력한 뒤 다음 섹션으로 진행한다.

**ROI 분류 기준:**

| 등급 | 판정 기준 | 예시 |
|------|-----------|------|
| High | 제품팀 병목·장애 직접 해결 / 반복 작업 자동화 / 팀 생산성 즉각 향상 | 장애 대응, CI 속도 개선, onboarding 자동화 |
| Medium | 장기 임팩트 작업 — 모니터링 강화, 문서화, 설계, 명확한 목적의 기술 탐색 | 대시보드 개선, ADR 작성, 아키텍처 설계 |
| Low | 자동화 가능한 수동 반복 / 결론 없는 탐색 / 재작업 / ROI 불명확한 작업 | 수동 배포 확인, 목적 불명확한 조사, 반복 수동 확인 |

**Reactive vs Proactive 판정:**
- Reactive: 요청·장애·알림 대응 (외부 트리거로 시작)
- Proactive: 자체 발의 개선·자동화·학습 (내부 트리거로 시작)

**ROI KPT 반영 룰:**
- Low ROI 작업 발견 → **Problem** 섹션에 포함 (자동화/제거 후보 명시)
- Reactive 비율 > 70% → **Problem**: 능동적 개선 시간 부족
- Top 3 정렬도 < 50% → **Problem**: 계획-실행 미스매치
- Low ROI 자동화 가능 항목 → **Try** 섹션에 포함
- 반복 이월 Warning 작업 → **Problem** 섹션에 포함 (작업명 + 초과일수 명시)
- 반복 이월 Critical 작업 → **Problem** + **Try** 양쪽에 포함 (Try에 구체적 처리 계획: 상향/분할/삭제 중 선택)

**ROI 분석 출력:**
```
### ROI 분석
| 작업 | 분류 | ROI | 비고 |
|------|------|-----|------|
| 항목1 | 인프라 개선 | High | 자동화 구현 |
| 항목2 | 문서화 | Medium | 장기 임팩트 |
| 항목3 | 수동 배포 확인 | Low | 스크립트화 가능 |

**ROI 분포:** High {N}% / Medium {N}% / Low {N}%   ← Step 4 raw/ 아카이빙에 그대로 전달
**Reactive** {N}% / **Proactive** {N}%
**Top 3 정렬도:** {완료}/{전체} ({%}) — 계획한 작업 중 실제 수행 비율 (이 값을 Growth Feedback에서 재사용)
**Low ROI 작업:** {목록 또는 없음}
```

---

#### 2.1 반복 이월 경고

Step 1의 `search-tasks` 결과(재호출 없음)에서 오늘 날짜(KST) 기준 기한 초과 Task를 탐지한다.

> **Caveat:** `due_date` 초과는 "반복 이월"의 직접 신호가 아닌 proxy 신호다.
> 한 번도 이월되지 않은 단순 지연 Task도 포함될 수 있다.
> 실제 이월 횟수가 필요하면 Notion DB 편집 이력을 별도 조회해야 한다 (현재 구현 범위 외).

**탐지 기준:**

| 초과 기간 | 등급 | 의미 |
|-----------|------|------|
| 2~6일 | Warning | 이월 반복 의심 |
| 7일 이상 | Critical | 우선순위 구조 문제 |

**탐지 로직:**
1. `search-tasks` 결과에서 `status != 완료` AND `due_date != null` AND `due_date < today(KST)` 필터링
2. 결과를 두 그룹으로 분리:
   - **그룹 A (높은 위험)**: `todos.in_progress`와 이름 매칭 안 됨 → "사용자가 잊고 있는 작업"
   - **그룹 B**: `todos.in_progress`와 이름 매칭됨 → 오늘 인지하고 있으나 미완료
3. 정렬: 등급 내림차순(Critical → Warning) → 초과일수 내림차순
4. 표 출력은 그룹 A를 위에, 그룹 B를 아래에 두고 그룹 헤더 행으로 구분
5. KPT 반영:
   - Critical 항목 → **Problem** + **Try** 양쪽 자동 포함
   - Warning 항목 → **Problem**에만 포함
   - 동일 작업이 `Low ROI` 작업과 겹치면 Problem에 **한 번만 등록** (중복 제거)
6. `search-tasks` API 실패 시 이 섹션 전체를 생략하고 KPT 본문에 "반복 이월 탐지 실패 (search-tasks 오류)" 한 줄을 Problem에 추가

**출력 (탐지 대상 0건이면 섹션 전체 생략):**
```
### 반복 이월 경고
| 작업 | 마감일 | 초과 | 등급 | 권고 |
|------|--------|------|------|------|
| **[잊고 있는 작업]** |  |  |  |  |
| 작업명 X | 2026-05-08 | 7일 | Critical | 우선순위 상향 / 분할 / 삭제 검토 |
| **[오늘 인지·미완료]** |  |  |  |  |
| 작업명 Y | 2026-05-12 | 3일 | Warning | 이번 주 내 확정 또는 이월 사유 명시 |

> Critical 작업: 우선순위 재설정, 더 작게 분할, 또는 삭제를 결정하세요.
> Warning 작업: 이번 주 내 처리 날짜를 확정하거나 이월 사유를 KPT에 기록하세요.
> [잊고 있는 작업] 그룹은 오늘 todos에 안 올린 기한 초과 Task — 가장 먼저 확인하세요.
```

---

**내일 할 것들 초안 생성 로직:**
1. 기존 `tomorrow` 필드 항목 포함 (오늘 완료된 항목은 제거)
2. 오늘 미완료 항목 포함
3. 세션 로그에서 파악된 진행 중 작업 중 내일 계속될 것 포함

**KPT 초안 생성 로직:**
- Keep: 오늘 완료한 작업, 잘 된 점 (두 소스 모두 반영)
- Problem: 미완료 항목, 반복 이월되는 작업, 병목
- Try: Problem 해결을 위한 구체적 개선 행동

**Growth Feedback 생성 로직 (KPT 하단에 추가):**
1. 실행율은 **2.0 ROI 분석의 Top 3 정렬도 값을 그대로 재사용** (중복 계산 금지)
2. `[실행]`/`[탐색]` 태그별 완료율 분리: `[실행] {M}/{N}, [탐색] {M}/{N}` (태그 정보는 ROI 분석에는 없으므로 여기서 별도 계산)
3. `## Hypothesis Log` 파싱:
   - `결과: H1이 맞았다` → 첫 가설 적중
   - `결과: H{2+}이 맞았다` 또는 `놓친 것:` → 놓친 레이어
   - 기록 건수 0이면 가설 관련 항목 전체 생략
4. Top 3에 `[실행]`/`[탐색]` 태그가 없으면 (아직 새 형식 미적용) Growth Feedback 섹션 전체를 생략

**출력 포맷:**
```
### ROI 분석
| 작업 | 분류 | ROI | 비고 |
|------|------|-----|------|
| (오늘 완료 항목별 row — 최소 1개. 0개면 표 생략 후 "오늘 완료 작업 없음 — ROI 분석 생략") |

**ROI 분포:** High {N}% / Medium {N}% / Low {N}%
**Reactive** {N}% / **Proactive** {N}%
**Top 3 정렬도:** {N}/{M} ({%})
**Low ROI 작업:** {목록 또는 없음}

---

### 반복 이월 경고
(탐지 대상 0건이면 이 섹션 생략)
| 작업 | 마감일 | 초과 | 등급 | 권고 |
|------|--------|------|------|------|
...

---

### 내일 할 것들 (초안)
- 항목1
- 항목2

---

### KPT 회고

**Keep** ✅
- 잘 된 것, 계속 유지할 것

**Problem** ⚠️
- 문제가 된 것, 개선이 필요한 것

**Try** 🔄
- 다음에 시도할 개선 방법

---

### Growth Feedback 📊
실행율: {완료}/{전체} ({%}) — [실행] {M}/{N}, [탐색] {M}/{N}
가설 사이클: {N}건
  - 첫 가설 적중: {N}건
  - 놓친 레이어: {목록}
(Hypothesis Log 기록이 없으면 가설 사이클 블록 생략)

수정할 내용 있으시면 알려주세요. 없으면 y로 Notion에 저장합니다.
```

---

### Step 2.5 — 미완료 Todo → Notion Task 등록 (선택)

Step 1에서 파악된 `todos.in_progress` (Obsidian `[ ]` 미완료 항목)를
Notion Task DB와 대조하여 미등록 항목의 등록을 제안한다.

**2.5.1. 활성 Task 목록 재사용**

Step 1에서 이미 조회한 `search-tasks` 결과를 그대로 사용한다 (재호출 없음).

**2.5.2. 매칭 판정 (Claude가 직접 수행)**

`todos.in_progress` 각 항목에 대해 `search-tasks` 결과의 `name`과 의미 기반 대조:
- 핵심 키워드가 70%+ 겹치거나, 한쪽이 다른 쪽의 부분 문자열이면 → **매칭 (Skip)**
- 매칭 없음 → **등록 후보**

**2.5.3. 사용자 확인 (AskUserQuestion)**

등록 후보가 1개 이상이면:

```
📋 Notion Task에 미등록된 미완료 항목:
1. k8s event dashboard 구성
2. Cilium 패치 버전 업그레이드 검토

(이미 등록됨 — Skip: "Alert 개선" ↔ "Alert improvement - alert rule redesign")

등록 방법을 선택하세요.
options:
  - label: "전체 등록"
  - label: "선택 등록 (번호 입력)"
  - label: "스킵"
```

등록 후보가 0개이면 이 Step 전체를 메시지 없이 스킵한다.

**2.5.4. Task 생성**

선택된 항목별:

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "항목명" --priority "P3" --category "WORK" \
  --due "내일 날짜(YYYY-MM-DD)"
```

- Priority: 기본 P3. 내일 할 것들 초안에 포함된 항목이면 P2 고려.
- Due Date: 내일 날짜 (carry-over 성격).
- Category: WORK.
- 성공 시 `📥 등록 완료: [P3] 항목명 (~YYYY-MM-DD)` 형식으로 출력.

---

### Step 3 — Notion 업데이트 (사용자 확인 후)

사용자가 y 또는 확인하면 세 업데이트를 **동시에 병렬 실행**:

```bash
python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py update-todos \
  --page-id PAGE_ID \
  --content "~~완료된 항목1~~\n~~완료된 항목2~~\n- 미완료 항목3"

python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py update-tomorrow \
  --page-id PAGE_ID \
  --content "- 항목1\n- 항목2"

python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py update-kpt \
  --page-id PAGE_ID \
  --content "Keep\n- 항목\n\nProblem\n- 항목\n\nTry\n- 항목"
```

`update-todos`에 전달할 content 포맷 규칙:
- Obsidian `[x]` 완료 항목 → `~~항목명~~` (strikethrough)
- Obsidian `[ ]` 미완료 항목 → `- 항목명`
- 세션 로그 추가 완료 항목 → `~~항목명~~` (strikethrough)

Notion Todos는 **기록 전용**이며 진행 중인 Todo 관리의 source of truth가 아니다.
완료/미완료 구분은 반드시 Obsidian 체크박스(`[x]`/`[ ]`) 기준으로 판단한다.

---

### Step 3.5 — Obsidian 리마인드 추가 (Step 3 이후 자동)

Step 3 완료 후, 오늘 완료된 작업 중 기억할 만한 것 + `## Notes` 내용을 요약해
오늘 Obsidian Daily Note의 `## 리마인드` 섹션에 append한다.

**선별 기준:**
- 완료된 작업 중 배움·결정·해결 패턴이 있는 것 1-3건만 (단순 완료 확인·수동 반복 작업 생략)
- `## Notes`가 비어있지 않으면 그대로 포함
- 추가 대상이 없으면 (완료 없음 + 노트 없음) 이 Step을 건너뛴다

**포맷:**
```
- [YYYY-MM-DD] {핵심 제목 1줄}
  {기억할 이유 또는 핵심 내용 1줄}
```

**실행:**
```bash
python3 /Users/changhwan/.claude/skills/daily:review/scripts/obsidian-remind-append.py \
  --date YYYY-MM-DD \
  --items '[{"title": "...", "detail": "..."}, ...]'
```

출력:
```
📌 리마인드 {N}건 추가 완료 — {YYYY-MM-DD}.md
```

---

### Step 4 — LLM Wiki Raw 아카이빙 (1회 질문 후 자동)

Step 3 완료 후, **사용자에게 한 줄 질문** 후 raw/에 append한다.
업무 데이터(결정·배운 것·개선점·주요 작업)는 자동 합성, 개인 상태는 사용자 응답으로 채운다.

**Step 4.1 — 개인 상태 1회 질문 (AskUserQuestion)**

Step 2 KPT 확인과 별도로, 다음을 한 번에 묻는다:

```
오늘 하루 짧게:
1. 에너지/집중도? (예: 높음 / 보통 / 낮음 또는 한 줄)
2. 인상 깊었던 것? (사람, 대화, 아이디어 — 없으면 없음)
3. 지금 머릿속에 남는 생각? (없으면 없음)
```

응답이 없거나 "없음"이면 해당 항목을 `-` 로 기록한다.

**Step 4.2 — raw/ 파일 합성 및 append**

업무 항목은 Step 1~2 데이터에서 자동 추출, 개인 상태는 사용자 응답 사용.

| 항목 | 소스 |
|------|------|
| 핵심 결정 | KPT Try + 오늘 완료 작업 중 의사결정 사항 |
| 배운 것 | KPT Keep + 세션 로그에서 학습·발견 내용 |
| 개선점/후회 | KPT Problem에서 구조적 문제 또는 반복 실수 |
| 주요 작업 | 완료 항목 요약 (3줄 이내) |
| ROI 분포 | Step 2.0 ROI 분석의 `High {N}% / Medium {N}% / Low {N}%` 값 그대로 |
| 에너지/집중도 | Step 4.1 사용자 응답 |
| 인상 깊었던 것 | Step 4.1 사용자 응답 |
| 머릿속에 남는 생각 | Step 4.1 사용자 응답 |

> ROI 분포는 raw/에 누적되어 주간/월간 트렌드 분석의 원천 데이터가 된다.
> Step 2.0이 Empty state(완료 작업 0건)였다면 `ROI 분포: -` 로 기록한다.

**포맷:**
```
## {YYYY-MM-DD} 핵심 기록

**결정한 것:**
- [결정 내용] (이유/맥락)

**배운 것:**
- [학습 내용]

**개선점/후회:**
- [문제 / 반복 패턴]

**주요 작업:**
- [작업 요약]

**ROI 분포:** High {N}% / Medium {N}% / Low {N}%

**오늘의 상태:**
- 에너지/집중도: [사용자 응답]
- 인상 깊었던 것: [사용자 응답]
- 머릿속에 남는 생각: [사용자 응답]
```

**실행:**
```bash
python3 /Users/changhwan/.claude/skills/daily:review/scripts/llm-wiki-append.py \
  --date YYYY-MM-DD \
  --content "## YYYY-MM-DD 핵심 기록\n..."
```

출력:
```
📚 LLM Wiki Raw 아카이빙 완료
- 파일: 04. Wiki/personal/raw/YYYY-MM-DD.md
```

---

## 스크립트 명령어 요약

| 명령 | 용도 |
|------|------|
| `read --date today` | 오늘 일지 읽기 |
| `update-todos --page-id ID --content "..."` | `Todo's` 속성 교체 (오늘 한 일) |
| `update-tomorrow --page-id ID --content "..."` | `내일 할 것들` 속성 교체 |
| `update-kpt --page-id ID --content "..."` | `KPT` 속성 교체 |

- `page_id`는 `read` 명령 응답의 `page_id` 필드 사용
- `update-todos`, `update-tomorrow`, `update-kpt` 모두 기존 값을 **교체** (append 아님)

---

## 주의사항

- Notion 업데이트는 항상 사용자 확인 후 실행
- **Step 1에서 Notion + Obsidian + 세션 로그 세 소스를 반드시 병렬로 읽는다** — Notion `Todo's` 프로퍼티는 DB 컬럼값(3개 내외)만 반환하므로 실제 todos와 불일치. Obsidian이 primary todos source
- **오늘 한 일 요약은 Obsidian `todos.completed`만 사용한다** — 세션 로그를 추가 완료 항목으로 포함하지 않는다. 세션 로그는 KPT·Growth Feedback 보완에만 사용
- **미완료 항목은 Obsidian `todos.in_progress`에서 읽는다** — Notion `todos` done=false 사용 금지
- **내일 할 것들과 KPT는 Step 2에서 반드시 함께 제시한다** — 한 번에 확인받고 한 번에 업데이트
- 중간에 확인 기다리다 멈추지 않는다 — 두 초안을 모두 보여준 뒤 단 한 번만 확인을 요청한다
- 오늘 일지가 없으면 `error` 필드 포함 — 날짜 확인 안내
- KPT content 포맷: `Keep\n- 항목\n\nProblem\n- 항목\n\nTry\n- 항목\n\nGrowth Feedback\n실행율: {N}/{M} ({%})\n가설 사이클: {N}건` (Growth Feedback이 있을 때만 포함)
- `update-tomorrow`, `update-kpt`는 기존 값을 **교체** (append 아님)

---

## 검증

스크립트 실행 후 JSON 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 `NOTION_TOKEN` 확인
- `error: page not found` → 오늘 날짜 Daily 페이지 존재 여부 확인
- `success: false` → 에러 메시지 확인 후 `page_id` 재검증
