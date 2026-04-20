#!/usr/bin/env python3
"""
Obsidian 지식 베이스 링크 정합성 검증 스크립트.

커맨드:
  check  [--target broken-links|orphans|stale|metadata|tags|missing-related|all]
         [--scope notes|resources|all] [--format text|json]
  fix    --target tags [--dry-run]
"""

import argparse
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, "/Users/changhwan/.claude/skills/_lib")
from obsidian import VaultScanner, parse_frontmatter, stale_days, VAULT_BASE
from tags import normalize_tags

STALE_THRESHOLD_DAYS = 90
REQUIRED_FIELDS = {"title", "date", "type", "tags"}


def cmd_check(args):
    scanner = VaultScanner()
    scopes = _parse_scope(args.scope)
    notes = scanner.scan_all(scopes=scopes)
    targets = _parse_targets(args.target)

    issues = {"broken-links": [], "orphans": [], "stale": [], "metadata": [], "tags": [], "missing-related": []}

    if "broken-links" in targets:
        issues["broken-links"] = check_broken_links(scanner, notes)

    if "orphans" in targets:
        inbound = scanner.build_link_graph()
        issues["orphans"] = check_orphans(notes, inbound)

    if "stale" in targets:
        issues["stale"] = check_stale(notes)

    if "metadata" in targets:
        issues["metadata"] = check_metadata(notes)

    if "tags" in targets:
        issues["tags"] = check_tags(notes)

    if "missing-related" in targets:
        issues["missing-related"] = check_missing_related(notes)

    total = sum(len(v) for v in issues.values())
    auto_fixable = len(issues["tags"])

    if args.format == "json":
        print(json.dumps({
            "date": str(date.today()),
            "total": total,
            "auto_fixable": auto_fixable,
            "issues": issues,
        }, ensure_ascii=False, indent=2))
    else:
        _print_text_report(issues, total, auto_fixable)


def cmd_fix(args):
    if args.target != "tags":
        print(f"auto-fix는 tags 타겟만 지원합니다. 입력: {args.target}")
        sys.exit(1)

    scanner = VaultScanner()
    notes = scanner.scan_all()
    tag_issues = check_tags(notes)

    if not tag_issues:
        print("태그 이슈 없음. 수정 불필요.")
        return

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}태그 정규화 대상: {len(tag_issues)}개")
    print()

    fixed = 0
    for issue in tag_issues:
        fpath = issue["filepath"]
        old_tags = issue["current_tags"]
        new_tags = issue["normalized_tags"]

        print(f"  {issue['filename']}")
        print(f"    현재: {old_tags}")
        print(f"    변경: {new_tags}")

        if not args.dry_run:
            _rewrite_tags_in_file(fpath, old_tags, new_tags)
            fixed += 1

    if args.dry_run:
        print(f"\n[DRY-RUN] {len(tag_issues)}개 파일이 수정될 예정입니다.")
    else:
        print(f"\n{fixed}개 파일 태그 정규화 완료.")


def check_broken_links(scanner: VaultScanner, notes) -> list:
    issues = []
    for note in notes:
        for raw_link in note.outlinks:
            pipe = raw_link.find("|")
            target = raw_link[:pipe] if pipe != -1 else raw_link
            target = target.strip()
            if target.startswith("http") or target.startswith("#"):
                continue
            resolved = scanner.resolve_link(raw_link)
            if not resolved:
                issues.append({
                    "filename": note.filename,
                    "filepath": note.filepath,
                    "broken_link": f"[[{raw_link}]]",
                    "target": target,
                    "severity": "error",
                })
    return issues


def check_orphans(notes, inbound: dict) -> list:
    issues = []
    for note in notes:
        if note.note_type == "daily":
            continue
        refs = inbound.get(note.filename, set())
        if not refs:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "inbound_count": 0,
                "severity": "warning",
            })
    return issues


def check_stale(notes) -> list:
    today = date.today()
    issues = []
    for note in notes:
        if note.note_type == "daily":
            continue
        if not note.last_reviewed or note.last_reviewed in ("", "None"):
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "last_reviewed": note.last_reviewed,
                "days_since_review": None,
                "reason": "last_reviewed 필드 없음",
                "severity": "info",
            })
            continue
        days = stale_days(note.last_reviewed, today)
        if days is not None and days > STALE_THRESHOLD_DAYS:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "last_reviewed": note.last_reviewed,
                "days_since_review": days,
                "reason": f"{days}일 미검토",
                "severity": "info",
            })
    return issues


