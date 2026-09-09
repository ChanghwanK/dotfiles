#!/usr/bin/env python3
"""Collect a unit of work as normalized JSON, for question generation.

Two deterministic sources are handled here:

  pr    a GitHub PR (or the current branch when no PR exists yet)
        --comments also pulls issue comments and reviews; experiment results
        and post-merge evidence often live there rather than in the body.
        referenced_prs (#numbers found in body/comments) is always emitted so
        a caller can walk the PR chain (instrumentation -> change -> cleanup).
  log-search
        grep the repository commit log for keywords and return the PR numbers
        found in commit subjects. Use it when the PR reference chain closes on
        itself (A references B, B references A) without reaching the PR that
        recorded why the work started.
  plan  a local plan file under ~/.claude/plans

Notion Tasks are NOT fetched here. The caller has Notion MCP tools and reads
the page directly; adding a second Notion client would duplicate credentials
and drift from the tasks:manage scripts.

Every subcommand emits the same shape so the caller can treat sources alike:

  {
    "success": true,
    "context": {
      "kind":    "pr" | "plan",
      "title":   str,
      "purpose": str,          # the stated why, "" when absent
      "body":    str,          # full narrative
      "units":   [ {id, label, title, status, body} ],
      ...source-specific fields
    }
  }

`units` is what makes phase-level and step-level questions possible: each
entry is one addressable sub-unit of the work.

stdlib only.
"""

import argparse
import json
import os
import re
import subprocess
import sys

PLANS_DIR = os.path.expanduser("~/.claude/plans")
DEFAULT_DIFF_LIMIT = 60000


def run(cmd, check=True):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


# --------------------------------------------------------------------------
# PR source
# --------------------------------------------------------------------------

def parse_pr_ref(ref):
    if not ref:
        return None
    ref = ref.strip().lstrip("#")
    if ref.isdigit():
        return ref
    match = re.search(r"/pull/(\d+)", ref)
    return match.group(1) if match else None


def gh_pr_view(pr_number, with_comments=False):
    fields = (
        "number,title,url,state,isDraft,baseRefName,headRefName,body,"
        "additions,deletions,changedFiles,files,commits,mergedAt"
    )
    if with_comments:
        fields += ",comments,reviews"
    cmd = ["gh", "pr", "view"]
    if pr_number:
        cmd.append(pr_number)
    cmd += ["--json", fields]
    code, out, err = run(cmd, check=False)
    if code != 0:
        return None, err.strip()
    return json.loads(out), None


def gh_pr_diff(pr_number, limit):
    cmd = ["gh", "pr", "diff"]
    if pr_number:
        cmd.append(pr_number)
    code, out, _ = run(cmd, check=False)
    if code != 0:
        return "", False
    return out[:limit], len(out) > limit


# Matches "#123" and "owner/repo#123". Excludes URL fragments ("/#123", "?a=1#123")
# and hex-like tokens where the "#" is glued to a word char other than a repo name.
PR_REF_RE = re.compile(r"(?:\b[\w.-]+/[\w.-]+|(?<![\w/&=]))#(\d{2,})\b")


def extract_pr_refs(*texts):
    """Collect #NNN references in first-seen order, deduplicated."""
    seen, refs = set(), []
    for text in texts:
        for num in PR_REF_RE.findall(text or ""):
            if num not in seen:
                seen.add(num)
                refs.append(num)
    return refs


def normalize_comments(data):
    """Flatten gh's comments + reviews into one chronological list.

    Reviews with an empty body (bare approvals) carry no evidence and are dropped.
    """
    rows = []
    for c in data.get("comments") or []:
        rows.append(
            {
                "kind": "comment",
                "author": (c.get("author") or {}).get("login", ""),
                "createdAt": c.get("createdAt", ""),
                "body": (c.get("body") or "").strip(),
            }
        )
    for r in data.get("reviews") or []:
        body = (r.get("body") or "").strip()
        if not body:
            continue
        rows.append(
            {
                "kind": "review",
                "state": r.get("state", ""),
                "author": (r.get("author") or {}).get("login", ""),
                "createdAt": r.get("submittedAt", ""),
                "body": body,
            }
        )
    rows.sort(key=lambda r: r["createdAt"])
    return rows


