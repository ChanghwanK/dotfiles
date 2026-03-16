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

### Step 1 — Handoff 로드

```bash
python3 /Users/changhwan/.claude/skills/handoff:pause/scripts/handoff.py load
```

- `ok: true` → Step 2로 진행
- `ok: false` → "저장된 handoff가 없습니다." 안내 후 종료

### Step 2 — 컨텍스트 출력

`assets/resume-output.md`의 출력 형식으로 결과를 출력한다.
`elapsed` 필드를 활용해 경과 시간을 표시한다.

### Step 3 — Handoff 소비

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
