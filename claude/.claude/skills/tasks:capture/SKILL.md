---
name: tasks:capture
description: |
  작업 중 떠오른 아이디어/할 일을 Notion Task DB에 즉시 캡처하는 스킬.
  긴 입력은 제목을 합성하고 원본을 description으로 자동 분리. priority/due date 파싱 시 즉시 생성, 누락 시 추천값과 함께 1회 질문.
  사용 시점: (1) 작업 중 갑자기 떠오른 아이디어 기록, (2) 나중에 할 일 빠르게 메모,
  (3) P3/P4 백로그 아이디어 적재.
  트리거 키워드: "캡처", "capture", "나중에 할 일", "아이디어", "메모해 둬",
  "tasks:capture", "할 일 메모", "잊기 전에",
  "Task 추가", "새 Task", "할 일 추가", "Task 만들어줘", "태스크 추가".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py create-task *)
  - AskUserQuestion
---

# tasks:capture

작업 중 떠오른 아이디어를 **최소한의 인터랙션**으로 Notion Task DB에 캡처한다.
GTD Inbox 원칙: 캡처 ≠ 의사결정. 일단 담고, 나중에 `/tasks:manage`로 정리한다.

---

## 핵심 원칙

- **Fast-capture 우선**: 모든 속성이 파싱되면 즉시 생성. 질문은 누락 시에만.
- **추천 기반 질문**: 누락 속성을 물을 때 추천값을 제시하여 빠른 선택 가능.
- **최대 1회 질문**: priority + due date 모두 누락이어도 한 번의 질문으로 묶어서 처리.
- **단일 출력**: 완료 메시지 1줄만 출력.

---

## 입력 파싱 규칙

사용자 입력에서 아래 속성을 추출한다. 명시되지 않은 속성은 기본값 적용.

| 속성 | 추출 방법 | 기본값 |
|------|-----------|--------|
| **이름** (필수) | 아래 "제목 추출 원칙" 참조. 반드시 Claude가 합성 | 없음 |
| **Priority** | 아래 Priority 매핑 참조 | 누락으로 처리 |
| **Category** | "개인", "MY", "personal", "사적" → MY; 그 외 모두 → WORK | `WORK` |
| **Due Date** | YYYY-MM-DD 또는 "오늘"/"내일"/"이번 주 금요일"/"다음 주" → 절대 날짜 변환 (KST 기준) | 누락으로 처리 |
| **Description** | 아래 "Description 추출 원칙" 참조 | 없음 (선택) |
| **Images** | 파일 경로 또는 URL 목록 (아래 "이미지 파싱" 참조) | 없음 (선택) |
| **ROI** | 아래 "ROI 자동 분류 (질문 없음)" 참조. 사용자에게 묻지 않음 | 10문항 순회 결과 전부 No일 때만 미설정 |

### 이미지 파싱

이미지 첨부 신호가 있으면 `--image` 플래그를 추가한다.

**신호:**
- 사용자가 파일 경로를 명시: `"/Users/changhwan/Desktop/error.png"` 등
- 대화에서 이미지(스크린샷)가 시각적으로 첨부됨 → Claude가 해당 이미지를 `~/.claude/todo-images/<title-slug>.png`로 저장 후 경로 사용
- URL 형태: `https://...` (Notion 페이지에 이미지 블록으로 삽입됨)

**규칙:**
- URL은 Notion 페이지에 image 블록으로 삽입
- 로컬 경로는 Notion 페이지에 callout 텍스트로 기록 (경로 보존)
- 이미지 없으면 플래그 생략

**Priority 매핑:**

| 키워드 | Priority 값 |
|--------|-------------|
| P1, 긴급, urgent, 무조건 | `P1` |
| P2, 중요, important | `P2` |
| P3 (명시), 나중에, 언젠가 | `P3` |

### 제목 추출 원칙

**입력 전체를 제목으로 쓰지 않는다.** 반드시 핵심만 뽑아 합성한다.

- **단순 짧은 입력**: 메타데이터 키워드(P1~P4, "개인" 등)만 제거하고 나머지를 제목으로 사용
- **추가 정보가 있는 입력**: Claude가 핵심 동작/목표를 담은 **20~40자 제목**을 합성
  - 추가 정보 = 조건·이유·배경·상세 요구사항 (예: "window는 7일", "왜냐하면", 쉼표 이후 설명)
  - `[카테고리 태그]`가 있으면 제목 앞에 유지
  - 제목 구성 규칙: **동사+목적어 포함, 조건·이유 제외**

