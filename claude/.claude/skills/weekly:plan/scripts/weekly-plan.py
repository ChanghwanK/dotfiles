#!/usr/bin/env python3
"""
주간 Plan 노트 CLI (Notion API 직접 호출, stdlib only)

Usage:
  python3 weekly-plan.py create [--date YYYY-MM-DD] [--dry-run]
  python3 weekly-plan.py candidates [--date YYYY-MM-DD] [--stale-weeks 4]
  python3 weekly-plan.py apply --spec spec.json [--only all|goals|reminders] [--date YYYY-MM-DD]
  python3 weekly-plan.py set-status --task <url> --status "진행 중"

환경변수: NOTION_TOKEN (Notion-Personal integration 토큰)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

NOTION_VERSION = "2025-09-03"
# #주간 Plan (Weekly Planner) 페이지 안의 인라인 Weekly DB
WEEKLY_DS_ID = "3db64745-3170-80fc-9a90-000b98f9c0d1"
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"
WEEKDAYS = ["월", "화", "수", "목", "금"]


def get_token():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        print("Error: NOTION_TOKEN is not set (source ~/.secrets.zsh)", file=sys.stderr)
        sys.exit(1)
    return token


def notion(token, method, path, body=None):
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def week_of(d):
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=4), monday + timedelta(days=6)


def week_title(d):
    monday, friday, _ = week_of(d)
    iso_week = monday.isocalendar()[1]
    return f"{iso_week}주차 {monday:%m.%d} ~ {friday:%m.%d}"


# ── block builders ────────────────────────────────────────────
def rt(text, italic=False):
    return [{"type": "text", "text": {"content": text}, "annotations": {"italic": italic}}] if text else []


def block(kind, text="", children=None, **extra):
    payload = {"rich_text": rt(text), **extra}
    if children:
        payload["children"] = children
    return {"object": "block", "type": kind, kind: payload}


def labeled(label):
    """불릿 없는 평문 문단 `레이블:` + 그 아래 빈 최상위 불릿 (notion-writing-style 레이블 규칙)."""
    return [block("paragraph", f"{label}:"), block("bulleted_list_item")]


def build_blocks(monday):
    callout = block("callout", color="gray_background", children=[
        block("numbered_list_item", "summary"),
        block("numbered_list_item", "어떤 고민을 했는지?"),
        block("numbered_list_item", "재발 방지를 위해 무엇을 해야할지?"),
    ])
    goals = [
        block("to_do", f"목표 {i}", checked=False, children=labeled("완료 기준"))
        for i in (1, 2, 3)
    ]
    days = [
        block("toggle", f"{monday + timedelta(days=i):%m.%d} {WEEKDAYS[i]}")
        for i in range(5)
    ]
    return [
        callout,
        block("heading_2", "이번 주 목표"), *goals,
        block("heading_2", "이번 주 하지 않을 것"), block("bulleted_list_item"),
        block("heading_2", "일별 기록"), *days,
        block("heading_2", "주간 회고"), *labeled("목표 달성"), *labeled("다음 주로 넘길 것"),
    ]


def find_existing(token, title):
    resp = notion(token, "POST", f"/data_sources/{WEEKLY_DS_ID}/query", {
        "filter": {"property": "이름", "title": {"equals": title}}, "page_size": 1,
    })
    results = resp.get("results", [])
    return results[0] if results else None


def cmd_create(args):
    d = date.fromisoformat(args.date) if args.date else date.today()
    monday, _, _ = week_of(d)
    title = week_title(d)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "title": title, "생성일": monday.isoformat(),
                          "blocks": len(build_blocks(monday))}, ensure_ascii=False, indent=2))
        return
    token = get_token()
    existing = find_existing(token, title)
    if existing:
        print(json.dumps({"created": False, "title": title, "page_id": existing["id"],
                          "url": existing["url"]}, ensure_ascii=False, indent=2))
        return
    page = notion(token, "POST", "/pages", {
        "parent": {"type": "data_source_id", "data_source_id": WEEKLY_DS_ID},
        "properties": {
            "이름": {"title": [{"text": {"content": title}}]},
            "생성일": {"date": {"start": monday.isoformat()}},
        },
        "children": build_blocks(monday),
    })
    print(json.dumps({"created": True, "title": title, "page_id": page["id"],
                      "url": page["url"]}, ensure_ascii=False, indent=2))


# ── candidates ────────────────────────────────────────────────
def parse_task(page):
    p = page["properties"]
    due = (p.get("Due Date") or {}).get("date") or {}
    sel = lambda k: ((p.get(k) or {}).get("select") or {}).get("name")
    return {
        "name": "".join(t["plain_text"] for t in p["Title"]["title"]).strip(),
        "status": ((p.get("상태") or {}).get("status") or {}).get("name"),
        "due_start": due.get("start"),
        "due_end": due.get("end"),
        "group": sel("Group"),
        "type": sel("Type"),
        "priority": sel("Priority"),
        "last_edited": (page.get("last_edited_time") or "")[:10] or None,
        "url": page["url"],
    }


def activity_date(t):
    # Due Date가 없거나 지난 진행 중 Task도 최근에 손댔으면 최근 작업으로 본다
    return max(d for d in (t["due_start"], t["last_edited"], "") if d is not None)


def query_all(token, ds_id, body):
    results, cursor = [], None
    while True:
        payload = dict(body, page_size=100, **({"start_cursor": cursor} if cursor else {}))
        resp = notion(token, "POST", f"/data_sources/{ds_id}/query", payload)
        results += resp.get("results", [])
        if not resp.get("has_more"):
            return results
        cursor = resp["next_cursor"]


def cmd_candidates(args):
    d = date.fromisoformat(args.date) if args.date else date.today()
    monday, _, sunday = week_of(d)
    stale_cutoff = monday - timedelta(weeks=args.stale_weeks)
    token = get_token()
    ds_id = notion(token, "GET", f"/databases/{TASK_DB_ID}")["data_sources"][0]["id"]
    tasks = [parse_task(p) for p in query_all(token, ds_id, {
        "filter": {"property": "상태", "status": {"does_not_equal": "완료"}},
        "sorts": [{"property": "Due Date", "direction": "ascending"}],
    })]

    def in_range(t, lo, hi):
        return t["due_start"] and lo.isoformat() <= t["due_start"] <= hi.isoformat()

    due_this_week = [t for t in tasks if in_range(t, monday, sunday)]
    next_week = [t for t in tasks if in_range(t, sunday + timedelta(days=1), sunday + timedelta(days=7))]
    # 이번 주·다음 주 마감은 위 두 목록에 이미 있으므로 진행 중 분류에서 뺀다
    in_progress = [t for t in tasks if t["status"] == "진행 중"
                   and not (t["due_start"] and t["due_start"] >= monday.isoformat())]
    in_progress_recent = sorted(
        (t for t in in_progress if activity_date(t) >= stale_cutoff.isoformat()),
        key=activity_date, reverse=True)
    carryover_todo = [t for t in tasks if t["status"] != "진행 중"
                      and in_range(t, stale_cutoff, monday - timedelta(days=1))]
    stale_in_progress = [t for t in in_progress if activity_date(t) < stale_cutoff.isoformat()]

    print(json.dumps({
        "week": week_title(d),
        "due_this_week": due_this_week,
        "due_next_week": next_week,
        "in_progress_recent": in_progress_recent,
        "carryover_todo": carryover_todo,
        "stale_in_progress_count": len(stale_in_progress),
        "open_total": len(tasks),
    }, ensure_ascii=False, indent=2))


# ── apply ─────────────────────────────────────────────────────
REMIND_HEADING = "이번 주 리마인드"


def rt_link(text, url=None):
    item = {"type": "text", "text": {"content": text}}
    if url:
        item["text"]["link"] = {"url": url}
    return [item]


def children_of(token, block_id):
    out, cursor = [], None
    while True:
        q = f"?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        resp = notion(token, "GET", f"/blocks/{block_id}/children{q}")
        out += resp.get("results", [])
        if not resp.get("has_more"):
            return out
        cursor = resp["next_cursor"]


def plain(b):
    return "".join(t.get("plain_text", "") for t in b.get(b["type"], {}).get("rich_text", []))


def section(blocks, heading):
    """heading_2 `heading` 아래부터 다음 heading_2 전까지의 (heading 블록, 본문 블록 목록)."""
    for i, b in enumerate(blocks):
        if b["type"] == "heading_2" and plain(b) == heading:
            body = []
            for nb in blocks[i + 1:]:
                if nb["type"] == "heading_2":
                    break
                body.append(nb)
            return b, body
    return None, []


def todo(text, url=None, checked=False):
    return {"object": "block", "type": "to_do",
            "to_do": {"rich_text": rt_link(text, url), "checked": checked}}


def cmd_apply(args):
    """spec JSON: {"goals": [{"title", "url"?, "done_when"}], "reminders": [{"label", "items": [{"text", "url"?}]}]}

    사용자가 노트에서 한 체크는 지우지 않는다.
    - 목표 체크박스는 텍스트만 바꾸고 checked 상태를 유지한다
    - 리마인드는 구역을 새로 쓰되, 같은 텍스트의 항목은 체크 상태를 이어받는다.
      새 spec에 없는 체크된 항목은 지우지 않고 '이전에 체크한 항목' 아래에 남긴다
    """
    spec = json.loads(open(args.spec, encoding="utf-8").read())
    parts = {"goals", "reminders"} if args.only == "all" else {args.only}
    d = date.fromisoformat(args.date) if args.date else date.today()
    token = get_token()
    page = find_existing(token, week_title(d))
    if not page:
        print(f"Error: '{week_title(d)}' 노트가 없습니다. create를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)
    blocks = children_of(token, page["id"])
    result = {"url": page["url"], "goals": 0, "reminders": 0, "kept_checked": [], "carried_checked": 0}

    goal_heading, goal_body = section(blocks, "이번 주 목표")
    if "goals" in parts:
        goal_todos = [b for b in goal_body if b["type"] == "to_do"]
        for g, b in zip(spec.get("goals", []), goal_todos):
            notion(token, "PATCH", f"/blocks/{b['id']}",
                   {"to_do": {"rich_text": rt_link(g["title"], g.get("url")),
                              "checked": b["to_do"].get("checked", False)}})
            kids = children_of(token, b["id"]) if b.get("has_children") else []
            bullet = next((k for k in kids if k["type"] == "bulleted_list_item"), None)
            if bullet:
                notion(token, "PATCH", f"/blocks/{bullet['id']}",
                       {"bulleted_list_item": {"rich_text": rt_link(g["done_when"])}})
            else:
                notion(token, "PATCH", f"/blocks/{b['id']}/children", {"children": [
                    block("paragraph", "완료 기준:"), block("bulleted_list_item", g["done_when"])]})
            result["goals"] += 1

    reminders = spec.get("reminders")
    if "reminders" in parts and reminders:
        heading, body = section(blocks, REMIND_HEADING)
        checked = {plain(b) for b in body if b["type"] == "to_do" and b["to_do"].get("checked")}
        new_texts = {i["text"] for g in reminders for i in g["items"]}
        kept = [b for b in body if b["type"] == "to_do" and b["to_do"].get("checked")
                and plain(b) not in new_texts]
        for b in body:
            notion(token, "DELETE", f"/blocks/{b['id']}")
        new = [] if heading else [block("heading_2", REMIND_HEADING)]
        for group in reminders:
            new.append(block("paragraph", f"{group['label']}:"))
            for i in group["items"]:
                was = i["text"] in checked
                result["carried_checked"] += was
                new.append(todo(i["text"], i.get("url"), checked=was))
        if kept:
            new.append(block("paragraph", "이전에 체크한 항목:"))
            new += [{"object": "block", "type": "to_do",
                     "to_do": {"rich_text": b["to_do"]["rich_text"], "checked": True}} for b in kept]
            result["kept_checked"] = [plain(b) for b in kept]
        anchor = heading["id"] if heading else (goal_body[-1]["id"] if goal_body else goal_heading["id"])
        notion(token, "PATCH", f"/blocks/{page['id']}/children", {"children": new, "after": anchor})
        result["reminders"] = sum(len(g["items"]) for g in reminders)

    print(json.dumps(result, ensure_ascii=False, indent=2))


TASK_STATUSES = ("해야할 것", "대기", "진행 중", "완료")


def page_id_from(ref):
    """Notion URL 또는 page id에서 32자리 id를 뽑는다."""
    tail = ref.rstrip("/").split("/")[-1].split("?")[0].replace("-", "")
    return tail[-32:]


def cmd_set_status(args):
    """사용자가 승인한 Task 상태 제안만 반영한다."""
    token = get_token()
    pid = page_id_from(args.task)
    before = parse_task(notion(token, "GET", f"/pages/{pid}"))
    page = notion(token, "PATCH", f"/pages/{pid}",
                  {"properties": {"상태": {"status": {"name": args.status}}}})
    after = parse_task(page)
    print(json.dumps({"name": after["name"], "before": before["status"], "after": after["status"],
                      "url": after["url"]}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Weekly Plan note CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="Create this week's note in Weekly DB (idempotent)")
    c.add_argument("--date", help="Any date in the target week (default: today)")
    c.add_argument("--dry-run", action="store_true")
    k = sub.add_parser("candidates", help="Collect weekly goal candidates from Task DB")
    k.add_argument("--date")
    k.add_argument("--stale-weeks", type=int, default=4,
                   help="Ignore carryover older than N weeks (default: 4)")
    a = sub.add_parser("apply", help="Write chosen goals and reminders into this week's note")
    a.add_argument("--spec", required=True, help="JSON file with goals and reminders")
    a.add_argument("--date")
    a.add_argument("--only", choices=("all", "goals", "reminders"), default="all",
                   help="Update only goals or only reminders (default: all)")
    st = sub.add_parser("set-status", help="Change a Task's 상태 (approved suggestions only)")
    st.add_argument("--task", required=True, help="Task page URL or id")
    st.add_argument("--status", required=True, choices=TASK_STATUSES)
    args = parser.parse_args()
    {"create": cmd_create, "candidates": cmd_candidates, "apply": cmd_apply,
     "set-status": cmd_set_status}[args.cmd](args)


if __name__ == "__main__":
    main()
