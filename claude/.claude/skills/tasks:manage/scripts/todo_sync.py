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

Usage:
  todo_sync.py sync   [--dry-run]   # pull → 충돌해소 → push (기본)
  todo_sync.py pull   [--dry-run]   # Notion → 로컬만
  todo_sync.py push   [--dry-run]   # 로컬 → Notion만
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
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {"last_full_sync": "", "conflicts": [], "rate_limit_backoff_until": None}


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
    local["done"] = remote["done"]
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

def pull(token, doc, conflicts, dry_run):
    """Notion → 로컬. tasks.json 재구성 + 각 페이지 to_do 블록 reconcile."""
    stats = {"tasks": 0, "created": 0, "adopted": 0, "remote_deleted": 0}

    # 1) Task 메타 재구성 (meta_dirty 보존 + 충돌 판정)
    old_tasks = {t["page_id"]: t for t in store.load_tasks()["tasks"]}
    new_tasks = []
    for task in nc.query_active_tasks(token):
        old = old_tasks.get(task["page_id"])
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
                # 로컬 status 유지 + meta_dirty 보존 → push가 반영
                new_tasks.append({**task, "status": old["status"],
                                  "meta_dirty": True,
                                  "meta_updated_at": old.get("meta_updated_at")})
        else:
            new_tasks.append(task)
    stats["tasks"] = len(new_tasks)
    if not dry_run:
        store.save_tasks({"version": 1, "synced_at": nc.now_kst(), "tasks": new_tasks})

    # 2) 각 활성 Task 페이지의 to_do 블록 reconcile
    remove_ids = []
    for task in new_tasks:
        page_id = task["page_id"]
        remote_blocks = [
            parse_todo_block(b)
            for b in nc.get_all_children(token, page_id)
            if b.get("type") == "to_do"  # callout 등 다른 블록 제외
        ]
        remote_by_id = {b["block_id"]: b for b in remote_blocks}
        local_todos = [t for t in doc["todos"]
                       if t.get("task_page_id") == page_id and not t.get("deleted")]
        local_by_block = {t["notion_block_id"]: t
                          for t in local_todos if t.get("notion_block_id")}

        for rb in remote_blocks:
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

    return stats


def _todo_from_remote(page_id, rb):
    now = nc.now_kst()
    return {
        "id": store._new_todo_id(),
        "task_page_id": page_id,
        "notion_block_id": rb["block_id"],
        "title": rb["title"],
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
            nc.notion_request(token, "PATCH", f"/pages/{task['page_id']}",
                              {"properties": {"상태": {"status": {"name": task["status"]}}}})
            task["meta_dirty"] = False
            changed = True
    if not dry_run and changed:
        store.save_tasks(tasks_doc)

    return stats, actions


# ── 오케스트레이션 ────────────────────────────────────────────

def _backup():
    if store.TODOS_FILE.exists():
        shutil.copy2(store.TODOS_FILE, BACKUP_FILE)


def run(mode, dry_run):
    token = nc.get_token()
    state = load_sync_state()
    conflicts = state.get("conflicts", [])
    conflicts_before = len(conflicts)

    if not dry_run:
        _backup()

    doc = store.load_todos()
    result = {"mode": mode, "dry_run": dry_run}

    try:
        if mode in ("sync", "pull"):
            result["pull"] = pull(token, doc, conflicts, dry_run)
        if mode in ("sync", "push"):
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
        state["rate_limit_backoff_until"] = None
        save_sync_state(state)

    result["success"] = True
    result["new_conflicts"] = len(conflicts) - conflicts_before
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="양방향 Todo Sync 엔진")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("sync", "pull", "push"):
        sp = sub.add_parser(name)
        sp.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    run(args.command, args.dry_run)


if __name__ == "__main__":
    main()
