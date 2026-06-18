#!/usr/bin/env python3
"""
로컬 Todo Store — tasktui의 오프라인 1차 저장소(CRUD).

설계 원칙:
  - Todo는 Notion Task(=Project) 페이지 본문의 to_do 블록에 대응하지만,
    네트워크 없이도 즉시 추가/토글/편집이 가능해야 한다(offline-first).
  - 따라서 모든 쓰기는 로컬 JSON에만 일어나고 dirty 플래그를 세운다.
    실제 Notion 반영은 todo_sync.py가 별도로 수행한다(관심사 분리).
  - Task당 Todo 진행률(done/total)은 저장하지 않고 todos.json에서 매번
    계산한다 — 캐시 이중화로 인한 불일치(stale count)를 원천 차단한다.

저장 경로: ~/.claude/tasktui/  (Claude Code 네이티브가 점유한 ~/.claude/tasks/ 회피)
  tasks.json   Notion Task 메타 캐시 (sync가 채움)
  todos.json   로컬 Todo (이 스크립트가 1차 소유)

Usage:
  todo_store.py list-tasks   [--format fzf|json]
  todo_store.py list-todos   --task <page_id> [--format fzf|json] [--include-done]
  todo_store.py add          --task <page_id> --title "..." [--due YYYY-MM-DD]
  todo_store.py toggle       --id <todo_id>
  todo_store.py edit         --id <todo_id> --title "..."
  todo_store.py delete       --id <todo_id>          # soft delete (tombstone)
  todo_store.py preview-task <page_id>               # fzf preview window용 텍스트
  todo_store.py summary      [--format text|json]    # statusline / 비인터랙티브 뷰
"""
import argparse
import json
import shutil
import signal
import sys
import unicodedata
import uuid
from pathlib import Path

import notion_common as nc

# fzf로 파이프하거나 preview로 실행될 때, fzf가 파이프를 먼저 닫으면(빠른 스크롤,
# 즉시 종료) 쓰기 도중 BrokenPipeError traceback이 발생한다. cat/grep처럼 SIGPIPE에서
# 조용히 종료하도록 기본 동작으로 되돌린다(Windows 등 미지원 플랫폼은 무시).
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

DATA_DIR = Path.home() / ".claude" / "tasktui"
TODOS_FILE = DATA_DIR / "todos.json"
TASKS_FILE = DATA_DIR / "tasks.json"

# Notion 상태 → 표시 아이콘. 목록에서 Task 진행 상태를 한눈에 보이게 한다.
STATUS_ICON = {"진행 중": "⏳", "시작 전": "⬜", "대기": "⏸", "완료": "✅"}

# Todo는 Task 하위뿐 아니라 독립(backlog/리마인드)으로도 존재한다.
# 독립 Todo는 이 sentinel page_id를 갖는 가상 버킷에 모이며, 실제 Notion 페이지가
# 없으므로 sync(pull/push) 대상에서 제외된다 — 로컬 전용이다.
BACKLOG_ID = "__backlog__"
BACKLOG_LABEL = "📥 Todos"

# memory import 대상 — 파일명 prefix로 선별한다.
# 기본은 actionable한 reminder_/task_만. project_*는 진행상황·지식 노트가 대부분
# 섞여 backlog를 희석하므로 --include-projects 옵션일 때만 포함한다.
PROJECTS_DIR = Path.home() / ".claude" / "projects"
IMPORT_PREFIXES = ("reminder_", "task_")
PROJECT_PREFIX = ("project_",)


# ── 저장소 I/O ────────────────────────────────────────────────

