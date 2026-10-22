---
paths:
  - "**/.claude/docs/**"
  - "**/.dotfiles/claude/.claude/**"
  - "**/.claude/projects/**/memory/**"
---

# 지침 문서를 고칠 때

`~/.claude/docs/`, 전역 `CLAUDE.md`, 메모리를 추가·수정·삭제하기 전에 `~/.claude/docs/rules-map.md`(규칙 정본 지도)를 Read한다.
새 문서를 만들면 그 지도의 "정본과 로딩 방식" 표에 한 줄을 추가하고, 로딩 방식(상시 / 훅 / Read 지시)을 정한다.
