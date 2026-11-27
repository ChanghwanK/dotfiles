# tasks:manage (공용 스크립트 디렉토리, 스킬 아님)

이 디렉토리에는 `SKILL.md`가 없다. 스킬이 아니라 Notion Task DB를 다루는 공용 스크립트를 두는 곳이다.
사용 기록에 스킬로 잡히지 않는다고 지우면 아래 스킬이 전부 멈춘다.

- `scripts/notion-task.py`: Task 생성·조회·상태 변경·연결. tasks:capture, alfred, daily:start, daily:retrospective,
  notion:add-engineering-note, task:review, tasks:tech-spec이 부른다
- `scripts/task-progress.py`: Task 진행 기록 (`test_task_progress.py`가 테스트)

## 지우거나 옮기기 전에

참조하는 파일 목록을 먼저 확인한다. `skills:manage delete`는 참조가 있으면 삭제를 거부한다.

```bash
python3 ~/.claude/skills/skills:manage/scripts/manage_skill.py delete tasks:manage --dry-run
```

결과의 `referrers`가 비어 있을 때만 지운다. 옮길 때는 `referrers`의 경로 문자열(`skills/tasks:manage/scripts/`)을 함께 바꾼다.
