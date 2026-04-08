#!/usr/bin/env python3
"""Helm chart version up helper.

Subcommands:
  info      - 현재 버전, git diff, 변경 파일 목록 출력
  bump      - Chart.yaml 버전 업데이트
  changelog - git log를 파싱하여 릴리스 노트 초안 생성
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
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


EXCLUDE_PATTERNS = [
    r"[Bb]ump.*version",
    r"[Uu]pdate.*version",
    r"[Uu]pdate.*[Cc]hart",
    r"[Tt]rigger CI",
    r"chart version up",
    r"[Vv]ersion up",
    r"^Merge",
    r"chore: [Uu]pdate version",
    r"chore: [Uu]pdate chart",
    r"chore: [Aa]dd.*version",
]

CATEGORY_MAP = {
    "feat": "Added",
    "fix": "Fixed",
    "refactor": "Changed",
    "perf": "Changed",
    "style": "Changed",
    "docs": "Changed",
    "chore": None,  # 기본 제외 (필터 통과 시만 포함)
    "test": None,
    "ci": None,
    "build": None,
}


def _should_exclude(message: str) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, message):
            return True
    return False


def _classify_commit(message: str) -> tuple[str, str]:
    """Returns (category, body) for a commit message."""
    m = re.match(r"^(\w+)(?:\([^)]*\))?!?:\s*(.+)$", message)
    if m:
        prefix = m.group(1)
        body = m.group(2)
        category = CATEGORY_MAP.get(prefix)
        return category, body
    return None, message


def cmd_changelog(args):
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

    version = args.version or current_version

    # Find range
    last_commit = find_last_version_commit(chart_path, repo_root)
    if last_commit:
        log = run_git(
            ["log", "--format=%H %s", f"{last_commit}..HEAD", "--", f"charts/{args.chart}/"],
            repo_root,
        )
    else:
        log = run_git(
            ["log", "--format=%H %s", "-30", "--", f"charts/{args.chart}/"],
            repo_root,
        )

    lines = [l.strip() for l in log.strip().split("\n") if l.strip()]

    categories: dict[str, list[str]] = {"Added": [], "Fixed": [], "Changed": []}
    uncategorized: list[str] = []

    for line in lines:
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        message = parts[1]
        if _should_exclude(message):
            continue
        category, body = _classify_commit(message)
        if category and category in categories:
            categories[category].append(body)
        elif category is None and not re.match(r"^\w+(?:\([^)]*\))?!?:", message):
            # 프리픽스 없는 커밋은 uncategorized로
            uncategorized.append(message)
        # category가 None(chore 등)이고 미제외면 uncategorized
        elif category is None:
            pass  # chore/test/ci 등은 제외

    today = date.today().isoformat()

    if args.format == "json":
        result = {
            "success": True,
            "chart": args.chart,
            "version": version,
            "date": today,
            "categories": categories,
            "uncategorized": uncategorized,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # markdown 형식
        lines_out = [f"## [{version}] - {today}", ""]
        has_content = False
        for cat in ["Added", "Fixed", "Changed"]:
            items = categories[cat]
            if items:
                has_content = True
                lines_out.append(f"### {cat}")
                for item in items:
                    lines_out.append(f"- {item}")
                lines_out.append("")
        if uncategorized:
            has_content = True
            lines_out.append("### Changed")
            for item in uncategorized:
                lines_out.append(f"- {item}")
            lines_out.append("")
        if not has_content:
            lines_out.append("_변경사항 없음 또는 자동 분류 불가_")
            lines_out.append("")
        print("\n".join(lines_out))


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

    # changelog
    p_cl = sub.add_parser("changelog", help="Generate release notes draft from git log")
    p_cl.add_argument("--chart", required=True, help="Chart name")
    p_cl.add_argument("--version", help="Version string for the header (defaults to current Chart.yaml version)")
    p_cl.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format")

    args = parser.parse_args()
    {"info": cmd_info, "bump": cmd_bump, "changelog": cmd_changelog}[args.command](args)


if __name__ == "__main__":
    main()