### Description 추출 원칙

- **1차 기준 (정보량)**: 원본 입력에 제목 외 추가 정보(조건·이유·배경·요구사항)가 있으면 → description으로 분리
- **2차 기준 (보조)**: 추가 정보 판단이 애매하면 30자 초과 입력에 description 자동 생성
- **단순 짧은 입력**: description 없음

> 예시 및 엣지 케이스 → `references/extraction-rules.md`

---

## Priority / Due Date 추천 로직

Priority가 파싱되지 않은 경우 아래 규칙으로 추천값을 계산한다.

| 입력 신호 | Priority 추천 |
|-----------|--------------|
| "긴급", "프로덕션", "장애", "OOM", "크리티컬" 등 | P1 |
| 업무 키워드 + 구체적 액션 (분석, 구현, 배포, 검토 등) | P2 |
| 기본 (대부분 아이디어/메모) | P3 |
| "나중에", "언젠가", "시간 되면", "여유 될 때" | P4 |

| Priority | Due Date 추천 |
|----------|---------------|
| P1 | 이번 주 금요일 |
| P2 | 이번 주 금요일 또는 다음 주 금요일 |
| P3 / P4 | 없음 |

---

## ROI 자동 분류 (질문 없음)

**GTD Inbox 원칙("캡처 ≠ 의사결정")을 지키기 위해 이 분류는 사용자에게 묻지 않는다.** Priority/Due Date와 달리 확인 게이트가 없다. Claude가 제목·description만으로 조용히 추정해 확신이 서면 즉시 반영하고, 진짜 보류 케이스에만 미설정으로 남겨 `/alfred groom`이 나중에 처리하게 한다.

1. [work-definition-framework.md](~/workspace/riiid/kubernetes/devops-wiki/01-decisions/work-definition-framework.md)의 **판단 순서(10문항)를 실제로 1번부터 순회한다.** "제목이 복잡해 보인다", "조사·설계가 필요해 보인다"는 인상만으로 이 순회를 생략하지 않는다 — 순회 없이 미설정 처리하는 것이 이번에 발생한 미스 케이스였다.
2. 10문항 중 **하나라도 Yes**가 나오면 그 시점에서 멈추고 해당 유형의 레벨(L1/L2/L3)로 확정한다. 조사·설계·마이그레이션처럼 착수 규모가 크다는 사실은 유형 판단 자체와 무관한 별개의 축(Quick-Win 상향 여부에만 영향)이므로, 규모가 크다는 이유로 유형 확정을 건너뛰지 않는다.
3. 같은 문서의 "Quick-Win 상향 규칙"을 적용한다: 파일 1개 이하의 단일 값/설정/문구 교체, 오타·링크·주석 수정, 명령어 한 번으로 끝나는 수정형 작업이면 L3→Medium, L2→High로 한 단계 올린다. (조사·설계가 필요한 규모면 이 상향만 건너뛴다 — 유형 레벨 자체는 2번에서 이미 확정됨)
4. "Notion Task ROI 매핑" 표로 레벨을 High/Medium/Low로 변환한다.
5. **미설정(생략)은 10문항 전부를 순회했는데 전부 No로 확인된 진짜 "보류" 케이스에만 적용한다.** 유형이 여러 개에 걸쳐 보이는 경우는 생략 사유가 아니다 — 판단 순서가 정한 우선순위(질문 번호가 빠른 유형 우선)를 그대로 따라 먼저 Yes가 나온 유형으로 확정한다.
6. 단순 한 줄 메모(P3/P4 + description 없음)라도 이 분류는 동일하게 적용한다: 본문 템플릿 여부와 무관하다.

---

## 본문 템플릿 (본격 Task)

GTD Inbox 원칙상 **모든 캡처에 템플릿을 강제하지 않는다.** 단순 메모는 가볍게 유지하고,
**본격 Task**에만 5-필드 본문 템플릿을 페이지 본문에 렌더링한다.

### 본격 판정

아래 중 **하나라도** 해당하면 본격 Task로 보고 본문 템플릿을 적용한다.

