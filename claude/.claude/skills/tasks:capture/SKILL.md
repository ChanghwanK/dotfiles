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
  - Write
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
| **Type** | "Task"/"Project" 명시 또는 문맥상 명확(예: "여러 단계로 나눠서", "설계+구현+배포"). 명시적으로 선언되지 않으면 **Priority/Due Date와 묶어 질문**(아래 "Type 확인" 참조) | `Task` |

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

### Type 확인

Notion Task DB의 `Type` 속성은 `Task`/`Project` 두 값뿐이다. 기본값은 항상 `Task`.

- **본격 Task(6-필드 본문 적용 대상, 아래 "본문 템플릿" 참조)**: 여러 단계(설계→검증→배포 등)로 나뉘는 상위 작업으로 보이면 Step 2-A 확인 화면에 `Type: Task [추천]`을 함께 보여주고, 사용자가 "2. 수정"으로 `Project`를 선택할 수 있게 한다. Type을 명시적으로 선언한 입력("이건 프로젝트로")이면 질문 없이 바로 반영한다.
- **단순 메모(Step 2-B, 템플릿 미적용)**: 한 줄 메모는 Project 범위가 될 수 없으므로 질문하지 않고 기본값 `Task`를 그대로 적용한다(GTD 캡처 원칙 유지, 불필요한 질문으로 fast-capture를 해치지 않기 위함).

---

## ROI 자동 분류 (질문 없음)

**GTD Inbox 원칙("캡처 ≠ 의사결정")을 지키기 위해 이 분류는 사용자에게 묻지 않는다.** Priority/Due Date와 달리 확인 게이트가 없다. Claude가 제목·description만으로 조용히 추정해 확신이 서면 즉시 반영하고, 진짜 보류 케이스에만 미설정으로 남겨 `/alfred groom`이 나중에 처리하게 한다.

1. [work-definition-framework.md](~/workspace/riiid/kubernetes/devops-wiki/01-decisions/work-definition-framework.md)의 **판단 순서(10문항)를 실제로 1번부터 순회한다.** "제목이 복잡해 보인다", "조사·설계가 필요해 보인다"는 인상만으로 이 순회를 생략하지 않는다. 순회 없이 미설정 처리하는 것이 과거에 발생한 미스 케이스였다.
2. 10문항 중 **하나라도 Yes**가 나오면 그 시점에서 멈추고 해당 유형의 레벨(L1/L2/L3)로 확정한다. 조사·설계·마이그레이션처럼 착수 규모가 크다는 사실은 유형 판단 자체와 무관한 별개의 축(Quick-Win 상향 여부에만 영향)이므로, 규모가 크다는 이유로 유형 확정을 건너뛰지 않는다.
3. 같은 문서의 "Quick-Win 상향 규칙"을 적용한다: 파일 1개 이하의 단일 값/설정/문구 교체, 오타·링크·주석 수정, 명령어 한 번으로 끝나는 수정형 작업이면 L3→Medium, L2→High로 한 단계 올린다. (조사·설계가 필요한 규모면 이 상향만 건너뛴다. 유형 레벨 자체는 2번에서 이미 확정됨)
4. "Notion Task ROI 매핑" 표로 레벨을 High/Medium/Low로 변환한다.
5. **미설정(생략)은 10문항 전부를 순회했는데 전부 No로 확인된 진짜 "보류" 케이스에만 적용한다.** 유형이 여러 개에 걸쳐 보이는 경우는 생략 사유가 아니다. 판단 순서가 정한 우선순위(질문 번호가 빠른 유형 우선)를 그대로 따라 먼저 Yes가 나온 유형으로 확정한다.
6. 단순 한 줄 메모(P3/P4 + description 없음)라도 이 분류는 동일하게 적용한다: 본문 템플릿 여부와 무관하다.

---

## 본문 템플릿 (본격 Task)

GTD Inbox 원칙상 **모든 캡처에 템플릿을 강제하지 않는다.** 단순 메모는 가볍게 유지하고,
**본격 Task**에만 6-필드 본문 템플릿을 페이지 본문에 렌더링한다.

### 본격 판정

아래 중 **하나라도** 해당하면 본격 Task로 보고 본문 템플릿을 적용한다.

- 최종 Priority가 **P1 또는 P2**. 사용자가 명시한 경우뿐 아니라 **자동 추천된 P2도 포함**한다.
- Description이 합성됨 (= 제목 외 추가 정보가 있음)

