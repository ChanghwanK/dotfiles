#!/usr/bin/env python3
"""
work:tracking 하루 기록 JSON을 가로 트리 HTML 페이지로 렌더한다.

사용법:
  python3 render.py --data <YYYY-MM-DD.json> [--out <file.html>]

- 스타일: ../assets/tree.css (확정 디자인, 단일 라이트 테마)
- 기본 출력: ~/.claude/work-tracking/<date>.html
- 출력: {"path": "<html 경로>", "date": "<날짜>"} JSON 한 줄
- 스키마: ../assets/example.json (2026-11-24 실제 기록)
"""

import argparse
import html
import json
import sys
from pathlib import Path

E = html.escape
SKILL_DIR = Path(__file__).resolve().parent.parent
CSS_PATH = SKILL_DIR / "assets" / "tree.css"
STORE = Path.home() / ".claude" / "work-tracking"

SECTIONS = [  # (번호, trees 키, 섹션 제목)
    ("1", "done", "무엇을 했나"),
    ("2", "next", "이어서 할 일"),
    ("3", "thoughts", "어떤 고민을 했나"),
    ("4", "hard", "어떤 어려움이 있었나"),
]
CHIP_KINDS = {"g", "y", "r", "z", "d", "i"}
CARRY_LABEL = {"done": "완료", "carried": "이월", "dropped": "중단"}
FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
             '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700'
             '&display=swap&family=IBM+Plex+Mono:wght@500">')


def fail(msg: str) -> None:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    sys.exit(1)


def chip(c) -> str:
    if not c:
        return ""
    kind = c.get("kind")
    if kind not in CHIP_KINDS:
        fail(f"알 수 없는 chip.kind: {kind}")
    return f'<span class="chip c-{kind}">{E(c.get("text", ""))}</span>'


def carry_chip(node: dict, date: str) -> str:
    """이월 항목(since가 오늘보다 앞섬)에 'N일째' 칩을 붙인다"""
    since = node.get("since")
    if not since or since >= date:
        return ""
    from datetime import date as d
    days = (d.fromisoformat(date) - d.fromisoformat(since)).days + 1
    return f'<span class="chip c-c">이월 {days}일째</span>'


def node_html(n: dict, lv: int, date: str) -> str:
    head = f'<span class="nm">{E(n["name"])}</span>{carry_chip(n, date)}{chip(n.get("chip"))}'
    sub, detail = n.get("sub"), n.get("detail") or []
    if lv == 1 or not (sub or detail):
        s = f'<div class="n l{lv}"><div class="nh">{head}</div></div>'
    else:
        subl = f'<span class="sb">{E(sub)}</span>' if sub else ""
        body = ('<ul class="dl">' + "".join(f"<li>{E(x)}</li>" for x in detail) + "</ul>") if detail else ""
        s = (f'<details class="n l{lv}"><summary><span class="nh">{head}'
             f'<span class="mk" aria-hidden="true"></span></span>{subl}</summary>'
             f'<div class="dt">{body}</div></details>')
    kids = n.get("kids") or []
    if kids:
        if lv >= 4:
            fail(f"트리 깊이는 4단계까지입니다: {n['name']}")
        s += '<ul class="br">' + "".join(f"<li>{node_html(k, lv + 1, date)}</li>" for k in kids) + "</ul>"
    return s


def tree_html(num: str, title: str, tree: dict, date: str) -> str:
    root = {"name": tree["root"], "kids": tree["groups"]}
    return (f'<section class="sec" id="s{num}"><div class="sh"><span class="no">{num}</span><h2>{E(title)}</h2></div>'
            f'<p class="cap">{E(tree.get("caption", ""))}</p><div class="scroll"><div class="tree">'
            f'<ul class="top br"><li>{node_html(root, 1, date)}</li></ul></div></div></section>')


def overview_html(d: dict) -> str:
    meta = " · ".join(f'{s["label"]} {s["value"]}' for s in d.get("stats", []))
    carry = ""
    co = d.get("carryover") or []
    if co:
        cnt = {}
        for c in co:
            cnt[c["status"]] = cnt.get(c["status"], 0) + 1
        parts = " · ".join(f"{CARRY_LABEL[k]} {cnt[k]}" for k in ("done", "carried", "dropped") if k in cnt)
        carry = f'<p class="ov-meta">지난 기록의 이어서 할 일 {len(co)}건: {E(parts)}</p>'
    pr_ = d.get("plan_review") or []
    if pr_:
        done = sum(1 for x in pr_ if x.get("status") == "done")
        carry += f'<p class="ov-meta">아침에 고른 할 일 {len(pr_)}건: 완료 {done} · 미완료 {len(pr_) - done}</p>'
    rows = "".join(
        f'<div class="ov-row"><h3><a href="#s{r["n"]}"><span class="ovn">{r["n"]}</span>{E(r["title"])}</a></h3>'
        f'<p>{E(r["text"])}</p></div>' for r in d["overview"])
    return (f'<section class="ov" aria-labelledby="ov-h"><h2 id="ov-h">Overview</h2>'
            f'<p class="ov-lead">{E(d["lead"])}</p><p class="ov-meta">{E(meta)}</p>{carry}'
            f'<div class="ov-grid">{rows}</div></section>')


