#!/usr/bin/env python3
"""Plan .md -> .html converter following ~/.claude/docs/plan-html-template.md"""
import sys
import re
import os

CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
  max-width: 720px;
  margin: 60px auto;
  padding: 0 24px 80px;
  color: #1a1a1a;
  line-height: 1.65;
  font-size: 15px;
  background: #fff;
}
h1 { font-size: 1.45rem; font-weight: 700; margin: 0 0 12px 0; }
.tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 20px; }
.tag { background: #f0f0f0; border-radius: 999px; padding: 2px 10px;
       font-size: 0.78rem; color: #555; font-family: 'SF Mono', 'Consolas', monospace; }
.title-hr { border: none; border-top: 1px solid #e0e0e0; margin: 0 0 28px 0; }
h2 { font-size: 1rem; font-weight: 700; margin: 32px 0 4px 0; }
h3 { font-size: 0.95rem; font-weight: 700; margin: 24px 0 8px 0; }
.section-hr { border: none; border-top: 1px solid #e0e0e0; margin: 0 0 14px 0; }
p { margin: 0 0 12px 0; }
code { font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
       background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
pre { background: #f5f5f5; padding: 12px 16px; border-radius: 6px;
      overflow-x: auto; font-size: 0.85em; margin: 12px 0; }
pre code { background: none; padding: 0; }
blockquote { background: #fffbeb; border-left: 3px solid #d97706;
  padding: 12px 16px; margin: 14px 0; border-radius: 0 4px 4px 0; font-size: 0.93em; }
blockquote p { margin: 0 0 6px 0; }
blockquote ul { margin: 6px 0 0 0; padding-left: 18px; }
ol, ul { padding-left: 22px; margin: 0 0 12px 0; }
li { margin-bottom: 5px; }
.dod-list { list-style: none; padding-left: 0; }
.dod-list li { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.dod-list input[type="checkbox"] { margin-top: 3px; flex-shrink: 0; }
strong { font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #e0e0e0; padding: 8px 12px; text-align: left; font-size: 0.9em; }
th { background: #f5f5f5; font-weight: 600; }
"""

KNOWN_SPHERES = {"observability", "santa", "socraai", "data-platform", "tech", "infra"}
KNOWN_ENVS = {"prod", "stg", "dev", "global", "idc"}


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


def render_lines(lines):
    """Render a list of plain body lines to HTML."""
    html = []
    i = 0
    while i < len(lines):
        line = lines[i]

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
            html.append("<blockquote>" + render_lines(bq_lines) + "</blockquote>")
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
                html.append(f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>')
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
            sections_html.append(render_lines(section_lines))
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