P3/P4 이면서 description도 없는 **단순 한 줄 메모**는 템플릿을 적용하지 않는다 (기존 경로 유지).

> 자동 추천 P2는 키워드만으로 붙어 정보량이 부족할 수 있다. 이 경우 6-필드를 추정으로 채우지 말고
> Step 1.5 게이트에서 질문하여 확인 후 합성한다. 게이트가 가드 역할을 한다.

### 6-필드 템플릿

```markdown
## 00. Summary
- {대상}
- {현재 상태}
- {접근 방법}

## 01. 문제 정의
- {무엇이 문제인지}
- *As-Is:*
  - {현재 상태}
- *To-Be:*
  - {이상 상태}

## 02. 해결 이유
- {왜 지금 해결해야 하는지}
- {방치 시 발생하는 영향}

## 03. 기대효과
- {파급 범위 또는 커버리지}
- *측정 기준:*
  - {무엇을 언제까지 측정해 판정하는지}

## 04. Goals/Non Goals
Goals
- {조건}일 때, {관찰 가능한 결과}가 발생하지 않는다
- {조건}일 때, {관찰 가능한 결과}가 발생한다
Non-Goals
- {이번엔 다루지 않는 것 (오버엔지니어링 방지 경계)}

## 05. 세부 계획
- [ ] {실행 액션}
- [ ] {검증 액션: 무엇을 확인하는지까지 명시}
- *롤백:*
  - {원복 방법과 소요 시간}
```

### 합성 가이드

- **문제 정의·해결 이유는 세션 컨텍스트에서 먼저 추출한다.** "세션 컨텍스트 분석 게이트" 섹션 참조.
- **추정으로 채우지 않는다.** 불명확하면 게이트에서 질문하여 확인 후 합성한다.
- **Summary는 반드시 3줄 이상.** 정보가 부족하면 `- (TBD) {확인 필요한 항목}` 형태로 표시한다.
- **Goals/Non Goals는 `Goals`/`Non-Goals`를 각각 독립된 줄(문단)로 두고 그 아래 불릿을 붙인다**
  (인라인 라벨이 아니라 별도 줄이어야 페이지 상단 TOC 콜아웃이 각 항목에 개별 링크를 걸 수 있다).
  **TOC 서브 앵커 예외(변경 금지)**: 이 평문 라벨은 `notion-writing-style.md`의 "Goals/Non-Goals는
  실제 헤딩으로" 규칙의 의도된 예외다(`notion-task.py`가 이 정확한 텍스트를 감지해 TOC를 만든다).
  볼드나 `##`/`###` 헤딩으로 바꾸지 않는다.
  Non-Goals는 오버엔지니어링 방지 관점에서 "이번엔 가시성만, 자동화는 범위 외" 같이 범위를 좁히는
  경계를 제시한다.
- **Goals는 행동·동작 기반으로 쓴다 (실행 스텝이 아니라 검증 가능한 관찰 명세).**
  "무엇을 한다"가 아니라 **작업이 끝났을 때 시스템이 어떤 조건에서 어떻게 동작하는지**를 서술한다.
  실행 동작은 전부 `05. 세부 계획`으로 옮긴다.
  - 형식: `{조건}일 때, {관찰 가능한 결과}가 발생한다` 또는 `~ 발생하지 않는다`
  - 좋은 예: "promote가 완료된 stable 리비전에서 replica가 부족해질 때, abort 알림이 오지 않는다" /
    "promote 전 리비전이 카나리 진행 중 abort될 때, abort 알림이 온다"
  - 나쁜 예(05로 옮길 대상): "trigger에 when 조건을 추가한다", "dev/stg/prod에 배포한다"
  - **억제 케이스와 정상 케이스를 쌍으로 쓴다.** "X일 때 안 온다"만 쓰면 과잉 억제(전면 침묵) 회귀를
    잡지 못하므로, "Y일 때는 온다"를 함께 둔다. 이렇게 쓰면 Goals가 그대로 완료 판정 기준 겸
    검증 시나리오가 된다.
  - 환경이 여러 개인 변경은 "위 동작이 dev, stg, prod에서 동일하게 성립한다"를 마지막 Goal로 둔다.
