# tasktui — Task-Todo 2계층 관리

Notion Task(=Project)와 로컬 Todo를 fzf/gum TUI로 탐색·편집하고 양방향
동기화하는 유저 레벨 기능.

## 데이터 모델 — Todo는 2-lane

Todo는 Task 하위뿐 아니라 **독립(backlog/리마인드)으로도** 존재한다.

| Lane | 계층 | 정의 | 원천/동기화 |
|------|------|------|------|
| **1. Task-scoped** | Task (Project) | Notion Task DB의 한 페이지 | Notion (tasks:capture로 등록) |
| | └ Todo | 그 페이지 본문의 `to_do` 블록 | 로컬 1차 + **Notion 양방향** |
| **2. Standalone** | Backlog Todo | Task 없는 독립 할 일 | 로컬 전용 (**Notion 미동기화**) |

- Backlog는 `📥 Backlog` 가상 버킷(sentinel `__backlog__`)에 모이며 TUI 최상단에 노출된다.
- Backlog Todo는 실제 Notion 페이지가 없어 pull/push 대상에서 **항상 제외**된다(로컬 전용).
- 기존 리마인드(memory 파일)는 `import-memory`로 Backlog에 가져올 수 있다.

## 파일

| 파일 | 역할 |
|------|------|
| `notion_common.py` | Notion API 공통 헬퍼(notion_request/parse_page/타임스탬프). notion-task.py 패턴 추출 |
| `todo_store.py` | 로컬 Todo CRUD (offline-first). 모든 로컬 쓰기를 소유 |
| `todo_sync.py` | 양방향 sync 엔진 (pull/push/충돌해소) |
| `~/.claude/scripts/task-tui.sh` | fzf/gum 2계층 TUI 진입점 |

런타임 데이터(`~/.claude/tasktui/`, dotfiles 밖):
`tasks.json`(Notion 메타 캐시) · `todos.json`(로컬 1차) · `todos.json.bak`(sync 직전 백업) · `.sync_state.json`(충돌 로그/backoff)

## 사용

```bash
# 인터랙티브 TUI (tty 필요 — Claude 도구 안에서 불가)
!bash ~/.claude/scripts/task-tui.sh

# 비인터랙티브 (Claude/스크립트에서)
/task                         # 진행 중 Task 요약
/todo-sync                    # 양방향 sync
/todo-sync dry-run            # 미리보기(쓰기 없음)
```

TUI는 `ctrl-t` 키로 두 탭을 오간다: `[ ●Tasks │ ○Todos ]`
(`tab` 키도 동작하지만 터미널/tmux가 가로채는 경우가 있어 `ctrl-t`를 기본으로 안내한다.)

- **Tasks 탭** (Notion Project 목록): `enter` 해당 Task의 Todo로 드릴인 · `ctrl-t` 탭전환 · `ctrl-r` sync · `ctrl-s` 상태변경 · `ctrl-n` 새 Task · `ctrl-i` memory import · `esc` 종료
  - 우선순위 필터(`1`=P1 `2`=P2 `3`=P3 `0`=ALL). **ALL(`0`)일 때만** 활성 Task 아래에
    최근 완료 Task가 함께 노출된다 — Due Date가 최근 14일 내인 완료본만(읽기 전용 캐시
    `tasks_completed.json`, sync가 채움). last_edited는 일괄 편집으로 흔들려 부적합해
    Due Date를 기준으로 쓴다. Due Date 없는 완료 Task는 표시되지 않는다.
  - 드릴인(Level 2): `enter` 토글 · `ctrl-a` 추가 · `ctrl-e` 편집 · `ctrl-d` 삭제 · `esc` 뒤로
- **Todos 탭** (전체 Todo 평면 목록, 소속 `· Task/Backlog` + `[repo]` 표시): `enter` 토글 · `ctrl-t` 탭전환 · `ctrl-a` 추가(Backlog) · `ctrl-e` 편집 · `ctrl-d` 삭제 · `ctrl-g` repo필터 · `ctrl-r` sync · `esc` 종료

### repo별 Todo 조회

Todo는 보통 repo에 속한다. import된 backlog는 출처 memory 경로(`~/.claude/projects/<cwd-slug>/memory/`)
에서 repo를 **자동 도출**한다(예: `riiid/kubernetes` → `kubernetes`). 수동 추가는 `--repo`로 지정.

- Todos 탭에서 줄 끝 `[repo]` 표시 → fzf에 repo명을 타이핑하면 즉시 필터
- `ctrl-g`로 repo를 골라 명시적 필터(필터 중 `ctrl-a` 추가 시 해당 repo 자동 태그)
- CLI: `todo_store.py list-all-todos --repo kubernetes`

### Backlog / memory import

```bash
# 기본: reminder_*/task_* memory만 Backlog로 (actionable)
python3 ~/.claude/skills/tasks:manage/scripts/todo_store.py import-memory

# project_* 진행상황·지식 노트까지 포함 (노이즈 많음, 명시적 opt-in)
python3 …/todo_store.py import-memory --include-projects

# 수동 Backlog 추가
python3 …/todo_store.py add --task __backlog__ --title "할 일"
```

- `memory_path`로 멱등(이미 import한 파일 재추가 안 함). 완료 처리 시 원본 memory 참조 가능.
- 기본이 `reminder_/task_`인 이유: `project_*`는 진행상황·지식 노트가 대부분이라 backlog를 희석.

## 동기화 모델

- **즉시 시작(k9s 방식)**: TUI는 로컬 캐시(`tasks.json`)로 **즉시 렌더**하며 시작 시 blocking
  pull을 하지 않는다(0.1s대). 최신화는 화면 안에서 `ctrl-r`로 명시적으로 한다.
  - 최초 실행(캐시 없음)일 때만 1회 pull로 초기 데이터를 채운다.
  - 백그라운드 자동 pull은 배제: pull(read-modify-write todos.json)이 사용자의 로컬
    토글과 경합해 변경을 덮을 위험이 있어서다. 동기화는 명시적 시점에만.
- **트리거**: 시작 시 캐시 렌더, 종료 시 push, 수동 `ctrl-r`/`/todo-sync` (백그라운드 데몬 없음)
- **충돌 해소**: todo 단위 last-write-wins. 양쪽 변경 시 `updated_at`(로컬 KST)과
  `last_edited_time`(Notion UTC)을 UTC로 정규화해 최신값 채택. 패배값은
  `.sync_state.json`의 `conflicts`에 보존(손실 방지).
- **안전장치**: sync 직전 `todos.json.bak` 백업, `--dry-run`은 로컬/Notion 무변경.

## 알려진 한계 (개선 여지)

1. **sync 성능**: `ctrl-r`/`/todo-sync`의 pull은 활성 Task 전체(현재 ~68개)를 순회 →
   throttle 0.35s/req로 ~25초. (시작은 캐시라 즉시 — 이 지연은 명시적 sync에만 해당)
   개선안: 진행 중/로컬 Todo 보유 Task로 sync 범위 한정, 또는 요청 병렬화.
2. **block_id 비영속**: Notion 페이지 복제/이동 시 block_id가 바뀌어 매칭이 깨질 수
   있음. 현재는 block_id 단일 키 매칭(텍스트 fuzzy 재매칭 미구현).
3. **완료된 Task의 Todo**: pull은 활성 Task만 reconcile. Notion에서 완료 처리된
   Task의 로컬 Todo는 목록에서 사라지되 todos.json에는 잔류(무해).
