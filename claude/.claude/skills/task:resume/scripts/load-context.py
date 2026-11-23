#!/usr/bin/env python3
"""
이어 갈 작업의 맥락을 입력 종류와 상관없이 같은 모양으로 꺼낸다 (task:resume).

사용법:
  python3 load-context.py brief   --date 2026-11-23 --id t16    # 하루 시작 브리핑 항목 (id: 스레드 id 또는 topN)
  python3 load-context.py session --id <session_id>              # Claude 세션 id
  python3 load-context.py search  --query 시크릿 [--days 7]      # 키워드로 최근 세션 후보 찾기

공통 출력(brief, session):
  source, title, project, cwd, status, stopped_at, next_action, done_when, done, evidence,
  prs, session{session_id,title,cwd,ended_at,last_user_messages,last_assistant}, session_error, error
search 출력: query, days, candidates[{session_id,title,cwd,ended_at,matched_in,first_message}], error

- 브리핑: ~/.claude/tmp/daily-start/<date>.json (daily:start가 쓴다. 필드 약속은 daily:start SKILL.md "이어가기 흐름")
- 세션: ~/.claude/skills/daily:start/scripts/extract-work.py 결과를 쓴다(그 스크립트의 필드에 기댄다)
- 찾지 못하면 error에 이유를 쓰고 exit 1
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
HOME = Path.home()
BRIEF_DIR = HOME / ".claude" / "tmp" / "daily-start"
PROJECTS_DIR = HOME / ".claude" / "projects"
EXTRACT = HOME / ".claude" / "skills" / "daily:start" / "scripts" / "extract-work.py"
FIELDS = ("title", "project", "cwd", "status", "tag", "stopped_at", "next_action", "done_when",
          "reason", "done", "follow_up", "evidence", "resume")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
MAX_TEXT = 600


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return code


def fail(msg):
    return out({"error": msg}, 1)


def clip(s):
    s = str(s or "").strip()
    return s if len(s) <= MAX_TEXT else s[:MAX_TEXT] + "…"


def sessions_on(day):
    """extract-work.py로 그날 활동한 세션 목록. 실패하면 []"""
    try:
        res = subprocess.run([sys.executable, str(EXTRACT), "--date", day], capture_output=True, text=True, timeout=60)
        return json.loads(res.stdout).get("sessions", [])
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def session_view(s):
    msgs = s.get("user_messages") or []
    return {
        "session_id": s.get("session_id"),
        "title": s.get("title"),
        "cwd": s.get("cwd"),
        "ended_at": s.get("ended_at"),
        "last_user_messages": [clip(m) for m in msgs[-3:]],
        "last_assistant": clip(s.get("last_assistant")),
    }


def find_session(session_id, days):
    """주어진 날짜 후보들을 차례로 보며 session_id 세션을 찾는다"""
    if not session_id:
        return None, "session_id 없음"
    for day in [d for d in days if d]:
        for s in sessions_on(day):
            if s.get("session_id") == session_id:
                return session_view(s), None
    return None, f"세션 로그에서 {session_id}를 찾지 못함 (확인한 날짜: {', '.join(d for d in days if d)})"


def base(source):
    return {"source": source, "error": None}


def merge_fields(item, *sources):
    for src in sources:  # 뒤 소스가 앞 소스를 덮는다
        for k in FIELDS:
            if (src or {}).get(k):
                item[k] = src[k]


def thread_session_id(thread, item):
    sessions = (thread or {}).get("sessions") or []
    sid = sessions[-1].get("session_id") if sessions else None
    if not sid:
        m = UUID_RE.search(item.get("resume") or "")
        sid = m.group(0) if m else None
    return sid


def cmd_brief(date, item_id):
    path = BRIEF_DIR / f"{date}.json"
    if not path.exists():
        return fail(f"브리핑 파일 없음: {path}. 그날 /daily:start를 실행했는지 확인하세요")
    data = json.loads(path.read_text(encoding="utf-8"))
    yday = data.get("yesterday") or {}
    threads = {t.get("id"): t for t in yday.get("threads") or []}
    top3 = data.get("top3") or []

    m = re.fullmatch(r"top(\d+)", item_id)
    if m:
        n = int(m.group(1))
        if not 1 <= n <= len(top3):
            return fail(f"top3에 {n}번 항목이 없음")
        top_item = top3[n - 1]
        thread = threads.get(top_item.get("thread_id"))
    else:
        thread = threads.get(item_id)
        top_item = next((t for t in top3 if t.get("thread_id") == item_id), None)
    if not thread and not top_item:
        return fail(f"{date} 브리핑에서 {item_id}를 찾지 못함")

    item = base("brief")
    item.update({"id": item_id, "date": date, "thread_date": yday.get("date"), "in_top3": bool(top_item)})
    merge_fields(item, thread, top_item)  # top3 값(오늘 기준 첫 행동 등)이 스레드 값을 덮는다
    item["prs"] = [{"number": p.get("number"), "state": p.get("state"), "url": p.get("url")} for p in (thread or {}).get("prs") or []]
    item["session"], item["session_error"] = find_session(thread_session_id(thread, item), [yday.get("date")])
    return out(item)


def brief_thread_for(session_id, days=7):
    """최근 브리핑에서 이 세션을 가진 스레드를 찾는다(있으면 멈춘 곳 등을 덧붙이기 위해)"""
    for path in sorted(BRIEF_DIR.glob("*.json"), reverse=True)[:days]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for t in (data.get("yesterday") or {}).get("threads") or []:
            ids = [s.get("session_id") for s in t.get("sessions") or []]
            if session_id in ids or session_id in (t.get("resume") or ""):
                return t, path.stem
    return None, None


def cmd_session(session_id):
    files = list(PROJECTS_DIR.glob(f"*/{session_id}.jsonl"))
    if not files:
        return fail(f"세션 파일을 찾지 못함: {session_id}")
    mtime = datetime.fromtimestamp(max(f.stat().st_mtime for f in files), KST)
    days = [(mtime - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    item = base("session")
    thread, brief_date = brief_thread_for(session_id)
    if thread:
        merge_fields(item, thread)
        item["brief"] = {"date": brief_date, "id": thread.get("id")}
    item["session"], item["session_error"] = find_session(session_id, days)
    if item["session"]:
        item.setdefault("title", item["session"]["title"])
        item.setdefault("cwd", item["session"]["cwd"])
    if not item["session"] and not thread:
        return out({**item, "error": item["session_error"]}, 1)
    return out(item)


def cmd_search(query, days):
    q = query.casefold()
    today = datetime.now(KST)
    found = {}
    for i in range(days):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        for s in sessions_on(day):
            sid = s.get("session_id")
            matched = []
            if q in str(s.get("title") or "").casefold():
                matched.append("title")
            if any(q in str(m).casefold() for m in s.get("user_messages") or []):
                matched.append("user_messages")
            if q in str(s.get("last_assistant") or "").casefold():
                matched.append("last_assistant")
            if not matched or not sid:
                continue
            prev = found.get(sid)
            if prev and (prev["ended_at"] or "") >= (s.get("ended_at") or ""):
                continue
            msgs = s.get("user_messages") or []
            found[sid] = {
                "session_id": sid, "title": s.get("title"), "cwd": s.get("cwd"), "ended_at": s.get("ended_at"),
                "matched_in": matched, "first_message": clip(msgs[0])[:160] if msgs else None,
                "_score": (2 if "title" in matched else 0) + len(matched),
            }
    ranked = sorted(found.values(), key=lambda c: (c["_score"], c["ended_at"] or ""), reverse=True)[:3]
    for c in ranked:
        c.pop("_score")
    if not ranked:
        return out({"query": query, "days": days, "candidates": [], "error": f"최근 {days}일 세션에서 '{query}'를 찾지 못함"}, 1)
    return out({"query": query, "days": days, "candidates": ranked, "error": None})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief"); b.add_argument("--date", required=True); b.add_argument("--id", required=True)
    s = sub.add_parser("session"); s.add_argument("--id", required=True)
    k = sub.add_parser("search"); k.add_argument("--query", required=True); k.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    if args.cmd == "search" and re.search(r"notion\.(so|site)", args.query):
        return fail("Notion 링크 재개는 지원하지 않습니다. 브리핑 항목, 세션 id, 키워드로 불러 주세요")
    if args.cmd == "brief":
        return cmd_brief(args.date, args.id)
    if args.cmd == "session":
        return cmd_session(args.id)
    return cmd_search(args.query, args.days)


if __name__ == "__main__":
    sys.exit(main())