- 최종 Priority가 **P1 또는 P2**. 사용자가 명시한 경우뿐 아니라 **자동 추천된 P2도 포함**한다.
- Description이 합성됨 (= 제목 외 추가 정보가 있음)

P3/P4 이면서 description도 없는 **단순 한 줄 메모**는 템플릿을 적용하지 않는다 (기존 경로 유지).

> 자동 추천 P2는 키워드만으로 붙어 정보량이 부족할 수 있다. 이 경우 5-필드를 추정으로 채우지 말고
> Step 1.5 게이트에서 질문하여 확인 후 합성한다. 게이트가 가드 역할을 한다.

### 5-필드 템플릿

```markdown
## 00. Summary
- {대상}
- {현재 상태}
- {접근 방법}

## 01. 문제 정의
- {무엇이 문제인지}
- {현재 상태(As-Is)}
- {이상 상태(To-Be)}

## 02. 해결 이유
- {왜 지금 해결해야 하는지}
- {방치 시 발생하는 영향}

## 03. 기대효과
- {이 Task로 개선되는 것}
- {측정 가능한 지표 또는 확인 기준}

## 04. Goals/Non Goals
Goals
- {이번 Task로 달성할 것}
Non-Goals
- {이번엔 다루지 않는 것 (오버엔지니어링 방지 경계)}
```

### 합성 가이드

- **문제 정의·해결 이유는 세션 컨텍스트에서 먼저 추출한다.** "세션 컨텍스트 분석 게이트" 섹션 참조.
- **추정으로 채우지 않는다.** 불명확하면 게이트에서 질문하여 확인 후 합성한다.
- **Summary는 반드시 3줄 이상.** 정보가 부족하면 `- (TBD) {확인 필요한 항목}` 형태로 표시한다.
- **Goals/Non Goals는 `Goals`/`Non-Goals`를 각각 독립된 줄(문단)로 두고 그 아래 불릿을 붙인다**
  (인라인 라벨이 아니라 별도 줄이어야 페이지 상단 TOC 콜아웃이 각 항목에 개별 링크를 걸 수 있다).
  Non-Goals는 오버엔지니어링 방지 관점에서 "이번엔 가시성만, 자동화는 범위 외" 같이 범위를 좁히는
  경계를 제시한다.
- 본문은 `--body` 인라인 Markdown 문자열로 전달한다 (위 템플릿 헤딩 구조 그대로).
- 체크리스트가 필요한 본문 또는 후속 액션은 `- [ ] 항목` / `- [x] 항목` Markdown을 사용한다.
  `notion-task.py`가 이를 Notion `to_do` block으로 변환하므로, 일반 bullet에 `[ ]` 텍스트를 직접 쓰지 않는다.
- **본문에 헤딩(`## 00.` ~ `## 04.`)이 있으면 `notion-task.py`가 페이지 맨 위에 TOC 콜아웃을
  자동으로 붙이고 각 헤딩/Goals/Non-Goals로 링크를 건다.** Claude가 별도로 목차를 작성할 필요는
  없다 (수동으로 콜아웃/목차 텍스트를 body에 넣지 않는다).
- **문장 스타일**: 초안 합성 시점부터 `~/.claude/docs/notion-writing-style.md` §문장을 따른다.
  서로 밀접한 사실(원인+결과, 비교/대구, 결론+바로 그 근거)은 연결어(~이며, ~고, ~는데, ~므로)로
  한 문장에 묶고, 무관한 사실만 짧게 끊는다. 한 문단·섹션 안에서 "~다."가 3회 이상 연속되면
  인접 문장을 합칠 수 있는지 재검토한다.

---

## 워크플로우

### Step 1 - 입력 파싱

사용자 입력을 분석하여 이름, Priority, Category, Due Date, Description을 추출한다.
- 추출 과정은 내부적으로만 처리.
- "오늘"/"내일"/"이번 주" → KST 기준 절대 날짜(YYYY-MM-DD)로 변환.
- **제목 합성 (반드시)**: "제목 추출 원칙"을 적용. 입력 전체를 제목으로 사용하지 않는다.
- **Description 추출**: "Description 추출 원칙"을 적용. 추가 정보가 있으면 description을 생성한다.
- Priority와 Due Date가 파싱되었는지 여부를 확인한다.
- **ROI 분류 (질문 없음)**: "ROI 자동 분류" 섹션의 10문항을 실제로 순회해 값을 정한다. 전부 No로 확인된 진짜 보류 케이스만 미설정으로 둔다. 이 단계는 사용자에게 묻지 않는다.
- **본격 판정**: "본문 템플릿 (본격 Task)" 섹션의 판정 기준을 적용한다.
  본격이면 Step 1.5를 거쳐 5-필드 초안을 합성한다.

