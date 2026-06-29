#!/usr/bin/env python3
"""PostToolUse hook for Notion page creation.

After a Notion page is created, inject context reminding the main agent to
run the `notion-review` subagent on the new page (enforces the no-em-dash /
no-emoji hard rules: auto-fix mechanical violations, report the rest).

Loop safety:
- Notion MCP create-pages matches this hook directly.
- Bash matches are filtered to notion-task.py create-task only.
- notion-review applies fixes via update-page, which does not match this hook.
"""
import sys
import json
import re


def find_ref(o):
    """Best-effort: pull a page url or id out of the tool response."""
    if isinstance(o, dict):
        for k in ("url", "page_id", "id"):
            v = o.get(k)
            if isinstance(v, str) and v:
                return v
        for v in o.values():
            r = find_ref(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_ref(v)
            if r:
                return r
    elif isinstance(o, str):
        s = o.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                r = find_ref(json.loads(s))
                if r:
                    return r
            except Exception:
                pass

        # Bash tool responses often wrap stdout as a string. Pull the explicit
        # Notion page id/url out of that stdout instead of guessing from any UUID.
        for pattern in (
            r'"page_id"\s*:\s*"([^"]+)"',
            r'"url"\s*:\s*"([^"]+)"',
        ):
            m = re.search(pattern, s)
            if m:
                return m.group(1)
    return ""


def text_blob(o):
    """Flatten hook input so relevance checks tolerate schema changes."""
    if isinstance(o, dict):
        return "\n".join(text_blob(v) for v in o.values())
    if isinstance(o, list):
        return "\n".join(text_blob(v) for v in o)
    if isinstance(o, str):
        return o
    return ""


def is_notion_create_pages(data):
    tool_name = str(data.get("tool_name", ""))
    return "notion-create-pages" in tool_name or "create-pages" in tool_name


def is_task_create(data):
    tool_input = data.get("tool_input", {})
    blob = text_blob(tool_input)
    return "notion-task.py" in blob and "create-task" in blob


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    source = None
    if is_notion_create_pages(data):
        source = "Notion page"
    elif is_task_create(data):
        source = "Notion Task page"
    else:
        return

    page_ref = find_ref(data.get("tool_response", {}))
    ref_txt = f" ({page_ref})" if page_ref else ""

    ctx = (
        f"A {source} was just created{ref_txt}. Per the no-em-dash / "
        "no-emoji hard rules, spawn the `notion-review` subagent on this page "
        'now (Agent tool, subagent_type: "notion-review", pass the page '
        "url/id). It auto-fixes mechanical violations and reports the rest. "
        "Skip ONLY if this write was itself a notion-review fix."
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": ctx,
        }
    }))


if __name__ == "__main__":
    main()