def check_metadata(notes) -> list:
    issues = []
    for note in notes:
        if note.note_type == "daily":
            continue
        fm, _ = parse_frontmatter(note.filepath)
        missing = []
        for field in REQUIRED_FIELDS:
            val = fm.get(field)
            if val is None or val == "" or val == []:
                missing.append(field)
        if missing:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "missing_fields": missing,
                "severity": "warning",
            })
    return issues


def check_tags(notes) -> list:
    issues = []
    for note in notes:
        if note.note_type == "daily":
            continue
        if not note.tags:
            continue
        normalized = normalize_tags(note.tags)
        if set(normalized) != set(note.tags):
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "current_tags": note.tags,
                "normalized_tags": normalized,
                "severity": "warning",
            })
    return issues


def check_missing_related(notes) -> list:
    issues = []
    for note in notes:
        if note.note_type != "learning-note":
            continue
        if "## 관련 노트" not in note.content_text and "## Related" not in note.content_text:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "severity": "info",
            })
    return issues


def _rewrite_tags_in_file(filepath: str, old_tags: list, new_tags: list):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # frontmatter의 tags 블록을 새 태그로 교체
    # 두 가지 형식 지원: list 형식과 inline 형식
    if not new_tags:
        new_tags_str = "tags: []"
    else:
        items = "\n".join(f"  - {t}" for t in new_tags)
        new_tags_str = f"tags:\n{items}"

    # inline: tags: [a, b]
    content = re.sub(r'tags:\s*\[.*?\]', new_tags_str, content)
    # block: tags:\n  - a\n  - b
    content = re.sub(r'tags:\n(  - .+\n)*', new_tags_str + "\n", content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def _print_text_report(issues: dict, total: int, auto_fixable: int):
    today = date.today().isoformat()
    print(f"obsidian:lint report — {today}")
    print("=" * 50)
    print()

    severity_order = [
        ("broken-links", "error", "ERROR"),
        ("metadata", "warning", "WARNING"),
        ("tags", "warning", "WARNING"),
        ("orphans", "warning", "WARNING"),
        ("missing-related", "info", "INFO"),
        ("stale", "info", "INFO"),
    ]

    for target, _, label in severity_order:
        items = issues.get(target, [])
        if not items:
            continue
        print(f"[{label}] {target}: {len(items)}개")
        for item in items[:10]:
            fname = item.get("filename", "")
            if target == "broken-links":
                print(f"  - {fname} → {item.get('broken_link')} 대상 없음")
            elif target == "orphans":
                print(f"  - {fname} (인바운드 링크 0개)")
            elif target == "stale":
                reason = item.get("reason", "")
                print(f"  - {fname} ({reason})")
            elif target == "metadata":
                missing = ", ".join(item.get("missing_fields", []))
                print(f"  - {fname} — {missing} 누락")
            elif target == "tags":
                cur = item.get("current_tags", [])
                new = item.get("normalized_tags", [])
                print(f"  - {fname}: {cur} → {new}")
            elif target == "missing-related":
                print(f"  - {fname}")
        if len(items) > 10:
            print(f"  ... 외 {len(items) - 10}개")
        print()

    print(f"총 이슈: {total}개")
    if auto_fixable:
        print(f"auto-fix 가능: tags 정규화 {auto_fixable}개 → obsidian-lint.py fix --target tags")


def _parse_scope(scope_str: str) -> tuple:
    if not scope_str or scope_str == "all":
        return ("notes", "resources")
    mapping = {
        "notes": ("notes",),
        "resources": ("resources",),
        "all": ("notes", "resources"),
    }
    return mapping.get(scope_str, ("notes", "resources"))


def _parse_targets(target_str: str) -> set:
    all_targets = {"broken-links", "orphans", "stale", "metadata", "tags", "missing-related"}
    if not target_str or target_str == "all":
        return all_targets
    return {t.strip() for t in target_str.split(",")} & all_targets


def main():
    parser = argparse.ArgumentParser(description="Obsidian 링크 정합성 검증")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="이슈 검사")
    p_check.add_argument("--target", default="all",
                         help="검사 항목: broken-links|orphans|stale|metadata|tags|missing-related|all")
    p_check.add_argument("--scope", default="notes", help="검사 범위: notes|resources|all")
    p_check.add_argument("--format", default="text", choices=["text", "json"])

    p_fix = sub.add_parser("fix", help="자동 수정 (tags만 지원)")
    p_fix.add_argument("--target", required=True, help="수정 항목: tags")
    p_fix.add_argument("--dry-run", action="store_true", help="변경 미리보기 (파일 수정 없음)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "check":
        cmd_check(args)
    elif args.command == "fix":
        cmd_fix(args)


if __name__ == "__main__":
    main()
