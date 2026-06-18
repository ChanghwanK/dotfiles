---
description: 로컬 Todo ↔ Notion Task to_do 블록 양방향 동기화 (비인터랙티브)
---

로컬 Todo와 Notion Task 페이지의 to_do 블록을 양방향 동기화합니다.
인터랙티브 입력이 없으므로 Claude 도구로 직접 실행할 수 있습니다.

1. `$ARGUMENTS`에 `dry-run`이 포함되면 미리보기만 수행합니다(쓰기 없음):

   ```bash
   python3 ~/.claude/skills/tasks:manage/scripts/todo_sync.py sync --dry-run
   ```

2. 그렇지 않으면 실제 동기화를 수행합니다 (시작 전 todos.json 자동 백업):

   ```bash
   python3 ~/.claude/skills/tasks:manage/scripts/todo_sync.py sync
   ```

3. 결과 JSON에서 다음을 사용자에게 보고합니다:
   - `pull`(tasks/created/adopted/remote_deleted), `push`(appended/updated/deleted/status_pushed)
   - `new_conflicts`가 1 이상이면 충돌 발생을 알리고,
     `~/.claude/tasktui/.sync_state.json`의 `conflicts` 로그에서 패배한 값을
     확인할 수 있음을 안내합니다 (last-write-wins로 최신값이 채택됨).

주의: 68개 활성 Task 전체를 순회하므로 수십 초가 걸릴 수 있습니다(throttle 0.35s/req).
