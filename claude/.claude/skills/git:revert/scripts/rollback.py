#!/usr/bin/env python3
"""GitOps rollback helper — commit search & impact analysis."""

import argparse
import json
import subprocess
import sys
import re
from datetime import datetime


def run_git(args: list[str], check: bool = True) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, check=check
    )
    return result.stdout.strip()


def parse_file_path(path: str) -> dict | None:
    """Parse src/sphere/circle/env/file into components."""
    m = re.match(r'^src/([^/]+)/([^/]+)/(infra-k8s-[^/]+)/(.+)$', path)
    if m:
        return {
            "sphere": m.group(1),
            "circle": m.group(2),
            "env": m.group(3),
            "file": m.group(4),
        }
    # common values
    m = re.match(r'^src/([^/]+)/([^/]+)/common/(.+)$', path)
    if m:
        return {
            "sphere": m.group(1),
            "circle": m.group(2),
            "env": "common",
            "file": m.group(3),
        }
    return None


def get_commit_files(commit_hash: str) -> list[str]:
    """Get list of files changed in a commit."""
    output = run_git(["show", "--name-only", "--format=", commit_hash])
    return [f for f in output.split("\n") if f.strip()]


def get_commit_info(commit_hash: str) -> dict:
    """Get detailed commit info."""
    fmt = "%H%n%h%n%s%n%an%n%aI%n%P"
    output = run_git(["show", "-s", f"--format={fmt}", commit_hash])
    lines = output.split("\n")
    parents = lines[5].split() if len(lines) > 5 else []
    files = get_commit_files(commit_hash)

    spheres = set()
    circles = set()
    envs = set()
    parsed_files = []

    for f in files:
        parsed = parse_file_path(f)
        if parsed:
            spheres.add(parsed["sphere"])
            circles.add(parsed["circle"])
            if parsed["env"] != "common":
                envs.add(parsed["env"])
            parsed_files.append(parsed)

    return {
        "hash": lines[0],
        "short_hash": lines[1],
        "message": lines[2],
        "author": lines[3],
        "date": lines[4],
        "is_merge": len(parents) > 1,
        "parents": parents,
        "files": files,
        "parsed_files": parsed_files,
        "spheres": sorted(spheres),
        "circles": sorted(circles),
        "envs": sorted(envs),
    }


def build_log_cmd(args) -> list[str]:
    """Build git log command from search args."""
    cmd = ["log", "--format=%H", f"--max-count={args.limit}"]

    if args.since:
        cmd.append(f"--since={args.since}")

    if args.grep:
        cmd.append(f"--grep={args.grep}")

    if args.tag:
        cmd.append(f"--grep={args.tag}")

    if args.chart_version:
        cmd.append(f"--grep={args.chart_version}")

    if args.author:
        cmd.append(f"--author={args.author}")

    if hasattr(args, 'hash') and args.hash:
        # Direct hash lookup
        return ["show", "-s", "--format=%H", args.hash]

    # Build path filter
    paths = []
    if args.sphere and args.circle and args.env:
        paths.append(f"src/{args.sphere}/{args.circle}/{args.env}/")
    elif args.sphere and args.circle:
        paths.append(f"src/{args.sphere}/{args.circle}/")
    elif args.sphere:
        paths.append(f"src/{args.sphere}/")

    if paths:
        cmd.append("--")
        cmd.extend(paths)

    return cmd


def check_conflicts(commit_hash: str, files: list[str]) -> list[dict]:
    """Find commits after the target that modified the same files."""
    conflicts = []
    for f in files:
        # Find commits that modified this file after the target commit
        output = run_git(
            ["log", "--format=%H %s", f"{commit_hash}..HEAD", "--", f],
            check=False
        )
        if output.strip():
            for line in output.strip().split("\n"):
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    conflicts.append({
                        "file": f,
                        "hash": parts[0][:12],
                        "message": parts[1],
                    })
    return conflicts


