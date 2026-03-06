#!/usr/bin/env python3
"""
Notion Plan Sender CLI
Usage:
  python3 notion-plan.py send --url <notion-page-url> --file <plan-file-path>
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import argparse
from pathlib import Path

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

NOTION_LANGUAGES = {
    "py": "python", "python": "python",
    "js": "javascript", "javascript": "javascript",
    "ts": "typescript", "typescript": "typescript",
    "sh": "shell", "bash": "shell", "shell": "shell",
    "zsh": "shell",
    "yaml": "yaml", "yml": "yaml",
    "json": "json",
    "go": "go",
    "java": "java",
    "rb": "ruby", "ruby": "ruby",
    "rs": "rust", "rust": "rust",
    "cpp": "c++", "c++": "c++",
    "c": "c",
    "cs": "c#", "csharp": "c#",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "md": "markdown", "markdown": "markdown",
    "dockerfile": "dockerfile",
    "tf": "plain text",
    "jsonnet": "plain text",
    "": "plain text",
}


def get_token():
    if not NOTION_TOKEN:
        print(json.dumps({"success": False, "error": "NOTION_TOKEN not set"}))
        sys.exit(1)
    return NOTION_TOKEN


def notion_request(token, method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        try:
            return json.loads(err_body)
        except Exception:
            return {"object": "error", "message": f"HTTP {e.code}: {err_body}"}


def parse_page_id_from_url(url):
    """Extract 32-char hex page ID from various Notion URL formats.

    Supports:
      - UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
      - Path ending with 32 hex: .../Title-{32hex}
      - Bare 32-char hex string
    """
    url = url.strip()

    # UUID format (with hyphens)
    m = re.search(
        r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        url, re.IGNORECASE
    )
    if m:
        return m.group(1).replace("-", "")

    # 32-char hex at end of path segment (before ? or # or end)
    m = re.search(r'([0-9a-f]{32})(?:[?#&]|$)', url, re.IGNORECASE)
    if m:
        return m.group(1).lower()

    # Bare 32-char hex
    if re.match(r'^[0-9a-f]{32}$', url, re.IGNORECASE):
        return url.lower()

    return None


def format_as_uuid(page_id):
    """Format raw 32-char hex as UUID with hyphens for Notion API."""
    h = page_id.replace("-", "").lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def make_text_segment(text, annotations=None):
    """Create a Notion rich_text text segment."""
    seg = {
        "type": "text",
        "text": {"content": text},
    }
    if annotations:
        base = {
            "bold": False, "italic": False, "code": False,
            "strikethrough": False, "underline": False, "color": "default",
        }
        base.update(annotations)
        seg["annotations"] = base
    return seg


def parse_inline_formatting(text):
    """Parse inline markdown formatting into Notion rich_text segments.

    Handles: **bold**, *italic*, `code`
    Returns a list of rich_text objects.
    """
    segments = []
    # Order: **bold** before *italic* to avoid partial match
    pattern = re.compile(r'\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`', re.DOTALL)
    last_end = 0

    for m in pattern.finditer(text):
        if m.start() > last_end:
            segments.append(make_text_segment(text[last_end:m.start()]))

        full = m.group(0)
        if full.startswith("**"):
            segments.append(make_text_segment(m.group(1), {"bold": True}))
        elif full.startswith("*"):
            segments.append(make_text_segment(m.group(2), {"italic": True}))
        else:
            segments.append(make_text_segment(m.group(3), {"code": True}))

        last_end = m.end()

    if last_end < len(text):
        segments.append(make_text_segment(text[last_end:]))

    return segments if segments else [make_text_segment(text)]


def make_code_block(content, lang=""):
    """Create Notion code block(s). Splits if content > 2000 chars."""
    notion_lang = NOTION_LANGUAGES.get(lang.lower(), "plain text")
    blocks = []
    if not content:
        return [{
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": ""}}],
                "language": notion_lang,
            }
        }]
    chunk_size = 2000
    for start in range(0, len(content), chunk_size):
        chunk = content[start:start + chunk_size]
        blocks.append({
            "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}],
                "language": notion_lang,
            }
        })
    return blocks


def make_heading_block(level, text):
    kind = f"heading_{level}"
    return {
        "type": kind,
        kind: {
            "rich_text": parse_inline_formatting(text),
            "color": "default",
        }
    }


def make_paragraph_block(text):
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": parse_inline_formatting(text),
            "color": "default",
        }
    }


def make_bulleted_block(text):
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": parse_inline_formatting(text),
            "color": "default",
        }
    }


def make_numbered_block(text):
    return {
        "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": parse_inline_formatting(text),
            "color": "default",
        }
    }


def make_todo_block(text, checked=False):
    return {
        "type": "to_do",
        "to_do": {
            "rich_text": parse_inline_formatting(text),
            "checked": checked,
            "color": "default",
        }
    }


def make_quote_block(text):
    return {
        "type": "quote",
        "quote": {
            "rich_text": parse_inline_formatting(text),
            "color": "default",
        }
    }


def make_divider_block():
    return {"type": "divider", "divider": {}}


class MarkdownToNotionParser:
    def parse(self, text):
        """Convert markdown text to a list of Notion block objects."""
        blocks = []
        lines = text.split("\n")

        in_code_block = False
        code_lang = ""
        code_lines = []

        for line in lines:
            # --- Inside a code block ---
            if in_code_block:
                if line.startswith("```"):
                    blocks.extend(make_code_block("\n".join(code_lines), code_lang))
                    in_code_block = False
                    code_lang = ""
                    code_lines = []
                else:
                    code_lines.append(line)
                continue

            # Code fence start
            if line.startswith("```"):
                in_code_block = True
                code_lang = line[3:].strip()
                code_lines = []
                continue

            # Divider (--- or ------ etc.)
            if re.match(r'^-{3,}$', line.strip()):
                blocks.append(make_divider_block())
                continue

            # Heading H1–H3
            m = re.match(r'^(#{1,3})\s+(.*)', line)
            if m:
                level = len(m.group(1))
                blocks.append(make_heading_block(level, m.group(2).strip()))
                continue

            # Heading H4+ → bold paragraph
            m = re.match(r'^#{4,}\s+(.*)', line)
            if m:
                blocks.append(make_paragraph_block(f"**{m.group(1).strip()}**"))
                continue

            # Checkbox (must match before bullet)
            m = re.match(r'^[-*]\s+\[( |x|X)\]\s+(.*)', line)
            if m:
                checked = m.group(1).lower() == "x"
                blocks.append(make_todo_block(m.group(2).strip(), checked))
                continue

            # Bullet list
            m = re.match(r'^[-*]\s+(.*)', line)
            if m:
                blocks.append(make_bulleted_block(m.group(1).strip()))
                continue

            # Numbered list
            m = re.match(r'^\d+\.\s+(.*)', line)
            if m:
                blocks.append(make_numbered_block(m.group(1).strip()))
                continue

            # Blockquote
            m = re.match(r'^>\s*(.*)', line)
            if m:
                blocks.append(make_quote_block(m.group(1).strip()))
                continue

            # Table row → code-style paragraph (v1: no table API)
            if line.startswith("|"):
                blocks.append(make_paragraph_block(line))
                continue

            # Empty line → skip
            if not line.strip():
                continue

            # Default: paragraph
            blocks.append(make_paragraph_block(line))

        # Unclosed code block
        if in_code_block and code_lines:
            blocks.extend(make_code_block("\n".join(code_lines), code_lang))

        return blocks


def send_blocks_to_page(token, page_id, blocks):
    """Send blocks to Notion page in batches of 100.

    Returns (error_dict_or_None, total_batches_sent).
    """
    batch_size = 100
    total_batches = 0
    uuid = format_as_uuid(page_id)

    for start in range(0, len(blocks), batch_size):
        batch = blocks[start:start + batch_size]
        resp = notion_request(token, "PATCH", f"/blocks/{uuid}/children", {
            "children": batch
        })
        if resp.get("object") == "error":
            return resp, total_batches
        total_batches += 1

    return None, total_batches


def cmd_send(args):
    token = get_token()

    # Parse page ID
    page_id = parse_page_id_from_url(args.url)
    if not page_id:
        print(json.dumps({
            "success": False,
            "error": f"Could not parse page ID from URL: {args.url}",
        }))
        sys.exit(1)

    # Read file
    file_path = Path(args.file).expanduser()
    if not file_path.exists():
        print(json.dumps({
            "success": False,
            "error": f"File not found: {args.file}",
        }))
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        print(json.dumps({"success": False, "error": "File is empty"}))
        sys.exit(1)

    # Parse markdown → Notion blocks
    parser = MarkdownToNotionParser()
    blocks = parser.parse(content)

    if not blocks:
        print(json.dumps({"success": False, "error": "No blocks generated from file"}))
        sys.exit(1)

    # Send to Notion
    error, batches = send_blocks_to_page(token, page_id, blocks)
    if error:
        print(json.dumps({
            "success": False,
            "error": error.get("message", str(error)),
        }))
        sys.exit(1)

    print(json.dumps({
        "success": True,
        "blocks_sent": len(blocks),
        "batches": batches,
        "page_id": format_as_uuid(page_id),
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Plan Sender CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send", help="Send plan markdown file to Notion page")
    send_parser.add_argument("--url", required=True, help="Notion page URL or page ID")
    send_parser.add_argument("--file", required=True, help="Path to plan markdown file")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)


if __name__ == "__main__":
    main()
