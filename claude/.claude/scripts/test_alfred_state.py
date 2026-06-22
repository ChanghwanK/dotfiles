#!/usr/bin/env python3
"""alfred-state.py 회귀 테스트 (실제 state 파일 무손상 — temp 사용).

dedup·cap·최신순·current_task 미러·구 스키마 마이그레이션·TTL 필터를 보호한다.
실행: python3 test_alfred_state.py   (성공 시 exit 0)
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("st", os.path.join(_HERE, "alfred-state.py"))
m = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m)

_failures = []


def chk(desc, got, want):
    if got != want:
        _failures.append(f"{desc}: got={got!r} want={want!r}")


# ── upsert: dedup + cap + 최신순 + current_task 미러 ───────────
st = {"current_task": {}, "recent_tasks": []}
for i in range(7):
    st = m.upsert_recent(st, {"page_id": f"p{i}", "name": f"T{i}"}, max_recent=5)
chk("cap=5", len(st["recent_tasks"]), 5)
chk("최신이 맨앞", st["recent_tasks"][0]["page_id"], "p6")
chk("current_task 미러", st["current_task"]["page_id"], "p6")

st = m.upsert_recent(st, {"page_id": "p3", "name": "T3"}, max_recent=5)
ids = [t["page_id"] for t in st["recent_tasks"]]
chk("dedup(p3 1회만)", ids.count("p3"), 1)
chk("p3 맨앞 승격", ids[0], "p3")

# ── 구 스키마(current_task만) → recent_tasks 승격 ──────────────
_tmp = tempfile.mkdtemp()
_old = os.path.join(_tmp, "s.json")
json.dump({"current_task": {"page_id": "X", "name": "old", "started_at": "2026-06-22T14:00:00+09:00"}},
          open(_old, "w"))
loaded = m._load(_old)
chk("구스키마 migrate len", len(loaded["recent_tasks"]), 1)
chk("구스키마 migrate id", loaded["recent_tasks"][0]["page_id"], "X")

# ── record→get 라운드트립 + TTL 필터 ─────────────────────────
m.STATE_PATH = os.path.join(_tmp, "state.json")


class _Args:
    pass


a = _Args()
a.page_id, a.name, a.priority, a.source = "pp", "현재작업", "P1", "tui"
m.cmd_record(a)
data = json.load(open(m.STATE_PATH))
chk("record 후 current_task", data["current_task"]["page_id"], "pp")

# 오래된 항목은 get(TTL=8h)에서 제외
data["recent_tasks"].append({"page_id": "stale", "name": "옛날", "started_at": "2026-06-20T09:00:00+09:00"})
json.dump(data, open(m.STATE_PATH, "w"), ensure_ascii=False)
buf = io.StringIO()
g = _Args()
g.max_age_hours = 8
with contextlib.redirect_stdout(buf):
    m.cmd_get(g)
res = json.loads(buf.getvalue())
got_ids = {t["page_id"] for t in res["recent_tasks"]}
chk("TTL: 최신 포함", "pp" in got_ids, True)
chk("TTL: stale 제외", "stale" in got_ids, False)

if _failures:
    print("FAIL ✗")
    for f in _failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS ✓")
