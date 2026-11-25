#!/usr/bin/env python3
"""
Notion Daily Work Log CLI
Usage:
  python3 notion-daily.py read --date today|yesterday|YYYY-MM-DD
  python3 notion-daily.py append-coach-tomorrow --page-id ID --items '["...", "..."]' [--dry-run]
  python3 notion-daily.py append-todos --page-id ID --items '["...", "..."]' [--dry-run]
  python3 notion-daily.py append-todos --page-id ID --tree '[{"text": "...", "link": "PLE-1", "children": [{"text": "..."}]}]' [--parent-block ID] [--no-prop] [--dry-run]
  python3 notion-daily.py list-todo-parents --page-id ID
  python3 notion-daily.py carry-tomorrow --page-id ID --from-date YYYY-MM-DD [--dry-run]

덧붙이는 쓰기 명령은 기존 블록을 고치거나 지우지 않는다.
- append-coach-tomorrow (daily:retrospective): Tomorrow 칸 아래 "회고 코치 추천" 구역에 할 일을 덧붙인다
- append-todos (daily:start): 아침 코치가 제안하고 사용자가 고른 할 일을 할 일 칸(제목 Today 또는 Todo's) 끝에 덧붙인다
- carry-tomorrow (daily:start): 전날 일지 Tomorrow 칸을 오늘 일지 Yesterday 칸 끝에 그대로 옮겨 적는다
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
# 일지마다 제목 표기가 다르다("Lesson Learn", "Lesson Learned", 할 일 칸 "Todo's"/"Today").
# 어느 쪽이든 같은 칸으로 읽고, 출력 키는 하나로 유지해 스킬 쪽 참조가 갈리지 않게 한다.
SECTION_HEADING_ALIASES = {"Lesson Learned": "Lesson Learn", "Today": "Todos"}
COLUMN_SECTIONS = {"todos": "Todos", "tomorrow": "Tomorrow", "yesterday": "Yesterday",
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


def flatten_text(nodes, depth=0, mark_checked=False):
    """mark_checked=True면 체크된 to_do 줄 앞에 "[x] "를 붙인다 (하위 항목 완료 판정용)."""
    lines = []
    for n in nodes:
        if n["text"].strip():
            prefix = "[x] " if mark_checked and n.get("checked") else ""
            lines.append("  " * depth + prefix + n["text"].strip())
        lines.extend(flatten_text(n["children"], depth + 1, mark_checked))
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

    def items_of(name, mark_checked=False):
        sec = sections.get(name)
        if not sec:
            return []
        return [{"text": x["text"].strip(),
                 "detail": "\n".join(flatten_text(x["children"], mark_checked=mark_checked))}
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
        # tomorrow·coach_tomorrow는 제목만 담는 기존 필드라 하위 항목(체크박스, 메모)이 사라진다.
        # 하위 항목으로 완료 판정이 갈리므로 detail을 함께 담은 필드를 덧붙인다. 기존 필드는 유지한다
        "tomorrow_items": items_of("Tomorrow", mark_checked=True),
        # Yesterday 칸: 전날 Tomorrow를 옮겨 적은 기록(carry-tomorrow가 쓴다). 예전 일지엔 없을 수 있어
        # missing_sections 검사 대상이 아니다
        "yesterday_items": items_of("Yesterday", mark_checked=True),
        "coach_tomorrow_items": items_of(COACH_TOMORROW_SECTION, mark_checked=True),
        "notes": [{"title": t["text"].strip(), "text": "\n".join(flatten_text(t["children"]))}
                  for t in notes if not t["text"].strip().startswith(WORRY_TOGGLE_PREFIX)],
        "worries": worries,
        "retro": {k: items_of(k) for k in RETRO_SECTIONS},
        "missing_sections": [k for k in ["Todos", "Tomorrow", *RETRO_SECTIONS] if k not in sections],
    }, sections


DAILY_DB_ID = "2bf64745-3170-8016-b20a-ff022dea06cb"


def find_page(token, target_date):
    """Due Date가 target_date(YYYY-MM-DD)인 일지 페이지를 돌려준다. 없으면 None."""
    body = {"filter": {"property": "Due Date", "date": {"equals": target_date}}}
    resp = notion_request(token, "POST", f"/data_sources/{resolve_ds_id(token, DAILY_DB_ID)}/query", body)
    results = resp.get("results", [])
    return results[0] if results else None


def cmd_read(args):
    token = get_token()
    target_date = resolve_date(args.date)
    page = find_page(token, target_date)

    if not page:
        print(json.dumps({
            "page_id": None,
            "date": target_date,
            "todos": [],
            "tomorrow": "",
            "kpt": "",
            "error": f"No page found for date {target_date}"
        }, ensure_ascii=False, indent=2))
        return

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


# carry-tomorrow가 옮기는 블록 종류. 글(rich_text)을 가진 블록만 그대로 다시 만들 수 있다
CARRY_TYPES = {"to_do", "bulleted_list_item", "numbered_list_item", "paragraph", "quote", "toggle", "callout"}


def copy_block(raw):
    """GET으로 읽은 블록을 children 없이 다시 만들 수 있는 모양으로(글·링크·체크·색 유지)."""
    t = raw["type"]
    src = raw.get(t, {})
    data = {"rich_text": [writable_rich(r) for r in src.get("rich_text", [])]}
    for key in ("checked", "color", "icon"):
        if key in src:
            data[key] = src[key]
    return {"object": "block", "type": t, t: data}


def read_children_raw(token, block_id):
    """block_id의 자식 블록 원본(JSON)을 페이지네이션까지 읽는다."""
    out, cursor = [], None
    while True:
        qs = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        resp = notion_request(token, "GET", f"/blocks/{block_id}/children{qs}")
        out.extend(resp.get("results", []))
        if not resp.get("has_more"):
            return out
        cursor = resp.get("next_cursor")


def carry_tree(token, raws, parent_id, after, dry_run, unsupported):
    """raws를 parent_id 아래(after 뒤)에 한 단계씩 만든다. Notion은 한 요청에 중첩 2단계까지만 받아서
    상위를 먼저 만들고 응답의 새 id 밑에 자식을 붙인다. 만든 블록 수를 돌려준다."""
    blocks, kept = [], []
    for raw in raws:
        if raw["type"] in CARRY_TYPES:
            blocks.append(copy_block(raw))
            kept.append(raw)
        else:
            unsupported.append(raw["type"])
    if not blocks:
        return 0
    count = len(blocks)
    if dry_run:
        new_ids = [None] * len(blocks)
    else:
        body = {"children": blocks}
        if after:
            body["after"] = after
        resp = notion_request(token, "PATCH", f"/blocks/{parent_id}/children", body)
        new_ids = [r["id"] for r in resp.get("results", [])][-len(blocks):]
    for raw, new_id in zip(kept, new_ids):
        if raw.get("has_children"):
            count += carry_tree(token, read_children_raw(token, raw["id"]), new_id, None, dry_run, unsupported)
    return count


def cmd_carry_tomorrow(args):
    """전날 일지의 Tomorrow 칸을 오늘 일지의 Yesterday 칸 끝에 그대로 옮겨 적는다(글·링크·체크·하위 항목 유지).

    Yesterday 칸에 같은 최상위 글이 이미 있으면 건너뛰어 다시 실행해도 중복되지 않는다.
    회고 코치 추천 구역은 Tomorrow와 제목이 달라 옮기지 않는다. 기존 블록은 고치거나 지우지 않는다.
    """
    token = get_token()
    src_page = find_page(token, resolve_date(args.from_date))
    if not src_page:
        print(json.dumps({"success": False, "error": f"{args.from_date} 일지 페이지가 없습니다"}, ensure_ascii=False))
        sys.exit(1)
    _, src_sections = parse_body(fetch_tree(token, src_page["id"]))
    tomorrow = src_sections.get("Tomorrow")
    if not tomorrow:
        print(json.dumps({"success": False, "error": f"{args.from_date} 일지 본문에 Tomorrow 칸이 없습니다"},
                         ensure_ascii=False))
        sys.exit(1)
    _, sections = parse_body(fetch_tree(token, args.page_id))
    yesterday = sections.get("Yesterday")
    if not yesterday:
        print(json.dumps({"success": False, "error": "오늘 일지 본문에 Yesterday 칸이 없습니다"}, ensure_ascii=False))
        sys.exit(1)

    already = {norm(n["text"]) for n in yesterday["nodes"] if n["text"].strip()}
    items = [n for n in tomorrow["nodes"] if n["text"].strip()]
    new_items = [n for n in items if norm(n["text"]) not in already]
    skipped = [n["text"].strip() for n in items if norm(n["text"]) in already]

    unsupported, after, created = [], yesterday["last_block_id"], 0
    for n in new_items:  # 상위 항목마다 따로 붙여 순서를 지킨다(after는 직전에 만든 블록)
        raw = notion_request(token, "GET", f"/blocks/{n['id']}")
        if raw["type"] not in CARRY_TYPES:
            unsupported.append(raw["type"])
            continue
        if args.dry_run:
            created += carry_tree(token, [raw], yesterday["parent_id"], after, True, unsupported)
            continue
        resp = notion_request(token, "PATCH", f"/blocks/{yesterday['parent_id']}/children",
                              {"children": [copy_block(raw)], "after": after})
        # 응답이 새 블록만 줄 수도, 부모의 자식 전체를 줄 수도 있어 글로 새 블록을 찾는다
        # (Yesterday 칸에 같은 글이 없다는 것은 위 중복 검사가 보장한다)
        results = resp.get("results", [])
        new_id = next((r["id"] for r in results
                       if norm(rich_text_to_plain(r.get(r["type"], {}).get("rich_text", []))) == norm(n["text"])),
                      results[0]["id"])
        created += 1
        if raw.get("has_children"):
            created += carry_tree(token, read_children_raw(token, raw["id"]), new_id, None, False, unsupported)
        after = new_id

    print(json.dumps({"success": True, "dry_run": args.dry_run, "from_page_id": src_page["id"],
                      "insert_after_block": yesterday["last_block_id"],
                      "appended": [n["text"].strip() for n in new_items], "skipped": skipped,
                      "blocks_created": created, "unsupported": sorted(set(unsupported))},
                     ensure_ascii=False, indent=2))


TODOS_PROP = "Todo's"
JIRA_BROWSE = "https://riiid-pioneer.atlassian.net/browse/"


JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def normalize_link(link):
    """링크 하나를 {label, url}로 바꾼다. 받는 형태: Jira 키("PLE-6"), URL 문자열, {"url", "label"?}.
    라벨을 주지 않으면 URL 종류로 정한다: Jira → 키, GitHub PR·이슈 → #번호, Gmail → 메일, 그 밖 → 호스트."""
    if isinstance(link, dict):
        url, label = str(link.get("url", "")).strip(), str(link.get("label", "")).strip()
    else:
        url, label = str(link or "").strip(), ""
    if not url:
        return None
    if JIRA_KEY_RE.match(url):
        url = JIRA_BROWSE + url
    if not url.startswith("https://"):
        return None  # https가 아닌 값은 링크로 쓰지 않는다
    if not label:
        m = re.search(r"/browse/([A-Z][A-Z0-9]+-\d+)", url)
        g = re.search(r"github\.com/[^/]+/([^/]+)/(?:pull|issues)/(\d+)", url)
        if m:
            label = m.group(1)
        elif g:
            label = f"{g.group(1)}#{g.group(2)}" if g.group(1) != "kubernetes" else f"#{g.group(2)}"
        elif "mail.google.com" in url:
            label = "메일"
        else:
            label = re.sub(r"^https://(www\.)?", "", url).split("/", 1)[0]
    return {"label": label, "url": url}


