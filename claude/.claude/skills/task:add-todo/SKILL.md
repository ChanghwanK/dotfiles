---
name: task:add-todo
description: |
  오늘 Obsidian Daily Note의 Todos 섹션에 항목을 추가하는 스킬.
  사용 시점: (1) 작업 완료 후 Daily Note에 완료 항목([x])으로 기록, (2) 새 할 일([  ]) 즉시 추가,
  (3) tasks:ing-listup 이후 완료 작업을 Daily Note에 반영.
  트리거 키워드: "todo 추가", "daily todo", "obsidian todo 추가", "할 일 추가", "완료 기록",
  "daily note에 추가", "task:add-todo", "/task:add-todo".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/task:add-todo/scripts/add_todo.py *)
---

# task:add-todo

오늘 날짜의 Obsidian Daily Note `## Todos` 섹션에 항목을 추가한다.
`--done` 플래그로 완료 항목(`- [x]`)과 미완료 항목(`- [ ]`) 모두 지원.

---

## 사용법

```bash
# 미완료 항목 추가
python3 /Users/changhwan/.claude/skills/task:add-todo/scripts/add_todo.py "할 일 텍스트"

# 완료 항목으로 추가 (작업 완료 후 기록 시)
python3 /Users/changhwan/.claude/skills/task:add-todo/scripts/add_todo.py "완료한 작업" --done

# 특정 날짜 Daily Note에 추가
python3 /Users/changhwan/.claude/skills/task:add-todo/scripts/add_todo.py "텍스트" --date 2026-05-12
```

---

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `text` | Todo 항목 텍스트 (필수) | - |
| `--done` | 완료 상태(`- [x]`)로 추가 | false (미완료 `- [ ]`) |
| `--date` | 대상 날짜 `YYYY-MM-DD` | 오늘 |

---

## 예시 출력

```
[task:add-todo] ✅ 완료 추가됨: - [x] IDC Nodes 대시보드 Disk Bottleneck Indicators 추가
파일: /Users/changhwan/Library/Mobile Documents/.../01. Daily/2026-05-12.md
```

---

## 주의사항

- Daily Note 파일이 없으면 에러 종료 (`daily:start`로 먼저 생성)
- `## Todos` 섹션이 없으면 에러 종료
- 기존 항목 마지막 줄 다음에 삽입 (섹션 순서 유지)
