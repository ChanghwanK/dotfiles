#!/usr/bin/env python3
"""PostToolUse hook for notion-create-pages.

After a Notion page is created, inject context reminding the main agent to run
the `notion-review` subagent on the new page (enforces the no-em-dash /
no-emoji hard rules: auto-fix mechanical violations, report the rest).

Loop safety: this hook matches create-pages only. notion-review applies fixes
via notion-update-page, which does NOT match this hook, so review fixes never
re-trigger a review.
"""
import sys
import json


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
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    page_ref = find_ref(data.get("tool_response", {}))
    ref_txt = f" ({page_ref})" if page_ref else ""

    ctx = (
        f"A Notion page was just created{ref_txt}. Per the no-em-dash / "
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