- **`05. 세부 계획`은 실행 액션을 체크박스(`- [ ]`)로 실제 실행 순서대로 나열한다.**
  Goals(무엇이 달성되는가)와 세부 계획(어떻게 하는가)을 분리해 Goals에 실행 스텝이 섞이지 않게 한다.
  - 환경 단계가 있으면 dev → stg → prod 순으로 쪼갠다.
  - 검증 스텝은 "검증한다"로 끝내지 않고 **무엇을 보고 판정하는지**까지 적는다.
  - 마지막에 `*롤백:*` 라벨 불릿으로 원복 방법과 소요 시간을 적는다. 인프라·설정 변경 Task는 이
    항목을 생략하지 않는다.
  - 이번 Task 범위를 넘는 후속 조사·분리 작업도 체크박스로 남겨 별도 Task 생성을 잊지 않게 한다.
- 본문은 위 템플릿 헤딩 구조 그대로 `--body-file`(권장) 또는 `--body` 인라인 문자열로 전달한다.
  6-필드 본문은 백틱·따옴표·체크박스가 섞여 셸 인용이 깨지기 쉬우므로, 스크래치패드에 파일로
  Write한 뒤 `--body-file`로 넘기는 경로를 기본으로 삼는다.
- 체크리스트가 필요한 본문 또는 후속 액션은 `- [ ] 항목` / `- [x] 항목` Markdown을 사용한다.
  `notion-task.py`가 이를 Notion `to_do` block으로 변환하므로, 일반 bullet에 `[ ]` 텍스트를 직접 쓰지 않는다.
- **본문에 헤딩(`## 00.` ~ `## 05.`)이 있으면 `notion-task.py`가 페이지 맨 위에 TOC 콜아웃을
  자동으로 붙이고 각 헤딩/Goals/Non-Goals로 링크를 건다.** Claude가 별도로 목차를 작성할 필요는
  없다 (수동으로 콜아웃/목차 텍스트를 body에 넣지 않는다).
  TOC 선별은 `_lib/notion_toc.py`가 블록 타입 `heading_` 접두사로 일반화 처리하므로 헤딩 번호를
  하드코딩하지 않는다. 필드를 늘려도 목차에 자동 반영된다.
- **문장 스타일**: 초안 합성 시점부터 `~/.claude/docs/notion-writing-style.md` §문장을 따른다.
  서로 밀접한 사실(원인+결과, 비교/대구, 결론+바로 그 근거)은 연결어(~이며, ~고, ~는데, ~므로)로
  한 문장에 묶고, 무관한 사실만 짧게 끊는다. 한 문단·섹션 안에서 "~다."가 3회 이상 연속되면
  인접 문장을 합칠 수 있는지 재검토한다.
- **레이블/화살표/중복**: `~/.claude/docs/notion-writing-style.md`의 "쓰기 시점 체크리스트"를 초안 단계부터 직접 적용한다.
  - 불릿 `레이블: 내용`은 레이블을 `*레이블:*`(이탤릭)로 직접 쓴다.
  - 레이블을 상위 불릿, 내용을 한 단계 들여쓴 하위 불릿으로 항상 중첩한다. 내용이 한 줄이어도 인라인으로 붙이지 않는다.
  - **01. 문제 정의의 As-Is/To-Be 라벨은 영어 단독으로 쓴다**: `*As-Is:*` / `*To-Be:*`. `현재 상태(As-Is)`처럼 한글 번역을 병기하지 않는다. 위 6-필드 템플릿의 표기를 그대로 따른다.
  - 버전/태그/상태 전환은 "to" 대신 화살표(`→`)로 직접 쓴다.
  - 00~05 섹션 간 같은 사실을 재진술하지 않는다 (예: 01. 문제 정의에서 이미 말한 내용을 03. 기대효과에서 다시 서술하지 않는다).
  - **Goals를 동작 명세로 쓰면 `03. 기대효과`와 충돌하기 쉽다.** 동작 서술은 04에만 두고, 03에는 파급 범위(커버리지)와 측정 기준만 남긴다.
  em dash/본문 이모지, "to"→화살표(숫자 버전·backtick 값 한정)는 쓰기 스크립트가 추가로 결정적 backstop을 건다.

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
  본격이면 Step 1.5를 거쳐 6-필드 초안을 합성한다.

### Step 1.5 - 세션 컨텍스트 분석 게이트 (본격 Task에만 적용)

6-필드 템플릿의 **문제 정의**와 **해결 이유**는 추정으로 채우지 않는다.
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

#### Step 2-A - 본격 Task (6-필드 본문 적용)

합성한 6-필드 초안 + 확정될 속성(Priority/Due/Type/ROI)을 **한 번에** 보여주고 단일 확인한다.
(추천값을 그대로 제시. "1회 확인 후 생성" 원칙)

