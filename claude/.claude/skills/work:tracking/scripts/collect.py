#!/usr/bin/env python3
"""
work:tracking 재료 수집. 하루치 세션 로그, 머지된 PR, 인계 문서, 지난 기록의 이어서 할 일을 한 JSON으로 모은다.

사용법:
  python3 collect.py [--date YYYY-MM-DD]   (기본: 오늘, KST)

- 세션: daily:start/scripts/extract-work.py --date D 를 그대로 호출한다(필드 변경 없음)
- PR: gh search prs --author @me --owner riiid, 그 날(KST) 머지된 것
- 인계 문서: ~/.claude/tmp/handoff-D-*.json 중 가장 늦은 것
- 이월 후보: ~/.claude/work-tracking/ 에서 D보다 앞선 가장 최근 기록의 trees.next 항목(id 있는 것)
- 출력 파일: ~/.claude/work-tracking/raw/<D>.json
- stdout: 파일 경로와 개수 요약 JSON 한 줄 (본문은 파일을 Read한다)
"""

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
HOME = Path.home()
EXTRACT = HOME / ".claude" / "skills" / "daily:start" / "scripts" / "extract-work.py"
STORE = HOME / ".claude" / "work-tracking"
HANDOFF_DIR = HOME / ".claude" / "tmp"
PR_OWNER = "riiid"


def run_json(cmd: list[str]):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if out.returncode != 0:
        return None, out.stderr.strip()[:300]
    try:
        return json.loads(out.stdout), None
    except json.JSONDecodeError as e:
        return None, f"JSON 파싱 실패: {e}"


def sessions(d: str):
    """D에 활동한 세션을 모은다.

    extract-work.py는 파일 수정일로 날짜를 정하므로, D에 시작해 다음 날 이어 쓴 세션은 D로 잡히지 않고
    오래된 세션을 다시 연 경우는 D로 잡힌다. 그래서 D부터 최대 7일 뒤까지 돌려 합친 뒤,
    started_at~ended_at 구간이 D와 겹치는 세션만 남긴다. 여러 날에 걸친 세션은 spans_days로 표시한다
    (user_messages에 다른 날 메시지가 섞여 있다).
    """
    today = datetime.now(KST).date()
    start = date.fromisoformat(d)
    seen, out, errs = set(), [], []
    for i in range(0, 8):
        day = start.fromordinal(start.toordinal() + i)
        if day > today:
            break
        data, err = run_json(["python3", str(EXTRACT), "--date", day.isoformat()])
        if err:
            errs.append(f"{day}: {err}")
        for s in (data or {}).get("sessions", []):
            sid = s.get("session_id")
            st, en = (s.get("started_at") or "")[:10], (s.get("ended_at") or "")[:10]
            if sid in seen or not st or not (st <= d <= (en or st)):
                continue
            seen.add(sid)
            s["spans_days"] = st != en
            out.append(s)
    out.sort(key=lambda s: s.get("started_at") or "")
    return out, "; ".join(errs) or None


def prs(d: str):
    rng = f"{d}T00:00:00+09:00..{d}T23:59:59+09:00"
    data, err = run_json(["gh", "search", "prs", "--author", "@me", "--owner", PR_OWNER, "--merged-at", rng,
                          "--json", "repository,number,title,closedAt,url", "--limit", "100"])
    items = []
    for p in data or []:
        merged = datetime.fromisoformat(p["closedAt"].replace("Z", "+00:00")).astimezone(KST)
        items.append({"repo": p["repository"]["nameWithOwner"], "number": p["number"], "title": p["title"],
                      "merged_at": merged.strftime("%H:%M"), "url": p["url"]})
    items.sort(key=lambda x: x["merged_at"])
    return items, err


def handoff(d: str):
    files = sorted(HANDOFF_DIR.glob(f"handoff-{d}-*.json"))
    if not files:
        return None
    try:
        h = json.loads(files[-1].read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return {"file": str(files[-1]), **{k: h.get(k) for k in ("timestamp", "completed", "in_progress", "next", "notes")}}


def carry_candidates(d: str):
    prev = sorted(p for p in STORE.glob("????-??-??.json") if p.stem < d)
    if not prev:
        return None, []
    rec = json.loads(prev[-1].read_text())
    found = []

    def walk(nodes, group):
        for n in nodes:
            if n.get("id"):
                found.append({"id": n["id"], "name": n["name"], "since": n.get("since", rec["date"]),
                              "group": group, "sub": n.get("sub"), "chip": n.get("chip")})
            walk(n.get("kids") or [], group)

    for g in rec.get("trees", {}).get("next", {}).get("groups", []):
        walk(g.get("kids") or [], g["name"])
    return {"date": rec["date"], "artifact_url": rec.get("artifact_url")}, found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(KST).date().isoformat())
    d = ap.parse_args().date
    try:
        date.fromisoformat(d)
    except ValueError:
        print(json.dumps({"error": f"날짜 형식이 아닙니다: {d}"}, ensure_ascii=False))
        return 1
    sess, s_err = sessions(d)
    pr_items, p_err = prs(d)
    prev, carry = carry_candidates(d)
    existing = STORE / f"{d}.json"
    out = {
        "date": d,
        "weekday": "월화수목금토일"[date.fromisoformat(d).weekday()],
        "existing_record": str(existing) if existing.exists() else None,
        "previous_record": prev,
        "carry_candidates": carry,
        "prs": pr_items,
        "handoff": handoff(d),
        "sessions": sess,
        "errors": {k: v for k, v in (("sessions", s_err), ("prs", p_err)) if v},
    }
    raw = STORE / "raw" / f"{d}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({"path": str(raw), "date": d, "sessions": len(sess), "prs": len(pr_items),
                      "carry_candidates": len(carry), "previous": prev and prev["date"],
                      "existing_record": out["existing_record"], "errors": out["errors"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