def cmd_search(args):
    """Search for rollback candidate commits."""
    if args.hash:
        hashes = [args.hash]
    else:
        log_cmd = build_log_cmd(args)
        output = run_git(log_cmd, check=False)
        if not output.strip():
            print(json.dumps({"commits": [], "count": 0}))
            return
        hashes = [h for h in output.split("\n") if h.strip()]

    commits = []
    for h in hashes:
        try:
            info = get_commit_info(h)
            # Apply post-filters
            if args.sphere and args.sphere not in info["spheres"]:
                continue
            if args.circle and args.circle not in info["circles"]:
                continue
            if args.env and args.env not in info["envs"]:
                continue
            commits.append(info)
        except subprocess.CalledProcessError:
            continue

    result = {
        "commits": commits,
        "count": len(commits),
    }
    print(json.dumps(result, indent=2, default=str))


def cmd_analyze(args):
    """Analyze impact of reverting specified commits."""
    hashes = [h.strip() for h in args.commits.split(",")]

    commits = []
    all_files = set()
    all_spheres = set()
    all_circles = set()
    all_envs = set()
    has_prod = False
    has_merge = False

    for h in hashes:
        try:
            info = get_commit_info(h)
            commits.append(info)
            all_files.update(info["files"])
            all_spheres.update(info["spheres"])
            all_circles.update(info["circles"])
            all_envs.update(info["envs"])
            if any("prod" in e for e in info["envs"]):
                has_prod = True
            if info["is_merge"]:
                has_merge = True
        except subprocess.CalledProcessError:
            print(json.dumps({"error": f"Commit not found: {h}"}), file=sys.stderr)
            sys.exit(1)

    # Check for potential conflicts
    all_conflicts = []
    for h in hashes:
        info = next(c for c in commits if c["hash"] == h or c["short_hash"] == h)
        conflicts = check_conflicts(info["hash"], info["files"])
        all_conflicts.extend(conflicts)

    # Get reverse diff for each commit
    diffs = []
    for h in hashes:
        diff = run_git(["diff", f"{h}..{h}~1", "--stat"], check=False)
        diffs.append({"hash": h, "stat": diff})

    result = {
        "commits": [{
            "hash": c["short_hash"],
            "message": c["message"],
            "date": c["date"],
            "is_merge": c["is_merge"],
            "files_count": len(c["files"]),
        } for c in commits],
        "impact": {
            "files": sorted(all_files),
            "files_count": len(all_files),
            "spheres": sorted(all_spheres),
            "circles": sorted(all_circles),
            "envs": sorted(all_envs),
        },
        "warnings": {
            "has_prod": has_prod,
            "has_merge": has_merge,
            "conflict_risk": len(all_conflicts) > 0,
            "conflicts": all_conflicts[:20],  # Limit output
        },
        "diffs": diffs,
    }
    print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="GitOps rollback helper")
    sub = parser.add_subparsers(dest="command", required=True)

    # search subcommand
    sp = sub.add_parser("search", help="Search rollback candidate commits")
    sp.add_argument("--sphere", help="Filter by sphere (e.g., santa, tech)")
    sp.add_argument("--circle", help="Filter by circle (e.g., gateway-server)")
    sp.add_argument("--env", help="Filter by env (e.g., infra-k8s-dev)")
    sp.add_argument("--tag", help="Search for image tag in commit message")
    sp.add_argument("--chart-version", help="Search for chart version in message")
    sp.add_argument("--grep", help="Custom grep pattern for commit message")
    sp.add_argument("--author", help="Filter by commit author name")
    sp.add_argument("--hash", help="Look up a specific commit hash")
    sp.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    sp.add_argument("--since", help="Search since date (e.g., '1 week ago')")

    # analyze subcommand
    ap = sub.add_parser("analyze", help="Analyze revert impact")
    ap.add_argument("--commits", required=True,
                    help="Comma-separated commit hashes to analyze")

    args = parser.parse_args()
    if args.command == "search":
        cmd_search(args)
    elif args.command == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    main()
