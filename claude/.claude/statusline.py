#!/usr/bin/env python3
"""
Claude Code statusline script - colorful edition.
Reads JSON from stdin and outputs a formatted multi-line statusline.

JSON fields used:
  workspace.current_dir               - current working directory
  model.display_name / model.id       - model name
  version                             - CLI version
  output_style.name                   - profile name
  context_window.remaining_percentage - context remaining %
  vim.mode                            - vim mode (optional)
  cost.session_total / session_cost_usd / total_cost  - session cost
  cost.hourly / hourly_cost           - hourly cost estimate
  permissions.bypass_mode / permissions.bypass / bypass_permissions - bypass mode

Runtime:
  git branch (via git CLI)
  kubectl context/namespace (via kubectl CLI)
"""

import datetime
import json
import os
import shutil
import subprocess
import sys

COST_TRACKER = os.path.expanduser("~/.claude/cost_tracker.json")

# ANSI escape codes
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

# Bright foreground colors
R  = "\033[91m"   # bright red
G  = "\033[92m"   # bright green
Y  = "\033[93m"   # bright yellow
B  = "\033[94m"   # bright blue
M  = "\033[95m"   # bright magenta
C  = "\033[96m"   # bright cyan
W  = "\033[97m"   # bright white


def co(color, text):
    return f"{color}{text}{RESET}"


def run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except Exception:
        return ""


def hyperlink(url, text):
    """OSC 8 terminal hyperlink – clickable in supported terminals."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def get_git_branch(cwd):
    if not run(["git", "-C", cwd, "rev-parse", "--git-dir"], cwd=cwd):
        return ""
    branch = run(
        ["git", "-C", cwd, "-c", "advice.detachedHead=false", "branch", "--show-current"],
        cwd=cwd,
    )
    return f" {co(G, '(' + branch + ')')}" if branch else ""


def get_pr(cwd):
    """Return clickable OSC 8 hyperlink for current branch's PR, or ''."""
    if not shutil.which("gh"):
        return ""
    out = run(["gh", "pr", "view", "--json", "number,url", "--jq", "[.number,.url]|@tsv"], cwd=cwd)
    if not out:
        return ""
    parts = out.split("\t")
    if len(parts) != 2:
        return ""
    number, url = parts[0].strip(), parts[1].strip()
    label = co(Y, f"PR #{number}")
    return hyperlink(url, label)


def get_claude_account():
    """Return the email of the currently logged-in Claude account."""
    try:
        r = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        info = json.loads(r.stdout.strip())
        return info.get("email") or ""
    except Exception:
        return ""


def get_kube_ctx():
    if not shutil.which("kubectl"):
        return ""
    ctx = run(["kubectl", "config", "current-context"])
    if not ctx:
        return ""
    ns = run(["kubectl", "config", "view", "--minify", "--output", "jsonpath={..namespace}"])
    ns = ns or "default"
    return f"⎈ {co(Y, ctx)}:{co(DIM + W, ns)}"


def shorten_path(path):
    home = os.path.expanduser("~")
    return ("~" + path[len(home):]) if path.startswith(home) else path


def get_weekly_cost(session_cost):
    """Track session costs per day and return 7-day rolling total."""
    try:
        with open(COST_TRACKER) as f:
            tracker = json.load(f)
    except Exception:
        tracker = {"sessions": []}

    today = datetime.date.today().isoformat()
    sessions = tracker.get("sessions", [])
    cost = float(session_cost)

    if sessions and sessions[-1]["date"] == today:
        if cost >= sessions[-1]["peak"]:
            sessions[-1]["peak"] = cost   # 같은 세션, peak 갱신
        else:
            sessions.append({"date": today, "peak": cost})  # 새 세션 시작
    else:
        sessions.append({"date": today, "peak": cost})  # 새 날짜

    # 30일 이전 데이터 정리
    cutoff_old = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    tracker["sessions"] = [s for s in sessions if s["date"] >= cutoff_old]

    try:
        with open(COST_TRACKER, "w") as f:
            json.dump(tracker, f)
    except Exception:
        pass

    # 최근 7일 합산
    cutoff_week = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
    return sum(s["peak"] for s in tracker["sessions"] if s["date"] >= cutoff_week)


