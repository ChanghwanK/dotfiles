#!/usr/bin/env python3
"""Helm chart version up helper.

Subcommands:
  info   - 현재 버전, git diff, 변경 파일 목록 출력
  bump   - Chart.yaml 버전 업데이트
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=cwd
    )
    return result.stdout.strip()


def parse_version(version_str: str) -> tuple[int, int, int, str]:
    """Parse version string. Returns (major, minor, patch, prerelease)."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", version_str)
    if not m:
        return (0, 0, 0, "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))


def next_version(current: str, bump_type: str) -> str:
    """Compute next version based on bump type."""
    major, minor, patch, _ = parse_version(current)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def find_last_version_commit(chart_path: str, repo_root: str) -> str:
    """Find the commit hash where Chart.yaml version was last changed."""
    rel_path = os.path.relpath(
        os.path.join(chart_path, "Chart.yaml"), repo_root
    )
    log = run_git(
        ["log", "--oneline", "--follow", "-20", "--", rel_path], repo_root
    )
    lines = log.strip().split("\n") if log.strip() else []
    if len(lines) >= 2:
        return lines[1].split()[0]
    return ""


def cmd_info(args):
    repo_root = args.repo_root
    chart_path = os.path.join(repo_root, "charts", args.chart)
    chart_yaml = os.path.join(chart_path, "Chart.yaml")

    if not os.path.exists(chart_yaml):
        print(json.dumps({"success": False, "error": f"Chart.yaml not found: {chart_yaml}"}, ensure_ascii=False))
        sys.exit(1)

    # Parse current version
    with open(chart_yaml) as f:
        content = f.read()
    m = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
    current_version = m.group(1).strip() if m else "unknown"

    # Find last version commit
    last_commit = find_last_version_commit(chart_path, repo_root)

    # Get git log since last version commit
    if last_commit:
        log = run_git(
            ["log", "--oneline", f"{last_commit}..HEAD", "--", f"charts/{args.chart}/"],
            repo_root,
        )
    else:
        log = run_git(
            ["log", "--oneline", "-10", "--", f"charts/{args.chart}/"],
            repo_root,
        )

    # Get changed files (staged + unstaged)
    diff_files = run_git(
        ["diff", "--name-only", "HEAD", "--", f"charts/{args.chart}/"],
        repo_root,
    )

    # Get diff stat
    diff_stat = run_git(
        ["diff", "--stat", "HEAD", "--", f"charts/{args.chart}/"],
        repo_root,
    )

    # Compute next versions
    result = {
        "success": True,
        "chart": args.chart,
        "current_version": current_version,
        "next_patch": next_version(current_version, "patch"),
        "next_minor": next_version(current_version, "minor"),
        "last_version_commit": last_commit,
        "git_log": log,
        "changed_files": diff_files,
        "diff_stat": diff_stat,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_bump(args):
    repo_root = args.repo_root
    chart_yaml = os.path.join(repo_root, "charts", args.chart, "Chart.yaml")

    if not os.path.exists(chart_yaml):
        print(json.dumps({"success": False, "error": f"Chart.yaml not found: {chart_yaml}"}, ensure_ascii=False))
        sys.exit(1)

    with open(chart_yaml) as f:
        content = f.read()

    m = re.search(r"^version:\s*(.+)$", content, re.MULTILINE)
    old_version = m.group(1).strip() if m else "unknown"

    # Determine new version
    if args.version:
        new_version = args.version
    elif args.bump_type:
        new_version = next_version(old_version, args.bump_type)
    else:
        new_version = next_version(old_version, "patch")

    # Replace version in Chart.yaml
    new_content = re.sub(
        r"^(version:\s*)(.+)$",
        f"\\g<1>{new_version}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    with open(chart_yaml, "w") as f:
        f.write(new_content)

    result = {
        "success": True,
        "chart": args.chart,
        "old_version": old_version,
        "new_version": new_version,
        "chart_yaml": chart_yaml,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Helm chart versionup helper")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Repository root path")
    sub = parser.add_subparsers(dest="command", required=True)

    # info
    p_info = sub.add_parser("info", help="Show current version and changes")
    p_info.add_argument("--chart", required=True, help="Chart name (e.g. webserver)")

    # bump
    p_bump = sub.add_parser("bump", help="Bump chart version")
    p_bump.add_argument("--chart", required=True, help="Chart name")
    p_bump.add_argument("--version", help="Explicit version (e.g. 0.3.52)")
    p_bump.add_argument("--bump-type", choices=["patch", "minor", "major"], help="Bump type")

    args = parser.parse_args()
    {"info": cmd_info, "bump": cmd_bump}[args.command](args)


if __name__ == "__main__":
    main()