def pr_local_fallback(base, limit):
    _, branch, _ = run(["git", "branch", "--show-current"])
    rng = f"{base}...HEAD"

    _, log, _ = run(["git", "log", rng, "--format=%h%x1f%s%x1f%b%x1e"], check=False)
    commits = []
    for entry in log.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f")
        commits.append(
            {
                "oid": parts[0],
                "messageHeadline": parts[1] if len(parts) > 1 else "",
                "messageBody": parts[2].strip() if len(parts) > 2 else "",
            }
        )

    _, numstat, _ = run(["git", "diff", rng, "--numstat"], check=False)
    files = []
    for line in numstat.strip().splitlines():
        cols = line.split("\t")
        if len(cols) == 3:
            add, dele, path = cols
            files.append(
                {
                    "path": path,
                    "additions": int(add) if add.isdigit() else 0,
                    "deletions": int(dele) if dele.isdigit() else 0,
                }
            )

    _, diff, _ = run(["git", "diff", rng], check=False)

    return {
        "source": "local-branch",
        "number": None,
        "title": commits[0]["messageHeadline"] if commits else "",
        "url": None,
        "state": "NOT_CREATED",
        "baseRefName": base.replace("origin/", ""),
        "headRefName": branch.strip(),
        "body": commits[0]["messageBody"] if commits else "",
        "files": files,
        "commits": commits,
        "diff": diff[:limit],
        "diff_truncated": len(diff) > limit,
    }


def collect_pr(args):
    pr_number = parse_pr_ref(args.ref)
    if args.ref and not pr_number:
        raise RuntimeError(f"Unparseable PR reference: {args.ref}")

    data, gh_err = gh_pr_view(pr_number, with_comments=args.comments)
    if data is None:
        raw = pr_local_fallback(args.base, args.diff_limit)
        raw["gh_error"] = gh_err
        if not raw["commits"] and not raw["files"]:
            raise RuntimeError(
                "No PR found and the local diff is empty. Run from inside the "
                "repository, or pass --ref explicitly."
            )
    else:
        diff, truncated = gh_pr_diff(pr_number, args.diff_limit)
        raw = dict(data)
        raw["source"] = "github-pr"
        raw["diff"] = diff
        raw["diff_truncated"] = truncated

    # One unit per commit. A single-commit PR yields one unit, which correctly
    # means "there is nothing smaller to quiz on".
    units = [
        {
            "id": c["oid"],
            "label": "commit",
            "title": c["messageHeadline"],
            "status": "done",
            "body": c.get("messageBody", ""),
        }
        for c in raw.get("commits", [])
    ]

    body = (raw.get("body") or "").strip()
    comments = normalize_comments(raw) if args.comments else []
    raw.pop("comments", None)
    raw.pop("reviews", None)
    own = str(raw.get("number") or "")
    commit_texts = [f"{u['title']}\n{u['body']}" for u in units]
    refs = extract_pr_refs(body, *(c["body"] for c in comments), *commit_texts)
    raw.update(
        {
            "kind": "pr",
            "purpose": body,
            "purpose_present": bool(body),
            "units": units,
            "comments": comments,
            "referenced_prs": [r for r in refs if r != own],
        }
    )
    return raw


# --------------------------------------------------------------------------
# Log search (chain discovery by keyword)
# --------------------------------------------------------------------------

SUBJECT_PR_RE = re.compile(r"\(#(\d+)\)\s*$|Merge pull request #(\d+)")


def log_search(args):
    cmd = ["git", "log", "--no-merges", f"--since={args.since}", "-i"]
    for kw in args.grep:
        cmd.append(f"--grep={kw}")
    if args.all_match:
        cmd.append("--all-match")
    cmd.append("--format=%h%x1f%ad%x1f%s%x1f%b%x1e")
    cmd.append("--date=short")
    code, out, err = run(cmd, check=False)
    if code != 0:
        raise RuntimeError(f"git log failed (run inside the repository): {err.strip()}")
    rows = []
    for entry in out.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f")
        sha, date, subject = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
        body = parts[3].strip() if len(parts) > 3 else ""
        m = SUBJECT_PR_RE.search(subject)
        pr = (m.group(1) or m.group(2)) if m else None
        rows.append(
            {
                "sha": sha,
                "date": date,
                "subject": subject,
                "pr": pr,
                "referenced_prs": extract_pr_refs(body),
            }
        )
    rows = rows[: args.limit]
    return {"keywords": args.grep, "since": args.since, "commits": rows}


# --------------------------------------------------------------------------
# Plan source
# --------------------------------------------------------------------------

def split_frontmatter(text):
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[3:end], text[end + 4:]


def parse_plan_todos(front):
    """Parse the `todos:` list without a YAML dependency.

    The plan writer emits a fixed shape (step / title / status / completed_at),
    so a targeted line parser is enough and avoids a third-party import. A plan
    hand-edited into a different shape simply yields fewer units.
    """
    todos = []
    current = None
    in_todos = False
    for line in front.splitlines():
        if re.match(r"^todos:\s*$", line):
            in_todos = True
            continue
        if in_todos and re.match(r"^[a-zA-Z_]+:", line):
            break  # next top-level key
        if not in_todos:
            continue
        item = re.match(r"^-\s+step:\s*(\d+)", line)
        if item:
            if current:
                todos.append(current)
            current = {"step": int(item.group(1)), "title": "", "status": ""}
            continue
        if current is None:
            continue
        for key in ("title", "status", "completed_at"):
            m = re.match(rf"^\s+{key}:\s*(.*)$", line)
            if m:
                current[key] = m.group(1).strip().strip("'\"")
    if current:
        todos.append(current)
    return todos