def ctx_color(pct):
    """Color for context remaining percentage (higher = more remaining = better)."""
    if pct > 50:
        return G
    elif pct > 20:
        return Y
    return R


def ctx_bar(pct, width=10):
    filled = round(pct / 100 * width)
    return "[" + "=" * filled + "-" * (width - filled) + "]"


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("❌ statusline: invalid JSON")
        return

    # ── Extract JSON fields ──────────────────────────────────────────────────
    cwd = data.get("workspace", {}).get("current_dir") or data.get("cwd") or os.getcwd()

    model_obj     = data.get("model") or {}
    model_display = (model_obj.get("display_name") or model_obj.get("id") or "").replace("Claude ", "")

    version = data.get("version") or ""
    if version and not version.startswith("v"):
        version = f"v{version}"

    profile = (data.get("output_style") or {}).get("name") or ""

    ctx_window    = data.get("context_window") or {}
    ctx_remaining = ctx_window.get("remaining_percentage") or ctx_window.get("used_percentage")

    vim_mode = (data.get("vim") or {}).get("mode") or ""

    # Cost – try several possible field paths
    cost_obj     = data.get("cost") or data.get("usage") or {}
    session_cost = (
        cost_obj.get("total_cost_usd")
        or cost_obj.get("session_total")
        or cost_obj.get("total")
        or data.get("session_cost_usd")
        or data.get("total_cost")
    )
    hourly_cost  = (
        cost_obj.get("hourly")
        or cost_obj.get("per_hour")
        or data.get("hourly_cost")
    )

    # Bypass permissions – try several possible field paths
    perms     = data.get("permissions") or {}
    bypass_on = bool(
        perms.get("bypass_mode")
        or perms.get("bypass")
        or data.get("bypass_permissions")
        or (perms.get("mode") == "bypass")
    )

    # ── Runtime ──────────────────────────────────────────────────────────────
    dir_display = shorten_path(cwd)
    git_branch     = get_git_branch(cwd)
    kube_ctx       = get_kube_ctx()
    pr_link        = get_pr(cwd)
    claude_account = get_claude_account()

    # ── Line 1: 📁 dir (branch)  ⎈ kube  🤖 model  📦 version  🎨 profile ──
    line1 = co(BOLD + C, f"📁 {dir_display}") + git_branch

    if kube_ctx:
        line1 += f"  🐳 {kube_ctx}"

    meta = []
    if model_display:
        meta.append(f"🤖 {co(M, model_display)}")
    if version:
        meta.append(f"📦 {co(B, version)}")

    if claude_account:
        meta.append(f"👤 {co(W, claude_account)}")

    if meta:
        line1 += "  " + "  ".join(meta)

    # ── Line 2: 🧠 context  💰 cost  ✏️ vim ────────────────────────────────
    line2_parts = []

    if ctx_remaining is not None:
        pct = float(ctx_remaining)
        bar = ctx_bar(pct)
        line2_parts.append(f"🧠 Context Remaining: {co(ctx_color(pct), f'{pct:.0f}%')} {co(DIM + W, bar)}")
    else:
        line2_parts.append(f"🧠 {co(DIM + W, 'ctx: TBD')}")

    if session_cost is not None:
        weekly_cost = get_weekly_cost(session_cost)
        cost_str = f"${float(session_cost):.2f}"
        if hourly_cost is not None:
            cost_str += f" ({co(DIM + G, '$' + f'{float(hourly_cost):.2f}/h')})"
        cost_str += f"  💰 ${weekly_cost:.2f}/week"
        line2_parts.append(f"💲 {co(G, cost_str)}")

    if vim_mode:
        line2_parts.append(f"✏️  {co(B, vim_mode)}")

    line2 = f"  {co(DIM + W, '│')}  ".join(line2_parts)

    # ── Line 3: bypass permissions (only when active) ───────────────────────
    lines = [line1, line2]

    if pr_link:
        lines.append(pr_link)

    if bypass_on:
        lines.append(
            f"⚡ {co(R, 'bypass permissions on')}"
            f" {co(DIM + W, '(shift+tab to cycle)')}"
        )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
