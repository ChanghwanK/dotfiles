---
name: handoff:resume
description: |
  복귀 시 저장된 작업 컨텍스트를 복원하는 Resume 스킬.
  트리거 키워드: "돌아왔다", "복귀", "resume", "다시 시작".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py *)
  - Read(/Users/changhwan/.claude/tmp/handoff-latest.json)
---

# Handoff Resume Skill

복귀 시 저장된 작업 컨텍스트를 복원한다.

---

## Resume 워크플로우

### Step 1: Handoff 로드

```bash
python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py load
```

- `ok: true` → Step 2로 진행
- `ok: false` → "저장된 handoff가 없습니다." 안내 후 종료

### Step 2: 컨텍스트 출력

`assets/resume-output.md`의 출력 형식으로 결과를 출력한다.
`elapsed` 필드를 활용해 경과 시간을 표시한다.

### Step 3: 소비하지 않음 (중요)

resume은 handoff를 **consume하지 않는다.** pending 상태를 유지해야 하는 이유:

- handoff에는 여러 task가 담길 수 있다. 사용자가 그중 일부만 이어가도
  consume해 버리면 나머지 task가 다음 pause의 병합 대상에서 빠져 유실된다
- pending → consumed 전환은 다음 pause(save)가 병합을 마친 뒤 자동으로 수행한다
- resume을 여러 번 실행해도 같은 컨텍스트가 나오는 것이 의도된 동작이다 (idempotent 조회)

`consume` 커맨드는 사용자가 **명시적으로** "이 handoff 다 끝났어", "handoff 정리해줘"라고
선언할 때만 실행한다:

```bash
python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py consume
```

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
| pending 없이 resume | "저장된 handoff가 없습니다" 안내 |
| 여러 task 중 일부만 이어감 | consume하지 않으므로 나머지 task는 pending 유지, 다음 pause 때 자동 승계 |
| resume 반복 실행 | 같은 컨텍스트 재출력 (정상, idempotent) |
| 모든 task 완료 선언 ("다 끝났어") | 이때만 consume 실행 |
