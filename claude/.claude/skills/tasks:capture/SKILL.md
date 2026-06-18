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
| **이름** (필수) | 아래 "제목 추출 원칙" 참조 — 반드시 Claude가 합성 | — |
| **Priority** | 아래 Priority 매핑 참조 | 누락으로 처리 |
| **Category** | "개인", "MY", "personal", "사적" → MY; 그 외 모두 → WORK | `WORK` |
| **Due Date** | YYYY-MM-DD 또는 "오늘"/"내일"/"이번 주 금요일"/"다음 주" → 절대 날짜 변환 (KST 기준) | 누락으로 처리 |
| **Description** | 아래 "Description 추출 원칙" 참조 | 없음 (선택) |
| **Images** | 파일 경로 또는 URL 목록 (아래 "이미지 파싱" 참조) | 없음 (선택) |

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
| P1, 긴급, urgent, 무조건 | `P1 - Must Have` |
| P2, 중요, important | `P2 - Should Have` |
| P3 (명시) | `P3 - Could Have` |
| P4, 나중에, 언젠가 | `P4 - Won't Have` |

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

## 워크플로우

### Step 1 — 입력 파싱

사용자 입력을 분석하여 이름, Priority, Category, Due Date, Description을 추출한다.
- 추출 과정은 내부적으로만 처리.
- "오늘"/"내일"/"이번 주" → KST 기준 절대 날짜(YYYY-MM-DD)로 변환.
- **제목 합성 (반드시)**: "제목 추출 원칙"을 적용. 입력 전체를 제목으로 사용하지 않는다.
- **Description 추출**: "Description 추출 원칙"을 적용. 추가 정보가 있으면 description을 생성한다.
- Priority와 Due Date가 파싱되었는지 여부를 확인한다.

### Step 2 — 누락 속성 확인 및 질문

파싱 결과에 따라 아래 케이스로 분기한다. **모든 선택지 마지막에 "0. 취소" 포함.**

**Case D (질문 없음)**: Priority, Due Date 모두 파싱됨 → Step 3으로 즉시 진행.

**Case A (Priority만 누락)**:

```
"GPU Memory Pressure 알아보기"의 우선순위를 선택해 주세요.
추천: P3 (일반 조사 태스크)

1. P1 - Must Have (긴급)
2. P2 - Should Have (중요)
3. P3 - Could Have [추천]
4. P4 - Won't Have (나중에)
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

### Step 3 — Notion Task 생성

파싱 + 질문 응답으로 확정된 속성으로 `notion-task.py create-task`를 호출한다.

```bash
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3 - Could Have" --category "WORK"

python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2 - Should Have" --due "2026-03-20" \
  --category "WORK" --description "배경 및 이유 설명"

# 이미지 포함 (URL: Notion에 이미지 블록 삽입, 로컬 경로: callout 텍스트로 기록)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2 - Should Have" --category "WORK" \
  --image "https://example.com/diagram.png" \
  --image "/Users/changhwan/Desktop/screenshot.png"
```

### Step 4 — 완료 출력

스크립트 JSON 출력의 `success` 필드로 성공 여부를 판단한다.

**성공** (`"success": true`):

```
📥 캡처 완료: [P3] Task 이름
📥 캡처 완료: [P2] Task 이름 (~2026-03-20)
📥 캡처 완료 ⚠️: [P3] Task 이름 (직접 입력 파싱 실패 → P3 기본값 적용)
```

**실패** (`"success": false`): JSON의 `error` 필드를 추출하여 사람 친화적으로 출력한다.

```
❌ 캡처 실패: NOTION_TOKEN 미설정 — 1Password에서 토큰을 확인하세요.
❌ 캡처 실패: Notion API 오류 (HTTP 400) — 속성명 불일치 가능성.
```

---

## 주의사항

- 이 스킬은 **Task 생성 전담**. Task 상태 변경/삭제는 `/tasks:status`, 이월은 `/tasks:carry-over` 사용.
- **반드시 1회 질문**으로 속성을 확정한 후 즉시 실행. 추가 확인 절차 없음.
- 동일 이름 Task가 이미 존재해도 중복 생성됨 (의도적 설계 — GTD 원칙). 중복 정리는 `/tasks:manage`에서.