### Step 1.5 - 세션 컨텍스트 분석 게이트 (본격 Task에만 적용)

5-필드 템플릿의 **문제 정의**와 **해결 이유**는 추정으로 채우지 않는다.
세션 대화에서 명확히 추출 가능한지 먼저 판단한다.

**추출 가능 판단 기준:**

| 필드 | 충분한 경우 | 불충분한 경우 |
|------|------------|--------------|
| 문제 정의 | 대화에서 현재 상태의 문제가 구체적으로 언급됨 | "이거 해줘" 수준으로 문제 맥락이 없음 |
| 해결 이유 | 영향, 불편함, 기술적 근거가 명시됨 | 동기가 전혀 언급되지 않음 |

**불충분하면 등록 전 질문한다.** 최대 2개 질문, AskUserQuestion으로 묶어 1회 확인.

질문 형식:
```
Task를 생성하기 전에 두 가지를 확인할게요.

1. 문제 정의: [지금 어떤 문제가 있나요? 현재 상태에서 무엇이 안 되거나 부족한가요?]
2. 해결 이유: [이 문제를 해결해야 하는 이유가 무엇인가요? 방치하면 어떤 영향이 있나요?]
```

사용자가 답하면 해당 내용을 기반으로 두 필드를 합성한다.
두 필드 모두 세션에서 명확히 추출 가능하면 질문 없이 합성 후 Step 2로 진행한다.

### Step 2 - 확인 및 질문

**본격 Task 여부에 따라 분기한다.**

#### Step 2-A - 본격 Task (5-필드 본문 적용)

합성한 5-필드 초안 + 확정될 속성(Priority/Due)을 **한 번에** 보여주고 단일 확인한다.
(추천값을 그대로 제시. "1회 확인 후 생성" 원칙)

```
다음 내용으로 Task를 생성할까요? (P2 · ~2026-03-20)

## 00. Summary
- ...
- ...
- ...

## 01. 문제 정의
- ...
- ...
- ...

## 02. 해결 이유
- ...
- ...

## 03. 기대효과
- ...
- ...

## 04. Goals/Non Goals
Goals
- ...
Non-Goals
- ...

1. 생성 [추천]
2. 수정 (속성·본문 직접 입력)
0. 취소
```

- "1. 생성" → 합성된 본문과 추천 속성으로 Step 3 진행.
- "2. 수정" → 사용자 입력을 반영하여 속성·본문 갱신 후 생성.
- "0. 취소" → 중단.

#### Step 2-B - 단순 메모 (템플릿 미적용)

파싱 결과에 따라 아래 케이스로 분기한다. **모든 선택지 마지막에 "0. 취소" 포함.**

**Case D (질문 없음)**: Priority, Due Date 모두 파싱됨 → Step 3으로 즉시 진행.

**Case A (Priority만 누락)**:

```
"GPU Memory Pressure 알아보기"의 우선순위를 선택해 주세요.
추천: P3 (일반 조사 태스크)

1. P1 (긴급)
2. P2 (중요)
3. P3 (일반/나중에) [추천]
0. 취소
```

**Case B (Due Date만 누락)**:

```
마감일을 설정할까요?
Priority P2 기준 추천: 이번 주 금요일 (2026-03-20)

1. 이번 주 금요일 (2026-03-20) [추천]
2. 다음 주 금요일 (2026-03-27)
3. 마감일 없음
0. 취소
```

**Case C (Priority + Due Date 모두 누락)**: 조합 선택지로 **1회** 질문한다.

```
"GPU Memory Pressure 알아보기" 속성을 선택해 주세요.
추천: P3, 마감일 없음

1. P3, 마감일 없음 [추천]
2. P2, 이번 주 금요일
3. P2, 다음 주 금요일
4. P1, 이번 주 금요일
5. P4, 마감일 없음
6. 직접 입력 (예: P2 내일)
0. 취소
```

"6. 직접 입력" 선택 후 파싱 실패 → P3, 마감일 없음으로 fallback 후 완료 메시지에 ⚠️ 표시.

