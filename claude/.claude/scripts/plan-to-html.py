#!/usr/bin/env python3
"""Plan .md -> .html converter following ~/.claude/docs/plan-html-template.md"""
import hashlib
import sys
import re
import os

try:
    import yaml
except ImportError:  # keep working when run under a python3 without PyYAML
    yaml = None

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Every caller of this module swallows errors (notify-plan-done.sh `|| true`,
# plan-text-preview.sh `2>/dev/null`, the approval server catches and exits 1).
# Without a fallback a missing assets dir would surface as a silently unstyled
# page rather than an error anyone can see.
_CSS_FALLBACK = (":root{--ink:#171A21;--paper:#F6F7F9}"
                 "body{color:var(--ink);background:var(--paper);"
                 "max-width:68ch;margin:60px auto;padding:0 24px}")


def _read_asset(name, fallback=""):
    try:
        with open(os.path.join(ASSETS_DIR, name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return fallback

KNOWN_SPHERES = {"observability", "santa", "socraai", "data-platform", "tech", "infra"}
KNOWN_ENVS = {"prod", "stg", "dev", "global", "idc"}

RISK_KEYWORDS = re.compile(r'blast radius|실패 시나리오|롤백 방법|rollback', re.IGNORECASE)
RISK_HEADING = re.compile(r'리스크|위험|롤백|blast radius|rollback', re.IGNORECASE)
CHECKBOX_ITEM = re.compile(r'^[-*] \[[ xX]\]')
OPTION_HEADING = re.compile(r'^###\s+Option\s+([A-Za-z0-9]+)\s*:\s*(.*)$')
RECOMMEND_LINE = re.compile(r'^\*\*추천\*\*\s*:\s*Option\s+([A-Za-z0-9]+)\s*(?:[—\-–]\s*)?(.*)$')

# Section dispatch. `Steps` is matched loosely so `## Steps (7개)` still renders
# as a checkable list, but note plan-todo.py's parse_steps() requires an exact
# `## Steps`, so a suffixed heading yields an empty frontmatter todos list and
# the checkboxes simply start unseeded.
STEPS_HEADING = re.compile(r'^Steps\b', re.IGNORECASE)
DETAIL_HEADING = re.compile(r'스텝별|상세 계획|Step Details', re.IGNORECASE)
STEP_ITEM = re.compile(r'^(\d+)\.\s+(.+)')
STEP_DETAIL_H3 = re.compile(r'^###\s+Step\s+(\d+)\s*(?:[—\-–:]\s*)?(.*)$')

QUIZ_HEADING = re.compile(r'^(이해 ?점검|Comprehension)', re.IGNORECASE)
QUIZ_Q = re.compile(r'^###\s+Q(\d+)\s*(?:\((초급|중급|고급)\))?\s*(?:[—\-–:]\s*)?(.*)$')
QUIZ_ANSWER = re.compile(r'^-\s+\*\*(?:모범답안|답안|Answer)\*\*\s*:\s*(.*)$')
QUIZ_CONTEXT = re.compile(r'^-\s+\*\*(?:컨텍스트|배경|Context)\*\*\s*:\s*(.*)$')


def _naive_frontmatter(fm_text):
    """Flat `k: v` fallback. Nested lists collapse into junk keys, so this is
    only good enough for scalar lookups like `type`."""
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def extract_frontmatter(text):
    """Remove YAML frontmatter and return (frontmatter_dict, body).

    Delimiters include the trailing newline, matching plan-todo.py. Without it
    a markdown horizontal rule in the body is mistaken for the closing fence
    and the body gets sliced at the wrong offset.
    """
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm_text, body = text[4:end], text[end + 5:]
            if yaml is not None:
                try:
                    fm = yaml.safe_load(fm_text)
                    if isinstance(fm, dict):
                        return fm, body
                except yaml.YAMLError:
                    pass
            return _naive_frontmatter(fm_text), body
    return {}, text


def extract_tags(fm, body):
    tags = []
    if fm.get("type"):
        tags.append(str(fm["type"]))
    # version pattern like "0.59.3 -> 0.84.0" or "v1.2 → v2.0"
    ver = re.search(r'v?[\d]+\.[\d]+(?:\.[\d]+)?\s*(?:→|->)\s*v?[\d]+\.[\d]+(?:\.[\d]+)?', body)
    if ver:
        tags.append(ver.group(0))
    # env / sphere
    for word in re.findall(r'\b\w[\w-]*\b', body):
        if word in KNOWN_SPHERES and word not in tags:
            tags.append(word)
        if word in KNOWN_ENVS and word not in tags:
            tags.append(word)
    return tags[:6]


def inline_md(text):
    """Convert inline markdown: bold, code, italic.

    Escapes first. The preview page now hosts state-changing endpoints, so raw
    HTML from a plan body must never reach the document: an injected <script>
    could approve a plan the reader never saw.
    """
    text = escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<![*])\*([^*\n]+)\*(?![*])', r'<em>\1</em>', text)
    return text


def escape(s):
    """Escape for both text nodes and double-quoted attribute values."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_compare_section(lines):
    """Parse a '## 옵션 비교' section into comparison cards. Returns None if no
    '### Option X: ...' subsections are found, so the caller can fall back to
    the default renderer."""
    cards = []
    current = None
    recommend_label = None
    recommend_text = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        m = OPTION_HEADING.match(line)
        if m:
            if current:
                cards.append(current)
            current = {"label": m.group(1), "name": m.group(2).strip(), "body": []}
            i += 1
            continue
        m2 = RECOMMEND_LINE.match(line)
        if m2:
            recommend_label = m2.group(1)
            recommend_text = m2.group(2).strip()
            i += 1
            continue
        if current is not None:
            current["body"].append(line)
        i += 1
    if current:
        cards.append(current)

    if not cards:
        return None

    card_html = []
    for c in cards:
        is_rec = recommend_label is not None and c["label"].lower() == recommend_label.lower()
        badge = '<span class="compare-badge">추천</span>' if is_rec else ''
        rec_class = ' recommended' if is_rec else ''
        body_html = render_lines(c["body"])
        card_html.append(
            f'<div class="compare-card{rec_class}">'
            f'<div class="compare-card-head"><span class="compare-label">Option {escape(c["label"])}</span>{badge}</div>'
            f'<h3 class="compare-name">{inline_md(c["name"])}</h3>'
            f'{body_html}'
            f'</div>'
        )

    grid_html = f'<div class="compare-grid">{"".join(card_html)}</div>'
    note_html = ""
    if recommend_label:
        reason = f' — {inline_md(recommend_text)}' if recommend_text else ""
        note_html = f'<p class="compare-note"><strong>추천</strong>: Option {escape(recommend_label)}{reason}</p>'
    return grid_html + note_html


def render_lines(lines):
    """Render a list of plain body lines to HTML."""
    html = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # H3 subheading (e.g. "스텝별 상세 계획" 내부의 "### Step 1 — ...")
        if line.startswith("### "):
            html.append(f'<h3>{inline_md(line[4:].strip())}</h3>')
            i += 1
            continue

        # fenced code block
        if line.strip().startswith("```"):
            lang = line.strip()[3:]
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(escape(lines[i]))
                i += 1
            html.append(f'<pre><code>{"<br>".join(code_lines)}</code></pre>'.replace("<br>", "\n"))
            i += 1
            continue

        # blockquote
        if line.startswith("> "):
            bq_lines = []
            while i < len(lines) and lines[i].startswith("> "):
                bq_lines.append(lines[i][2:])
                i += 1
            bq_class = ' class="risk"' if RISK_KEYWORDS.search(" ".join(bq_lines)) else ''
            html.append(f"<blockquote{bq_class}>" + render_lines(bq_lines) + "</blockquote>")
            continue

        # unordered list
        if re.match(r'^[-*] ', line):
            # Only the contiguous bullet run decides. A 10-line lookahead used to
            # turn an unrelated list into checkboxes just because a DoD item sat
            # nearby, and checkbox state is now persisted per item.
            run_end = i
            while run_end < len(lines) and re.match(r'^[-*] ', lines[run_end]):
                run_end += 1
            is_dod = any(CHECKBOX_ITEM.match(l) for l in lines[i:run_end])
            list_class = ' class="dod-list"' if is_dod else ""
            items = []
            while i < len(lines) and re.match(r'^[-*] ', lines[i]):
                item = lines[i][2:]
                if is_dod:
                    checked = item[:3].lower() == "[x]"
                    item = re.sub(r'^\[.\]\s*', '', item)
                    chk = ' checked data-seed="done"' if checked else ''
                    # Content-hashed so reordering the list does not shift every
                    # stored state onto the wrong item.
                    key = hashlib.sha1(item.encode("utf-8")).hexdigest()[:8]
                    items.append(
                        f'<li><input type="checkbox" class="chk"'
                        f' data-key="dod:{key}"{chk}>'
                        f' <span>{inline_md(item)}</span></li>')
                else:
                    items.append(f'<li>{inline_md(item)}</li>')
                i += 1
            html.append(f'<ul{list_class}>' + "".join(items) + '</ul>')
            continue

        # ordered list
        if re.match(r'^\d+\. ', line):
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                item = re.sub(r'^\d+\. ', '', lines[i])
                items.append(f'<li>{inline_md(item)}</li>')
                i += 1
            html.append('<ol>' + "".join(items) + '</ol>')
            continue

        # table
        if "|" in line and i + 1 < len(lines) and re.match(r'^[\s|:-]+$', lines[i + 1]):
            rows = []
            while i < len(lines) and "|" in lines[i]:
                rows.append(lines[i])
                i += 1
            if rows:
                header = [c.strip() for c in rows[0].strip("|").split("|")]
                body_rows = rows[2:]  # skip separator
                th = "".join(f"<th>{inline_md(h)}</th>" for h in header)
                trs = [f'<tr>{"".join(f"<td>{inline_md(c.strip())}</td>" for c in r.strip("|").split("|"))}</tr>'
                       for r in body_rows]
                html.append(f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead>'
                            f'<tbody>{"".join(trs)}</tbody></table></div>')
            continue

        # empty line
        if not line.strip():
            i += 1
            continue

        # paragraph
        html.append(f'<p>{inline_md(line)}</p>')
        i += 1

    return "\n".join(html)


def fence_mask(lines):
    """[bool] — True where a line is inside a fenced code block (or is the
    fence itself). A plan that quotes markdown headings in a code block would
    otherwise have those headings split its sections.
    """
    mask, in_fence = [], False
    for line in lines:
        is_fence = line.lstrip().startswith("```")
        mask.append(in_fence or is_fence)
        if is_fence:
            in_fence = not in_fence
    return mask


def split_sections(lines):
    """Split a plan body into (title, [(heading, body_lines), ...]).

    Separated from rendering because the sidebar TOC and the Steps/detail
    cross-links both need to know the whole section list before any section
    is rendered.
    """
    fenced = fence_mask(lines)
    title = None
    sections = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not fenced[i]:
            if title is None and line.startswith("# "):
                title = line[2:].strip()
                i += 1
                continue
            if line.startswith("## "):
                heading = line[3:].strip()
                i += 1
                body = []
                while i < len(lines) and not (
                        not fenced[i] and lines[i].startswith("## ")):
                    body.append(lines[i])
                    i += 1
                sections.append((heading, body))
                continue
        i += 1
    return title, sections


def todo_status_map(fm):
    """{step_number: status} from the frontmatter plan-todo.py maintains."""
    out = {}
    for t in (fm.get("todos") or []):
        if isinstance(t, dict) and isinstance(t.get("step"), int):
            out[t["step"]] = t.get("status")
    return out


def compute_plan_key(title, step_titles):
    """localStorage namespace.

    Content-hashed rather than keyed on frontmatter `plan_id`: the browser
    preview renders from a temp copy that has no frontmatter yet, while the
    archive copy does. A content hash keeps both on the same namespace so
    checkbox state survives the transition.
    """
    seed = "\n".join([title or ""] + list(step_titles))
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def parse_step_items(lines):
    """[(n, text)] for a `## Steps` body, or None if it holds anything else.

    Indented continuation lines fold into the preceding item; anything else
    aborts so prose is never silently dropped.
    """
    items = []
    for line in lines:
        if not line.strip():
            continue
        m = STEP_ITEM.match(line)
        if m:
            items.append([len(items) + 1, m.group(2).strip()])
            continue
        if items and (line.startswith("  ") or line.startswith("\t")):
            items[-1][1] += " " + line.strip()
            continue
        return None
    return items or None


def render_steps_section(lines, detail_steps, todo_status):
    items = parse_step_items(lines)
    if items is None:
        return None
    out = []
    for n, text in items:
        done = todo_status.get(n) == "done"
        chk = ' checked data-seed="done"' if done else ''
        jump = (f'<a class="step-jump" href="#step-detail-{n}">상세</a>'
                if n in detail_steps else '')
        out.append(
            f'<li class="step-item" id="step-{n}" data-step="{n}">'
            f'<input type="checkbox" class="chk" data-key="step:{n}"{chk}>'
            f'<span class="step-text">{inline_md(text)}</span>{jump}</li>')
    return f'<ol class="steps-list">{"".join(out)}</ol>'


def render_step_details_section(lines, n_steps):
    """`### Step N` blocks as accordions.

    Kept `open` by default: a collapsed <details> is invisible to Ctrl+F and to
    print. Bulk collapsing is a sidebar action instead. The back-link sits in
    the body rather than the <summary> because an <a> inside <summary> toggles
    the disclosure on click.
    """
    fenced = fence_mask(lines)
    blocks, cur, preamble = [], None, []
    for idx, line in enumerate(lines):
        m = None if fenced[idx] else STEP_DETAIL_H3.match(line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "body": []}
            continue
        (cur["body"] if cur is not None else preamble).append(line)
    if cur:
        blocks.append(cur)
    if not blocks:
        return None

    out = []
    if any(l.strip() for l in preamble):
        out.append(render_lines(preamble))
    for b in blocks:
        back = (f'<a class="step-back" href="#step-{b["n"]}">Steps 목록으로</a>'
                if b["n"] <= n_steps else '')
        out.append(
            f'<details class="step-detail" id="step-detail-{b["n"]}"'
            f' data-step="{b["n"]}" open>'
            f'<summary><span class="step-badge">Step {b["n"]}</span>'
            f'<span class="step-detail-title">{inline_md(b["title"])}</span></summary>'
            f'<div class="step-detail-body">{back}{render_lines(b["body"])}</div>'
            f'</details>')
    return "".join(out)


def render_quiz_section(lines):
    """`## 이해 점검` as answerable questions with a revealable model answer.

    Free answer rather than multiple choice: the answer key ships in the plan
    markdown (the terminal prints it too), so auto-grading would be theatre.
    What the typed answers are actually for is the 논의 round-trip, where
    Claude grades them.

    The textareas carry form="plan-form" so they submit with the sidebar form
    without wrapping the document. In static mode no such form exists and the
    attribute is inert.
    """
    fenced = fence_mask(lines)
    items, cur, bucket = [], None, None
    for idx, line in enumerate(lines):
        m = None if fenced[idx] else QUIZ_Q.match(line)
        if m:
            if cur:
                items.append(cur)
            cur = {"n": int(m.group(1)), "level": m.group(2) or "",
                   "q": m.group(3).strip(), "ctx": [], "ans": []}
            bucket = "ctx"
            continue
        if cur is None:
            continue
        if not fenced[idx]:
            a = QUIZ_ANSWER.match(line)
            if a:
                bucket = "ans"
                if a.group(1).strip():
                    cur["ans"].append(a.group(1).strip())
                continue
            c = QUIZ_CONTEXT.match(line)
            if c:
                bucket = "ctx"
                if c.group(1).strip():
                    cur["ctx"].append(c.group(1).strip())
                continue
        cur[bucket].append(line)
    if cur:
        items.append(cur)
    if not items:
        return None

    out = ['<p class="quiz-note">답을 적고 모범답안을 열어 확인하십시오. '
           '작성한 답변은 "논의" 제출 시 함께 전송됩니다.</p>']
    for it in items:
        n = it["n"]
        level = (f'<span class="quiz-level">{escape(it["level"])}</span>'
                 if it["level"] else '')
        ctx_html = (f'<div class="quiz-ctx">{render_lines(it["ctx"])}</div>'
                    if any(l.strip() for l in it["ctx"]) else '')
        model = (f'<details class="quiz-model"><summary>모범답안 보기</summary>'
                 f'<div class="quiz-model-body">{render_lines(it["ans"])}</div></details>'
                 if any(l.strip() for l in it["ans"]) else '')
        # The hidden field carries the question text so the server never has to
        # re-parse the markdown to label an answer.
        label = f'{it["level"]} | {it["q"]}'.strip(' |')
        out.append(
            f'<div class="quiz-item" data-q="{n}">'
            f'<div class="quiz-q">{level}<span class="quiz-q-text">'
            f'{inline_md(it["q"])}</span></div>'
            f'{ctx_html}'
            f'<textarea class="quiz-answer" name="quiz_{n}" form="plan-form"'
            f' rows="3" placeholder="답변 (선택)"></textarea>'
            f'<input type="hidden" name="quizq_{n}" form="plan-form"'
            f' value="{escape(label)}">'
            f'{model}</div>')
    return (f'<div class="quiz" id="quiz" data-quiz-count="{len(items)}">'
            f'{"".join(out)}</div>')


def render_section_body(heading, lines, ctx):
    """Dispatch one H2 section to its specialised renderer.

    Every specialised renderer returns None when the section does not match its
    shape, so an unexpected body always degrades to the generic renderer rather
    than losing content.
    """
    if heading == "옵션 비교":
        html = render_compare_section(lines)
        if html is not None:
            return html
    elif STEPS_HEADING.match(heading):
        html = render_steps_section(lines, ctx["detail_steps"], ctx["todo_status"])
        if html is not None:
            return html
    elif DETAIL_HEADING.search(heading):
        html = render_step_details_section(lines, ctx["n_steps"])
        if html is not None:
            return html
    elif QUIZ_HEADING.match(heading):
        html = render_quiz_section(lines)
        if html is not None:
            return html

    html = render_lines(lines)
    if RISK_HEADING.search(heading):
        html = f'<div class="section-risk">{html}</div>'
    return html


# CSS and JS are inlined, so 'unsafe-inline' is unavoidable and injected script
# cannot be blocked here. What this does buy is the exfiltration half:
# default-src 'none' plus form-action 'self' means injected script has nowhere
# to send what it reads.
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "connect-src 'self'; form-action 'self'; img-src data:")

# Set on document.documentElement before the stylesheet is parsed. Reading the
# stored theme from the end-of-body script instead would flash the wrong theme.
THEME_BOOTSTRAP = ("try{var t=localStorage.getItem('planTheme');"
                   "if(t==='dark'||t==='light')"
                   "document.documentElement.dataset.theme=t;}catch(e){}")

# Emitted only in mode="server". A plain form, deliberately: plan.js is now the
# single largest thing on the page and one syntax error in it would take every
# listener with it. Submitting a decision must survive that, so it stays a
# no-JS form POST. plan-approval-server.py substitutes __CSRF__.
ACTIONS_HTML = """<form id="plan-form" method="POST" action="/decide" accept-charset="utf-8">
    <input type="hidden" name="csrf" value="__CSRF__">
    <label class="actions-label" for="discuss">논의 / 수정 요청</label>
    <textarea id="discuss" name="discussion" rows="5"
              placeholder="바꾸고 싶은 점, 궁금한 점"></textarea>
    <div class="actions-row">
      <button type="submit" name="action" value="approve" class="btn btn-approve">승인</button>
      <button type="submit" name="action" value="pause" class="btn btn-pause">논의</button>
      <button type="submit" name="action" value="reject" class="btn btn-reject">거부</button>
    </div>
  </form>"""


def render_document(md_text, src_name="plan.md", mode="static"):
    """Render a plan markdown document to a self-contained HTML string.

    mode 'static'  : archive/read-only. No action form.
    mode 'server'  : served by plan-approval-server.py, gets the decision form.
    """
    fm, body = extract_frontmatter(md_text)
    lines = body.splitlines()
    title, sections = split_sections(lines)
    if not title:
        title = src_name.replace(".md", "")

    tags = extract_tags(fm, body)
    todo_status = todo_status_map(fm)

    # Pass 1: cross-section facts the per-section renderers need.
    step_items, detail_steps = None, set()
    for heading, blines in sections:
        if STEPS_HEADING.match(heading) and step_items is None:
            step_items = parse_step_items(blines)
        elif DETAIL_HEADING.search(heading):
            bfenced = fence_mask(blines)
            detail_steps |= {int(m.group(1))
                             for j, l in enumerate(blines)
                             if not bfenced[j] and (m := STEP_DETAIL_H3.match(l))}
    step_titles = [t for _, t in (step_items or [])]
    ctx = {"detail_steps": detail_steps, "todo_status": todo_status,
           "n_steps": len(step_titles)}

    # Pass 2: TOC + section bodies.
    toc, blocks = [], []
    for n, (heading, blines) in enumerate(sections):
        toc.append(f'<li><a href="#sec-{n}" data-target="sec-{n}">'
                   f'{escape(heading)}</a></li>')
        blocks.append(
            f'<section class="sec" id="sec-{n}">'
            f'<h2>{escape(heading)}</h2><hr class="section-hr">'
            f'{render_section_body(heading, blines, ctx)}</section>')

    tag_html = "".join(f'<span class="tag">{escape(t)}</span>' for t in tags)
    tags_div = f'<div class="tags">{tag_html}</div>' if tags else ""
    actions = ACTIONS_HTML if mode == "server" else ""
    css = _read_asset("plan.css", _CSS_FALLBACK)
    js = _read_asset("plan.js").replace("</script>", "<\\/script>")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="{CSP}">
  <title>{escape(title)}</title>
  <script>{THEME_BOOTSTRAP}</script>
  <style>{css}</style>
</head>
<body data-mode="{escape(mode)}" data-plan-key="{compute_plan_key(title, step_titles)}">
<aside id="sidebar">
  <div id="sidebar-head"><span id="plan-title-mini">{escape(title)}</span></div>
  <div id="progress" hidden>
    <div id="progress-track"><div id="progress-bar"></div></div>
    <span id="progress-label"></span>
  </div>
  <nav id="plan-toc" aria-label="목차"><ol>{"".join(toc)}</ol></nav>
  <div id="sidebar-tools">
    <button type="button" id="theme-toggle">테마: 자동</button>
    <button type="button" id="collapse-all">전체 접기</button>
    <button type="button" id="help-toggle">단축키</button>
  </div>
  <div id="plan-actions">{actions}</div>
</aside>
<main id="content">
  <h1>{escape(title)}</h1>
  {tags_div}
  <hr class="title-hr">
  {"".join(blocks)}
</main>
<div id="help-panel" hidden></div>
<script>{js}</script>
</body>
</html>"""


def render(md_path, mode="static"):
    """Render to a string without writing. Used by the approval server."""
    with open(md_path, encoding="utf-8") as f:
        return render_document(f.read(), os.path.basename(md_path), mode)


def convert(md_path):
    """Render and write the sibling .html. Signature is depended on by
    notify-plan-done.sh, plan-text-preview.sh and plan-approval-server.py."""
    html = render(md_path, "static")
    out_path = md_path.replace(".md", ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: plan-to-html.py <plan.md>", file=sys.stderr)
        sys.exit(1)
    out = convert(sys.argv[1])
    print(out)
