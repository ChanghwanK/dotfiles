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
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py *)
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

세 소스를 **동시에** 읽는다:

```bash
# (1) Notion 일지 (page_id, tomorrow, kpt 필드 획득용)
python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py read --date today

# (2) Obsidian Daily Note todos (primary todos 소스)
python3 /Users/changhwan/.claude/skills/tasks:show/scripts/notion-task.py today

# (3) 오늘 Claude 대화 transcript (Obsidian에 없는 작업 포착)
python3 /Users/changhwan/.claude/skills/daily:review/scripts/extract-work.py --date today
```

**종합 분석 로직:**

| 소스 | 사용 목적 |
|------|-----------|
| Notion `read` | `page_id`, `tomorrow`, `kpt` 필드 획득 전용 |
| Obsidian `today` → `todos.completed` | **완료 항목 primary source** |
| Obsidian `today` → `todos.in_progress` | **미완료 항목 primary source** |
| Obsidian `today` → `top3` | 오늘 목표 달성 여부 |
| Transcript `sessions` | Obsidian에도 없는 실제 작업 내용 추출 |

> ⚠️ Notion `todos` 필드는 DB 프로퍼티 컬럼만 읽히므로 실제 todos와 불일치. **Obsidian을 primary source로 사용**한다.

**Transcript 해석 방법:**
- `sessions[].project`로 어떤 리포지토리/프로젝트에서 작업했는지 파악
- `sessions[].user_messages`에서 실제 작업 의도와 내용 추출
- Obsidian 완료 목록에 없는 작업을 **추가 완료 항목**으로 포함

**출력 포맷:**
```
## {YYYY-MM-DD} 하루 마무리

### 오늘 한 일 요약
- [Obsidian] 항목1
- [Transcript] 항목2 (프로젝트명)

### 미완료 🔄
- 항목 (있을 경우만)

### 메모 / 인사이트 📝
- 메모 (있을 경우만)
```

---

### Step 2 — 내일 할 것들 + KPT 초안 (한 번에 제시)

Step 1에서 수집한 전체 작업 맥락 기반으로 **동시에 초안 작성해 한 번에 보여준다.**

**내일 할 것들 초안 생성 로직:**
1. 기존 `tomorrow` 필드 항목 포함 (오늘 완료된 항목은 제거)
2. 오늘 미완료 항목 포함
3. Transcript에서 파악된 진행 중 작업 중 내일 계속될 것 포함

**KPT 초안 생성 로직:**
- Keep: 오늘 완료한 작업, 잘 된 점 (두 소스 모두 반영)
- Problem: 미완료 항목, 반복 이월되는 작업, 병목
- Try: Problem 해결을 위한 구체적 개선 행동

**출력 포맷:**
```
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

수정할 내용 있으시면 알려주세요. 없으면 y로 Notion에 저장합니다.
```

---

### Step 3 — Notion 업데이트 (사용자 확인 후)

사용자가 y 또는 확인하면 두 업데이트를 **동시에 병렬 실행**:

```bash
python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py update-tomorrow \
  --page-id PAGE_ID \
  --content "- 항목1\n- 항목2"

python3 /Users/changhwan/.claude/skills/daily:review/scripts/notion-daily.py update-kpt \
  --page-id PAGE_ID \
  --content "Keep\n- 항목\n\nProblem\n- 항목\n\nTry\n- 항목"
```

---

## 스크립트 명령어 요약

| 명령 | 용도 |
|------|------|
| `read --date today` | 오늘 일지 읽기 |
| `update-tomorrow --page-id ID --content "..."` | `내일 할 것들` 속성 교체 |
| `update-kpt --page-id ID --content "..."` | `KPT` 속성 교체 |

- `page_id`는 `read` 명령 응답의 `page_id` 필드 사용
- `update-tomorrow`, `update-kpt`는 기존 값을 **교체** (append 아님)

---

## 주의사항

- Notion 업데이트는 항상 사용자 확인 후 실행
- **Step 1에서 Notion + Obsidian + Transcript 세 소스를 반드시 병렬로 읽는다** — Notion `Todo's` 프로퍼티는 DB 컬럼값(3개 내외)만 반환하므로 실제 todos와 불일치. Obsidian이 primary todos source
- **미완료 항목은 Obsidian `todos.in_progress`에서 읽는다** — Notion `todos` done=false 사용 금지
- **내일 할 것들과 KPT는 Step 2에서 반드시 함께 제시한다** — 한 번에 확인받고 한 번에 업데이트
- 중간에 확인 기다리다 멈추지 않는다 — 두 초안을 모두 보여준 뒤 단 한 번만 확인을 요청한다
- 오늘 일지가 없으면 `error` 필드 포함 — 날짜 확인 안내
- KPT content 포맷: `Keep\n- 항목\n\nProblem\n- 항목\n\nTry\n- 항목`
- `update-tomorrow`, `update-kpt`는 기존 값을 **교체** (append 아님)

---

## 검증

스크립트 실행 후 JSON 응답의 `success` 필드를 반드시 확인한다.

실패 시:
- `NOTION_TOKEN not set` → `~/.secrets.zsh`에서 `NOTION_TOKEN` 확인
- `error: page not found` → 오늘 날짜 Daily 페이지 존재 여부 확인
- `success: false` → 에러 메시지 확인 후 `page_id` 재검증
