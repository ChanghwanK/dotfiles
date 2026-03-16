---
name: tasks:capture
description: |
  작업 중 떠오른 아이디어/할 일을 Notion Task DB에 즉시 캡처하는 스킬.
  입력에서 priority/due date를 파싱하면 즉시 생성, 누락 시 추천값과 함께 1회 질문.
  사용 시점: (1) 작업 중 갑자기 떠오른 아이디어 기록, (2) 나중에 할 일 빠르게 메모,
  (3) P3/P4 백로그 아이디어 적재.
  트리거 키워드: "캡처", "capture", "나중에 할 일", "아이디어", "메모해 둬",
  "tasks:capture", "할 일 메모", "잊기 전에".
model: haiku
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py *)
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
| **이름** (필수) | 메타데이터 키워드 제거 후 나머지 텍스트 | — |
| **Priority** | P1/P2/P3/P4 또는 "긴급"(→P1) / "중요"(→P2) / "나중에"(→P4) 감지 | 누락으로 처리 |
| **Category** | "개인", "MY", "personal", "사적" → MY; 그 외 모두 → WORK | `WORK` |
| **Due Date** | YYYY-MM-DD 또는 "오늘"/"내일"/"이번 주 금요일"/"다음 주" → 절대 날짜 변환 | 누락으로 처리 |

**Priority 매핑:**

| 키워드 | Priority 값 |
|--------|-------------|
| P1, 긴급, urgent, 무조건 | `P1 - Must Have` |
| P2, 중요, important | `P2 - Should Have` |
| P3 (명시) | `P3 - Could Have` |
| P4, 나중에, 언젠가 | `P4 - Won't Have` |

---

## Priority / Due Date 추천 로직

Priority가 파싱되지 않은 경우 아래 규칙으로 추천값을 계산한다.

**Priority 추천:**

| 입력 신호 | 추천 |
|-----------|------|
| "긴급", "프로덕션", "장애", "OOM", "크리티컬" 등 | P1 |
| 업무 키워드 + 구체적 액션 (분석, 구현, 배포, 검토 등) | P2 |
| 기본 (대부분 아이디어/메모) | P3 |
| "나중에", "언젠가", "시간 되면", "여유 될 때" | P4 |

**Due Date 추천 (Priority 연동):**

| Priority | Due Date 추천 |
|----------|---------------|
| P1 | 이번 주 금요일 (YYYY-MM-DD) |
| P2 | 이번 주 금요일 또는 다음 주 금요일 (YYYY-MM-DD) |
| P3 / P4 | 없음 |

---

## 워크플로우

### Step 1 — 입력 파싱

사용자 입력을 분석하여 이름, Priority, Category, Due Date를 추출한다.
- 추출 과정은 내부적으로만 처리.
- "오늘" → 오늘 날짜(YYYY-MM-DD), "내일" → 내일 날짜, "이번 주" → 이번 주 금요일로 변환.
- Priority와 Due Date가 파싱되었는지 여부를 확인한다.

### Step 2 — 누락 속성 확인 및 질문

파싱 결과에 따라 아래 케이스로 분기한다.

**Case D (질문 없음)**: Priority, Due Date 모두 파싱됨 → Step 3으로 즉시 진행.

**Case A (Priority만 누락)**: Priority 추천값을 계산하고 AskUserQuestion으로 선택지를 제시한다.

예시 질문:
```
"GPU Memory Pressure 알아보기"의 우선순위를 선택해 주세요.
추천: P3 (일반 조사 태스크)

1. P1 - Must Have (긴급)
2. P2 - Should Have (중요)
3. P3 - Could Have [추천]
4. P4 - Won't Have (나중에)
```

**Case B (Due Date만 누락)**: Priority 기반 추천 Due Date를 계산하고 AskUserQuestion으로 확인한다.

예시 질문:
```
마감일을 설정할까요?
Priority P2 기준 추천: 이번 주 금요일 (2026-03-20) 또는 다음 주 금요일 (2026-03-27)

1. 이번 주 금요일 (2026-03-20) [추천]
2. 다음 주 금요일 (2026-03-27)
3. 마감일 없음
```

**Case C (Priority + Due Date 모두 누락)**: 조합 선택지로 **1회** 질문한다.

예시 질문:
```
"GPU Memory Pressure 알아보기" 속성을 선택해 주세요.
추천: P3, 마감일 없음

1. P3, 마감일 없음 [추천]
2. P2, 이번 주 금요일
3. P2, 다음 주 금요일
4. P1, 이번 주 금요일
5. P4, 마감일 없음
6. 직접 입력 (예: P2 내일)
```

사용자가 "5. 직접 입력"을 선택한 경우, 입력값을 파싱하여 priority/due를 추출한다.

### Step 3 — Notion Task 생성

파싱 + 질문 응답으로 확정된 속성으로 `notion-task.py create-task`를 호출한다.

```bash
# 기본 (WORK, Priority만)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3 - Could Have" --category "WORK"

# Due Date 포함
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P2 - Should Have" --due "2026-03-20" --category "WORK"

# 개인 Task (MY)
python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py \
  create-task --name "Task 이름" --priority "P3 - Could Have" --category "MY"
```

### Step 4 — 완료 출력

성공 시 1줄만 출력 (due date 있으면 포함):

```
📥 캡처 완료: [P3] Task 이름
📥 캡처 완료: [P2] Task 이름 (~2026-03-20)
```

실패 시:

```
❌ 캡처 실패: {에러 메시지}
```

---

## 예시

| 입력 | 파싱 결과 | 질문 발생 여부 |
|------|-----------|---------------|
| `CI 파이프라인 캐시 최적화` | 이름: CI 파이프라인 캐시 최적화, WORK, Priority 누락 | Case C — 1회 질문 |
| `P1 긴급 프로덕션 OOM 이슈 분석` | 이름: 프로덕션 OOM 이슈 분석, P1, WORK | Case D — 즉시 캡처 |
| `내일까지 독서 50페이지 개인` | 이름: 독서 50페이지, MY, 내일 날짜, Priority 누락 | Case A — priority만 질문 |
| `나중에 Karpenter 튜닝 실험` | 이름: Karpenter 튜닝 실험, P4, WORK | Case D — 즉시 캡처 |
| `GPU Memory Pressure 알아보기` | 이름: GPU Memory Pressure 알아보기, WORK, Priority 누락 | Case C — 추천 P3, 마감일 없음 제시 |
| `P2 코드 리뷰` | 이름: 코드 리뷰, P2, WORK, Due Date 누락 | Case B — 이번 주 금요일 추천 |
| `MY personal 독서 목표 설정` | 이름: 독서 목표 설정, MY, Priority 누락 | Case C — 추천 P3 제시 |

---

## 주의사항

- 이 스킬은 **캡처 전용**. Task 수정/삭제/이월은 `/tasks:manage` 사용.
- 중요도 판단이 필요한 Task는 `/tasks:manage`로 생성하여 deliberate하게 설정.
- **최대 1회 질문**으로 속성을 확정한 후 즉시 실행한다. 추가 확인 절차 없음.
