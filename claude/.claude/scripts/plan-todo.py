#!/usr/bin/env python3
"""Plan TODO CLI — manages frontmatter-based TODO state in ~/.claude/plans/*.md"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

PLANS_DIR = Path.home() / ".claude" / "plans"
STATE_FILE = PLANS_DIR / ".state.json"
KST = timezone(timedelta(hours=9))

STATUS_ICON = {
    "done": "✅",
    "in_progress": "⏳",
    "pending": "⬜",
}


# ── helpers ──────────────────────────────────────────────────────────────────


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"sessions": {}, "active": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def plan_id_from_file(path: Path) -> str:
    """plan-elegant-tiger.md → elegant-tiger"""
    name = path.stem
    # strip leading 'plan-' prefix if present
    if name.startswith("plan-"):
        name = name[5:]
    return name


def parse_plan_file(path: Path) -> tuple[dict | None, str]:
    """Returns (frontmatter_dict_or_None, body_without_frontmatter)."""
    text = path.read_text()
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm_text = text[4:end]
            body = text[end + 5:]
            try:
                fm = yaml.safe_load(fm_text)
                return fm, body
            except yaml.YAMLError:
                pass
    return None, text


def write_plan_file(path: Path, fm: dict, body: str):
    fm_text = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{fm_text}---\n{body}")


def parse_title(body: str) -> str | None:
    """Extract the first # heading from the plan body."""
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def parse_steps(body: str) -> list[str]:
    """Extract ordered step titles from ## Steps section."""
    steps = []
    in_steps = False
    for line in body.splitlines():
        if re.match(r"^## Steps\s*$", line):
            in_steps = True
            continue
        if in_steps:
            if line.startswith("## ") and not line.startswith("## Steps"):
                break
            m = re.match(r"^\d+\.\s+(.+)", line)
            if m:
                steps.append(m.group(1).strip())
    return steps


def find_plan_file(name_or_id: str) -> Path | None:
    """Partial match: plan-elegant-tiger.md matches 'elegant', 'tiger', 'elegant-tiger'."""
    for p in sorted(PLANS_DIR.glob("*.md")):
        if p.name.startswith("."):
            continue
        pid = plan_id_from_file(p)
        if name_or_id.lower() in p.stem.lower() or name_or_id.lower() in pid.lower():
            return p
    return None


def get_active_plan_for_session(session_id: str) -> Path | None:
    state = load_state()
    pid = state["sessions"].get(session_id)
    if not pid:
        # fallback: latest active plan
        active = state.get("active", [])
        if active:
            pid = active[-1]
    if not pid:
        return None
    # search by plan_id
    for p in PLANS_DIR.glob("*.md"):
        if p.name.startswith("."):
            continue
        if plan_id_from_file(p) == pid:
            return p
    return None


# ── subcommands ──────────────────────────────────────────────────────────────