def toc_html(d: dict, has_prs: bool) -> str:
    s = '<nav class="toc" aria-label="목차"><p class="toc-t">목차</p><ol>'
    for num, key, title in SECTIONS:
        names = " · ".join(g["name"] for g in d["trees"][key]["groups"])
        s += (f'<li><a href="#s{num}"><span class="tn">{num}</span><span class="tl"><b>{E(title)}</b>'
              f'<small>{E(names)}</small></span></a></li>')
    if has_prs:
        s += (f'<li><a href="#s5"><span class="tn">5</span><span class="tl"><b>PR 목록</b>'
              f'<small>머지 {len(d["prs"])}건, 링크 포함</small></span></a></li>')
    return s + "</ol></nav>"


def prs_html(d: dict) -> str:
    prs = d.get("prs") or []
    if not prs:
        return ""
    groups = []
    for p in prs:
        if p["group"] not in groups:
            groups.append(p["group"])
    s = (f'<section class="sec prs" id="s5"><div class="sh"><span class="no">5</span><h2>PR 목록</h2></div>'
         f'<p class="cap">{E(d["date"])}에 머지한 PR {len(prs)}건입니다. 시각은 머지 시각(KST)입니다.</p>')
    for g in groups:
        s += f'<h3 class="prg">{E(g)}</h3><ul class="prl">'
        for p in (x for x in prs if x["group"] == g):
            short = p["repo"].split("/")[-1]
            s += (f'<li><a href="https://github.com/{E(p["repo"])}/pull/{int(p["number"])}">{E(short)} #{int(p["number"])}</a>'
                  f'<span class="prt">{E(p["title"])}</span><span class="prm">{E(p.get("merged_at", ""))}</span></li>')
        s += "</ul>"
    ob = d.get("open_branches") or []
    if ob:
        s += '<p class="prn">PR을 만들지 않은 브랜치: ' + ", ".join(f"<code>{E(b)}</code>" for b in ob) + "</p>"
    return s + "</section>"


def render(d: dict) -> str:
    for k in ("date", "weekday", "title", "lead", "overview", "trees"):
        if k not in d:
            fail(f"필수 키 누락: {k}")
    for _, key, _ in SECTIONS:
        if key not in d["trees"]:
            fail(f"trees.{key} 누락")
    date = d["date"]
    css = CSS_PATH.read_text()
    body = overview_html(d) + toc_html(d, bool(d.get("prs"))) + "".join(
        tree_html(num, title, d["trees"][key], date) for num, key, title in SECTIONS) + prs_html(d)
    span = f' · {E(d["span"])}' if d.get("span") else ""
    return f'''<title>{E(d["title"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
{FONT_LINK}
<style>
{css}</style>
<div class="wrap">
<header>
  <div><p class="eyebrow">{E(date)} ({E(d["weekday"])}){span}</p><h1>{E(d["title"])}</h1></div>
  <div class="legend">
    <span class="chip c-g">완료·결론</span><span class="chip c-y">진행·대기</span><span class="chip c-r">오늘</span><span class="chip c-z">날짜·미확인</span><span class="chip c-c">이월</span><span class="chip c-d">직접</span><span class="chip c-i">추론</span>
  </div>
</header>
<div class="tools"><button type="button" id="openAll">모두 펼치기</button><button type="button" id="closeAll">모두 접기</button></div>
<p class="hint">마디를 누르면 상세 내용이 펼쳐집니다.</p>
{body}
<footer>근거: {E(d.get("sources", ""))} 트리가 넓으면 좌우로 밀어서 봅니다.</footer>
</div>
<script>
document.getElementById('openAll').addEventListener('click',()=>document.querySelectorAll('details.n').forEach(d=>d.open=true));
document.getElementById('closeAll').addEventListener('click',()=>document.querySelectorAll('details.n').forEach(d=>d.open=false));
</script>'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="하루 기록 JSON")
    ap.add_argument("--out", help="출력 HTML 경로 (기본: ~/.claude/work-tracking/<date>.html)")
    a = ap.parse_args()
    try:
        d = json.loads(Path(a.data).expanduser().read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail(f"데이터를 읽지 못했습니다: {e}")
    page = render(d)
    if "—" in page:
        fail("em dash(U+2014)가 들어 있습니다. 콜론·쉼표·괄호로 바꾸십시오")
    out = Path(a.out).expanduser() if a.out else STORE / f'{d["date"]}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(json.dumps({"path": str(out), "date": d["date"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
