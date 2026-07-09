---
name: plan:todo
description: |
  현재 세션의 active 플랜 TODO 체크리스트 출력 스킬.
  각 step의 상태(✅ 완료 / ⏳ 진행 중 / ⬜ 대기)와 진행률 표시.
  트리거 키워드: "플랜 todo", "남은 작업", "진행 중인 플랜", "/plan:todo", "뭐가 남았어"
model: haiku
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/scripts/plan-todo.py todo*)
---

# plan:todo

현재 active 플랜의 step 체크리스트를 출력한다.

## 실행 방법

```bash
python3 /Users/changhwan/.claude/scripts/plan-todo.py todo
```

## 출력 형식

```
📋 **plan-name**: N/M 완료

  ✅ Step 1: 완료된 단계  _(완료: 2026-05-08T10:25)_
  ⏳ Step 2: 진행 중
  ⬜ Step 3: 대기 중
  ⬜ Step 4: 대기 중
```

결과를 그대로 출력. 추가 설명 불필요.
