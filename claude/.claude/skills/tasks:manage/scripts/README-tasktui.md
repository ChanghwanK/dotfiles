# tasktui: Task-Todo 2계층 관리

Notion Task(=Project)와 로컬 Todo를 fzf/gum TUI로 탐색·편집하고 양방향
동기화하는 유저 레벨 기능.

## 데이터 모델: Todo는 2-lane

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
# 인터랙티브 TUI (tty 필요, Claude 도구 안에서 불가)
!bash ~/.claude/scripts/task-tui.sh

# 비인터랙티브 (Claude/스크립트에서)
/task                         # 진행 중 Task 요약
/todo-sync                    # 양방향 sync
/todo-sync dry-run            # 미리보기(쓰기 없음)
```

TUI는 **엔티티로 분리한 세 탭**을 `ctrl-t`로 순환한다: `[ ●Now │ ○Tasks │ ○Todos ]`
(`tab` 키도 동작하지만 터미널/tmux가 가로채거나 Tasks 탭에서 다중 선택으로 쓰이므로 `ctrl-t`를 기본으로 안내한다.)

**설계 원칙**: Task(프로젝트)와 Todo(실행 항목)는 granularity가 달라 한 리스트에 섞지 않는다(`Tasks`/`Todos`로 분리). 혼합은 "지금 붙어 있는 일"을 보는 `Now` 한 곳에만 의도적으로 둔다. "오늘 마감"·"완료"는 별도 탭이 아니라 각 면의 **칩 필터**다. 시작 탭은 `Now`.

- **Now 탭** (혼합 예외, `📁`=Task `▷`=Todo): 진행 중 Task(`진행 중`) + 진행중 Todo(`진행중`)만 모은다. 마감일 무관, 순수 WIP를 한눈에 점검해 동시 진행이 과한지 본다. `enter` 열기/드릴인 · `space` Todo상태전환 · `ctrl-t` 탭전환 · `ctrl-r` sync · `esc` 종료. 하단에 `WIP: Task N · Todo M` 카운트. Task 상태 변경은 여기서 하지 않는다(Tasks 탭 `ctrl-s`).
- **Tasks 탭** (Notion Project 전용): `enter` Task 세션 · `space` 하위 Todo 드릴인 · `ctrl-s` 상태변경 · `ctrl-a` 새 Task · `ctrl-d` 삭제(Notion) · `ctrl-o` Notion열기 · `ctrl-i` import · `ctrl-p` Plan · `ctrl-r` sync · `esc` 종료
  - 우선순위 필터(`1`=P1 `2`=P2 `3`=P3 `0`=ALL) + **오늘 마감 칩**(`ctrl-f` 토글, 마감 ≤ 오늘(지남 포함)인 Task만). **ALL(`0`)일 때만** 활성 Task 아래에 최근 완료 Task가 함께 노출된다(Due Date 최근 14일 내, 읽기 전용 캐시 `tasks_completed.json`). 오늘 마감 칩이 켜지면 Backlog·완료본은 제외된다.
  - 드릴인(Level 2): `enter` 세션 · `space` 토글 · `ctrl-a` 추가 · `ctrl-e` 제목 · `ctrl-n` 설명 · `ctrl-d` 삭제 · `ctrl-p` Plan · `esc` 뒤로
- **Todos 탭** (실행 항목 전용 평면 목록, 소속 `· Task/Backlog` + `[repo]` 표시): `enter` Claude열기 · `space` 상태전환 · `ctrl-a` 추가(Backlog) · `ctrl-e` 제목 · `ctrl-n` 설명 · `ctrl-d` 삭제 · `ctrl-p` Plan뷰 · `ctrl-g` repo필터 · `ctrl-r` sync · `esc` 종료
  - **렌즈 칩**(우선순위 키와 동형): `1`=활성(시작전·진행중, 기본) · `2`=오늘(마감 ≤ 오늘, 지남 포함) · `3`=완료 · `0`=전체. 완료 렌즈에서 `space`는 재오픈(✓→□)으로 동작해 회고+되살리기를 겸한다. 모든 렌즈가 같은 상태 badge로 렌더돼 탭 내 시각이 일관된다.

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
- **트리거**: 시작 시 캐시 렌더, 종료 시 push, 수동 `ctrl-r`(메타)/`ctrl-u`(전체)/`/todo-sync` (백그라운드 데몬 없음)
- **lazy 본문 fetch**: 본문(to_do 블록) 조회는 활성 Task당 1회 API 호출이라 Task가 많으면 느리다.
  그래서 본문을 "필요할 때만" 당긴다.
  - `ctrl-r` = **메타만**(`sync-meta`): Task 목록 + push. 본문 reconcile 없음 → ~1초.
  - Task **드릴인**(Tasks/Today/Doing 탭 enter·space) = 그 Task 본문만(`pull-task`) → ~0.5초.
  - `ctrl-u` = **전체 본문**(`sync` full): 평면 탭은 전체, Tasks 탭은 현재 우선순위 범위. 느림(Task 수 비례).
  - 트레이드오프: Notion 웹 등 외부에서 바꾼 todo는 평면 Todos/Done 탭에 즉시 안 뜬다.
    해당 Task 드릴인 또는 `ctrl-u`로 반영한다. body_md 캐시는 메타 sync 시 carry-over로 보존.
- **충돌 해소**: todo 단위 last-write-wins. 양쪽 변경 시 `updated_at`(로컬 KST)과
  `last_edited_time`(Notion UTC)을 UTC로 정규화해 최신값 채택. 패배값은
  `.sync_state.json`의 `conflicts`에 보존(손실 방지).
- **안전장치**: sync 직전 `todos.json.bak` 백업, `--dry-run`은 로컬/Notion 무변경.

## 알려진 한계 (개선 여지)

1. **전체 sync 성능**: `ctrl-u`/`/todo-sync`의 full pull은 활성 Task 전체(현재 ~70개)를
   순회 → throttle 0.35s/req로 ~30초. (`ctrl-r` 메타 sync는 ~1초, 드릴인은 ~0.5초)
   추가 개선 여지: full pull도 진행 중/로컬 Todo 보유 Task로 범위 한정, 또는 요청 병렬화
   (단 Notion 평균 3 req/s 한도라 병렬화 효과는 제한적, 429 위험).
2. **block_id 비영속**: Notion 페이지 복제/이동 시 block_id가 바뀌어 매칭이 깨질 수
   있음. 현재는 block_id 단일 키 매칭(텍스트 fuzzy 재매칭 미구현).
3. **완료된 Task의 Todo**: pull은 활성 Task만 reconcile. Notion에서 완료 처리된
   Task의 로컬 Todo는 목록에서 사라지되 todos.json에는 잔류(무해).