def cmd_init(args):
    path = Path(args.plan_file).expanduser()
    if not path.exists():
        print(f"[plan-todo] ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    fm, body = parse_plan_file(path)
    pid = plan_id_from_file(path)
    steps = parse_steps(body)

    if fm is None:
        fm = {}

    # build or update frontmatter
    now = now_kst()
    if "plan_id" not in fm:
        fm["plan_id"] = pid
    if "title" not in fm:
        title = parse_title(body)
        if title:
            fm["title"] = title
    if "session_id" not in fm or args.session_id:
        fm["session_id"] = args.session_id or fm.get("session_id", "unknown")
    if "status" not in fm:
        fm["status"] = "active"
    if "created" not in fm:
        fm["created"] = now
    fm["updated"] = now

    existing_todos = {t["step"]: t for t in fm.get("todos", [])}
    todos = []
    for i, title in enumerate(steps, start=1):
        if i in existing_todos:
            todos.append(existing_todos[i])
        else:
            todos.append({"step": i, "title": title, "status": "pending", "completed_at": None})
    fm["todos"] = todos

    write_plan_file(path, fm, body)

    # update state.json
    state = load_state()
    if args.session_id:
        state["sessions"][args.session_id] = pid
    if pid not in state.get("active", []):
        state.setdefault("active", []).append(pid)
    save_state(state)

    print(f"[plan-todo] Initialized: {pid} ({len(todos)} steps)")


def cmd_list(args):
    status_filter = args.status  # active|completed|abandoned|legacy|all

    groups: dict[str, list[tuple[str, Path]]] = {
        "active": [],
        "completed": [],
        "abandoned": [],
        "legacy": [],
    }

    for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith(".") or p.name == "CLAUDE.md":
            continue
        fm, body = parse_plan_file(p)
        pid = plan_id_from_file(p)
        if fm is None:
            groups["legacy"].append((pid, p))
        else:
            status = fm.get("status", "active")
            groups.setdefault(status, []).append((pid, p))

    order = ["active", "completed", "abandoned", "legacy"]
    for grp in order:
        items = groups.get(grp, [])
        if not items:
            continue
        if status_filter not in ("all", grp):
            continue
        print(f"\n### {grp.upper()} ({len(items)})")
        for pid, p in items:
            fm, body = parse_plan_file(p)
            if fm:
                todos = fm.get("todos", [])
                done = sum(1 for t in todos if t.get("status") == "done")
                total = len(todos)
                updated = fm.get("updated", "")[:10]
                title = fm.get("title") or parse_title(body) or pid
                if len(title) > 72:
                    title = title[:69] + "…"
                print(f"  {title}  [{done}/{total}]  {updated}")
            else:
                mtime = datetime.fromtimestamp(p.stat().st_mtime, KST).isoformat()[:10]
                print(f"  {pid}  [legacy]  {mtime}")


def cmd_show(args):
    name = args.name
    path = find_plan_file(name) if name else None

    if path is None and name:
        print(f"[plan-todo] No plan found matching: {name}", file=sys.stderr)
        sys.exit(1)

    if path is None:
        # fallback: most recent active
        for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("."):
                continue
            fm, body = parse_plan_file(p)
            if fm and fm.get("status") == "active":
                path = p
                break

    if path is None:
        print("[plan-todo] No active plan found.", file=sys.stderr)
        sys.exit(1)

    fm, body = parse_plan_file(path)
    print(body.strip())


def cmd_todo(args):
    session_id = args.session_id
    if session_id:
        path = get_active_plan_for_session(session_id)
    else:
        path = None

    if path is None:
        # fallback: most recently modified active plan
        for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("."):
                continue
            fm, body = parse_plan_file(p)
            if fm and fm.get("status") == "active":
                path = p
                break

    if path is None:
        print("[plan-todo] No active plan found.")
        return

    fm, body = parse_plan_file(path)
    todos = fm.get("todos", [])
    done_count = sum(1 for t in todos if t.get("status") == "done")
    total = len(todos)
    pid = fm.get("plan_id", plan_id_from_file(path))
    display = fm.get("title") or pid

    print(f"📋 **{display}** — {done_count}/{total} 완료\n")
    for t in todos:
        icon = STATUS_ICON.get(t.get("status", "pending"), "⬜")
        completed = f"  _(완료: {t['completed_at'][:16]})_" if t.get("completed_at") else ""
        print(f"  {icon} Step {t['step']}: {t['title']}{completed}")


def cmd_check(args):
    step_num = int(args.step)
    session_id = args.session_id

    if getattr(args, "plan_id", ""):
        path = find_plan_file(args.plan_id)
        if path is None:
            print(f"[plan-todo] Plan not found: {args.plan_id}", file=sys.stderr)
            sys.exit(1)
    elif session_id:
        path = get_active_plan_for_session(session_id)
    else:
        path = None

    if path is None:
        for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("."):
                continue
            fm, body = parse_plan_file(p)
            if fm and fm.get("status") == "active":
                path = p
                break

    if path is None:
        print("[plan-todo] No active plan found.", file=sys.stderr)
        sys.exit(1)

    fm, body = parse_plan_file(path)
    todos = fm.get("todos", [])
    matched = False
    for t in todos:
        if t["step"] == step_num:
            t["status"] = "done"
            t["completed_at"] = now_kst()
            matched = True
            break

    if not matched:
        print(f"[plan-todo] Step {step_num} not found in plan.", file=sys.stderr)
        sys.exit(1)

    # auto-complete plan if all done
    if all(t.get("status") == "done" for t in todos):
        fm["status"] = "completed"
        # remove from active list
        state = load_state()
        pid = fm.get("plan_id")
        if pid in state.get("active", []):
            state["active"].remove(pid)
        save_state(state)
        print(f"[plan-todo] Step {step_num} done. All steps complete → plan status: completed")
    else:
        print(f"[plan-todo] Step {step_num} marked done.")

    fm["updated"] = now_kst()
    write_plan_file(path, fm, body)


def cmd_steps_fzf(args):
    """fzf plan_view용 — <step_num>\t<icon> Step N: title  (완료: ...)"""
    path = find_plan_file(args.plan_id)
    if not path:
        print(f"0\t(plan not found: {args.plan_id})")
        return
    fm, _ = parse_plan_file(path)
    todos = (fm or {}).get("todos", [])
    if not todos:
        print("0\t(steps 없음 — plan init 필요)")
        return
    icons = {"done": "✅", "in_progress": "⏳", "pending": "⬜"}
    for t in todos:
        icon = icons.get(t.get("status", "pending"), "⬜")
        completed = t.get("completed_at")
        at = f"  (완료: {completed[:16]})" if completed else ""
        print(f"{t['step']}\t{icon} Step {t['step']}: {t.get('title', '')}{at}")


def cmd_list_fzf(args):
    """plan picker용 — <plan_id>\t<icon> <title>  [done/total]  <updated>"""
    status_icons = {"active": "⏳", "completed": "✅", "abandoned": "🚫", "legacy": "📦"}
    plans = []
    for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("."):
            continue
        fm, body = parse_plan_file(p)
        if not fm:
            continue
        pid = plan_id_from_file(p)
        todos = fm.get("todos", [])
        done = sum(1 for t in todos if t.get("status") == "done")
        title = fm.get("title") or parse_title(body) or pid
        status = fm.get("status", "legacy")
        updated = str(fm.get("updated") or "")[:10]
        icon = status_icons.get(status, "·")
        plans.append((status, pid, icon, title, done, len(todos), updated))
    plans.sort(key=lambda x: (0 if x[0] == "active" else 1, x[6]))
    print(f"__none__\t  (연결 해제)")
    for status, pid, icon, title, done, total, updated in plans:
        print(f"{pid}\t{icon} {title}  [{done}/{total}]  {updated}")


def cmd_uncheck(args):
    """step을 pending으로 복원."""
    step_num = int(args.step)
    if args.plan_id:
        path = find_plan_file(args.plan_id)
        if path is None:
            print(f"[plan-todo] Plan not found: {args.plan_id}", file=sys.stderr)
            sys.exit(1)
    else:
        path = None
        for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("."):
                continue
            fm, _ = parse_plan_file(p)
            if fm and fm.get("status") in ("active", "completed"):
                path = p
                break
    if path is None:
        print("[plan-todo] No plan found.", file=sys.stderr)
        sys.exit(1)
    fm, body = parse_plan_file(path)
    todos = fm.get("todos", [])
    matched = False
    for t in todos:
        if t["step"] == step_num:
            t["status"] = "pending"
            t["completed_at"] = None
            matched = True
            break
    if not matched:
        print(f"[plan-todo] Step {step_num} not found.", file=sys.stderr)
        sys.exit(1)
    if fm.get("status") == "completed":
        fm["status"] = "active"
        state = load_state()
        pid = fm.get("plan_id")
        if pid and pid not in state.get("active", []):
            state.setdefault("active", []).append(pid)
        save_state(state)
    fm["updated"] = now_kst()
    write_plan_file(path, fm, body)
    print(f"[plan-todo] Step {step_num} restored to pending.")


def cmd_statusline(args):
    session_id = args.session_id
    if session_id:
        path = get_active_plan_for_session(session_id)
    else:
        path = None

    if path is None:
        # fallback: most recently modified active plan
        for p in sorted(PLANS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.name.startswith("."):
                continue
            fm, body = parse_plan_file(p)
            if fm and fm.get("status") == "active":
                path = p
                break

    if path is None:
        print("", end="")
        return

    fm, body = parse_plan_file(path)
    pid = fm.get("plan_id", plan_id_from_file(path))
    plan_title = fm.get("title") or pid
    if len(plan_title) > 40:
        plan_title = plan_title[:37] + "…"
    todos = fm.get("todos", [])
    done = sum(1 for t in todos if t.get("status") == "done")
    total = len(todos)

    # find next pending/in_progress step
    next_step = None
    for t in todos:
        if t.get("status") != "done":
            next_step = t
            break

    if next_step:
        icon = STATUS_ICON.get(next_step.get("status", "pending"), "⬜")
        step_title = next_step["title"]
        if len(step_title) > 60:
            step_title = step_title[:57] + "…"
        print(f"📋 {plan_title} ({done}/{total}) {icon} Step {next_step['step']}: {step_title}", end="")
    else:
        print(f"📋 {plan_title} ({done}/{total}) ✅ 완료", end="")


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="plan-todo",
        description="Plan TODO CLI — manages frontmatter TODO state in ~/.claude/plans/*.md",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Inject frontmatter into a plan file")
    p_init.add_argument("plan_file", help="Path to the plan .md file")
    p_init.add_argument("--session-id", default="")

    # list
    p_list = sub.add_parser("list", help="List all plans grouped by status")
    p_list.add_argument("--status", default="all",
                        choices=["active", "completed", "abandoned", "legacy", "all"])

    # show
    p_show = sub.add_parser("show", help="Print plan body (excluding frontmatter)")
    p_show.add_argument("name", nargs="?", default=None,
                        help="Plan name or partial ID (omit for latest active)")

    # todo
    p_todo = sub.add_parser("todo", help="Show TODO checklist for active plan")
    p_todo.add_argument("--session-id", default="")

    # check
    p_check = sub.add_parser("check", help="Mark a step as done")
    p_check.add_argument("step", type=int, help="Step number to mark done")
    p_check.add_argument("--session-id", default="")
    p_check.add_argument("--plan-id", default="", dest="plan_id",
                         help="Plan ID to use directly (skips session/auto detection)")

    # uncheck
    p_uncheck = sub.add_parser("uncheck", help="Restore a step to pending")
    p_uncheck.add_argument("step", type=int, help="Step number to restore")
    p_uncheck.add_argument("--session-id", default="")
    p_uncheck.add_argument("--plan-id", default="", dest="plan_id")

    # steps-fzf
    p_sfzf = sub.add_parser("steps-fzf", help="Print plan steps as fzf TSV")
    p_sfzf.add_argument("--plan-id", required=True, dest="plan_id")

    # list-fzf
    sub.add_parser("list-fzf", help="Print all plans as fzf TSV for picker")

    # statusline
    p_sl = sub.add_parser("statusline", help="Print 1-line statusline text")
    p_sl.add_argument("--session-id", default="")

    args = parser.parse_args()
    dispatch = {
        "init": cmd_init,
        "list": cmd_list,
        "show": cmd_show,
        "todo": cmd_todo,
        "check": cmd_check,
        "uncheck": cmd_uncheck,
        "steps-fzf": cmd_steps_fzf,
        "list-fzf": cmd_list_fzf,
        "statusline": cmd_statusline,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
