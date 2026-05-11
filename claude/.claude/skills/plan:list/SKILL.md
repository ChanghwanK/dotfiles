---
name: plan:list
description: |
  전체 플랜 인덱스 조회 스킬. active/completed/abandoned/legacy 그룹별로 모든 플랜 나열.
  각 플랜의 이름, 진행률(N/M), 최근 업데이트 날짜 표시.
  트리거 키워드: "플랜 목록", "plan list", "어떤 플랜들이 있어", "과거 플랜", "/plan:list"
model: haiku
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/scripts/plan-todo.py list*)
---

# plan:list

전체 플랜을 status 그룹별로 나열한다.

## 실행 방법

```bash
# 전체
python3 /Users/changhwan/.claude/scripts/plan-todo.py list --status all

# active만
python3 /Users/changhwan/.claude/scripts/plan-todo.py list --status active
```

args에 `active`, `completed`, `abandoned`, `legacy` 중 하나가 있으면 해당 그룹만, 없으면 `all`.

## 출력

```
### ACTIVE (N)
  plan-name  [done/total]  YYYY-MM-DD

### COMPLETED (N)
  ...
```

결과 바로 출력. 추가 설명 불필요.
