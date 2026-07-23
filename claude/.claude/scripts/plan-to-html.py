#!/usr/bin/env python3
"""Plan .md -> .html converter following ~/.claude/docs/plan-html-template.md"""
import sys
import re
import os

CSS = """
:root {
  --ink: #171A21;
  --paper: #F6F7F9;
  --surface: #FFFFFF;
  --line: #E1E4E9;
  --muted: #5B6472;
  --accent: #3A55A6;
  --risk: #B3261E;
  --risk-bg: #FBEAEA;
  --callout: #9A6700;
  --callout-bg: #FFF6E5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ink: #E7E9EE;
    --paper: #14161B;
    --surface: #1C1F26;
    --line: #2B2F38;
    --muted: #8A93A3;
    --accent: #8DA0EE;
    --risk: #F2938D;
    --risk-bg: #3A1F20;
    --callout: #FFD98A;
    --callout-bg: #3A2E12;
  }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  max-width: 68ch;
  margin: 60px auto;
  padding: 0 24px 80px;
  color: var(--ink);
  background: var(--paper);
  line-height: 1.65;
  font-size: 15px;
}
h1, h2, h3 { text-wrap: balance; letter-spacing: -0.01em; }
h1 { font-size: 1.5rem; font-weight: 700; margin: 0 0 12px 0; }
.tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tag { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
       padding: 2px 10px; font-size: 0.78rem; color: var(--muted);
       font-family: 'SF Mono', 'Consolas', monospace; font-variant-numeric: tabular-nums; }
.title-hr { border: none; border-top: 1px solid var(--line); margin: 0 0 28px 0; }
h2 { font-size: 1.02rem; font-weight: 700; margin: 32px 0 4px 0; }
h3 { font-size: 0.96rem; font-weight: 700; margin: 24px 0 8px 0; }
.section-hr { border: none; border-top: 1px solid var(--line); margin: 0 0 14px 0; }
p { margin: 0 0 12px 0; }
code { font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
       background: var(--surface); border: 1px solid var(--line);
       padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
pre { background: var(--surface); border: 1px solid var(--line); padding: 12px 16px;
      border-radius: 6px; overflow-x: auto; font-size: 0.85em; margin: 12px 0; }
pre code { background: none; border: none; padding: 0; }
blockquote { background: var(--callout-bg); border-left: 3px solid var(--callout);
  color: var(--ink); padding: 12px 16px; margin: 14px 0; border-radius: 0 4px 4px 0; font-size: 0.93em; }
blockquote.risk { background: var(--risk-bg); border-left-color: var(--risk); }
blockquote p { margin: 0 0 6px 0; }
blockquote ul { margin: 6px 0 0 0; padding-left: 18px; }
ol, ul { padding-left: 22px; margin: 0 0 12px 0; }
li { margin-bottom: 5px; }
.dod-list { list-style: none; padding-left: 0; }
.dod-list li { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.dod-list input[type="checkbox"] { margin-top: 3px; flex-shrink: 0; accent-color: var(--accent); }
strong { font-weight: 600; }
.table-wrap { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--line); padding: 8px 12px; text-align: left; font-size: 0.9em;
         font-variant-numeric: tabular-nums; }
th { background: var(--surface); font-weight: 600; }
.compare-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 12px; margin: 12px 0; }
.compare-card { border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; background: var(--surface); }
.compare-card.recommended { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.compare-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.compare-label { font-family: 'SF Mono', 'Consolas', monospace; font-size: 0.78rem; color: var(--muted); }
.compare-badge { font-size: 0.72rem; font-weight: 600; color: var(--accent);
                 border: 1px solid var(--accent); border-radius: 999px; padding: 1px 8px; }
.compare-name { margin: 0 0 8px 0; font-size: 0.95rem; }
.compare-card ul { margin: 0; padding-left: 18px; }
.compare-note { font-size: 0.9em; color: var(--muted); }
.section-risk { border-left: 3px solid var(--risk); background: var(--risk-bg);
                border-radius: 0 6px 6px 0; padding: 10px 16px 2px; }
.section-risk > :last-child { margin-bottom: 8px; }
"""

KNOWN_SPHERES = {"observability", "santa", "socraai", "data-platform", "tech", "infra"}
KNOWN_ENVS = {"prod", "stg", "dev", "global", "idc"}

RISK_KEYWORDS = re.compile(r'blast radius|실패 시나리오|롤백 방법|rollback', re.IGNORECASE)
RISK_HEADING = re.compile(r'리스크|위험|롤백|blast radius|rollback', re.IGNORECASE)
OPTION_HEADING = re.compile(r'^###\s+Option\s+([A-Za-z0-9]+)\s*:\s*(.*)$')
RECOMMEND_LINE = re.compile(r'^\*\*추천\*\*\s*:\s*Option\s+([A-Za-z0-9]+)\s*(?:[—\-–]\s*)?(.*)$')


def extract_frontmatter(text):
    """Remove YAML frontmatter and return (frontmatter_dict, body)."""
    fm = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm_text = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in fm_text.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip()
            return fm, body
    return fm, text


def extract_tags(fm, body):
    tags = []
    if "type" in fm:
        tags.append(fm["type"])
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
    """Convert inline markdown: bold, code, links."""
    # code spans
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape(m.group(1))}</code>', text)
    # bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # italic (skip if already inside tag)
    text = re.sub(r'(?<![*])\*([^*\n]+)\*(?![*])', r'<em>\1</em>', text)
    return text


def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            is_dod = any("[ ]" in l or "[x]" in l for l in lines[i:i+10] if re.match(r'^[-*] ', l))
            list_class = ' class="dod-list"' if is_dod else ""
            items = []
            while i < len(lines) and re.match(r'^[-*] ', lines[i]):
                item = lines[i][2:]
                if is_dod:
                    checked = item.startswith("[x]")
                    item = re.sub(r'^\[.\] ', '', item)
                    chk = 'checked' if checked else ''
                    items.append(f'<li><input type="checkbox" {chk}> <span>{inline_md(item)}</span></li>')
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


def convert(md_path):
    text = open(md_path, encoding="utf-8").read()
    fm, body = extract_frontmatter(text)

    lines = body.splitlines()
    # Extract title from first H1
    title = os.path.basename(md_path).replace(".md", "")
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    tags = extract_tags(fm, body)

    sections_html = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # skip H1 (used as title)
        if line.startswith("# "):
            i += 1
            continue

        # H2 section header
        if line.startswith("## "):
            heading = line[3:].strip()
            sections_html.append(f'<h2>{escape(heading)}</h2>\n<hr class="section-hr">')
            i += 1
            # collect until next H2
            section_lines = []
            while i < len(lines) and not lines[i].startswith("## "):
                section_lines.append(lines[i])
                i += 1
            if heading == "옵션 비교":
                compare_html = render_compare_section(section_lines)
                content_html = compare_html if compare_html is not None else render_lines(section_lines)
            else:
                content_html = render_lines(section_lines)
                if RISK_HEADING.search(heading):
                    content_html = f'<div class="section-risk">{content_html}</div>'
            sections_html.append(content_html)
            continue

        i += 1

    tag_html = "".join(f'<span class="tag">{escape(t)}</span>' for t in tags)
    tags_div = f'<div class="tags">{tag_html}</div>' if tags else ""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>{escape(title)}</h1>
  {tags_div}
  <hr class="title-hr">
  {"".join(sections_html)}
</body>
</html>"""

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
