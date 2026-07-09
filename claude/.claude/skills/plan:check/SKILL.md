---
name: plan:check
description: |
  플랜 step 완료 처리 스킬. 지정한 step 번호를 done으로 마크하고 완료 시각 기록.
  모든 step 완료 시 plan status를 automatically completed로 전환.
  트리거 키워드: "step 완료", "plan check", "/plan:check", "완료 처리"
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/scripts/plan-todo.py check*)
  - Bash(python3 /Users/changhwan/.claude/scripts/plan-todo.py todo*)
---

# plan:check

지정 step을 완료 처리하고 진행률을 갱신한다.

## 실행 방법

args가 step 번호 (예: `2`, `3`). 반드시 숫자여야 한다.

```bash
python3 /Users/changhwan/.claude/scripts/plan-todo.py check {args}
```

완료 후 바로 todo 출력으로 현재 진행률 보여주기:

```bash
python3 /Users/changhwan/.claude/scripts/plan-todo.py todo
```

## 출력

```
[plan-todo] Step 2 marked done.

📋 **plan-name**: 2/6 완료
  ✅ Step 1: ...
  ✅ Step 2: ...  _(완료: 2026-05-08T10:30)_
  ⬜ Step 3: ...
```

args 없으면 "step 번호를 지정해주세요 (예: `/plan:check 2`)" 안내.
