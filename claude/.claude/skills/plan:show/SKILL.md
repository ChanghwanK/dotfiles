---
name: plan:show
description: |
  Plan 본문 재출력 스킬. frontmatter 제외하고 플랜 본문(Summary/Steps/DoD/상세계획)을 그대로 출력.
  이름 없이 호출하면 현재 세션의 active 플랜 출력.
  트리거 키워드: "플랜 다시 보여줘", "plan show", "어떤 플랜이었지", "플랜 본문", "/plan:show"
model: haiku
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/scripts/plan-todo.py show*)
---

# plan:show

현재 active 플랜(또는 지정한 플랜)의 본문을 재출력한다.

## 실행 방법

args가 있으면 부분 이름 매칭으로 찾고, 없으면 현재 active 플랜을 출력.

```bash
python3 /Users/changhwan/.claude/scripts/plan-todo.py show {args}
```

## 출력

플랜 파일의 frontmatter를 제외한 본문 markdown 그대로 출력.
추가 설명 없이 바로 본문만 출력.