ROI는 묻지 않지만, **어떤 유형으로 판정했는지 한 줄 근거는 확인 화면 앞에 밝힌다**
(10문항 순회 결과를 사용자가 검산할 수 있어야 오분류가 드러난다).
추천 Due가 템플릿 기본값(P2 → 이번 주 금요일)과 다르면 **왜 다른지 한 줄로 적는다**
(예: 3단계 환경 검증에 하루는 부족하므로 다음 주 금요일).

```
ROI 판정: Q1~Q7 No, Q8(가시성 확보형) Yes → L3 → Low. Quick-Win 상향은 3개 환경에 걸쳐 제외.

다음 내용으로 Task를 생성할까요? (P2 · Type: Task [추천] · ~2026-03-27 · ROI Low)

## 00. Summary
- ...
- ...
- ...

## 01. 문제 정의
- ...
- *As-Is:*
  - ...
- *To-Be:*
  - ...

## 02. 해결 이유
- ...
- ...

## 03. 기대효과
- ...
- *측정 기준:*
  - ...

## 04. Goals/Non Goals
Goals
- {조건}일 때, ... 오지 않는다
- {조건}일 때, ... 온다
Non-Goals
- ...

## 05. 세부 계획
- [ ] ...
- [ ] ...
- *롤백:*
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

# 본격 Task: 6-필드 본문 템플릿 전달 (본문 내용은 위 "6-필드 템플릿" 섹션이 단일 출처)
# description은 짧은 한 줄 요약, 본문은 6-필드 전체.
# --type 생략 시 기본값 Task. Project로 확정된 경우만 명시.
#
# 권장 경로: 본문을 스크래치패드 파일로 Write한 뒤 --body-file로 넘긴다.
#   백틱·따옴표·체크박스가 섞인 6-필드 본문에서 셸 인용 사고를 원천 차단한다.
#   (--body-file 과 --body 를 함께 주면 파일이 우선한다)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --due "2026-03-27" \
  --category "WORK" --type "Task" --roi "Low" --description "한 줄 요약" \
  --body-file "/path/to/scratchpad/task-body.md"

# 대안: 짧은 본문은 --body 인라인 Markdown으로 전달해도 된다
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --category "WORK" \
  --body '## 00. Summary
- 대상
- 현재 상태
- 접근 방법'

# 이미지 포함 (URL: Notion에 이미지 블록 삽입, 로컬 경로: callout 텍스트로 기록)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2" --category "WORK" \
  --image "https://example.com/diagram.png" \
  --image "/Users/changhwan/Desktop/screenshot.png"
```

> **본문 인용 주의**: `--body` 인라인 본문에 작은따옴표(`'`)가 포함되면 셸 인용이 깨진다. `'\''`로
> 이스케이프하거나 제거한다. 6-필드 본문은 길고 특수문자가 섞이므로 `--body-file`을 쓰면 이 문제
> 자체가 사라진다.
> 본문 헤딩은 `## 00. Summary` / `## 01. 문제 정의` / `## 02. 해결 이유` / `## 03. 기대효과` /
> `## 04. Goals/Non Goals` / `## 05. 세부 계획` 6개를 고정 순서로 사용한다.
> `notion-task.py`는 헤딩 이름을 검증하지 않는 일반 마크다운 파서이므로, 이 순서·명칭은 스크립트
> 제약이 아니라 이 스킬의 컨벤션이다. 임의로 늘리거나 이름을 바꾸지 않는다.

### Step 3.5 - Task 간 연결 / PR 참조 표기

Task DB에는 `Related Task`라는 self-relation 프로퍼티가 있다 (양방향 sync: 한쪽만 채우면
반대쪽에도 자동 반영). 새 Task가 기존 Task의 후속·연관 작업이면 본문에 마크다운 텍스트
백링크를 쓰지 말고 이 프로퍼티로 연결한다.

```bash
# 생성 시점에 바로 연결 (기존 Task의 page ID를 알고 있을 때)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3" --category "WORK" \
  --related-task "<기존-task-page-id>"

# 이미 존재하는 두 Task를 사후에 연결
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  link-related-task --page-id "<task-A-page-id>" --related-page-id "<task-B-page-id>"
```

**PR 참조는 링크 멘션으로.** 본문·description에서 PR을 언급할 때 `PR #1234` 같은 plain text
대신 GitHub PR의 실제 URL(`https://github.com/riiid/kubernetes/pull/1234`)을 그대로 붙인다.
Notion이 bare URL을 자동으로 언마크(unfurl)해 리치 프리뷰/멘션으로 렌더링한다.

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