def entry_links(entry):
    """항목의 link(예전 형식, 하나)와 links(여러 개)를 합쳐 중복 없이 {label, url} 목록으로."""
    raw = ([entry["link"]] if entry.get("link") else []) + list(entry.get("links") or [])
    out, seen = [], set()
    for r in raw:
        n = normalize_link(r)
        if n and n["url"] not in seen:
            seen.add(n["url"])
            out.append(n)
    return out


def link_segments(links):
    """글 뒤에 붙일 rich_text 조각: "  라벨 · 라벨" (라벨마다 링크)."""
    segs = []
    for i, l in enumerate(links):
        segs.append({"type": "text", "text": {"content": "  " if i == 0 else " · "}})
        segs.append({"type": "text", "text": {"content": l["label"], "link": {"url": l["url"]}}})
    return segs


def todo_block_rich(text, link=None, children=None, checked=False, links=None):
    """to_do 블록. 링크(Jira 키, 메일·PR URL 등)는 글 끝에 라벨 링크로 붙이고, children은 하위 to_do로 넣는다."""
    ls = entry_links({"link": link, "links": links})
    rich = [{"type": "text", "text": {"content": text}}] + link_segments(ls)
    block = {"object": "block", "type": "to_do", "to_do": {"rich_text": rich, "checked": bool(checked)}}
    if children:
        block["to_do"]["children"] = [todo_block_rich(c["text"], c.get("link"), links=c.get("links"))
                                      for c in children if c.get("text", "").strip()]
    return block