def _load(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def _atomic_write(path, data):
    """temp 파일에 쓰고 rename — 쓰기 중 중단 시 원본 보존(부분 쓰기 방지)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)


def load_todos():
    return _load(TODOS_FILE, {"version": 1, "todos": []})


def save_todos(doc):
    _atomic_write(TODOS_FILE, doc)


def load_tasks():
    return _load(TASKS_FILE, {"version": 1, "synced_at": "", "tasks": []})


def save_tasks(doc):
    _atomic_write(TASKS_FILE, doc)


# ── Todo 도메인 헬퍼 ──────────────────────────────────────────

def _new_todo_id():
    return "td_" + uuid.uuid4().hex[:8]


def _find_todo(doc, todo_id):
    for t in doc["todos"]:
        if t["id"] == todo_id:
            return t
    return None


def _visible_todos(doc, page_id=None, include_done=True):
    """tombstone(deleted) 제외. page_id/done 필터 적용."""
    out = []
    for t in doc["todos"]:
        if t.get("deleted"):
            continue
        if page_id is not None and t.get("task_page_id") != page_id:
            continue
        if not include_done and t.get("done"):
            continue
        out.append(t)
    return out


def _counts_for(doc, page_id):
    """Task의 (완료, 전체) Todo 수 — 표시 시점에 라이브 계산."""
    todos = _visible_todos(doc, page_id)
    done = sum(1 for t in todos if t.get("done"))
    return done, len(todos)


# ── 출력 포맷 ─────────────────────────────────────────────────

def _priority_short(priority):
    # "P2 - Should Have" → "P2", 없으면 공백 정렬용 "  "
    return priority.split(" ")[0] if priority else "--"


def _eaw(c: str) -> int:
    """East Asian Width — CJK 문자는 터미널에서 2칸 차지."""
    return 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1


def _display_width(s: str) -> int:
    return sum(_eaw(c) for c in s)


def _fit(s: str, width: int) -> str:
    """CJK-aware 고정폭 컬럼: 넘치면 …로 잘라내고, 모자라면 공백으로 패딩."""
    dw = _display_width(s)
    if dw > width:
        result, w = [], 0
        for c in s:
            cw = _eaw(c)
            if w + cw > width - 1:
                result.append('…')
                break
            result.append(c)
            w += cw
        s = ''.join(result)
        dw = _display_width(s)
    return s + ' ' * (width - dw)


def _parse_plan_light(plan_id: str):
    """plan frontmatter만 경량 파싱. yaml 미설치 시 None 반환."""
    try:
        import yaml
    except ImportError:
        return None
    plans_dir = Path.home() / ".claude" / "plans"
    for p in plans_dir.glob("*.md"):
        if p.name.startswith("."):
            continue
        stem = p.stem
        pid = stem[5:] if stem.startswith("plan-") else stem
        if pid == plan_id:
            text = p.read_text()
            if text.startswith("---\n"):
                end = text.find("\n---\n", 4)
                if end != -1:
                    try:
                        return yaml.safe_load(text[4:end])
                    except Exception:
                        pass
    return None


def _task_display(task, done, total):
    icon = STATUS_ICON.get(task.get("status", ""), "·")
    # 아이콘은 이모지(2칸)와 ASCII(1칸)가 섞이므로 2칸으로 통일
    icon_col = icon if _display_width(icon) >= 2 else icon + " "
    pri = _priority_short(task.get("priority", ""))
    name = task.get("name", "(이름 없음)")
    plan_badge = " 📋" if task.get("plan_id") else ""
    # 이름+배지를 터미널 너비 기반 동적 컬럼에 맞춤
    # Tasks 탭은 preview 창(right:48%)이 있으므로 리스트 영역 ≈ 52%
    # 오버헤드: icon(2)+space(1)+[Pn](4)+sep(2)+todo(7)+sep(2)+due(5)+sep(2) = 25
    _cols = shutil.get_terminal_size((120, 24)).columns
    name_width = max(36, int(_cols * 0.50) - 25)
    name_col = _fit(name + plan_badge, name_width)
    due = task.get("due_date", "")
    due_str = f"~{due[5:10]}" if due else "     "  # ~MM-DD (5칸) 또는 공백
    tags = task.get("tags", [])
    tag_str = " ".join(f"#{t}" for t in tags)
    todo_str = f"({done}/{total})".rjust(7)
    return f"{icon_col} [{pri}]  {name_col}  {todo_str}  {due_str}  {tag_str}".rstrip()


def _todo_display(todo):
    """Level 2 및 preview용 — 터미널 너비 기반 동적 컬럼."""
    box = "☑" if todo.get("done") else "☐"
    title = todo.get("title", "")
    plan_badge = " 📋" if todo.get("plan_id") else ""
    # 오버헤드: box(2) + sep(2) + due(5) + dirty(2) + buffer(2) = 13
    _cols = shutil.get_terminal_size((120, 24)).columns
    title_width = max(44, _cols - 13)
    title_col = _fit(title + plan_badge, title_width)
    due = todo.get("due", "")
    due_str = f"~{due[5:10]}" if due else "     "  # ~MM-DD 5칸
    dirty = " *" if todo.get("dirty") else "  "
    return f"{box} {title_col}  {due_str}{dirty}"


# ── 커맨드 ────────────────────────────────────────────────────

def cmd_list_tasks(args):
    tdoc = load_todos()
    tasks = load_tasks()["tasks"]
    prio = getattr(args, "priority", "") or ""  # "P1"|"P2"|"P3"|"" (전체)
    bdone, btotal = _counts_for(tdoc, BACKLOG_ID)
    if args.format == "json":
        enriched = [{"page_id": BACKLOG_ID, "name": BACKLOG_LABEL, "status": "",
                     "priority": "", "todo_done": bdone, "todo_count": btotal}]
        for task in tasks:
            if prio and not _priority_short(task.get("priority", "")).startswith(prio):
                continue
            done, total = _counts_for(tdoc, task["page_id"])
            enriched.append({**task, "todo_done": done, "todo_count": total})
        print(json.dumps({"tasks": enriched}, ensure_ascii=False, indent=2))
        return
    # fzf: "<page_id>\t<표시줄>". Backlog 버킷을 항상 최상단에 노출한다.
    backlog_name = _fit(BACKLOG_LABEL, 40)
    backlog_todo = f"({bdone}/{btotal})".rjust(7)
    print(f"{BACKLOG_ID}\t   [--]  {backlog_name}  {backlog_todo}")
    for task in tasks:
        if prio and not _priority_short(task.get("priority", "")).startswith(prio):
            continue
        done, total = _counts_for(tdoc, task["page_id"])
        print(f"{task['page_id']}\t{_task_display(task, done, total)}")


def cmd_list_todos(args):
    doc = load_todos()
    todos = _visible_todos(doc, args.task, include_done=args.include_done)
    if args.format == "json":
        print(json.dumps({"todos": todos}, ensure_ascii=False, indent=2))
        return
    # fzf: "<todo_id>\t<표시줄>". 미완료 먼저, 그 안에서 최근 추가 순(내림차순).
    # layout=reverse 환경에서 stdout 첫 항목이 화면 하단에 표시되므로
    # 최근 항목이 먼저 출력되어야 화면 하단(가장 잘 보이는 위치)에 나타난다.
    todos.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    todos.sort(key=lambda t: t.get("done", False))  # stable: 미완료 먼저
    for t in todos:
        print(f"{t['id']}\t{_todo_display(t)}")


def repo_of(todo):
    """Todo의 소속 repo 라벨을 도출한다.

    import된 backlog는 memory_path가 `~/.claude/projects/<encoded-cwd>/memory/...`
    형태라 거기서 repo를 뽑는다(예: riiid/kubernetes → kubernetes). 수동 추가는
    저장된 repo 필드를, 그 외(Task-scoped 등)는 빈 문자열을 반환한다.
    """
    if todo.get("repo"):
        return todo["repo"]
    mp = todo.get("memory_path")
    if not mp:
        return ""
    return _repo_from_memory_path(mp)


def _repo_from_memory_path(path_str):
    """project 디렉토리 슬러그에서 홈/워크스페이스 prefix를 벗겨 repo 라벨을 만든다.

    슬러그는 cwd의 `/`를 `-`로 치환한 형태라 완벽한 복원은 불가하지만,
    그룹핑 라벨로는 충분하다. 흔한 prefix(workspace-riiid-, workspace-)를 정리한다.
    """
    parts = Path(path_str).parts
    try:
        slug = parts[parts.index("projects") + 1]
    except (ValueError, IndexError):
        return ""
    home_slug = str(Path.home()).replace("/", "-")  # 예: -Users-changhwan
    s = slug[len(home_slug):] if slug.startswith(home_slug) else slug
    for pre in ("-workspace-riiid-", "-workspace-", "-"):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s.lstrip("-") or slug


def cmd_list_all_todos(args):
    """모든 Todo를 평면 목록으로 — Todos 탭용. 각 Todo에 소속 컨텍스트(Task명/Todos)
    와 repo 라벨을 함께 표기해 어디에 속한 할 일인지 한눈에 보이게 한다.
    --repo 지정 시 해당 repo만 필터링한다."""
    doc = load_todos()
    tasks_map = {t["page_id"]: t.get("name", "") for t in load_tasks()["tasks"]}

    def ctx_of(t):
        pid = t.get("task_page_id")
        if pid == BACKLOG_ID:
            return BACKLOG_LABEL
        return tasks_map.get(pid) or "(task?)"

    todos = _visible_todos(doc)
    repo_filter = getattr(args, "repo", None)
    if repo_filter:
        todos = [t for t in todos if repo_of(t) == repo_filter]
    todos.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    todos.sort(key=lambda t: (t.get("done", False), repo_of(t), ctx_of(t)))  # stable
    if args.format == "json":
        print(json.dumps({"todos": [{**t, "context": ctx_of(t), "repo": repo_of(t)} for t in todos]},
                         ensure_ascii=False, indent=2))
        return
    # title_width: 터미널 너비에서 고정 오버헤드를 뺀 값으로 동적 계산
    # 오버헤드: box(2) + sep(2) + due(5) + dirty(2) + max_repo(20) + buffer(4) = 35
    _term_cols = shutil.get_terminal_size((120, 24)).columns
    title_width = max(44, _term_cols - 35)

    # fzf: "{box} {title:dynamic} {due:5} {dirty}  [· {task명}]  [{repo}]"
    # Todos 버킷 소속은 ctx 생략 (자명하므로), Task 연결 시만 Task명 표시
    for t in todos:
        box = "☑" if t.get("done") else "☐"
        title_field = t.get("title", "") + (" 📋" if t.get("plan_id") else "")
        title_col = _fit(title_field, title_width)
        due = t.get("due", "")
        due_str = f"~{due[5:10]}" if due else "     "
        dirty = " *" if t.get("dirty") else "  "
        repo = repo_of(t)
        repo_tag = f"  [{repo}]" if repo else ""
        ctx = ctx_of(t)
        ctx_part = f"  · {_fit(ctx, 16)}" if ctx != BACKLOG_LABEL else ""
        print(f"{t['id']}\t{box} {title_col}  {due_str}{dirty}{ctx_part}{repo_tag}")


def cmd_get(args):
    """단일 Todo의 전체 JSON을 반환 — Enter 키로 Claude Code 세션 열 때 사용"""
    doc = load_todos()
    tasks_map = {t["page_id"]: t.get("name", "") for t in load_tasks()["tasks"]}
    todo = next((t for t in doc["todos"] if t["id"] == args.id and not t.get("deleted")), None)
    if todo is None:
        print(json.dumps({"error": "not_found"}))
        return
    pid = todo.get("task_page_id", BACKLOG_ID)
    ctx = BACKLOG_LABEL if pid == BACKLOG_ID else (tasks_map.get(pid) or "(task?)")
    print(json.dumps({**todo, "context": ctx, "repo": repo_of(todo)}, ensure_ascii=False))


def cmd_add(args):
    if not args.title.strip():
        _err("--title은 비어 있을 수 없습니다")
    doc = load_todos()
    now = nc.now_kst()
    # Backlog(로컬 전용) Todo는 sync 대상이 아니므로 dirty를 세우지 않는다.
    is_backlog = args.task == BACKLOG_ID
    todo = {
        "id": _new_todo_id(),
        "task_page_id": args.task,
        "notion_block_id": None,  # push 시점에 채워짐 (Backlog은 항상 None)
        "title": args.title.strip(),
        "done": False,
        "due": args.due or "",
        "created_at": now,
        "updated_at": now,
        "dirty": not is_backlog,  # Task-scoped만 다음 sync에서 Notion에 append
        "deleted": False,
        "notion_last_edited": "",
    }
    if getattr(args, "memory_path", None):
        todo["source"] = "import"
        todo["memory_path"] = args.memory_path
    if getattr(args, "repo", None):
        todo["repo"] = args.repo
    doc["todos"].append(todo)
    save_todos(doc)
    print(json.dumps({"success": True, "id": todo["id"], "title": todo["title"]},
                     ensure_ascii=False))


def cmd_toggle(args):
    doc = load_todos()
    todo = _find_todo(doc, args.id)
    if not todo or todo.get("deleted"):
        _err(f"todo not found: {args.id}")
    todo["done"] = not todo.get("done", False)
    todo["updated_at"] = nc.now_kst()
    todo["dirty"] = todo.get("task_page_id") != BACKLOG_ID  # Backlog은 로컬 전용
    save_todos(doc)
    print(json.dumps({"success": True, "id": todo["id"], "done": todo["done"]},
                     ensure_ascii=False))


def cmd_edit(args):
    if not args.title.strip():
        _err("--title은 비어 있을 수 없습니다")
    doc = load_todos()
    todo = _find_todo(doc, args.id)
    if not todo or todo.get("deleted"):
        _err(f"todo not found: {args.id}")
    todo["title"] = args.title.strip()
    todo["updated_at"] = nc.now_kst()
    todo["dirty"] = todo.get("task_page_id") != BACKLOG_ID  # Backlog은 로컬 전용
    save_todos(doc)
    print(json.dumps({"success": True, "id": todo["id"], "title": todo["title"]},
                     ensure_ascii=False))


def cmd_delete(args):
    """Task-scoped는 soft delete(tombstone) — 즉시 제거하면 다음 pull에서 Notion
    블록이 부활하므로, sync가 블록을 아카이브할 때까지 표식을 유지한다.
    Backlog(로컬 전용)는 원격 블록이 없어 부활 위험이 없으므로 즉시 제거한다."""
    doc = load_todos()
    todo = _find_todo(doc, args.id)
    if not todo or todo.get("deleted"):
        _err(f"todo not found: {args.id}")
    if todo.get("task_page_id") == BACKLOG_ID:
        doc["todos"] = [t for t in doc["todos"] if t["id"] != args.id]
        save_todos(doc)
        print(json.dumps({"success": True, "id": args.id, "deleted": True},
                         ensure_ascii=False))
        return
    todo["deleted"] = True
    todo["updated_at"] = nc.now_kst()
    todo["dirty"] = True
    save_todos(doc)
    print(json.dumps({"success": True, "id": todo["id"], "deleted": True},
                     ensure_ascii=False))


def cmd_preview_task(args):
    """fzf preview window용 — 선택 Task의 메타 + Todo 체크리스트(평문)."""
    page_id = args.page_id
    tdoc = load_todos()
    if page_id == BACKLOG_ID:
        print(f"  {BACKLOG_LABEL}  (Task 없는 독립 Todo · 로컬 전용)")
        task = None
    else:
        task = next((t for t in load_tasks()["tasks"] if t["page_id"] == page_id), None)
    if task:
        print(f"  {task.get('name', '')}")
        print(f"  상태: {task.get('status', '')}   우선순위: {task.get('priority', '')}")
        if task.get("due_date"):
            print(f"  마감: {task['due_date']}")
        if task.get("tags"):
            print(f"  태그: {' '.join('#' + t for t in task['tags'])}")
        plan_id = task.get("plan_id")
        if plan_id:
            fm = _parse_plan_light(plan_id)
            if fm:
                steps = fm.get("todos", [])
                done_cnt = sum(1 for s in steps if s.get("status") == "done")
                plan_title = fm.get("title", plan_id)
                step_icons = {"done": "✅", "in_progress": "⏳", "pending": "⬜"}
                row = " ".join(step_icons.get(s.get("status", "pending"), "⬜") for s in steps)
                print(f"\n  📋 Plan: {plan_title} ({done_cnt}/{len(steps)})")
                print(f"     {row}")
            else:
                print(f"\n  📋 Plan: {plan_id} (파일 없음)")
    elif page_id != BACKLOG_ID:
        print("  (동기화 전 — sync 후 메타 표시)")
    print()
    todos = _visible_todos(tdoc, page_id)
    if not todos:
        print("  (todo 없음)")
        return
    done = sum(1 for t in todos if t.get("done"))
    print(f"  Todo {done}/{len(todos)}")
    todos.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    todos.sort(key=lambda t: t.get("done", False))  # stable: 미완료 먼저
    for t in todos:
        print(f"    {_todo_display(t)}")


def cmd_set_task_status(args):
    """Task 상태를 로컬에서 변경하고 meta_dirty 표식 — push가 Notion에 반영한다.
    모든 로컬 쓰기는 store가 소유하므로(sync는 Notion I/O만) 여기에 둔다."""
    if args.status not in nc.VALID_STATUSES:
        _err(f"Invalid status '{args.status}'. Valid: {sorted(nc.VALID_STATUSES)}")
    doc = load_tasks()
    task = next((t for t in doc["tasks"] if t["page_id"] == args.task), None)
    if not task:
        _err(f"task not found in cache: {args.task} (sync 먼저 실행)")
    task["status"] = args.status
    task["meta_dirty"] = True
    task["meta_updated_at"] = nc.now_kst()
    save_tasks(doc)
    print(json.dumps({"success": True, "page_id": args.task, "status": args.status},
                     ensure_ascii=False))


def _parse_memory_frontmatter(path):
    """memory 파일의 name/description를 가볍게 추출(yaml 의존 없이).

    memory frontmatter는 단순한 key: value 형태라 라인 파싱으로 충분하다.
    description은 actionable 한 줄 요약(날짜 포함)이라 Todo 제목으로 적합하다.
    """
    try:
        text = path.read_text()
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    name = desc = ""
    for line in text[3:end].splitlines():
        s = line.strip()
        if s.startswith("name:"):
            name = s[5:].strip().strip("\"'")
        elif s.startswith("description:"):
            desc = s[12:].strip().strip("\"'")
    return {"name": name, "description": desc}


def cmd_import_memory(args):
    """프로젝트 memory(reminder_*/task_*/project_*)를 Backlog Todo로 import.

    memory_path로 멱등성을 보장(이미 import된 파일은 건너뜀)하며, 완료 처리 시
    원본 memory를 참조할 수 있도록 경로를 todo에 링크로 보관한다.
    """
    doc = load_todos()
    existing = {t.get("memory_path") for t in doc["todos"] if t.get("memory_path")}
    prefixes = IMPORT_PREFIXES + (PROJECT_PREFIX if args.include_projects else ())
    imported = []
    for mem in sorted(PROJECTS_DIR.glob("*/memory/*.md")):
        if not mem.name.startswith(prefixes):
            continue
        if str(mem) in existing:
            continue
        fmd = _parse_memory_frontmatter(mem)
        if not fmd:
            continue
        title = (fmd["description"] or fmd["name"] or mem.stem)[:120]
        now = nc.now_kst()
        doc["todos"].append({
            "id": _new_todo_id(),
            "task_page_id": BACKLOG_ID,
            "notion_block_id": None,
            "title": title,
            "done": False,
            "due": "",
            "created_at": now,
            "updated_at": now,
            "dirty": False,       # 로컬 전용
            "deleted": False,
            "notion_last_edited": "",
            "source": "import",
            "memory_path": str(mem),
        })
        imported.append(title)
    if not args.dry_run and imported:
        save_todos(doc)
    print(json.dumps({"success": True, "imported": len(imported),
                      "titles": imported, "dry_run": args.dry_run},
                     ensure_ascii=False, indent=2))


def cmd_link_plan(args):
    """task 또는 todo에 plan_id 연결/해제."""
    plan_id = args.plan_id.strip()
    if plan_id:
        plans_dir = Path.home() / ".claude" / "plans"
        candidates = list(plans_dir.glob(f"*{plan_id}*.md"))
        # 정확 매칭 우선, 없으면 후보가 하나도 없으면 오류
        if not candidates:
            _err(f"plan file not found: {plan_id}")
    if args.target == "task":
        doc = load_tasks()
        obj = next((t for t in doc["tasks"] if t["page_id"] == args.id), None)
        if not obj:
            _err(f"task not found: {args.id}")
        obj["plan_id"] = plan_id
        save_tasks(doc)
    else:  # todo
        doc = load_todos()
        obj = _find_todo(doc, args.id)
        if not obj or obj.get("deleted"):
            _err(f"todo not found: {args.id}")
        obj["plan_id"] = plan_id
        save_todos(doc)
    print(json.dumps({"success": True, "linked": plan_id or None}, ensure_ascii=False))


def cmd_summary(args):
    """비인터랙티브 요약 — /task 커맨드와 statusline 노출에 공용."""
    tdoc = load_todos()
    tasks = load_tasks()["tasks"]
    in_progress = [t for t in tasks if t.get("status") == "진행 중"]
    rows = []
    for task in in_progress:
        done, total = _counts_for(tdoc, task["page_id"])
        rows.append({"name": task["name"], "done": done, "total": total,
                     "priority": _priority_short(task.get("priority", ""))})
    if args.format == "json":
        print(json.dumps({"in_progress": rows, "synced_at": load_tasks().get("synced_at", "")},
                         ensure_ascii=False))
        return
    if not rows:
        print("진행 중 Task 없음")
        return
    for r in rows:
        print(f"⏳ [{r['priority']}] {r['name']} ({r['done']}/{r['total']})")


# ── main ──────────────────────────────────────────────────────

def _err(msg):
    print(json.dumps({"success": False, "error": msg}, ensure_ascii=False))
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="로컬 Todo Store (offline-first)")
    sub = p.add_subparsers(dest="command", required=True)

    lt = sub.add_parser("list-tasks")
    lt.add_argument("--format", choices=["fzf", "json"], default="fzf")
    lt.add_argument("--priority", default="", help="우선순위 필터 (P1|P2|P3|P4, 빈값=전체)")

    ld = sub.add_parser("list-todos")
    ld.add_argument("--task", required=True)
    ld.add_argument("--format", choices=["fzf", "json"], default="fzf")
    ld.add_argument("--include-done", action="store_true", default=True)

    la = sub.add_parser("list-all-todos")
    la.add_argument("--format", choices=["fzf", "json"], default="fzf")
    la.add_argument("--repo", default=None, help="해당 repo의 Todo만 필터")

    gt = sub.add_parser("get")
    gt.add_argument("--id", required=True)

    ad = sub.add_parser("add")
    ad.add_argument("--task", required=True)
    ad.add_argument("--title", required=True)
    ad.add_argument("--due", default=None)
    ad.add_argument("--memory-path", dest="memory_path", default=None,
                    help="Backlog import 시 원본 memory 경로 링크")
    ad.add_argument("--repo", default=None, help="이 Todo의 소속 repo 라벨")

    im = sub.add_parser("import-memory")
    im.add_argument("--dry-run", action="store_true")
    im.add_argument("--include-projects", action="store_true",
                    help="project_* 메모도 포함 (기본은 reminder_/task_만)")

    tg = sub.add_parser("toggle")
    tg.add_argument("--id", required=True)

    ed = sub.add_parser("edit")
    ed.add_argument("--id", required=True)
    ed.add_argument("--title", required=True)

    dl = sub.add_parser("delete")
    dl.add_argument("--id", required=True)

    pv = sub.add_parser("preview-task")
    pv.add_argument("page_id")

    ss = sub.add_parser("set-task-status")
    ss.add_argument("--task", required=True)
    ss.add_argument("--status", required=True)

    sm = sub.add_parser("summary")
    sm.add_argument("--format", choices=["text", "json"], default="text")

    lp = sub.add_parser("link-plan")
    lp.add_argument("--target", choices=["task", "todo"], required=True)
    lp.add_argument("--id", required=True)
    lp.add_argument("--plan-id", dest="plan_id", required=True)

    args = p.parse_args()
    dispatch = {
        "list-tasks": cmd_list_tasks,
        "list-todos": cmd_list_todos,
        "list-all-todos": cmd_list_all_todos,
        "get": cmd_get,
        "add": cmd_add,
        "toggle": cmd_toggle,
        "edit": cmd_edit,
        "delete": cmd_delete,
        "preview-task": cmd_preview_task,
        "set-task-status": cmd_set_task_status,
        "import-memory": cmd_import_memory,
        "summary": cmd_summary,
        "link-plan": cmd_link_plan,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
