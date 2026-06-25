#!/usr/bin/env python3
"""
양방향 Sync 엔진 — 로컬 Todo ↔ Notion Task 페이지의 to_do 블록.

데이터 모델:
  Notion Task DB의 각 페이지 = Project(=Task). 그 페이지 본문의 to_do 체크박스
  블록 = Todo. 로컬 todos.json은 오프라인 1차 저장소이며, 이 엔진이 Notion과
  reconcile한다.

충돌 해소 (last-write-wins + 손실 방지):
  todo 단위로 remote_changed/local_changed를 판정한다.
    - 한쪽만 변경 → 그쪽 채택
    - 양쪽 변경 → updated_at(로컬) vs last_edited_time(Notion) 비교, 최신 채택
      패배한 값은 .sync_state.json의 conflicts 로그에 보존(데이터 손실 방지)
  타임존: 로컬은 KST(+09:00), Notion은 UTC(Z) → 둘 다 UTC로 정규화 후 비교.

안전장치:
  - sync 시작 시 todos.json → todos.json.bak 백업
  - --dry-run: 어떤 쓰기(로컬/Notion)도 하지 않고 계획만 출력

성능 모델 (lazy 본문 fetch):
  본문(to_do 블록) 조회는 활성 Task당 1회 API 호출이라, Task가 많으면 sync가
  느리다. 그래서 본문 fetch를 "필요할 때만"으로 분리한다.
    - sync-meta : Task 목록(메타)만 pull + push. 본문 reconcile 없음 → 빠름.
    - pull-task : 특정 Task 한 개의 본문만 reconcile (드릴인 시).
    - sync      : 메타 + 전체 본문(또는 --priority 범위) + push (full).
  메타만 갱신할 때 기존 body_md 캐시는 보존한다(preview가 깨지지 않게).

Usage:
  todo_sync.py sync       [--priority P1] [--dry-run]  # 메타+본문+push (full)
  todo_sync.py sync-meta  [--dry-run]                  # 메타+push (본문 스킵, 빠름)
  todo_sync.py pull-task  --page-id <id> [--dry-run]   # 단일 Task 본문+push
  todo_sync.py pull       [--dry-run]                  # Notion → 로컬만 (full)
  todo_sync.py push       [--dry-run]                  # 로컬 → Notion만
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone

import notion_common as nc
import todo_store as store

SYNC_STATE_FILE = store.DATA_DIR / ".sync_state.json"
BACKUP_FILE = store.TODOS_FILE.with_suffix(".json.bak")
CONFLICT_LOG_CAP = 50  # 무한 성장 방지


# ── sync 상태 ─────────────────────────────────────────────────

def load_sync_state():
    # 손상 시 .corrupt 격리 후 기본값 복구 — 충돌 로그가 든 이 파일이 깨져도
    # sync 전체가 크래시하지 않게 한다(store._load와 동일한 방어 정책 재사용).
    return store._load(
        SYNC_STATE_FILE,
        {"last_full_sync": "", "conflicts": [], "rate_limit_backoff_until": None})


def save_sync_state(state):
    state["conflicts"] = state.get("conflicts", [])[-CONFLICT_LOG_CAP:]
    store._atomic_write(SYNC_STATE_FILE, state)


# ── Notion to_do 블록 ↔ 로컬 todo ─────────────────────────────

def parse_todo_block(block):
    """Notion to_do 블록 → 비교용 dict."""
    td = block.get("to_do", {})
    return {
        "block_id": block["id"],
        "title": nc.rich_text_to_plain(td.get("rich_text", [])),
        "done": td.get("checked", False),
        "last_edited": block.get("last_edited_time", ""),
    }


def build_todo_block(title, done):
    """로컬 todo → Notion to_do 블록 append/update body."""
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": nc.plain_to_rich_text(title), "checked": done},
    }


# ── 충돌 판정 ─────────────────────────────────────────────────

def _resolve_matched(local, remote, conflicts):
    """
    block_id로 매칭된 (로컬 todo, 원격 블록) 한 쌍을 reconcile한다.
    pull 단계에서 호출 — 결과적으로 로컬을 원격값으로 덮거나(dirty=False),
    로컬 변경을 보존(dirty 유지 → push가 처리)한다.
    """
    remote_edited = nc.to_utc(remote["last_edited"])
    local_seen = nc.to_utc(local.get("notion_last_edited", ""))
    # local_seen이 없으면(첫 매칭) 원격을 새 정보로 간주
    remote_changed = local_seen is None or (
        remote_edited is not None and remote_edited > local_seen
    )
    local_changed = bool(local.get("dirty"))

    if remote_changed and not local_changed:
        _adopt_remote(local, remote)
    elif local_changed and not remote_changed:
        pass  # push-win: dirty 유지
    elif not remote_changed and not local_changed:
        local["notion_last_edited"] = remote["last_edited"]  # baseline 갱신
    else:
        # 양쪽 변경 → last-write-wins
        local_updated = nc.to_utc(local.get("updated_at", ""))
        local_wins = (
            local_updated is not None
            and remote_edited is not None
            and local_updated >= remote_edited
        )
        if local_wins:
            conflicts.append(_conflict_entry(local, remote, "local"))
            # 로컬 유지, dirty 유지 → push가 원격 덮어씀
        else:
            conflicts.append(_conflict_entry(local, remote, "remote"))
            _adopt_remote(local, remote)


def _adopt_remote(local, remote):
    local["title"] = remote["title"]
    new_done = remote["done"]
    # done 변경 시 status도 일관되게 조정.
    # 진행중은 로컬 컨텍스트이므로 Notion unchecked일 때 보존한다.
    if new_done:
        local["status"] = "완료"
    elif local.get("status") == "완료":
        local["status"] = "시작전"
    local["done"] = new_done
    local["notion_last_edited"] = remote["last_edited"]
    local["dirty"] = False


def _conflict_entry(local, remote, winner):
    return {
        "at": nc.now_kst(),
        "todo_id": local["id"],
        "winner": winner,
        "local_value": {"title": local.get("title"), "done": local.get("done"),
                        "updated_at": local.get("updated_at")},
        "remote_value": {"title": remote.get("title"), "done": remote.get("done"),
                         "last_edited": remote.get("last_edited")},
    }


# ── PULL ──────────────────────────────────────────────────────

def pull_meta(token, conflicts, dry_run):
    """Notion → 로컬, Task 메타만. tasks.json 재구성 + 완료 캐시 갱신.

    본문(to_do 블록)은 건드리지 않는다 — get_all_children을 호출하지 않으므로
    Task 수와 무관하게 1~2회 API 호출로 끝난다(빠름). 본문 reconcile은
    pull_task_bodies가 담당한다.

    반환: (stats, new_tasks). new_tasks는 메모리 리스트로, 후속 pull_task_bodies가
    dry_run 여부와 무관하게 그대로 받아 본문을 채울 수 있게 전달한다.
    """
    stats = {"tasks": 0, "completed": 0}
    old_tasks = {t["page_id"]: t for t in store.load_tasks()["tasks"]}
    new_tasks = []
    for task in nc.query_active_tasks(token):
        old = old_tasks.get(task["page_id"])
        # 본문 미리보기 캐시는 메타 갱신만으로 다시 만들 수 없다(children 미조회).
        # 기존 캐시를 carry-over해 preview가 빈 본문으로 깨지지 않게 한다.
        # 해당 Task 본문을 pull_task_bodies가 처리할 때 최신값으로 덮인다.
        if old and old.get("body_md"):
            task["body_md"] = old["body_md"]
        if old and old.get("meta_dirty"):
            remote_edited = nc.to_utc(task["notion_last_edited"])
            local_updated = nc.to_utc(old.get("meta_updated_at", ""))
            remote_wins = (
                remote_edited is not None and local_updated is not None
                and remote_edited > local_updated
            )
            if remote_wins:
                conflicts.append({"at": nc.now_kst(), "task": task["page_id"],
                                  "winner": "remote", "field": "status",
                                  "local": old.get("status"), "remote": task["status"]})
                new_tasks.append(task)
            else:
                # 로컬 status 유지 + meta_dirty 보존 → push가 반영.
                # body_md는 위에서 task에 이미 carry되어 spread에 포함된다.
                new_tasks.append({**task, "status": old["status"],
                                  "meta_dirty": True,
                                  "meta_updated_at": old.get("meta_updated_at")})
        else:
            new_tasks.append(task)
    stats["tasks"] = len(new_tasks)
    if not dry_run:
        store.save_tasks({"version": 1, "synced_at": nc.now_kst(), "tasks": new_tasks})

        # 최근 완료 Task 캐시 갱신 — Tasks 탭 ALL 뷰 노출용 읽기 전용 캐시.
        # 활성 Task와 분리되어 to_do reconcile/push/충돌 대상이 아니다(매번 통째로 교체).
        completed = nc.query_recent_completed_tasks(token)
        store.save_completed_tasks({"version": 1, "synced_at": nc.now_kst(),
                                    "tasks": completed})
        stats["completed"] = len(completed)

    return stats, new_tasks


def pull_task_bodies(token, doc, conflicts, dry_run, tasks_list, page_ids=None):
    """각 Task 페이지의 to_do 블록을 reconcile + 본문 preview 캐시 갱신.

    page_ids=None이면 tasks_list 전체, 아니면 그 집합에 속한 Task만 처리한다
    (lazy: 드릴인한 Task 또는 우선순위 범위만). get_all_children이 Task당 1회라
    여기서 처리하는 Task 수가 곧 본문 fetch 비용이다.

    tasks_list는 메모리 리스트(pull_meta 산출물 또는 load_tasks 결과)이며,
    body_md를 채운 뒤 전체를 tasks.json에 재저장한다(처리 안 한 Task의 기존
    body_md는 보존된다).
    """
    stats = {"created": 0, "adopted": 0, "remote_deleted": 0, "bodies": 0}
    remove_ids = []
    targets = [t for t in tasks_list
               if page_ids is None or t["page_id"] in page_ids]
    for task in targets:
        page_id = task["page_id"]
        children = nc.get_all_children(token, page_id)
        remote_blocks = [
            parse_todo_block(b)
            for b in children
            if b.get("type") == "to_do"  # callout 등 다른 블록 제외
        ]
        # 페이지 본문(비-todo 블록)을 preview 표시용으로 캐시한다. children을
        # 위에서 이미 fetch했으므로 추가 API 호출 없이 추출한다.
        task["body_md"] = nc.blocks_to_preview_text(children)
        stats["bodies"] += 1
        remote_by_id = {b["block_id"]: b for b in remote_blocks}
        local_todos = [t for t in doc["todos"]
                       if t.get("task_page_id") == page_id and not t.get("deleted")]
        local_by_block = {t["notion_block_id"]: t
                          for t in local_todos if t.get("notion_block_id")}

        # 삭제 대기(tombstone)된 todo가 가리키는 블록 — pull이 새 todo로 부활시키면
        # 안 된다. run()이 pull→push 순서라 push가 블록을 삭제하기 전에 이 블록이
        # 아직 Notion에 살아 있어, 매칭되는 로컬이 없다고 판정되면(tombstone은
        # local_todos에서 제외됨) 재생성되어 삭제가 무효화된다. push가 이 블록들을
        # 삭제하고 tombstone을 purge할 때까지 재생성 대상에서 제외한다.
        tombstoned_blocks = {t.get("notion_block_id")
                             for t in doc["todos"]
                             if t.get("task_page_id") == page_id
                             and t.get("deleted") and t.get("notion_block_id")}

        for rb in remote_blocks:
            if rb["block_id"] in tombstoned_blocks:
                continue  # 삭제 예정 블록 — 부활 금지 (push가 처리)
            local = local_by_block.get(rb["block_id"])
            if local is None:
                stats["created"] += 1
                if not dry_run:
                    doc["todos"].append(_todo_from_remote(page_id, rb))
            else:
                before = local.get("dirty"), local.get("title"), local.get("done")
                _resolve_matched(local, rb, conflicts)
                if before != (local.get("dirty"), local.get("title"), local.get("done")):
                    stats["adopted"] += 1

        # 원격에서 사라진(삭제된) 로컬 todo 처리
        for t in local_todos:
            bid = t.get("notion_block_id")
            if bid and bid not in remote_by_id:
                if t.get("dirty"):
                    # 삭제 vs 로컬 수정 충돌 → block_id 비우고 dirty 유지(push가 재생성)
                    conflicts.append({"at": nc.now_kst(), "todo_id": t["id"],
                                      "winner": "local", "note": "remote-deleted vs local-edit"})
                    if not dry_run:
                        t["notion_block_id"] = None
                else:
                    stats["remote_deleted"] += 1
                    remove_ids.append(t["id"])

    if not dry_run and remove_ids:
        doc["todos"] = [t for t in doc["todos"] if t["id"] not in remove_ids]

    # body_md가 채워진 tasks_list로 재저장해 preview가 description+body를 읽게 한다.
    # page_ids로 일부만 처리해도 나머지 Task의 기존 body_md는 리스트에 그대로 남아
    # 보존된다.
    if not dry_run:
        store.save_tasks({"version": 1, "synced_at": nc.now_kst(), "tasks": tasks_list})

    return stats


def pull(token, doc, conflicts, dry_run):
    """full pull (하위호환): 메타 + 전체 본문 reconcile."""
    mstats, new_tasks = pull_meta(token, conflicts, dry_run)
    bstats = pull_task_bodies(token, doc, conflicts, dry_run, new_tasks, None)
    return {**mstats, **bstats}


def _priority_page_ids(tasks, priority):
    """우선순위 라벨에 해당하는 page_id 집합 (sync --priority 범위 제한용)."""
    return {t["page_id"] for t in tasks if t.get("priority") == priority}


def _todo_from_remote(page_id, rb):
    now = nc.now_kst()
    return {
        "id": store._new_todo_id(),
        "task_page_id": page_id,
        "notion_block_id": rb["block_id"],
        "title": rb["title"],
        "status": "완료" if rb["done"] else "시작전",
        "done": rb["done"],
        "due": "",
        "created_at": now,
        "updated_at": now,
        "dirty": False,
        "deleted": False,
        "notion_last_edited": rb["last_edited"],
    }


# ── PUSH ──────────────────────────────────────────────────────

def push(token, doc, dry_run):
    """로컬 dirty → Notion. append/update/delete 블록 + Task 상태 push."""
    stats = {"appended": 0, "updated": 0, "deleted": 0, "status_pushed": 0}
    actions = []
    purge_ids = []

    for t in doc["todos"]:
        if not t.get("dirty"):
            continue
        if t.get("task_page_id") == store.BACKLOG_ID:
            continue  # Backlog은 로컬 전용 — Notion에 보내지 않는다
        bid = t.get("notion_block_id")
        page_id = t["task_page_id"]

        if t.get("deleted"):
            if bid:
                actions.append(("delete", t["title"]))
                stats["deleted"] += 1
                if not dry_run:
                    nc.notion_request(token, "DELETE", f"/blocks/{bid}")
            purge_ids.append(t["id"])  # 로컬에서 완전 제거
            continue

        if bid is None:
            actions.append(("append", t["title"]))
            stats["appended"] += 1
            if not dry_run:
                resp = nc.notion_request(
                    token, "PATCH", f"/blocks/{page_id}/children",
                    {"children": [build_todo_block(t["title"], t["done"])]})
                new_block = resp.get("results", [{}])[0]
                t["notion_block_id"] = new_block.get("id")
                t["notion_last_edited"] = new_block.get("last_edited_time", "")
                t["dirty"] = False
        else:
            actions.append(("update", t["title"]))
            stats["updated"] += 1
            if not dry_run:
                resp = nc.notion_request(
                    token, "PATCH", f"/blocks/{bid}",
                    {"to_do": {"rich_text": nc.plain_to_rich_text(t["title"]),
                               "checked": t["done"]}})
                t["notion_last_edited"] = resp.get("last_edited_time", "")
                t["dirty"] = False

    if not dry_run and purge_ids:
        doc["todos"] = [t for t in doc["todos"] if t["id"] not in purge_ids]

    # Task 상태 push (meta_dirty)
    tasks_doc = store.load_tasks()
    changed = False
    for task in tasks_doc["tasks"]:
        if not task.get("meta_dirty"):
            continue
        actions.append(("status", f"{task['name']} → {task['status']}"))
        stats["status_pushed"] += 1
        if not dry_run:
            # 상태와 Done 체크박스를 함께 push한다. Task DB는 완료를 status와 Done
            # 두 속성으로 이중 관리하므로(DONE 뷰·롤업은 Done 기준), 상태만 보내면
            # status=완료인데 DONE 뷰에 안 보이는 불일치가 생긴다(notion-task.py와 동일 정책).
            nc.notion_request(token, "PATCH", f"/pages/{task['page_id']}",
                              {"properties": {
                                  "상태": {"status": {"name": task["status"]}},
                                  "Done": {"checkbox": task["status"] == "완료"}}})
            task["meta_dirty"] = False
            changed = True
    if not dry_run and changed:
        store.save_tasks(tasks_doc)

    return stats, actions


# ── 오케스트레이션 ────────────────────────────────────────────

def _backup():
    if store.TODOS_FILE.exists():
        shutil.copy2(store.TODOS_FILE, BACKUP_FILE)


def run(mode, dry_run, page_id=None, priority=None):
    token = nc.get_token()
    state = load_sync_state()
    conflicts = state.get("conflicts", [])
    conflicts_before = len(conflicts)

    if not dry_run:
        _backup()

    doc = store.load_todos()
    result = {"mode": mode, "dry_run": dry_run}
    # 전체 본문을 빠짐없이 당긴 경우만 "full 본문 동기화"로 본다(헤더 stale 표시용).
    # --priority로 일부만 당긴 sync는 부분이므로 제외한다.
    did_full_bodies = False

    try:
        # ── PULL 계열 ──
        if mode == "sync-meta":
            mstats, _ = pull_meta(token, conflicts, dry_run)
            result["pull"] = mstats
        elif mode in ("sync", "pull"):
            mstats, new_tasks = pull_meta(token, conflicts, dry_run)
            page_ids = (_priority_page_ids(new_tasks, priority)
                        if (mode == "sync" and priority) else None)
            bstats = pull_task_bodies(token, doc, conflicts, dry_run, new_tasks, page_ids)
            result["pull"] = {**mstats, **bstats}
            did_full_bodies = page_ids is None
        elif mode == "pull-task":
            # 메타는 갱신하지 않는다(드릴인 대상은 이미 목록에 보였음).
            # 현재 캐시에서 해당 Task의 본문만 reconcile한다.
            tasks_list = store.load_tasks()["tasks"]
            bstats = pull_task_bodies(token, doc, conflicts, dry_run,
                                      tasks_list, {page_id})
            result["pull"] = bstats

        # ── PUSH 계열 ──
        if mode in ("sync", "sync-meta", "pull-task", "push"):
            pstats, actions = push(token, doc, dry_run)
            result["push"] = pstats
            if dry_run:
                result["push_actions"] = actions
    except nc.NotionError as e:
        if e.status == 429:
            state["rate_limit_backoff_until"] = datetime.now(timezone.utc).isoformat()
        save_sync_state(state)
        print(json.dumps({"success": False, "error": str(e),
                          "hint": "rate limit이면 잠시 후 재시도"}, ensure_ascii=False))
        sys.exit(1)

    if not dry_run:
        store.save_todos(doc)
        state["conflicts"] = conflicts
        state["last_full_sync"] = nc.now_kst()
        if did_full_bodies:
            state["last_body_sync"] = nc.now_kst()
        state["rate_limit_backoff_until"] = None
        save_sync_state(state)

    result["success"] = True
    result["new_conflicts"] = len(conflicts) - conflicts_before
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="양방향 Todo Sync 엔진")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("sync", "sync-meta", "pull-task", "pull", "push"):
        sp = sub.add_parser(name)
        sp.add_argument("--dry-run", action="store_true")
        if name == "sync":
            sp.add_argument("--priority", default=None,
                            help="본문 reconcile을 이 우선순위(P1/P2/P3) Task로 제한")
        if name == "pull-task":
            sp.add_argument("--page-id", required=True,
                            help="본문을 reconcile할 Task의 Notion page_id")
    args = p.parse_args()
    run(args.command, args.dry_run,
        page_id=getattr(args, "page_id", None),
        priority=getattr(args, "priority", None))


if __name__ == "__main__":
    main()
