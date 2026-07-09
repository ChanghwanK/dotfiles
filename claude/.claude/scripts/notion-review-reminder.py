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


def is_notion_create_pages(data):
    tool_name = str(data.get("tool_name", ""))
    return "notion-create-pages" in tool_name or "create-pages" in tool_name


_INVOKE_RE = re.compile(r'^\s*(?:sudo\s+)?(?:[\w./~-]*/)?python3?\b')


def is_task_create(data):
    """True only if the Bash `command` itself executes notion-task.py create-task.

    Checking only the `command` field (not `description` or other tool_input
    text) and requiring the segment to actually start with a python
    invocation avoids false positives from commands that merely mention the
    strings, e.g. `grep -n "notion-task.py create-task" file.py` or a
    `description` that describes searching for create-task call sites.
    """
    command = data.get("tool_input", {}).get("command", "")
    if not isinstance(command, str) or not command:
        return False

    # Join backslash line-continuations first: the real call sites in this
    # repo format the invocation across several lines (`notion-task.py \` /
    # `  create-task ... \`), and splitting on bare `\n` before joining would
    # scatter that single invocation across fragments that individually fail
    # the checks below.
    joined = re.sub(r'\\\s*\n', ' ', command)
    segments = re.split(r'&&|\|\||[;\n|]', joined)

    return any(
        _INVOKE_RE.match(seg) and "notion-task.py" in seg and re.search(r'\bcreate-task\b', seg)
        for seg in segments
    )


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