def read_todos_prop(token, page_id):
    page = notion_request(token, "GET", f"/pages/{page_id}")
    return rich_text_to_plain(page.get("properties", {}).get(TODOS_PROP, {}).get("rich_text", []))


def read_todos_prop_rich(token, page_id):
    """Todo's property의 rich_text를 쓰기용 조각으로 읽는다(기존 링크를 지우지 않으려고)."""
    page = notion_request(token, "GET", f"/pages/{page_id}")
    segs = []
    for r in page.get("properties", {}).get(TODOS_PROP, {}).get("rich_text", []):
        content = r.get("plain_text", "")
        seg = {"type": "text", "text": {"content": content}}
        href = r.get("href") or ((r.get("text") or {}).get("link") or {}).get("url")
        if href:
            seg["text"]["link"] = {"url": href}
        segs.append(seg)
    return segs


def trim_trailing_bullet(segs):
    """끝에 남은 빈 글머리표 자리("  • ")는 새 항목이 채운다."""
    while segs:
        c = segs[-1]["text"]["content"]
        t = re.sub(r"\n?[ \t]*•?[ \t]*$", "", c) if not segs[-1]["text"].get("link") else c
        if t == c:
            break
        if t:
            segs[-1]["text"]["content"] = t
            break
        segs.pop()
    return segs


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
        # --items: 문자열 또는 {"text", "links"?} (링크: Jira 키, 메일·PR URL)
        entries = []
        for x in json.loads(args.items or "[]"):
            e = dict(x) if isinstance(x, dict) else {"text": str(x)}
            e["text"] = str(e.get("text", "")).strip()
            if e["text"]:
                entries.append(e)
    _, sections = parse_body(fetch_tree(token, args.page_id))

    todos = sections.get("Todos")
    if not todos:
        print(json.dumps({"success": False,
                          "error": "본문에 할 일 칸(제목 Today 또는 Todo's)이 없어 덧붙일 위치를 찾지 못했습니다"},
                         ensure_ascii=False))
        sys.exit(1)

    # 글 끝에 링크 라벨("  PLE-27 · #10315")이 붙어 저장되므로, 라벨을 붙인 글로도 비교한다(재실행 중복 방지)
    def written_keys(e):
        return {norm(e["text"]), norm(e["text"] + "".join(l["label"] for l in entry_links(e)))}

    already_written = {norm(t["text"]) for t in flatten_todos(todos["nodes"])}
    new_entries, skipped = [], []
    for e in entries:
        keys = written_keys(e)
        (skipped if keys & already_written else new_entries).append(e)
        already_written |= keys

    blocks = [todo_block_rich(e["text"], e.get("link"), e.get("children"), args.checked, e.get("links"))
              for e in new_entries]
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

    # property: 기존 rich_text 조각(링크 포함)을 그대로 두고 끝에 "  • 글  라벨 · 라벨" 줄을 덧붙인다
    prop_before = prop_after = None
    prop_segs = None
    if not args.no_prop:
        before = read_todos_prop_rich(token, args.page_id)
        prop_before = "".join(s["text"]["content"] for s in before)
        prop_segs = trim_trailing_bullet([dict(s, text=dict(s["text"])) for s in before])
        for e in new_entries:
            lead = "\n" if prop_segs else ""
            prop_segs.append({"type": "text", "text": {"content": f"{lead}  • {e['text']}"}})
            prop_segs.extend(link_segments(entry_links(e)))
        prop_after = "".join(s["text"]["content"] for s in prop_segs) if new_entries else prop_before
        for s in prop_segs:  # rich_text 조각 하나는 2000자 상한
            s["text"]["content"] = s["text"]["content"][:2000]

    if new_entries and not args.dry_run:
        notion_request(token, "PATCH", f"/blocks/{target}/children", body)
        if not args.no_prop and prop_after != prop_before:
            notion_request(token, "PATCH", f"/pages/{args.page_id}", {"properties": {
                TODOS_PROP: {"rich_text": prop_segs[:100]}}})

    # 항목마다 블록 id를 돌려준다(하루 시작 보드의 상태 반영 버튼이 이 id의 checked만 바꾼다).
    # 쓰기 뒤 Todos를 다시 읽어 글로 맞춘다. dry-run에서 새 항목은 아직 블록이 없어 id가 null이다
    by_key = {}
    for t in todo_nodes_with_ids(load_todos_section(token, args.page_id)["nodes"]):
        by_key.setdefault(norm(t["text"]), t["id"])
    skipped_ids = {id(e) for e in skipped}

    def block_id_of(e):
        return next((by_key[k] for k in written_keys(e) if k in by_key), None)

    blocks = [{"text": e["text"], "id": block_id_of(e), "skipped": id(e) in skipped_ids} for e in entries]

    print(json.dumps({"success": True, "dry_run": args.dry_run,
                      "insert_after_block": insert_after, "parent_block": args.parent_block,
                      "appended": [e["text"] for e in new_entries], "skipped": [e["text"] for e in skipped],
                      "blocks": blocks,
                      "prop_before": prop_before, "prop_after": prop_after}, ensure_ascii=False, indent=2))