def parse_plan_sections(body):
    """Map `## Heading` -> section text, preserving order."""
    sections = {}
    order = []
    name = None
    buf = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            if name:
                sections[name] = "\n".join(buf).strip()
            name = m.group(1)
            order.append(name)
            buf = []
        else:
            buf.append(line)
    if name:
        sections[name] = "\n".join(buf).strip()
    return sections, order


def find_step_detail(body, step_no):
    """Pull the `### Step N ...` block so step-level questions have substance."""
    pattern = rf"^###\s+Step\s+{step_no}\b.*$"
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start = i
            break
    if start is None:
        return ""
    out = [lines[start]]
    for line in lines[start + 1:]:
        if re.match(r"^##\s", line) or re.match(r"^###\s", line):
            break
        out.append(line)
    return "\n".join(out).strip()


def resolve_plan_path(args):
    if args.path:
        return os.path.expanduser(args.path)
    if args.name:
        name = args.name if args.name.endswith(".md") else f"{args.name}.md"
        return os.path.join(PLANS_DIR, name)
    raise RuntimeError("Pass --name or --path. Use `list-plans` to see options.")


def collect_plan(args):
    path = resolve_plan_path(args)
    if not os.path.isfile(path):
        raise RuntimeError(f"Plan not found: {path}")

    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    front, body = split_frontmatter(text)
    todos = parse_plan_todos(front)
    sections, order = parse_plan_sections(body)

    def front_value(key):
        m = re.search(rf"^{key}:\s*(.*)$", front, re.MULTILINE)
        return m.group(1).strip().strip("'\"") if m else ""

    units = [
        {
            "id": str(t["step"]),
            "label": "step",
            "title": t.get("title", ""),
            "status": t.get("status", ""),
            "body": find_step_detail(body, t["step"]),
        }
        for t in todos
    ]

    # A plan states its purpose in Summary/Goals/Context, not in one field.
    purpose_parts = [
        sections.get(k, "")
        for k in ("Summary", "Goals", "Context", "완료 조건 (DoD)")
        if sections.get(k)
    ]
    purpose = "\n\n".join(purpose_parts).strip()

    return {
        "kind": "plan",
        "source": "plan-file",
        "path": path,
        "plan_id": front_value("plan_id"),
        "title": front_value("title"),
        "state": front_value("status"),
        "purpose": purpose,
        "purpose_present": bool(purpose),
        "body": body.strip(),
        "sections": order,
        "units": units,
        "units_done": sum(1 for u in units if u["status"] == "done"),
    }


def list_plans(_args):
    if not os.path.isdir(PLANS_DIR):
        return {"plans": []}
    rows = []
    for fname in sorted(os.listdir(PLANS_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(PLANS_DIR, fname)
        with open(path, encoding="utf-8") as fh:
            head = fh.read(4000)
        front, _ = split_frontmatter(head)

        def val(key):
            m = re.search(rf"^{key}:\s*(.*)$", front, re.MULTILINE)
            return m.group(1).strip().strip("'\"") if m else ""

        rows.append(
            {
                "name": fname[:-3],
                "title": val("title"),
                "status": val("status"),
                "updated": val("updated"),
            }
        )
    rows.sort(key=lambda r: r.get("updated", ""), reverse=True)
    return {"plans": rows}


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collect a work unit as JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pr = sub.add_parser("pr", help="GitHub PR, or the current branch")
    p_pr.add_argument("--ref", help="PR number, #number, or PR URL")
    p_pr.add_argument("--base", default="origin/main")
    p_pr.add_argument("--diff-limit", type=int, default=DEFAULT_DIFF_LIMIT)
    p_pr.add_argument(
        "--comments",
        action="store_true",
        help="Also collect issue comments and non-empty reviews (chronological)",
    )
    p_pr.set_defaults(func=collect_pr)

    p_plan = sub.add_parser("plan", help="Plan file under ~/.claude/plans")
    p_plan.add_argument("--name", help="Plan name without .md")
    p_plan.add_argument("--path", help="Explicit path to a plan file")
    p_plan.set_defaults(func=collect_plan)

    p_list = sub.add_parser("list-plans", help="List available plans")
    p_list.set_defaults(func=list_plans)

    p_log = sub.add_parser("log-search", help="Find PRs by commit-log keyword")
    p_log.add_argument("--grep", action="append", required=True, help="Keyword (repeatable, OR by default)")
    p_log.add_argument("--all-match", action="store_true", help="Require every keyword")
    p_log.add_argument("--since", default="90 days ago")
    p_log.add_argument("--limit", type=int, default=30)
    p_log.set_defaults(func=log_search)

    args = parser.parse_args()

    try:
        result = args.func(args)
        if args.cmd in ("list-plans", "log-search"):
            print(json.dumps({"success": True, **result}, ensure_ascii=False))
        else:
            print(json.dumps({"success": True, "context": result}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - surface any failure as JSON
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
