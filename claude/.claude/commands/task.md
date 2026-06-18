---
description: Task-Todo 현황 요약 + TUI 실행 안내 (Notion Task = Project, 로컬 Todo 2계층)
---

다음을 수행합니다.

1. 진행 중 Task와 Todo 진행률 요약을 출력합니다 (캐시만 읽음, API 호출 없음):

   ```bash
   python3 ~/.claude/skills/tasks:manage/scripts/todo_store.py summary
   ```

2. 요약을 사용자에게 보여준 뒤, 인터랙티브 TUI는 tty가 필요하므로 Claude 도구
   안에서 띄울 수 없음을 안내합니다. 사용자가 직접 아래를 실행하도록 안내합니다:

   ```
   !bash ~/.claude/scripts/task-tui.sh
   ```

   - `ctrl-t` 키로 Tasks 탭 ↔ Todos 탭 전환
   - Tasks 탭: `enter` 드릴인 · `ctrl-s` 상태변경 · `ctrl-n` 새 Task · `ctrl-i` import
   - Todos 탭(전체 평면, `[repo]` 표시): `enter` 토글 · `ctrl-a` 추가 · `ctrl-e` 편집 · `ctrl-d` 삭제 · `ctrl-g` repo필터

3. `$ARGUMENTS`가 비어 있지 않으면, 그 내용을 새 Todo 또는 Task 캡처 요청으로
   해석할 수 있는지 확인하고, 필요 시 `tasks:capture` 스킬을 제안합니다.