def cmd_list_todo_parents(args):
    """Todos 칸의 최상위 to_do 목록(id, text, checked). 보드 반영 때 상위 항목 후보로 쓴다."""
    token = get_token()
    _, sections = parse_body(fetch_tree(token, args.page_id))
    todos = sections.get("Todos")
    if not todos:
        print(json.dumps({"success": False, "error": "본문에 할 일 칸(제목 Today 또는 Todo's)이 없습니다"}, ensure_ascii=False))
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
        print(json.dumps({"success": False, "error": "본문에 할 일 칸(제목 Today 또는 Todo's)이 없습니다"}, ensure_ascii=False))
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


def writable_rich(r):
    """GET으로 읽은 rich_text 조각을 PATCH에 다시 보낼 수 있는 모양으로(서식·링크·멘션 유지)."""
    t = r.get("type", "text")
    out = {"type": t, t: r.get(t, {})}
    if r.get("annotations"):
        out["annotations"] = r["annotations"]
    return out


def cmd_add_links(args):
    """이미 있는 Todos 할 일 끝에 링크를 덧붙인다. 글과 체크 상태는 그대로 둔다.

    - --map: [{"block_id": "<list-todos의 id>", "links": ["PLE-6", "<URL>", {"url", "label"}]}]
    - 블록에 이미 걸린 URL은 건너뛰어 다시 실행해도 중복되지 않는다
    - Todo's property는 건드리지 않는다
    """
    token = get_token()
    plan = json.loads(args.map)
    by_id = {t["id"].replace("-", ""): t for t in todo_nodes_with_ids(load_todos_section(token, args.page_id)["nodes"])}
    unknown = [p.get("block_id") for p in plan if str(p.get("block_id", "")).replace("-", "") not in by_id]
    if unknown:
        print(json.dumps({"success": False, "error": "Todos 칸의 할 일이 아닌 id가 있어 아무것도 쓰지 않았습니다",
                          "unknown": unknown}, ensure_ascii=False))
        sys.exit(1)
    results = []
    for p in plan:
        bid = p["block_id"]
        block = notion_request(token, "GET", f"/blocks/{bid}")
        rich = block.get("to_do", {}).get("rich_text", [])
        have = {r.get("href") for r in rich if r.get("href")}
        new = [l for l in entry_links({"links": p.get("links")}) if l["url"] not in have]
        if new and not args.dry_run:
            body = {"to_do": {"rich_text": [writable_rich(r) for r in rich] + link_segments(new)}}
            notion_request(token, "PATCH", f"/blocks/{bid}", body)
        results.append({"block_id": bid, "text": by_id[bid.replace("-", "")]["text"],
                        "added": [f"{l['label']} <{l['url']}>" for l in new],
                        "already": len(entry_links({"links": p.get("links")})) - len(new)})
    print(json.dumps({"success": True, "dry_run": args.dry_run, "results": results}, ensure_ascii=False, indent=2))


