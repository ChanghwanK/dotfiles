# notion-daily.py 스크립트 동작 상세

## `read` 커맨드

- Daily DB (`2bf64745-3170-8016-b20a-ff022dea06cb`)를 Due Date 필터로 쿼리
- 페이지 블록을 파싱해 섹션(Todo's, Note, Tomorrow, KPT) 구분
- `to_do` 블록: `checked` 또는 strikethrough → `done: true`
- `bulleted_list_item`: strikethrough → `done: true`

## `read-weekly` 커맨드

- Task DB (`2da64745-3170-8072-80bd-fb05cf592929`)를 이번 주 월~일 Due Date 범위로 필터
- Priority 오름차순 정렬 (P1 먼저)
- 반환 필드: `page_id`, `name`, `priority`, `status`, `due_start`, `due_end`, `tags`, `level`
- `level` 분류:
  - `weekly_project`: `due_end`가 있고 `status == "진행 중"` (주간 프로젝트 목표)
  - `daily`: 그 외 일반 Task

## `create` 커맨드

- 해당 날짜에 이미 페이지가 있으면 `created: false` + 기존 `page_id` 반환 (멱등 — 중복 방지)
- 없으면 DB에 새 페이지 생성: `이름`(title) + `Due Date`(date) 프로퍼티 설정
- `--title` 미지정 시 기본값: `@YYYY-MM-DD 업무 일지`

## `update-todos` / `update-tomorrow` / `update-kpt` 커맨드

- 각각 `Todo's` / `내일 할 것들` / `KPT` rich_text 프로퍼티를 **교체** (PATCH `/pages/{page_id}`)
- 각 줄이 별도 rich_text 세그먼트로 저장됨 (strikethrough=false)
- **파괴적 연산** — 기존 내용을 덮어쓴다. `--dry-run` 플래그로 변경 미리보기 가능.
