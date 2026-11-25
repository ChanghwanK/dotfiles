#!/usr/bin/env python3
"""Tech Spec 실행 폴더 관리, 포맷 lint, HTML 렌더, 리뷰 집계.

  spec_tool.py init <slug> --title "<제목>"            실행 폴더 생성, 경로 출력
  spec_tool.py link-research <run_dir> <research_run>   research:deep 실행 폴더를 research/로 연결
  spec_tool.py lint <run_dir>                          spec.md 포맷 검사(H2 고정 다섯 개 등)
  spec_tool.py render <run_dir> [--round N]            spec.md → spec.html
  spec_tool.py snapshot <run_dir> --round N            spec.md → history/spec-rN.md
  spec_tool.py diff <run_dir> --round N                history/spec-r(N-1).md 대비 바뀐 섹션 출력
  spec_tool.py reviews <run_dir> --stage plan|spec --round N
                                                       리뷰 JSON에 id 부여, 심각도 집계, 미판정 id 출력

python-markdown(tables, fenced_code, md_in_html, toc, sane_lists)만 쓴다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
RUNS = Path.home() / ".claude" / "tech-spec-runs"
H2_FIXED = ["Background", "Goals & KeyResult", "설계 및 계획", "예상 질문 정리", "마일스톤"]
OBJECTIVE_RE = re.compile(r"^>\s*\[!objective\]\s*(.+)$", re.IGNORECASE)
SEVERITIES = ("blocker", "major", "minor")


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def run_path(p: str) -> Path:
    run = Path(p).expanduser().resolve()
    if not run.is_dir():
        sys.exit(f"run_dir not found: {run}")
    return run


def strip_code(text: str) -> list[tuple[int, str, bool]]:
    """(줄번호, 줄, 코드블록 안 여부) 목록."""
    rows, fence = [], None
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*(```|~~~)", line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif m.group(1) == fence:
                fence = None
            rows.append((i, line, True))
            continue
        rows.append((i, line, fence is not None))
    return rows


def sections(text: str) -> dict[str, str]:
    """H2/H3 제목 경로 → 본문. 'H2' 또는 'H2 > H3' 키."""
    result: dict[str, list[str]] = {}
    h2 = h3 = None
    for _, line, in_code in strip_code(text):
        if not in_code and line.startswith("## "):
            h2, h3 = line[3:].strip(), None
            result.setdefault(h2, [])
            continue
        if not in_code and line.startswith("### ") and h2:
            h3 = line[4:].strip()
            result.setdefault(f"{h2} > {h3}", [])
            continue
        key = f"{h2} > {h3}" if h3 else h2
        if key:
            result[key].append(line)
            if h3:
                result[h2].append(line)
    return {k: "\n".join(v).strip() for k, v in result.items()}


# ---------------------------------------------------------------- init

def cmd_init(a) -> int:
    run = RUNS / f"{dt.date.today().isoformat()}-{a.slug}"
    for sub in ("reviews", "history", "context"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    meta = run / "run.json"
    if not meta.exists():
        meta.write_text(json.dumps({"title": a.title, "slug": a.slug, "created": dt.datetime.now().isoformat(timespec="seconds"),
                                    "artifact_url": "", "research_run": "", "max_rounds": a.max_rounds},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    adj = run / "adjudication.md"
    if not adj.exists():
        adj.write_text("# 리뷰 판정 기록\n\n형식: `issue_id | 수용 / 기각 / 보류 | 근거 또는 반영 위치`\n\n", encoding="utf-8")
    print(run)
    return 0


def cmd_link_research(a) -> int:
    run = run_path(a.run_dir)
    target = Path(a.research_run).expanduser().resolve()
    if not target.is_dir():
        sys.exit(f"research run not found: {target}")
    link = run / "research"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    meta["research_run"] = str(target)
    (run / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    out({"linked": str(link), "target": str(target),
         "files": sorted(p.name for p in target.iterdir())[:40]})
    return 0


# ---------------------------------------------------------------- lint

def lint_text(text: str) -> dict:
    errors, warnings = [], []
    rows = strip_code(text)
    body = [(i, l) for i, l, c in rows if not c]
    h1 = [(i, l) for i, l in body if re.match(r"^# ", l)]
    h2 = [(i, l[3:].strip()) for i, l in body if l.startswith("## ")]
    obj = [(i, l) for i, l in body if OBJECTIVE_RE.match(l)]
    if len(h1) != 1:
        errors.append(f"H1은 정확히 1개여야 한다(현재 {len(h1)}개)")
    if len(obj) != 1:
        errors.append(f"Objective 콜아웃(`> [!objective] ...`)은 정확히 1개여야 한다(현재 {len(obj)}개)")
    elif h2 and obj[0][0] > h2[0][0]:
        errors.append("Objective 콜아웃은 첫 H2보다 앞에 있어야 한다")
    names = [n for _, n in h2]
    if names != H2_FIXED:
        errors.append(f"H2는 {H2_FIXED} 순서여야 한다. 현재 {names}")
    sec = sections(text)
    gk = sec.get("Goals & KeyResult", "")
    if "**Goal**" not in gk:
        errors.append("Goals & KeyResult에 `**Goal**` 불릿이 없다")
    if "**Key Result**" not in gk:
        errors.append("Goals & KeyResult에 `**Key Result**` 불릿이 없다")
    elif not re.search(r"^\s+- KR\d+\. ", gk, re.M):
        warnings.append("Key Result가 `KRn. ...` 헤드라인 형식이 아니다(task:keyresult)")
    todo_key = next((k for k in sec if k.startswith("설계 및 계획 > ") and k.endswith("Todo")), None)
    if not todo_key:
        errors.append("설계 및 계획에 `### Todo`가 없다")
    elif not re.search(r"^\s*- \[[ xX]\] ", sec[todo_key], re.M):
        errors.append("Todo에 체크박스(`- [ ] `)가 없다")
    design_h3 = [k for k in sec if k.startswith("설계 및 계획 > ") and not k.endswith("Todo")]
    if not design_h3:
        warnings.append("설계 및 계획에 Todo 외 주제별 H3가 없다")
    for name in ("예상 질문 정리", "마일스톤"):
        if not sec.get(name):
            warnings.append(f"{name} 섹션이 비어 있다")
    for i, l in body:
        if "—" in l:
            errors.append(f"{i}행: em dash(U+2014) 사용")
        m = re.match(r"^( +)(?:[-*+]|\d+\.) ", l)
        if m and len(m.group(1)) % 4:
            warnings.append(f"{i}행: 목록 들여쓰기가 4칸 배수가 아니다(렌더 시 중첩이 깨짐)")
    undecided = len(re.findall(r"\(미결정", "\n".join(l for _, l in body)))
    dec_key = next((k for k in sec if k.startswith("설계 및 계획 > ") and k.endswith("결정 필요")), None)
    if undecided and not dec_key:
        errors.append(f"본문에 `(미결정` 표시가 {undecided}개 있는데 설계 및 계획에 `### 결정 필요` 표가 없다")
    dec_rows = 0
    if dec_key:
        dec_rows = max(0, len([l for l in sec[dec_key].splitlines() if l.startswith("|")]) - 2)
        if not dec_rows:
            errors.append("`### 결정 필요`에 표 행이 없다")
        head = next((l for l in sec[dec_key].splitlines() if l.startswith("|")), "")
        if [c.strip() for c in head.strip().strip("|").split("|")] != DECISION_COLS:
            errors.append(f"`### 결정 필요` 표 머리글은 {DECISION_COLS}여야 한다")
        for l in sec[dec_key].splitlines():
            if re.match(r"^\|\s*\d+\s*\|", l):
                c = [x.strip() for x in l.strip().strip("|").split("|")]
                if len(c) > 2 and c[2] not in ("필수", "필수 아님"):
                    errors.append(f"결정 {c[0]}번의 필수 칸은 `필수` 또는 `필수 아님`이어야 한다(현재 `{c[2]}`)")
        nums = {l.split("|")[1].strip() for l in sec[dec_key].splitlines() if re.match(r"^\|\s*\d+\s*\|", l)}
        explained = set(re.findall(r"<summary>\s*(\d+)\.", sec[dec_key]))
        if nums - explained:
            warnings.append(f"`### 결정 필요` 항목 {sorted(nums - explained, key=int)}에 상세 설명(`<details>`의 `<summary>N. ...`)이 없다")
    opens = sum(l.count("<details") for _, l in body)
    closes = sum(l.count("</details>") for _, l in body)
    if opens != closes:
        errors.append(f"<details> 열림 {opens}개, 닫힘 {closes}개가 맞지 않는다")
    stats = {
        "h3": [k.split(" > ", 1)[1] for k in sec if " > " in k],
        "todo_items": len(re.findall(r"^\s*- \[[ xX]\] ", sec.get(todo_key or "", ""), re.M)),
        "undecided_marks": undecided,
        "decision_rows": dec_rows,
        "unconfirmed_cause": len(re.findall(r"\(원인 미확인\)", text)),
        "chars": len(text),
    }
    return {"ok": not errors, "errors": errors, "warnings": warnings, "stats": stats}


def cmd_lint(a) -> int:
    run = run_path(a.run_dir)
    spec = run / "spec.md"
    if not spec.exists():
        sys.exit("spec.md not found")
    res = lint_text(spec.read_text(encoding="utf-8"))
    out(res)
    return 0 if res["ok"] else 1


# ---------------------------------------------------------------- render

def review_meta(run: Path, rnd: int | None) -> str:
    chips = []
    if rnd:
        chips.append(f'<span class="chip gray">라운드 {rnd} 리뷰 반영</span>')
        counts = {s: 0 for s in SEVERITIES}
        adj = adjudicated_ids(run)
        rejected = adj["기각"] | adj["보류"]
        for f in (run / "reviews").glob(f"*-spec-r{rnd}.json"):
            for it in json.loads(f.read_text(encoding="utf-8")).get("issues", []):
                if it.get("id") not in rejected and it.get("severity") in counts:
                    counts[it["severity"]] += 1
        if any(counts.values()) or list((run / "reviews").glob(f"*-spec-r{rnd}.json")):
            chips.append(f'<span class="chip {"red" if counts["blocker"] else "green"}">blocker {counts["blocker"]}</span>')
            chips.append(f'<span class="chip {"yellow" if counts["major"] else "green"}">major {counts["major"]}</span>')
            chips.append(f'<span class="chip gray">minor {counts["minor"]}</span>')
        else:
            chips.append('<span class="chip yellow">리뷰 전</span>')
    else:
        chips.append('<span class="chip yellow">리뷰 전</span>')
    chips.insert(0, f"<span>{dt.date.today().isoformat()}</span>")
    return "\n    ".join(chips)


def render_markdown(md_text: str) -> tuple[str, str]:
    import markdown  # noqa: PLC0415
    md = markdown.Markdown(extensions=["tables", "fenced_code", "md_in_html", "sane_lists", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-3", "slugify": slug_ko}})
    body = md.convert(md_text)
    toc_html = md.toc  # type: ignore[attr-defined]
    toc_html = re.sub(r'^<div class="toc">\s*|\s*</div>\s*$', "", toc_html.strip())
    toc_html = toc_html.replace("<ul>", "<ol>").replace("</ul>", "</ol>")

    def task(m: re.Match) -> str:
        checked = " checked" if m.group(2).lower() == "x" else ""
        return f'<li class="task">{m.group(1) or ""}<input type="checkbox" disabled{checked} aria-label="할 일">'

    body = re.sub(r"<li>(<p>)?\[([ xX])\]\s?", task, body)
    # mermaid 펜스는 Artifact가 기본 렌더하는 <pre class="mermaid">로 바꾼다
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  lambda m: f'<div class="diagram"><pre class="mermaid">{m.group(1)}</pre></div>', body, flags=re.S)
    # 근거 표기 [@c123] → 작은 위첨자 칩
    body = re.sub(r"\[@(c\d{3})\]", r'<sup class="cite" title="research claim \1">\1</sup>', body)
    body = re.sub(r"<table>", '<div class="table-wrap"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)

    def widen(m: re.Match) -> str:  # 열이 4개 이상인 표는 본문 폭보다 넓게 편다
        head = re.search(r"<tr>(.*?)</tr>", m.group(0), flags=re.S)
        cols = len(re.findall(r"<th[ >]", head.group(1))) if head else 0
        return m.group(0).replace('<div class="table-wrap">', f'<div class="table-wrap wide cols-{cols}">', 1) if cols >= 4 else m.group(0)

    body = re.sub(r'<div class="table-wrap"><table>.*?</table></div>', widen, body, flags=re.S)
    body = mark_decisions(body)
    return body, toc_html


DECISION_ID = "결정-필요"
DECISION_COLS = ["#", "결정", "필수", "선택지", "추천", "판단 기준"]


def mark_decisions(body: str) -> str:
    """`### 결정 필요` 표를 강조 표로 바꾸고, 본문의 `(미결정` 표시를 노란 표시로 바꾼다(코드 블록 제외)."""
    # 제목과 표 사이에 정의 문단이 올 수 있다. 다음 제목(h2/h3)을 넘어가지 않는다
    body = re.sub(rf'<h3 id="{DECISION_ID}">([^<]*)</h3>((?:(?!<h[23][ >]).)*?)<div class="table-wrap([^"]*)">',
                  rf'<h3 id="{DECISION_ID}" class="decide-h">\1</h3>\2<div class="table-wrap\3 decide-table">', body, count=1, flags=re.S)
    def chips(m: re.Match) -> str:  # 필수 열 값을 칩으로
        t = m.group(0)
        t = t.replace("<td>필수 아님</td>", '<td><span class="chip gray">필수 아님</span></td>')
        return t.replace("<td>필수</td>", '<td><span class="chip red">필수</span></td>')

    body = re.sub(r'<div class="table-wrap[^"]* decide-table"><table>.*?</table>', chips, body, flags=re.S)
    body = attach_decision_details(body)
    parts = re.split(r"(<pre.*?</pre>|<code>.*?</code>)", body, flags=re.S)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("(미결정", '(<mark class="undecided">미결정</mark>')
    return "".join(parts)


def attach_decision_details(body: str) -> str:
    """표 뒤의 `<details><summary>N. ...</summary>` 설명을 해당 행 아래 펼침 행으로 옮기고 '상세 보기' 버튼을 단다."""
    m = re.search(r'(<div class="table-wrap[^"]* decide-table"><table>)(.*?)(</table></div>)', body, flags=re.S)
    if not m:
        return body
    nxt = re.search(r"<h[23][ >]", body[m.end():])
    tail_end = m.end() + (nxt.start() if nxt else len(body) - m.end())
    tail = body[m.end():tail_end]
    details = {}

    def grab(d: re.Match) -> str:
        details[d.group(1)] = d.group(2).strip()
        return ""

    tail = re.sub(r"<details[^>]*>\s*<summary>\s*(\d+)\.[^<]*</summary>(.*?)</details>", grab, tail, flags=re.S)
    if not details:
        return body
    table = m.group(2)
    cols = len(re.findall(r"<th[ >]", table.split("</tr>", 1)[0]))

    def row(r: re.Match) -> str:
        tr = r.group(0)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)
        n = re.sub(r"<[^>]+>", "", cells[0]).strip() if cells else ""
        if n not in details:
            return tr
        did = f"dd-{n}"
        btn = f'<button type="button" class="detail-btn" aria-expanded="false" aria-controls="{did}">상세 보기</button>'
        tds = list(re.finditer(r"<td[^>]*>(.*?)</td>", tr, flags=re.S))
        if len(tds) >= 2:
            t2 = tds[1]
            tr = tr[:t2.end() - 5] + btn + tr[t2.end() - 5:]
        return tr + f'\n<tr class="decide-detail" id="{did}" hidden><td colspan="{cols}"><div class="detail-body">{details[n]}</div></td></tr>'

    table = re.sub(r"<tr>(?:(?!</tr>).)*<td.*?</tr>", row, table, flags=re.S)
    tools = '<div class="decide-tools"><button type="button" class="detail-all" aria-expanded="false">상세 모두 펼치기</button></div>\n'
    return (body[:m.start()] + tools + m.group(1) + table + m.group(3) + tail + body[tail_end:])


def decision_banner(body: str) -> str:
    m = re.search(r'<div class="table-wrap[^"]* decide-table"><table>(.*?)</table>', body, flags=re.S)
    if not m:
        return ""
    rows = re.findall(r"<tr>(.*?)</tr>", m.group(1), flags=re.S)
    if len(rows) < 2:
        return ""
    head = [re.sub(r"<[^>]+>", "", h).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", rows[0], flags=re.S)]
    ni = head.index("결정") if "결정" in head else 1
    ri = head.index("필수") if "필수" in head else None
    hi = head.index("#") if "#" in head else None
    must, opt = [], []
    for r in rows[1:]:
        # '상세 보기' 버튼 글자가 결정 이름에 붙지 않도록 버튼을 먼저 지운다
        raw = [re.sub(r"<button.*?</button>", "", x, flags=re.S) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
        cells = [re.sub(r"<[^>]+>", "", x).strip() for x in raw]
        if len(cells) <= ni:
            continue
        name = html.escape(html.unescape(cells[ni]))
        num = html.escape(cells[hi]) if hi is not None and len(cells) > hi else ""
        (opt if ri is not None and len(cells) > ri and cells[ri] == "필수 아님" else must).append((num, name))
    if not must and not opt:
        return ""
    total = len(must) + len(opt)
    split = f'<span class="chip red">필수 {len(must)}</span> <span class="chip gray">필수 아님 {len(opt)}</span>' if ri is not None else ""

    def group(items: list, chip: str) -> str:
        if not items:
            return ""
        lis = "".join((f'<li><span class="decide-num">{n}</span>' if n else "<li>") + f'<span class="decide-name">{x}</span></li>'
                      for n, x in items)
        return f'<div class="decide-group">{chip}<ul>{lis}</ul></div>'

    groups = (group(must, '<span class="chip red">필수</span>' if ri is not None else "")
              + group(opt, '<span class="chip gray">필수 아님</span>'))
    return (f'<a class="decide-banner" href="#{DECISION_ID}"><span class="decide-count">결정 필요 {total}건</span>{split}'
            f'<span class="decide-hint">눌러서 표로 이동</span>{groups}</a>')


def slug_ko(value: str, separator: str) -> str:
    value = re.sub(r"[^\w\s가-힣-]", "", value).strip().lower()
    return re.sub(r"[\s]+", separator, value) or "section"


def embed_images(body: str, run: Path) -> tuple[str, int, list[str]]:
    """로컬 이미지 경로를 data URI로 바꾼다(Artifact는 로컬 파일을 못 읽는다)."""
    import base64  # noqa: PLC0415
    import mimetypes  # noqa: PLC0415
    embedded, missing = 0, []

    def repl(m: re.Match) -> str:
        nonlocal embedded
        src = html.unescape(m.group(1))
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        path = Path(src).expanduser()
        if not path.is_absolute():
            path = run / path
        if not path.is_file():
            missing.append(src)
            return m.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        embedded += 1
        return f'src="data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"'

    body = re.sub(r'src="([^"]+)"', repl, body)
    return body, embedded, missing


def cmd_render(a) -> int:
    run = run_path(a.run_dir)
    src = run / (a.src or "spec.md")
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    title, objective, keep = "Tech Spec", "", []
    for line in lines:
        if line.startswith("# ") and title == "Tech Spec":
            title = line[2:].strip()
            continue
        m = OBJECTIVE_RE.match(line)
        if m and not objective:
            objective = m.group(1).strip()
            continue
        keep.append(line)
    body, toc = render_markdown("\n".join(keep))
    body, embedded, missing = embed_images(body, run)
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    footer = f"tasks:tech-spec · 실행 폴더 {html.escape(run.name)}"
    if meta.get("research_run"):
        footer += f" · 리서치 {html.escape(Path(meta['research_run']).name)}"
    tmpl = (SKILL / "assets" / "spec.html.tmpl").read_text(encoding="utf-8")
    if not objective:
        tmpl = re.sub(r'\s*<div class="objective">.*?</div>', "", tmpl, count=1, flags=re.S)
    meta_html = review_meta(run, a.round)
    if a.label:
        meta_html = f'<span class="chip yellow">{html.escape(a.label)}</span>\n    ' + meta_html
    page = (tmpl.replace("{{TITLE}}", html.escape(title)).replace("{{OBJECTIVE}}", html.escape(objective))
            .replace("{{META}}", meta_html).replace("{{TOC}}", toc).replace("{{DECISIONS}}", decision_banner(body))
            .replace("{{BODY}}", body).replace("{{FOOTER}}", footer))
    dest = run / (a.out or "spec.html")
    dest.write_text(page, encoding="utf-8")
    is_spec = bool(objective)  # 브리핑처럼 Objective가 없는 문서는 스펙 전용 검사를 건너뛴다
    structure = check_html_structure(page, text if is_spec else "", is_spec)
    out({"html": str(dest), "bytes": dest.stat().st_size, "title": title, "objective": bool(objective),
         "images_embedded": embedded, "images_missing": missing, "structure": structure})
    return 0 if structure["ok"] else 1


def check_html_structure(page: str, md_text: str, is_spec: bool) -> dict:
    """HTML 정본 구조(spec-format.md "HTML 출력 구조")를 검사한다. 템플릿이나 렌더가 바뀌어 구조가 깨지면 잡는다."""
    errors = []
    if "{{" in page:
        errors.append("치환되지 않은 템플릿 자리표시자가 남았다")
    if "max-width: none" not in page:
        errors.append("전체 폭 레이아웃(.page max-width: none)이 아니다")
    order = ["<h1>", '<nav class="toc"', '<article class="doc">', "<footer>"]
    if is_spec:
        order.insert(1, '<div class="objective">')
    pos = [page.find(t) for t in order]
    if any(x < 0 for x in pos):
        errors.append(f"필수 블록이 없다: {[t for t, x in zip(order, pos) if x < 0]}")
    elif pos != sorted(pos):
        errors.append("블록 순서가 H1 → Objective → 목차 → 본문 → footer가 아니다")
    toc = re.search(r'<nav class="toc".*?</nav>', page, flags=re.S)
    toc_links = len(re.findall(r"<a href=", toc.group(0))) if toc else 0
    if toc_links < 3:
        errors.append(f"목차 링크가 {toc_links}개뿐이다")
    stats = {"toc_links": toc_links}
    if is_spec:
        missing_h2 = [h for h in H2_FIXED if f">{html.escape(h)}</a>" not in (toc.group(0) if toc else "")]
        if missing_h2:
            errors.append(f"목차에 고정 H2가 빠졌다: {missing_h2}")
        sec = sections(md_text)
        dec_key = next((k for k in sec if k.startswith("설계 및 계획 > ") and k.endswith("결정 필요")), None)
        if dec_key:
            rows = [l for l in sec[dec_key].splitlines() if re.match(r"^\|\s*\d+\s*\|", l)]
            details = len(re.findall(r'<tr class="decide-detail"', page))
            buttons = len(re.findall(r'class="detail-btn"', page))
            stats.update({"decision_rows": len(rows), "detail_rows": details})
            banner = page.find('<a class="decide-banner"')
            if banner < 0:
                errors.append("결정 필요 배너가 없다")
            elif not (page.find('<nav class="toc"') < banner < page.find('<article class="doc">')):
                errors.append("결정 필요 배너가 목차와 본문 사이에 있지 않다")
            if "decide-table" not in page.split("</style>", 1)[-1]:
                errors.append("결정 필요 표가 강조 표(decide-table)로 렌더되지 않았다")
            if details != len(rows) or buttons != len(rows):
                errors.append(f"결정 {len(rows)}건 중 상세 보기 행 {details}개, 버튼 {buttons}개다(항목마다 <details><summary>N. ...</summary> 필요)")
            if details and "detail-btn" not in page.split("<script>", 1)[-1]:
                errors.append("상세 보기 토글 스크립트가 없다")
            if any("| 필수 |" in l for l in rows) and 'chip red">필수<' not in page:
                errors.append("필수 칩이 렌더되지 않았다")
    return {"ok": not errors, "errors": errors, "stats": stats}


# ---------------------------------------------------------------- snapshot / diff

def cmd_snapshot(a) -> int:
    run = run_path(a.run_dir)
    if a.plan:
        dest = run / "history" / f"plan-v{a.round}.md"
        shutil.copyfile(run / "plan.md", dest)
    else:
        dest = run / "history" / f"spec-r{a.round}.md"
        shutil.copyfile(run / "spec.md", dest)
    print(dest)
    return 0


def cmd_diff(a) -> int:
    run = run_path(a.run_dir)
    prev = run / "history" / f"spec-r{a.round - 1}.md"
    if not prev.exists():
        sys.exit(f"{prev.name} not found")
    old, new = sections(prev.read_text(encoding="utf-8")), sections((run / "spec.md").read_text(encoding="utf-8"))
    changed = [k for k in new if old.get(k) != new[k] and " > " in k or (k not in old)]
    # H2 단위 변경은 H3가 없는 H2(예상 질문 정리, 마일스톤 등)만 따로 본다
    for k in new:
        if " > " not in k and not any(x.startswith(k + " > ") for x in new) and old.get(k) != new[k] and k not in changed:
            changed.append(k)
    removed = [k for k in old if k not in new]
    out({"changed": changed, "removed": removed})
    for k in changed:
        print(f"\n----- {k}\n{new[k]}")
    return 0


# ---------------------------------------------------------------- reviews

def adjudicated_ids(run: Path) -> dict[str, set[str]]:
    res: dict[str, set[str]] = {"수용": set(), "기각": set(), "보류": set()}
    adj = run / "adjudication.md"
    if adj.exists():
        for line in adj.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*-?\s*`?([\w-]+-r\d+-\d+)`?\s*\|\s*(수용|기각|보류)", line)
            if m:
                res[m.group(2)].add(m.group(1))
    return res


def cross_check_summary(run: Path, files: list[Path], stage: str, rnd: int) -> dict:
    """reviews/xcheck/<검토자>-<stage>-rN.json: 다른 리뷰어의 blocker·major 지적을 valid/partial/invalid로 본 결과."""
    targets = {}
    for f in files:
        try:
            for it in json.loads(f.read_text(encoding="utf-8")).get("issues", []):
                if it.get("severity") in ("blocker", "major") and it.get("id"):
                    targets[it["id"]] = f.name.split("-", 1)[0]
        except json.JSONDecodeError:
            continue
    verdicts: dict[str, dict] = {}
    for f in sorted((run / "reviews" / "xcheck").glob(f"*-{stage}-r{rnd}.json")):
        checker = f.name.split("-", 1)[0]
        try:
            for it in json.loads(f.read_text(encoding="utf-8")).get("assessments", []):
                verdicts[it.get("id", "")] = {"by": checker, "verdict": it.get("verdict"), "reason": it.get("reason", ""),
                                              "corrected_fix": it.get("corrected_fix", "")}
        except json.JSONDecodeError:
            continue
    if not verdicts:
        return {"done": False, "targets": len(targets)}
    count = {"valid": 0, "partial": 0, "invalid": 0}
    for v in verdicts.values():
        count[v["verdict"]] = count.get(v["verdict"], 0) + 1
    return {"done": True, "targets": len(targets), "assessed": len(verdicts), "by_verdict": count,
            "disputed": {k: v for k, v in verdicts.items() if v["verdict"] in ("partial", "invalid")},
            "not_assessed": sorted(k for k in targets if k not in verdicts)}


def duplicate_candidates(files: list[Path]) -> list[list[str]]:
    """서로 다른 리뷰어가 같은 섹션에서 같은 원문·문제를 짚은 지적 쌍(판정을 한 번에 하기 위한 후보)."""
    items = []
    for f in files:
        try:
            for it in json.loads(f.read_text(encoding="utf-8")).get("issues", []):
                words = set(re.findall(r"[\w가-힣]{2,}", f"{it.get('quote', '')} {it.get('problem', '')}"))
                items.append((f.name.split("-", 1)[0], it.get("id", ""), it.get("section", "").split(" > ")[0], words))
        except json.JSONDecodeError:
            continue
    pairs = []
    for i, (r1, id1, s1, w1) in enumerate(items):
        for r2, id2, s2, w2 in items[i + 1:]:
            if r1 != r2 and s1 == s2 and w1 and w2 and len(w1 & w2) / min(len(w1), len(w2)) >= 0.35:
                pairs.append([id1, id2])
    return pairs


def cmd_reviews(a) -> int:
    run = run_path(a.run_dir)
    files = sorted((run / "reviews").glob(f"*-{a.stage}-r{a.round}.json"))
    if not files:
        sys.exit(f"no reviews/*-{a.stage}-r{a.round}.json")
    adj = adjudicated_ids(run)
    decided = set().union(*adj.values())
    table, undecided, questions = [], [], []
    for f in files:
        reviewer = f.name.split("-", 1)[0]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            table.append({"reviewer": reviewer, "error": f"invalid json: {e}"})
            continue
        changed = False
        for k, it in enumerate(data.get("issues", []), 1):
            if not it.get("id"):
                it["id"] = f"{reviewer}-{a.stage}-r{a.round}-{k:02d}"
                changed = True
        if changed:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        counts = {s: 0 for s in SEVERITIES}
        open_counts = {s: 0 for s in SEVERITIES}
        for it in data.get("issues", []):
            sev = it.get("severity", "minor")
            counts[sev] = counts.get(sev, 0) + 1
            if it["id"] not in adj["기각"] | adj["보류"]:
                open_counts[sev] = open_counts.get(sev, 0) + 1
            if it["id"] not in decided:
                undecided.append(it["id"])
        questions += data.get("expected_questions", [])
        table.append({"reviewer": reviewer, "verdict": data.get("verdict"), "counts": counts,
                      "open_after_adjudication": open_counts, "summary": data.get("summary", "")})
    open_bm = sum(r.get("open_after_adjudication", {}).get("blocker", 0) + r.get("open_after_adjudication", {}).get("major", 0)
                  for r in table)
    out({"stage": a.stage, "round": a.round, "reviewers": table, "undecided_ids": undecided,
         "likely_duplicates": duplicate_candidates(files),
         "cross_check": cross_check_summary(run, files, a.stage, a.round),
         "expected_questions": questions, "open_blocker_major": open_bm,
         "converged": open_bm == 0 and not any("error" in r for r in table)})
    return 0


# ---------------------------------------------------------------- briefing

def adjudication_rows(run: Path) -> dict[str, tuple[str, str]]:
    rows = {}
    adj = run / "adjudication.md"
    if adj.exists():
        for line in adj.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*-?\s*`?([\w-]+-r\d+-\d+)`?\s*\|\s*(수용|기각|보류)\s*\|\s*(.*)$", line)
            if m:
                rows[m.group(1)] = (m.group(2), m.group(3).strip())
    return rows


def section_changes(old_text: str, new_text: str) -> list[str]:
    import difflib  # noqa: PLC0415
    old, new = sections(old_text), sections(new_text)
    out_rows = []
    keys = list(dict.fromkeys(list(old) + list(new)))
    for k in keys:
        if " > " not in k and any(x.startswith(k + " > ") for x in keys):
            continue  # H3가 있는 H2는 H3 단위로만 본다
        a_, b_ = old.get(k, ""), new.get(k, "")
        if a_ == b_:
            continue
        diff = list(difflib.unified_diff(a_.splitlines(), b_.splitlines(), lineterm="", n=0))
        plus = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        minus = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        state = "신설" if k not in old else ("삭제" if k not in new else "수정")
        out_rows.append(f"| {k} | {state} | +{plus} / -{minus} |")
    return out_rows


def cmd_briefing(a) -> int:
    run = run_path(a.run_dir)
    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    adj = adjudication_rows(run)
    hist = run / "history"
    plans = sorted(hist.glob("plan-v*.md"), key=lambda p: int(re.search(r"v(\d+)", p.name).group(1)))
    specs = sorted(hist.glob("spec-r*.md"), key=lambda p: int(re.search(r"r(\d+)", p.name).group(1)))
    lines = [f"# 리뷰 흐름 브리핑: {meta.get('title', '')}", "",
             "## 흐름", ""]
    flow = ["자료 수집(research:deep, codex 교차 수집, 사내 조사)"]
    for stage, versions in (("plan", plans), ("spec", specs)):
        rounds = sorted({int(m.group(1)) for f in (run / "reviews").glob(f"*-{stage}-r*.json")
                         if (m := re.search(r"-r(\d+)\.json$", f.name))})
        label = "1차 계획" if stage == "plan" else "Tech Spec"
        for i, v in enumerate(versions, 1):
            flow.append(f"{label} {v.stem.split('-')[1]}")
            if i <= len(rounds):
                revs = sorted({f.name.split("-", 1)[0] for f in (run / "reviews").glob(f"*-{stage}-r{rounds[i-1]}.json")})
                flow.append(f"{label} 리뷰 r{rounds[i-1]}({', '.join(revs)})")
    if (run / "spec.md").exists():
        flow.append("최종 Tech Spec")
    lines.append(" → ".join(flow))
    lines.append("")

    for stage, label in (("plan", "1차 계획"), ("spec", "Tech Spec")):
        files = sorted((run / "reviews").glob(f"*-{stage}-r*.json"))
        if not files:
            continue
        rounds = sorted({int(re.search(r"-r(\d+)\.json$", f.name).group(1)) for f in files})
        for rnd in rounds:
            lines += [f"## {label} 리뷰 r{rnd}", "", "| 리뷰어 | 판정 | blocker | major | minor | 수용 | 기각 | 보류 |",
                      "|--------|------|---------|-------|-------|------|------|------|"]
            detail = []
            for f in sorted((run / "reviews").glob(f"*-{stage}-r{rnd}.json")):
                reviewer = f.name.split("-", 1)[0]
                data = json.loads(f.read_text(encoding="utf-8"))
                issues = data.get("issues", [])
                c = {s_: sum(1 for i in issues if i.get("severity") == s_) for s_ in SEVERITIES}
                d = {k: sum(1 for i in issues if adj.get(i.get("id", ""), ("",))[0] == k) for k in ("수용", "기각", "보류")}
                lines.append(f"| {reviewer} | {data.get('verdict', '')} | {c['blocker']} | {c['major']} | {c['minor']} | "
                             f"{d['수용']} | {d['기각']} | {d['보류']} |")
                for i in issues:
                    dec, why = adj.get(i.get("id", ""), ("미판정", ""))
                    prob = re.sub(r"\s+", " ", i.get("problem", ""))
                    if len(prob) > a.max_chars:
                        prob = prob[: a.max_chars] + "…"
                    detail.append(f"| {i.get('id', '')} | {i.get('severity', '')} | {i.get('section', '')} | {prob} | {dec} | {why} |")
            lines += ["", "| id | 심각도 | 위치 | 지적 | 판정 | 반영·근거 |", "|----|--------|------|------|------|-----------|"] + detail + [""]

    for label, versions in (("1차 계획", plans), ("Tech Spec", specs + ([run / "spec.md"] if (run / "spec.md").exists() and specs else []))):
        for prev, cur in zip(versions, versions[1:]):
            rows = section_changes(prev.read_text(encoding="utf-8"), cur.read_text(encoding="utf-8"))
            if not rows:
                continue
            name_b = "최종" if cur.name == "spec.md" else cur.stem.split("-")[1]
            lines += [f"## {label} {prev.stem.split('-')[1]} → {name_b} 변경 섹션", "",
                      "| 섹션 | 변경 | 줄 수 |", "|------|------|-------|"] + rows + [""]

    dest = run / "briefing.md"
    head = ""
    if dest.exists() and a.keep_narrative:
        old = dest.read_text(encoding="utf-8")
        m = re.search(r"(## 요약\n.*?)(?=\n## 흐름)", old, flags=re.S)
        head = m.group(1).rstrip() + "\n\n" if m else ""
    text = "\n".join(lines)
    if head:
        text = text.replace("## 흐름", head + "## 흐름", 1)
    dest.write_text(text + "\n", encoding="utf-8")
    out({"briefing": str(dest), "plan_versions": [p.name for p in plans], "spec_versions": [p.name for p in specs],
         "undecided_issues": sum(1 for l in lines if "| 미판정 |" in l)})
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("slug"); s.add_argument("--title", required=True)
    s.add_argument("--max-rounds", type=int, default=3); s.set_defaults(func=cmd_init)
    s = sub.add_parser("link-research"); s.add_argument("run_dir"); s.add_argument("research_run"); s.set_defaults(func=cmd_link_research)
    s = sub.add_parser("lint"); s.add_argument("run_dir"); s.set_defaults(func=cmd_lint)
    s = sub.add_parser("render"); s.add_argument("run_dir"); s.add_argument("--round", type=int, default=0)
    s.add_argument("--src", default="", help="run_dir 기준 원본(md), 기본 spec.md")
    s.add_argument("--out", default="", help="run_dir 기준 출력(html), 기본 spec.html")
    s.add_argument("--label", default="", help="메타 줄 맨 앞 칩(예: 초안)"); s.set_defaults(func=cmd_render)
    s = sub.add_parser("snapshot"); s.add_argument("run_dir"); s.add_argument("--round", type=int, required=True)
    s.add_argument("--plan", action="store_true", help="plan.md → history/plan-vN.md"); s.set_defaults(func=cmd_snapshot)
    s = sub.add_parser("briefing"); s.add_argument("run_dir"); s.add_argument("--max-chars", type=int, default=260)
    s.add_argument("--keep-narrative", action="store_true", help="기존 briefing.md의 '## 요약' 절을 보존")
    s.set_defaults(func=cmd_briefing)
    s = sub.add_parser("diff"); s.add_argument("run_dir"); s.add_argument("--round", type=int, required=True); s.set_defaults(func=cmd_diff)
    s = sub.add_parser("reviews"); s.add_argument("run_dir"); s.add_argument("--stage", choices=["plan", "spec"], required=True)
    s.add_argument("--round", type=int, required=True); s.set_defaults(func=cmd_reviews)
    a = p.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