### Step 3 - Notion Task 생성

파싱 + 질문 응답으로 확정된 속성으로 `notion-task.py create-task`를 호출한다.

```bash
# 단순 메모 (P3/P4, 본문 템플릿 없음, ROI 애매 → 미설정)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3" --category "WORK"

# ROI가 확신 서면 즉시 반영 (예: 단일 값 수정 → Quick-Win 상향 후 High)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3" --category "WORK" --roi "High"

python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --due "2026-03-20" \
  --category "WORK" --description "배경 및 이유 설명" --roi "Medium"

# 본격 Task: 5-필드 본문 템플릿을 --body 인라인 Markdown으로 전달
# (헤딩 구조 그대로. description은 짧은 한 줄 요약, --body는 전체 본문)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --due "2026-03-20" \
  --category "WORK" --description "한 줄 요약" \
  --body '## 00. Summary
- 대상
- 현재 상태
- 접근 방법

## 01. 문제 정의
- 현재 상태(As-Is)에서 무엇이 문제인지 구체적으로 작성합니다.
- 이상 상태(To-Be)를 작성합니다.

## 02. 해결 이유
- 왜 지금 해결해야 하는지
- 방치 시 발생하는 영향

## 03. 기대효과
- 개선 지표
- 확인 기준

## 04. Goals/Non Goals
Goals
- 이번 Task로 달성할 것
Non-Goals
- 이번 범위에서 제외하는 것'

# 이미지 포함 (URL: Notion에 이미지 블록 삽입, 로컬 경로: callout 텍스트로 기록)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --category "WORK" \
  --image "https://example.com/diagram.png" \
  --image "/Users/changhwan/Desktop/screenshot.png"
```

> **본문 인용 주의**: 본문에 작은따옴표(`'`)가 포함되면 셸 인용이 깨진다. `'\''`로 이스케이프하거나 제거한다.
> 본문 헤딩은 `## 00. Summary` / `## 01. 문제 정의` / `## 02. 해결 이유` / `## 03. 기대효과` / `## 04. Goals/Non Goals` 5개를 고정 순서로 사용한다.

### Step 4 - 완료 출력

스크립트 JSON 출력의 `success` 필드로 성공 여부를 판단한다.

**성공** (`"success": true`): 태그 요약 줄 다음에 반드시 `제목: [{name}]({url})` 줄을 붙인다.
JSON의 `url` 필드(Notion 페이지 URL)를 제목 텍스트 자체의 markdown 링크로 건다 (URL을 별도로 노출하지 않는다).
사용자가 제목을 클릭해 캡처된 내용을 바로 확인할 수 있게 하기 위함이다.

**절대 생략 금지**: 이 줄은 성공 응답마다 예외 없이 포함한다. 완료 메시지만 출력하고
제목/링크 줄을 빠뜨리는 실수가 있었으므로, 최종 답변을 보내기 전에 이 줄이 있는지 반드시 확인한다.

```
📥 캡처 완료: [P3]
제목: [Task 이름](https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)

📥 캡처 완료: [P2][ROI Medium] (~2026-03-20)
제목: [Task 이름](https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)

📥 캡처 완료 ⚠️: [P3] (직접 입력 파싱 실패 → P3 기본값 적용)
제목: [Task 이름](https://www.notion.so/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
```

ROI가 미설정(애매해서 생략)이면 `[ROI ...]` 태그 자체를 붙이지 않는다(불필요한 "미설정" 노이즈 방지).

**실패** (`"success": false`): JSON의 `error` 필드를 추출하여 사람 친화적으로 출력한다.

```
❌ 캡처 실패: NOTION_TOKEN 미설정. 1Password에서 토큰을 확인하세요.
❌ 캡처 실패: Notion API 오류 (HTTP 400). 속성명 불일치 가능성.
```

---

## 주의사항

- 이 스킬은 **Task 생성 전담**. Task 상태 변경/삭제는 `/tasks:status`, 이월은 `/tasks:carry-over` 사용.
- **반드시 1회 질문**으로 속성을 확정한 후 즉시 실행. 추가 확인 절차 없음.
- 동일 이름 Task가 이미 존재해도 중복 생성됨 (의도적 설계, GTD 원칙). 중복 정리는 `/tasks:manage`에서.