def cmd_sync_prop(args):
    """Todo's property를 본문 Todos 칸의 최상위 할 일 목록으로 다시 쓴다(본문을 직접 고쳐 둘이 어긋났을 때).

    줄마다 "  • 할 일 글"이고, 본문 할 일에 걸린 링크는 그대로 옮긴다. 기존 property 값은 덮어쓴다.
    --strike-done: 본문에서 체크된 할 일은 property 줄에 취소선을 긋는다(회고 때 끝낸 일 표시).
    """
    token = get_token()
    todos = load_todos_section(token, args.page_id)
    top = [n for n in todos["nodes"] if n["type"] == "to_do" and n["text"].strip()]
    segs, struck = [], []
    for i, n in enumerate(top):
        rich = notion_request(token, "GET", f"/blocks/{n['id']}").get("to_do", {}).get("rich_text", [])
        strike = bool(args.strike_done and n["checked"])
        segs.append({"type": "text", "text": {"content": ("\n" if i else "") + "  • "}})
        for r in rich:
            w = writable_rich(r)
            # 본문에 이미 그어 둔 취소선은 유지하고, 체크된 할 일이면 새로 긋는다
            w["annotations"] = dict(w.get("annotations") or {}, strikethrough=strike or bool((w.get("annotations") or {}).get("strikethrough")))
            segs.append(w)
        if strike:
            struck.append(n["text"].strip())
    before_rich = notion_request(token, "GET", f"/pages/{args.page_id}").get("properties", {}).get(TODOS_PROP, {}).get("rich_text", [])
    before = rich_text_to_plain(before_rich)
    before_struck = "".join(r.get("plain_text", "") for r in before_rich if (r.get("annotations") or {}).get("strikethrough"))
    after = "".join(("\n" if i else "") + "  • " + n["text"].strip() for i, n in enumerate(top))
    after_struck = "".join(s["text"]["content"] for s in segs if s["type"] == "text" and s.get("annotations", {}).get("strikethrough"))
    changed = after != before or after_struck != before_struck
    if len(segs) > 100:
        print(json.dumps({"success": False, "error": f"property rich_text 조각이 {len(segs)}개라 Notion 상한(100)을 넘습니다"},
                         ensure_ascii=False))
        sys.exit(1)
    if not args.dry_run and changed:
        notion_request(token, "PATCH", f"/pages/{args.page_id}", {"properties": {TODOS_PROP: {"rich_text": segs}}})
    print(json.dumps({"success": True, "dry_run": args.dry_run, "changed": changed, "struck": struck,
                      "prop_before": before, "prop_after": after}, ensure_ascii=False, indent=2))


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

    carry_parser = subparsers.add_parser(
        "carry-tomorrow", help="전날 일지 Tomorrow 칸을 오늘 일지 Yesterday 칸에 옮겨 적는다")
    carry_parser.add_argument("--page-id", required=True, help="오늘 일지 page_id (read 출력)")
    carry_parser.add_argument("--from-date", required=True, help="Tomorrow를 가져올 일지 날짜 (YYYY-MM-DD 또는 yesterday)")
    carry_parser.add_argument("--dry-run", action="store_true", help="Notion에 쓰지 않고 옮길 항목만 출력한다")

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

    links_parser = subparsers.add_parser(
        "add-links", help="이미 있는 Todos 할 일 끝에 링크(Jira 키, 메일·PR URL)를 덧붙인다")
    links_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")
    links_parser.add_argument("--map", required=True,
                              help='JSON 배열: [{"block_id": "<list-todos id>", "links": ["PLE-6", "<URL>"]}]')
    links_parser.add_argument("--dry-run", action="store_true", help="Notion에 쓰지 않고 붙일 링크만 출력한다")

    sync_parser = subparsers.add_parser(
        "sync-prop", help="Todo's property를 본문 Todos 칸의 최상위 할 일(링크 포함)로 다시 쓴다")
    sync_parser.add_argument("--page-id", required=True, help="read 출력의 page_id")
    sync_parser.add_argument("--strike-done", action="store_true", help="본문에서 체크된 할 일은 property 줄에 취소선을 긋는다")
    sync_parser.add_argument("--dry-run", action="store_true", help="Notion에 쓰지 않고 전후만 출력한다")

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args)
    elif args.command == "append-coach-tomorrow":
        cmd_append_coach_tomorrow(args)
    elif args.command == "carry-tomorrow":
        cmd_carry_tomorrow(args)
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
    elif args.command == "add-links":
        cmd_add_links(args)
    elif args.command == "sync-prop":
        cmd_sync_prop(args)


if __name__ == "__main__":
    main()
