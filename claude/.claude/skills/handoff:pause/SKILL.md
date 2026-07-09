---
name: handoff:pause
description: |
  자리 비움 시 현재 작업 컨텍스트를 저장하는 Pause 스킬.
  트리거 키워드: "자리 비움", "나갔다 올게", "점심", "외출", "pause", "handoff".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Write(/Users/changhwan/.claude/tmp/handoff-payload.json)
---

# Handoff Pause Skill

자리를 비울 때 현재 작업 상태를 저장한다.

---

## Pause 워크플로우

### Step 1: 컨텍스트 수집 (병렬)

세 소스를 **동시에** 처리한다:

1. **Claude 대화 분석**: 현재 세션의 대화를 기반으로 아래 4가지를 분석한다.
   - `completed`: 이번 세션에서 완료한 작업들
   - `in_progress`: 진행 중인 작업 (각각 `task`와 `context` 포함)
   - `next`: 다음에 할 것들
   - `notes`: 복귀 시 알아야 할 주의사항

2. **다른 세션 작업 추출** (병렬 실행):
```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date today
```

다른 세션에서 진행한 작업이 있으면 `completed`나 `in_progress`에 반영한다.

3. **기존 pending handoff 병합** (멀티태스크 유실 방지):
```bash
python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py load
```

`ok: true`이고 `status: pending`이면 기존 handoff를 새 payload에 **병합**한다 (버리지 않는다):

- 기존 `in_progress` 중 이번 세션과 무관하거나 아직 미완료인 task → 새 payload의 `in_progress`에 그대로 승계한다. `context` 앞에 `[YYYY-MM-DD 승계]` 표기를 붙인다
- 기존 `in_progress` 중 이번 세션에서 완료된 task → `completed`로 이동한다
- 기존 `next` 중 여전히 유효한 항목 → `next`에 승계한다 (완료·무효화된 항목은 제거)
- 중복 판정은 task 의미 기준 (같은 작업이 양쪽에 있으면 최신 context로 1건만)
- 기존 `notes`에 다른 작업의 핵심 포인터(레포 경로, 이슈 URL, Task ID 등)가 있으면 새 `notes`에 보존한다

이 병합으로 handoff는 항상 "현재 열려 있는 모든 작업"의 단일 뷰가 된다.
서로 다른 시점에 pause한 작업들이 덮어쓰기로 유실되는 것을 막는 핵심 규칙이다.

### Step 2: Handoff 저장

사유(`reason`)는 사용자 메시지에서 추출한다 (예: "점심", "외출", "미팅").
명시되지 않으면 "자리 비움"을 기본값으로 사용한다.

```bash
# 1. 페이로드 JSON 작성
# Write 도구로 /Users/changhwan/.claude/tmp/handoff-payload.json 작성
# 형식:
# {
#   "completed": ["작업1", "작업2"],
#   "in_progress": [{"task": "작업명", "context": "진행 상황"}],
#   "next": ["다음1", "다음2"],
#   "notes": "메모"
# }

# 2. handoff.py save 실행
python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py save --reason "사유" --data /Users/changhwan/.claude/tmp/handoff-payload.json
```

### Step 3: 확인 출력

`assets/pause-output.md`의 출력 형식으로 결과를 출력한다.
항목이 없는 섹션은 생략한다.

---

## 파일 수명주기

| 파일 | 역할 | 수명 |
|------|------|------|
| `handoff-latest.json` | 유일한 복원 대상 (resume이 읽음) | 항상 1개, save가 덮어씀 |
| `handoff-YYYY-MM-DD-HHMM.json` | 저장 시점 **불변 스냅샷** (forensic용) | 14일 후 save 시 자동 삭제. `status`는 저장 시점 값으로 박제되므로 신뢰하지 말 것 |
| `handoff-payload.json` | save 입력용 임시 파일 | save 성공 시 자동 삭제 (stale 재사용 방지) |

---

## Handoff JSON 스키마

```json
{
  "version": 1,
  "timestamp": "2026-03-09T12:30:00+09:00",
  "reason": "점심",
  "status": "pending | consumed",
  "completed": ["완료한 작업1", "작업2"],
  "in_progress": [
    {"task": "진행 중 작업", "context": "어디까지 했는지"}
  ],
  "next": ["다음 할 것1", "다음 할 것2"],
  "notes": "복귀 시 알아야 할 주의사항"
}
```

---

## Edge Cases

| 상황 | 처리 |
|------|------|
| 이미 pending인데 다시 pause | Step 1-3 병합 규칙으로 기존 작업을 승계한 뒤 저장 (save가 기존 pending을 consumed 처리하지만, 내용은 이미 새 payload에 병합돼 있으므로 유실 없음) |
| 승계 task가 오래돼 유효성 불명 | 삭제하지 않고 승계하되 context에 `[확인 필요]` 표기, 사용자가 resume 시 판단 |
| 사유 미제공 | "자리 비움" 기본값 사용 |
| 현재 세션에 대화가 거의 없음 | extract-work.py 결과만 활용 + 기존 pending 병합은 항상 수행 |
