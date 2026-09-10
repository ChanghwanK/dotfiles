#!/usr/bin/env python3
"""Triage a PR into an understanding grade and pick the pr:reviewer mode.

Grades answer one question: does merging this PR require the owner to hold
its theory in their head, or can a verification device stand in for that?

  A  understanding required   -> reviewer mode (questions, then a verdict)
  B  a device verifies it     -> summary mode (CI / tests are the gate)
  C  mechanical               -> summary mode

The grade is deterministic: path rules and added-line content rules from
grade_rules.json, max grade wins, flags accumulate. The caller (Claude) may
raise the grade freely and may lower it only with a stated reason; the
script never applies judgment it cannot show in `files[].rules`.

PR context comes from task:understand-quiz's collect_work_context.py so the
two skills read the same PR the same way. stdlib only.

Subcommands:
  triage    [--ref N|URL] [--base origin/main] [--context-file f.json]
  classify  --path p [--path p ...]        dry check of path rules only
  rules                                    print the loaded rule table
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "grade_rules.json")
COLLECT_SCRIPT = os.path.expanduser(
    "~/.claude/skills/task:understand-quiz/scripts/collect_work_context.py"
)
GRADE_RANK = {"C": 0, "B": 1, "A": 2}


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as fh:
        rules = json.load(fh)
    for rule in rules["path_rules"]:
        rule["_re"] = re.compile(rule["pattern"])
    for rule in rules["content_rules"]:
        rule["_applies"] = re.compile(rule["applies_to"])
        rule["_re"] = re.compile(rule["pattern"], re.MULTILINE)
    for rule in rules.get("routine", {}).values():
        if isinstance(rule, dict):
            rule["_re"] = re.compile(rule["pattern"])
    return rules


def higher(a, b):
    return a if GRADE_RANK[a] >= GRADE_RANK[b] else b


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

def collect_context(args):
    if args.context_file:
        with open(args.context_file, encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        if not os.path.isfile(COLLECT_SCRIPT):
            raise RuntimeError(f"collector missing: {COLLECT_SCRIPT}")
        cmd = [sys.executable, COLLECT_SCRIPT, "pr", "--base", args.base]
        if args.ref:
            cmd += ["--ref", args.ref]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"collector returned non-JSON: {proc.stderr.strip()}")
    if not payload.get("success"):
        raise RuntimeError(payload.get("error", "collector failed"))
    return payload["context"]


def split_added_lines(diff):
    """Map path -> added lines (without the leading '+'), from a unified diff."""
    added = {}
    current = None
    for line in diff.splitlines():
        header = re.match(r"^diff --git a/(.+?) b/(.+)$", line)
        if header:
            current = header.group(2)
            added.setdefault(current, [])
            continue
        if current is None or line.startswith("+++"):
            continue
        if line.startswith("+"):
            added[current].append(line[1:])
    return added


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def classify_path(path, rules):
    grade, matched, flags = None, [], set()
    for rule in rules["path_rules"]:
        if rule["_re"].search(path):
            matched.append({"id": rule["id"], "grade": rule["grade"], "reason": rule["reason"]})
            grade = rule["grade"] if grade is None else higher(grade, rule["grade"])
            flags.update(rule.get("flags", []))
    if grade is None:
        grade = rules["default_grade"]
        matched.append({"id": "default", "grade": grade, "reason": rules["default_reason"]})
    return grade, matched, flags


def classify_content(path, added_lines, rules):
    grade, matched, flags = None, [], set()
    text = "\n".join(added_lines)
    if not text:
        return grade, matched, flags
    for rule in rules["content_rules"]:
        if not rule["_applies"].search(path):
            continue
        hit = rule["_re"].search(text)
        if not hit:
            continue
        sample = hit.group(0).strip()[:80]
        matched.append(
            {"id": rule["id"], "grade": rule["grade"], "reason": rule["reason"], "sample": sample}
        )
        if rule["grade"]:
            grade = rule["grade"] if grade is None else higher(grade, rule["grade"])
        flags.update(rule.get("flags", []))
    return grade, matched, flags


def detect_envs(path, rules):
    tokens = set(re.split(r"[/._\-]+", path.lower()))
    return sorted(env for env, names in rules["env_tokens"].items() if tokens & set(names))


def detect_routine(added_lines, rules):
    """Name the routine pattern when every added line fits it, else None."""
    lines = [l for l in added_lines if l.strip()]
    if not lines:
        return None
    for name, rule in rules.get("routine", {}).items():
        if not isinstance(rule, dict):
            continue
        if all(rule["_re"].match(l) for l in lines):
            return name
    return None


def classify_file(path, added_lines, rules):
    p_grade, p_rules, p_flags = classify_path(path, rules)
    c_grade, c_rules, c_flags = classify_content(path, added_lines, rules)
    grade = higher(p_grade, c_grade) if c_grade else p_grade
    flags = p_flags | c_flags
    envs = detect_envs(path, rules)
    if "prod" in envs:
        flags.add("prod")
    return {
        "path": path,
        "grade": grade,
        "envs": envs,
        "flags": sorted(flags),
        "routine": detect_routine(added_lines, rules),
        "rules": p_rules + c_rules,
    }


# --------------------------------------------------------------------------
# signals and mode
# --------------------------------------------------------------------------

def verification_signals(files):
    paths = [f["path"] for f in files]
    cwd = os.getcwd()
    checks = []
    for sub in ("", "frontend"):
        pkg = os.path.join(cwd, sub, "package.json")
        if not os.path.isfile(pkg):
            continue
        with open(pkg, encoding="utf-8", errors="ignore") as fh:
            try:
                scripts = json.load(fh).get("scripts", {})
            except json.JSONDecodeError:
                scripts = {}
        if "check" in scripts:
            checks.append(f"cd {sub} && pnpm check" if sub else "pnpm check")
    makefile = os.path.join(cwd, "Makefile")
    if os.path.isfile(makefile):
        with open(makefile, encoding="utf-8", errors="ignore") as fh:
            if re.search(r"^check\s*:", fh.read(), re.MULTILINE):
                checks.append("make check")
    return {
        "ci_in_repo": os.path.isdir(os.path.join(cwd, ".github", "workflows")),
        "tests_in_diff": any(
            any(r["id"] == "test-code" for r in f["rules"]) for f in files
        ),
        "check_commands": checks,
        "diff_paths": len(paths),
    }


def select_axes(flags, rules):
    sel = rules["axis_selection"]
    wanted = set(sel["always"])
    for flag in flags:
        wanted.update(sel["by_flag"].get(flag, []))
    ordered = [a for a in sel["priority"] if a in wanted]
    ordered = ordered[: sel["max_questions"]]
    catalog = rules["axis_catalog"]
    return [{"axis": a, **catalog[a]} for a in ordered]


def decide(files, verification, rules):
    grade = "C"
    flags = set()
    for f in files:
        grade = higher(grade, f["grade"])
        flags.update(f["flags"])
    reasons = sorted(
        {r["reason"] for f in files if f["grade"] == grade for r in f["rules"] if r["grade"] == grade}
    )
    adjustment = None
    routine_names = {f["routine"] for f in files}
    all_routine = bool(files) and None not in routine_names and len(routine_names) == 1
    if grade == "A" and all_routine and "prod" not in flags:
        # Every added line is a non-prod tag bump: the pipeline is the device.
        name = routine_names.pop()
        grade = "B"
        reasons = [rules["routine"][name]["reason"]]
        adjustment = f"A -> B: 모든 파일이 관례 작업({name})이고 prod가 아님"
    if grade == "B" and not verification["ci_in_repo"]:
        # A device that does not exist cannot stand in for understanding.
        grade = "A"
        adjustment = "B -> A: 리포에 CI 워크플로우가 없어 검증 장치 부재"
    mode = "reviewer" if grade == "A" else "summary"
    return {
        "grade": grade,
        "mode": mode,
        "flags": sorted(flags),
        "grade_reasons": reasons,
        "adjustment": adjustment,
        "axes": select_axes(flags, rules) if mode == "reviewer" else [],
    }


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_triage(args):
    rules = load_rules()
    context = collect_context(args)
    added = split_added_lines(context.get("diff", ""))
    files = [
        classify_file(f["path"], added.get(f["path"], []), rules)
        for f in context.get("files", [])
    ]
    verification = verification_signals(files)
    decision = decide(files, verification, rules)
    by_grade = {g: [f["path"] for f in files if f["grade"] == g] for g in ("A", "B", "C")}
    return {
        "success": True,
        **decision,
        "files_by_grade": by_grade,
        "files": files,
        "verification": verification,
        "size": {
            "changed_files": len(files),
            "additions": sum(f.get("additions", 0) for f in context.get("files", [])),
            "deletions": sum(f.get("deletions", 0) for f in context.get("files", [])),
            "diff_truncated": context.get("diff_truncated", False),
        },
        "context": context,
    }


def cmd_classify(args):
    rules = load_rules()
    return {
        "success": True,
        "files": [classify_file(p, [], rules) for p in args.path],
    }


def cmd_rules(_args):
    rules = load_rules()
    return {
        "success": True,
        "default_grade": rules["default_grade"],
        "path_rules": [
            {k: v for k, v in r.items() if not k.startswith("_")} for r in rules["path_rules"]
        ],
        "content_rules": [
            {k: v for k, v in r.items() if not k.startswith("_")} for r in rules["content_rules"]
        ],
        "axis_selection": rules["axis_selection"],
    }


def main():
    parser = argparse.ArgumentParser(description="Grade a PR for pr:reviewer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("triage", help="Grade a PR and choose the mode")
    p.add_argument("--ref", help="PR number, #number, or URL (default: current branch)")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--context-file", help="Use a saved collector JSON instead of calling gh")
    p.set_defaults(func=cmd_triage)

    p = sub.add_parser("classify", help="Apply path rules to given paths only")
    p.add_argument("--path", action="append", required=True)
    p.set_defaults(func=cmd_classify)

    p = sub.add_parser("rules", help="Print the loaded rule table")
    p.set_defaults(func=cmd_rules)

    args = parser.parse_args()
    try:
        print(json.dumps(args.func(args), ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - surface any failure as JSON
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
