#!/usr/bin/env python3
"""
Notion Daily Work Log CLI
Usage:
  python3 notion-daily.py read --date today|yesterday|YYYY-MM-DD
  python3 notion-daily.py append-coach-tomorrow --page-id ID --items '["...", "..."]' [--dry-run]
  python3 notion-daily.py append-todos --page-id ID --items '["...", "..."]' [--dry-run]
  python3 notion-daily.py append-todos --page-id ID --tree '[{"text": "...", "link": "PLE-1", "children": [{"text": "..."}]}]' [--parent-block ID] [--no-prop] [--dry-run]
  python3 notion-daily.py list-todo-parents --page-id ID

쓰기는 두 명령뿐이고, 둘 다 덧붙이기만 한다. 기존 블록은 고치거나 지우지 않는다.
- append-coach-tomorrow (daily:retrospective): Tomorrow 칸 아래 "회고 코치 추천" 구역에 할 일을 덧붙인다
- append-todos (daily:start): 아침 코치가 제안하고 사용자가 고른 할 일을 Todos 칸 끝에 덧붙인다
그 밖의 회고 내용은 daily:retrospective가 정리본으로 출력한다.
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta
import argparse
import re
import os


def get_token():
    import os
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("Error: NOTION_TOKEN environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return token


def notion_request(token, method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2025-09-03",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


# ── data source resolution (Notion-Version 2025-09-03) ────────
# 2025-09-03부터 쿼리는 database가 아니라 data source 단위다.
# 단일 data source DB를 전제로 db_id→ds_id를 1회 조회 후 프로세스 내 캐시한다.
_DS_CACHE = {}


def resolve_ds_id(token, db_id):
    """db_id → data source id (프로세스 내 캐시). 2025-09-03 쿼리/생성에 필요."""
    if db_id not in _DS_CACHE:
        db = notion_request(token, "GET", f"/databases/{db_id}")
        sources = db.get("data_sources", [])
        if not sources:
            raise RuntimeError(f"database {db_id} has no data_sources")
        _DS_CACHE[db_id] = sources[0]["id"]
    return _DS_CACHE[db_id]


def resolve_date(date_str):
    today = date.today()
    if date_str == "today":
        return today.isoformat()
    elif date_str == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    else:
        try:
            date.fromisoformat(date_str)
            return date_str
        except ValueError:
            print(f"Invalid date format: {date_str}. Use today/yesterday/YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)


def rich_text_to_plain(rich_text_list):
    """Extract plain text from rich_text array."""
    return "".join(item.get("plain_text", "") for item in rich_text_list)


def parse_todos_from_rich_text(rich_text_list):
    """
    Parse todos from a rich_text property.
    Each rich_text segment may contain multiple lines.
    Strikethrough annotation on the segment marks those lines as done.

    Returns list of: {"text": "- item text", "done": bool}
    """
    todos = []
    for segment in rich_text_list:
        text = segment.get("plain_text", "")
        done = segment.get("annotations", {}).get("strikethrough", False)
        # Split by newline: each non-empty line is a todo item
        lines = text.split("\n")
        for line in lines:
            if line.strip():
                todos.append({"text": line, "done": done})
    return todos


def parse_page_properties(page):
    """
    Parse page properties into structured sections.
    Property names: "Todo's", "내일 할 것들", "KPT"
    """
    props = page.get("properties", {})

    def get_rich_text_plain(prop_name):
        prop = props.get(prop_name, {})
        rt = prop.get("rich_text", [])
        return rich_text_to_plain(rt)

    todos_rich_text = props.get("Todo's", {}).get("rich_text", [])
    todos = parse_todos_from_rich_text(todos_rich_text)

    return {
        "todos": todos,
        "tomorrow": get_rich_text_plain("내일 할 것들"),
        "kpt": get_rich_text_plain("KPT"),
    }


# ── 본문 블록 파싱 ─────────────────────────────────────────────
# 일지 템플릿의 본문 구역은 제목 블록 글자로 찾는다. 아이콘·공백이 붙어 있어
# (예: "☑️ Todo’s") 글자와 숫자만 남겨 비교한다.
RETRO_SECTIONS = ["Keep", "Problem", "Try", "Lesson Learn"]
# 일지마다 제목 표기가 다르다("Lesson Learn", "Lesson Learned"). 어느 쪽이든 같은 칸으로
# 읽고, 출력 키는 RETRO_SECTIONS의 이름 하나로 유지해 스킬 쪽 참조가 갈리지 않게 한다.
SECTION_HEADING_ALIASES = {"Lesson Learned": "Lesson Learn"}
COLUMN_SECTIONS = {"todos": "Todos", "tomorrow": "Tomorrow",
                   **{re.sub(r"\W", "", k).lower(): k for k in RETRO_SECTIONS},
                   **{re.sub(r"\W", "", alias).lower(): section
                      for alias, section in SECTION_HEADING_ALIASES.items()}}
WORRY_TOGGLE_PREFIX = "고민"
# 회고 코치가 Tomorrow 칸 아래에 덧붙이는 구역. 사용자가 직접 쓴 Tomorrow 항목과 섞이지
# 않게 제목을 따로 둔다. 템플릿에 없는 구역이라 missing_sections 검사 대상이 아니다.
COACH_TOMORROW_SECTION = "회고 코치 추천"
COLUMN_SECTIONS[re.sub(r"\W", "", COACH_TOMORROW_SECTION).lower()] = COACH_TOMORROW_SECTION


def norm(text):
    return re.sub(r"\W", "", text or "").lower()


def block_text(block):
    data = block.get(block["type"], {})
    return rich_text_to_plain(data.get("rich_text", []))


def fetch_tree(token, block_id):
    """block_id의 자식 블록을 재귀로 읽는다 (페이지네이션 포함)."""
    nodes, cursor = [], None
    while True:
        qs = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        resp = notion_request(token, "GET", f"/blocks/{block_id}/children{qs}")
        for b in resp.get("results", []):
            node = {
                "id": b["id"],
                "type": b["type"],
                "text": block_text(b),
                "checked": b.get("to_do", {}).get("checked") if b["type"] == "to_do" else None,
                "children": fetch_tree(token, b["id"]) if b.get("has_children") else [],
            }
            nodes.append(node)
        if not resp.get("has_more"):
            return nodes
        cursor = resp.get("next_cursor")


def flatten_text(nodes, depth=0):
    lines = []
    for n in nodes:
        if n["text"].strip():
            lines.append("  " * depth + n["text"].strip())
        lines.extend(flatten_text(n["children"], depth + 1))
    return lines


def flatten_todos(nodes, depth=0):
    todos = []
    for n in nodes:
        if n["type"] == "to_do" and n["text"].strip():
            todos.append({"text": n["text"].strip(), "checked": bool(n["checked"]), "depth": depth})
            todos.extend(flatten_todos(n["children"], depth + 1))
    return todos


def parse_column(column, sections):
    """column 안을 제목(heading)으로 나눠 sections에 채운다. divider는 구역 끝이다."""
    current = None
    for n in column["children"]:
        if n["type"].startswith("heading_") and norm(n["text"]) in COLUMN_SECTIONS:
            name = COLUMN_SECTIONS[norm(n["text"])]
            current = sections.setdefault(name, {
                "parent_id": column["id"], "heading_id": n["id"],
                "last_block_id": n["id"], "nodes": [],
            })
            continue
        if n["type"] == "divider" or n["type"].startswith("heading_"):
            current = None
            continue
        if current is None:
            continue
        current["nodes"].append(n)
        if n["text"].strip() or n["children"]:
            current["last_block_id"] = n["id"]


def parse_body(tree):
    sections, notes = {}, []
    h2 = None
    for n in tree:
        if n["type"] == "heading_2":
            h2 = norm(n["text"])
            continue
        if n["type"] == "column_list":
            for col in n["children"]:
                parse_column(col, sections)
            continue
        if h2 == "notes" and n["type"] == "toggle":
            notes.append(n)

    def items_of(name):
        sec = sections.get(name)
        if not sec:
            return []
        return [{"text": x["text"].strip(), "detail": "\n".join(flatten_text(x["children"]))}
                for x in sec["nodes"] if x["text"].strip()]

    worries = []
    for t in notes:
        if t["text"].strip().startswith(WORRY_TOGGLE_PREFIX):
            for w in t["children"]:
                if w["text"].strip():
                    worries.append({"title": w["text"].strip(),
                                    "detail": "\n".join(flatten_text(w["children"]))})

    todo_sec = sections.get("Todos")
    return {
        "todos": flatten_todos(todo_sec["nodes"]) if todo_sec else [],
        "tomorrow": [i["text"] for i in items_of("Tomorrow")],
        "coach_tomorrow": [i["text"] for i in items_of(COACH_TOMORROW_SECTION)],
        "notes": [{"title": t["text"].strip(), "text": "\n".join(flatten_text(t["children"]))}
                  for t in notes if not t["text"].strip().startswith(WORRY_TOGGLE_PREFIX)],
        "worries": worries,
        "retro": {k: items_of(k) for k in RETRO_SECTIONS},
        "missing_sections": [k for k in ["Todos", "Tomorrow", *RETRO_SECTIONS] if k not in sections],
    }, sections


def cmd_read(args):
    token = get_token()
    target_date = resolve_date(args.date)

    DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"

    # Query DB for the page with matching Due Date
    body = {
        "filter": {
            "property": "Due Date",
            "date": {
                "equals": target_date
            }
        }
    }
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, DB_ID)}/query", body)
    results = resp.get("results", [])

    if not results:
        print(json.dumps({
            "page_id": None,
            "date": target_date,
            "todos": [],
            "tomorrow": "",
            "kpt": "",
            "error": f"No page found for date {target_date}"
        }, ensure_ascii=False, indent=2))
        return

    page = results[0]
    page_id = page["id"]
    parsed = parse_page_properties(page)

    output = {
        "page_id": page_id,
        "date": target_date,
        "todos": parsed["todos"],
        "tomorrow": parsed["tomorrow"],
        "kpt": parsed["kpt"],
    }
    try:
        output["body"], _ = parse_body(fetch_tree(token, page_id))
    except SystemExit:
        output["body_error"] = "본문 블록 조회 실패 (stderr 참고)"
    print(json.dumps(output, ensure_ascii=False, indent=2))



def todo_block(text):
    return {"object": "block", "type": "to_do",
            "to_do": {"rich_text": [{"type": "text", "text": {"content": text}}], "checked": False}}


def cmd_append_coach_tomorrow(args):
    """Tomorrow 칸 아래 "회고 코치 추천" 구역에 할 일을 덧붙인다.

    구역이 없으면 Tomorrow 마지막 항목 뒤에 제목과 함께 만들고, 있으면 그 끝에 잇는다.
    같은 글이 이미 있으면 건너뛰어 다시 실행해도 중복되지 않는다.
    """
    token = get_token()
    items = [x.strip() for x in json.loads(args.items) if x.strip()]
    _, sections = parse_body(fetch_tree(token, args.page_id))

    tomorrow = sections.get("Tomorrow")
    if not tomorrow:
        print(json.dumps({"success": False,
                          "error": "본문에 Tomorrow 칸이 없어 덧붙일 위치를 찾지 못했습니다"},
                         ensure_ascii=False))
        sys.exit(1)

    coach = sections.get(COACH_TOMORROW_SECTION)
    already_written = {norm(n["text"]) for n in coach["nodes"]} if coach else set()
    new_items, skipped = [], []
    for item in items:
        (skipped if norm(item) in already_written else new_items).append(item)
        already_written.add(norm(item))

    children = [todo_block(item) for item in new_items]
    if coach is None:
        heading = {"object": "block", "type": "heading_3", "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": COACH_TOMORROW_SECTION}}]}}
        children.insert(0, heading)
    insert_after = (coach or tomorrow)["last_block_id"]

    if new_items and not args.dry_run:
        notion_request(token, "PATCH", f"/blocks/{tomorrow['parent_id']}/children",
                       {"children": children, "after": insert_after})

    print(json.dumps({"success": True, "dry_run": args.dry_run,
                      "section_created": coach is None and bool(new_items),
                      "insert_after_block": insert_after,
                      "appended": new_items, "skipped": skipped}, ensure_ascii=False, indent=2))


TODOS_PROP = "Todo's"
JIRA_BROWSE = "https://riiid-pioneer.atlassian.net/browse/"


def todo_block_rich(text, link=None, children=None, checked=False):
    """to_do 블록. link(Jira 키)가 있으면 글 끝에 링크 텍스트로 붙이고, children은 하위 to_do로 넣는다."""
    rich = [{"type": "text", "text": {"content": text}}]
    if link:
        url = link if link.startswith("http") else JIRA_BROWSE + link
        label = link.rsplit("/", 1)[-1]
        rich += [{"type": "text", "text": {"content": "  "}},
                 {"type": "text", "text": {"content": label, "link": {"url": url}}}]
    block = {"object": "block", "type": "to_do", "to_do": {"rich_text": rich, "checked": bool(checked)}}
    if children:
        block["to_do"]["children"] = [todo_block_rich(c["text"]) for c in children if c.get("text", "").strip()]
    return block


def read_todos_prop(token, page_id):
    page = notion_request(token, "GET", f"/pages/{page_id}")
    return rich_text_to_plain(page.get("properties", {}).get(TODOS_PROP, {}).get("rich_text", []))


def cmd_append_todos(args):
    """Todos 칸에 할 일을 덧붙이고, Todo's property 끝에도 같은 줄을 덧붙인다.

    - --items: 글자만 있는 최상위 to_do (daily:start 아침 코치용, 기존 형식)
    - --tree: [{"text", "link"?, "children": [{"text"}]}] 하위 to_do와 Jira 링크를 포함한 항목
    - --parent-block: 주면 그 to_do의 하위 끝에, 없으면 Todos 칸 끝에 넣는다
    - property: 기존 값을 읽어 끝에 "  • <상위 글>"을 덧붙인다(덮어쓰지 않음). --no-prop으로 끈다
    Todos 칸에 이미 있는 글(하위 항목 포함)과 같으면 건너뛰어 다시 실행해도 중복되지 않는다.
    """
    token = get_token()
    if args.tree:
        entries = [e for e in json.loads(args.tree) if str(e.get("text", "")).strip()]
        for e in entries:
            e["text"] = e["text"].strip()
    else:
        entries = [{"text": x.strip()} for x in json.loads(args.items or "[]") if x.strip()]
    _, sections = parse_body(fetch_tree(token, args.page_id))

    todos = sections.get("Todos")
    if not todos:
        print(json.dumps({"success": False,
                          "error": "본문에 Todos 칸이 없어 덧붙일 위치를 찾지 못했습니다"},
                         ensure_ascii=False))
        sys.exit(1)

    already_written = {norm(t["text"]) for t in flatten_todos(todos["nodes"])}
    new_entries, skipped = [], []
    for e in entries:
        (skipped if norm(e["text"]) in already_written else new_entries).append(e)
        already_written.add(norm(e["text"]))

    blocks = [todo_block_rich(e["text"], e.get("link"), e.get("children"), args.checked) for e in new_entries]
    if args.parent_block:
        top_ids = {n["id"].replace("-", "") for n in todos["nodes"] if n["type"] == "to_do"}
        if args.parent_block.replace("-", "") not in top_ids:
            print(json.dumps({"success": False,
                              "error": f"--parent-block {args.parent_block}가 Todos 칸의 최상위 할 일이 아닙니다"},
                             ensure_ascii=False))
            sys.exit(1)
        target, body = args.parent_block, {"children": blocks}
        insert_after = "(상위 항목의 하위 끝)"
    else:
        insert_after = todos["last_block_id"]
        target, body = todos["parent_id"], {"children": blocks, "after": insert_after}

    prop_before = prop_after = None
    if not args.no_prop:
        prop_before = read_todos_prop(token, args.page_id)
        lines = [f"  • {e['text']}" + (f" ({e['link'].rsplit('/', 1)[-1]})" if e.get("link") else "")
                 for e in new_entries]
        kept = prop_before.split("\n")
        while kept and kept[-1].strip() in ("", "•"):  # 끝에 남은 빈 글머리표 자리는 새 항목이 채운다
            kept.pop()
        prop_after = "\n".join(kept + lines) if lines else prop_before

    if new_entries and not args.dry_run:
        notion_request(token, "PATCH", f"/blocks/{target}/children", body)
        if not args.no_prop and prop_after != prop_before:
            notion_request(token, "PATCH", f"/pages/{args.page_id}", {"properties": {
                TODOS_PROP: {"rich_text": [{"type": "text", "text": {"content": prop_after[:2000]}}]}}})

    print(json.dumps({"success": True, "dry_run": args.dry_run,
                      "insert_after_block": insert_after, "parent_block": args.parent_block,
                      "appended": [e["text"] for e in new_entries], "skipped": [e["text"] for e in skipped],
                      "prop_before": prop_before, "prop_after": prop_after}, ensure_ascii=False, indent=2))


def cmd_list_todo_parents(args):
    """Todos 칸의 최상위 to_do 목록(id, text, checked). 보드 반영 때 상위 항목 후보로 쓴다."""
    token = get_token()
    _, sections = parse_body(fetch_tree(token, args.page_id))
    todos = sections.get("Todos")
    if not todos:
        print(json.dumps({"success": False, "error": "본문에 Todos 칸이 없습니다"}, ensure_ascii=False))
        sys.exit(1)
    parents = [{"id": n["id"], "text": n["text"].strip(), "checked": bool(n["checked"]),
                "children": len(n["children"])}
               for n in todos["nodes"] if n["type"] == "to_do" and n["text"].strip()]
    print(json.dumps({"success": True, "parents": parents}, ensure_ascii=False, indent=2))


def todo_nodes_with_ids(nodes, depth=0):
    """Todos 칸의 to_do를 모든 깊이에서 (id, text, checked, depth)로 편다."""
    out = []
    for n in nodes:
        if n["type"] == "to_do" and n["text"].strip():
            out.append({"id": n["id"], "text": n["text"].strip(), "checked": bool(n["checked"]), "depth": depth})
        out.extend(todo_nodes_with_ids(n.get("children", []), depth + 1))
    return out


def load_todos_section(token, page_id):
    _, sections = parse_body(fetch_tree(token, page_id))
    todos = sections.get("Todos")
    if not todos:
        print(json.dumps({"success": False, "error": "본문에 Todos 칸이 없습니다"}, ensure_ascii=False))
        sys.exit(1)
    return todos


def cmd_list_todos(args):
    """Todos 칸의 할 일을 모든 깊이에서 id와 함께 출력한다. 보드 완료 체크를 일지 할 일과 맞출 때 쓴다."""
    token = get_token()
    todos = load_todos_section(token, args.page_id)
    print(json.dumps({"success": True, "todos": todo_nodes_with_ids(todos["nodes"])}, ensure_ascii=False, indent=2))


def cmd_check_todos(args):
    """Todos 칸의 to_do 블록 체크 상태를 바꾼다. 글은 건드리지 않고 checked만 PATCH한다.

    - --block-ids: list-todos의 id 배열. Todos 칸 안의 to_do가 아니면 쓰지 않고 실패한다
    - --uncheck: 체크를 해제한다 (보드에서 완료를 되돌렸을 때)
    이미 원하는 상태인 블록은 건너뛰어 다시 실행해도 같은 결과다.
    """
    token = get_token()
    want = not args.uncheck
    ids = [str(x).replace("-", "") for x in json.loads(args.block_ids) if str(x).strip()]
    by_id = {t["id"].replace("-", ""): t for t in todo_nodes_with_ids(load_todos_section(token, args.page_id)["nodes"])}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        print(json.dumps({"success": False, "error": "Todos 칸의 할 일이 아닌 id가 있어 아무것도 쓰지 않았습니다",
                          "unknown": unknown}, ensure_ascii=False))
        sys.exit(1)
    changed = [by_id[i] for i in ids if by_id[i]["checked"] != want]
    unchanged = [by_id[i] for i in ids if by_id[i]["checked"] == want]
    if not args.dry_run:
        for t in changed:
            notion_request(token, "PATCH", f"/blocks/{t['id']}", {"to_do": {"checked": want}})
    print(json.dumps({"success": True, "dry_run": args.dry_run, "checked": want,
                      "changed": [{"id": t["id"], "text": t["text"]} for t in changed],
                      "unchanged": [{"id": t["id"], "text": t["text"]} for t in unchanged]},
                     ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Daily Work Log CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # read command
    read_parser = subparsers.add_parser("read", help="Read daily work log")
    read_parser.add_argument("--date", required=True,
                             help="Date to read: today, yesterday, or YYYY-MM-DD")


    coach_parser = subparsers.add_parser(
        "append-coach-tomorrow", help='Tomorrow 칸 아래 "회고 코치 추천" 구역에 할 일을 덧붙인다')
    coach_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")
    coach_parser.add_argument("--items", required=True, help='JSON 배열: ["할 일 1", "할 일 2"]')
    coach_parser.add_argument("--dry-run", action="store_true",
                              help="Notion에 쓰지 않고 덧붙일 내용과 위치만 출력한다")

    todos_parser = subparsers.add_parser(
        "append-todos", help="Todos 칸 끝에 할 일을 덧붙인다 (daily:start 아침 코치용)")
    todos_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")
    todos_parser.add_argument("--items", help='JSON 배열: ["할 일 1", "할 일 2"] (글자만 있는 최상위 할 일)')
    todos_parser.add_argument("--tree", help='JSON 배열: [{"text": "...", "link": "PLE-123", "children": [{"text": "..."}]}]')
    todos_parser.add_argument("--parent-block", help="이 최상위 to_do의 하위 끝에 넣는다 (list-todo-parents의 id)")
    todos_parser.add_argument("--no-prop", action="store_true", help="Todo's property는 건드리지 않는다")
    todos_parser.add_argument("--checked", action="store_true",
                              help="체크된 상태로 넣는다 (보드에서 완료한 일이 일지에 없을 때)")
    todos_parser.add_argument("--dry-run", action="store_true",
                              help="Notion에 쓰지 않고 덧붙일 내용과 위치만 출력한다")

    parents_parser = subparsers.add_parser(
        "list-todo-parents", help="Todos 칸의 최상위 할 일 목록 (보드 반영 때 상위 항목 후보)")
    parents_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")

    list_parser = subparsers.add_parser(
        "list-todos", help="Todos 칸의 할 일 전체(모든 깊이, id 포함). 보드 완료 체크와 맞출 때 쓴다")
    list_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")

    check_parser = subparsers.add_parser(
        "check-todos", help="Todos 칸 할 일의 체크 상태를 바꾼다 (보드 완료 체크 반영용)")
    check_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")
    check_parser.add_argument("--block-ids", required=True, help='JSON 배열: list-todos의 id ["...", "..."]')
    check_parser.add_argument("--uncheck", action="store_true", help="체크를 해제한다")
    check_parser.add_argument("--dry-run", action="store_true", help="Notion에 쓰지 않고 바뀔 항목만 출력한다")

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args)
    elif args.command == "append-coach-tomorrow":
        cmd_append_coach_tomorrow(args)
    elif args.command == "append-todos":
        if not args.items and not args.tree:
            parser.error("append-todos에는 --items 또는 --tree가 필요합니다")
        cmd_append_todos(args)
    elif args.command == "list-todo-parents":
        cmd_list_todo_parents(args)
    elif args.command == "list-todos":
        cmd_list_todos(args)
    elif args.command == "check-todos":
        cmd_check_todos(args)


if __name__ == "__main__":
    main()
