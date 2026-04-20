#!/usr/bin/env python3
"""
LLM Wiki 정합성 검증 스크립트.

커맨드:
  check  [--target broken-links|index-sync|index-dead|metadata|type-invalid|tags|orphans|missing-related|stale|all]
         [--format text|json]
  fix    --target tags [--dry-run]
"""

import argparse
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, "/Users/changhwan/.claude/skills/_lib")
from obsidian import VaultScanner, parse_frontmatter, stale_days, VAULT_BASE, slugify_for_match
from tags import normalize_tags

STALE_THRESHOLD_DAYS = 90
REQUIRED_FIELDS = {"title", "date", "type", "tags"}
WIKI_NOTE_TYPES = {"concept", "system", "incident", "synthesis", "career"}
WIKI_META_FILES = {"_index.md", "_log.md", "_overview.md", "schema.md"}
WIKI_DIR = os.path.join(VAULT_BASE, "04. Wiki")


def cmd_check(args):
    scanner = VaultScanner()
    notes = scanner.scan_all(scopes=("wiki",))
    targets = _parse_targets(args.target)

    issues = {k: [] for k in [
        "broken-links", "index-sync", "index-dead",
        "metadata", "type-invalid", "tags",
        "orphans", "missing-related", "stale",
    ]}

    if "broken-links" in targets:
        issues["broken-links"] = check_broken_links(scanner, notes)

    if "index-sync" in targets:
        issues["index-sync"] = check_index_sync(scanner)

    if "index-dead" in targets:
        issues["index-dead"] = check_index_dead(scanner)

    if "metadata" in targets:
        issues["metadata"] = check_metadata(notes)

    if "type-invalid" in targets:
        issues["type-invalid"] = check_type_invalid(notes)

    if "tags" in targets:
        issues["tags"] = check_tags(notes)

    if "orphans" in targets:
        inbound = _build_wiki_link_graph(scanner, notes)
        issues["orphans"] = check_orphans(notes, inbound)

    if "missing-related" in targets:
        issues["missing-related"] = check_missing_related(notes)

    if "stale" in targets:
        issues["stale"] = check_stale(notes)

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
    notes = scanner.scan_all(scopes=("wiki",))
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


# ── 체크 함수들 ──────────────────────────────────────────────────────────────

def check_broken_links(scanner: VaultScanner, notes) -> list:
    """[[링크]] 대상 파일 없음"""
    issues = []
    for note in notes:
        for raw_link in note.outlinks:
            pipe = raw_link.find("|")
            target = (raw_link[:pipe] if pipe != -1 else raw_link).strip()
            if target.startswith("http") or target.startswith("#"):
                continue
            if not scanner.resolve_link(raw_link):
                issues.append({
                    "filename": note.filename,
                    "filepath": note.filepath,
                    "broken_link": f"[[{raw_link}]]",
                    "target": target,
                    "severity": "error",
                })
    return issues


def check_index_sync(scanner: VaultScanner) -> list:
    """04. Wiki/ 노트가 _index.md에 등록되어 있는지 확인"""
    index_path = os.path.join(WIKI_DIR, "_index.md")
    if not os.path.exists(index_path):
        return [{"filename": "_index.md", "filepath": index_path,
                 "reason": "_index.md 파일 없음", "severity": "error"}]

    with open(index_path, encoding="utf-8") as f:
        raw = f.read()

    # 인라인 코드/코드블록 제거 후 wikilink 추출
    body = re.sub(r'```.*?```', '', raw, flags=re.DOTALL)
    body = re.sub(r'`[^`\n]*`', '', body)

    linked_stems: set[str] = set()
    for m in re.finditer(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', body):
        text = m.group(1).strip()
        linked_stems.add(text.lower())
        linked_stems.add(slugify_for_match(text))

    issues = []
    for root, dirs, files in os.walk(WIKI_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            if fname in WIKI_META_FILES:
                continue
            stem = fname[:-3]
            if stem.lower() not in linked_stems and slugify_for_match(stem) not in linked_stems:
                issues.append({
                    "filename": fname,
                    "filepath": os.path.join(root, fname),
                    "reason": "_index.md에 미등록",
                    "severity": "error",
                })
    return issues


def check_index_dead(scanner: VaultScanner) -> list:
    """_index.md 항목 중 실제 파일이 없는 링크 탐지"""
    index_path = os.path.join(WIKI_DIR, "_index.md")
    if not os.path.exists(index_path):
        return []

    with open(index_path, encoding="utf-8") as f:
        raw = f.read()

    # 인라인 코드/코드블록 제거 후 wikilink 추출
    body = re.sub(r'```.*?```', '', raw, flags=re.DOTALL)
    body = re.sub(r'`[^`\n]*`', '', body)

    issues = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', body):
        raw_link = m.group(1)
        pipe = raw_link.find("|")
        target = (raw_link[:pipe] if pipe != -1 else raw_link).strip()
        if target.startswith("http") or target.startswith("#"):
            continue
        if not scanner.resolve_link(raw_link):
            issues.append({
                "filename": "_index.md",
                "filepath": index_path,
                "broken_link": f"[[{raw_link}]]",
                "target": target,
                "severity": "error",
            })
    return issues


def check_metadata(notes) -> list:
    """필수 frontmatter 필드 누락 탐지"""
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
            continue
        fm, _ = parse_frontmatter(note.filepath)
        missing = [f for f in REQUIRED_FIELDS if not fm.get(f) and fm.get(f) != 0]
        if missing:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "missing_fields": missing,
                "severity": "warning",
            })
    return issues


def check_type_invalid(notes) -> list:
    """type 필드가 Wiki 허용 값 외인 노트 탐지"""
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
            continue
        if note.note_type and note.note_type not in WIKI_NOTE_TYPES:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "current_type": note.note_type,
                "valid_types": sorted(WIKI_NOTE_TYPES),
                "severity": "warning",
            })
    return issues


def check_tags(notes) -> list:
    """domain/ 형식 미준수 태그 탐지"""
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
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


def check_orphans(notes, inbound: dict) -> list:
    """인바운드 링크 0개인 Wiki 노트 탐지 (_index.md 링크 포함)"""
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
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


def check_missing_related(notes) -> list:
    """concept/incident/synthesis 타입 노트에 관련 노트 섹션 없음"""
    related_types = {"concept", "incident", "synthesis"}
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
            continue
        if note.note_type not in related_types:
            continue
        if "## 관련 노트" not in note.content_text and "## Related" not in note.content_text:
            issues.append({
                "filename": note.filename,
                "filepath": note.filepath,
                "severity": "info",
            })
    return issues


def check_stale(notes) -> list:
    """last_reviewed 없음 또는 90일 초과 노트"""
    today = date.today()
    issues = []
    for note in notes:
        if note.filename in WIKI_META_FILES:
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


# ── 내부 유틸 ────────────────────────────────────────────────────────────────

def _build_wiki_link_graph(scanner: VaultScanner, notes) -> dict:
    """wiki 노트 기반 역방향 링크 그래프 (_index.md의 링크도 포함)"""
    inbound: dict = {}
    for note in notes:
        inbound.setdefault(note.filename, set())

    for note in notes:
        for raw_link in note.outlinks:
            resolved = scanner.resolve_link(raw_link)
            if resolved:
                target_fname = os.path.basename(resolved)
                inbound.setdefault(target_fname, set())
                inbound[target_fname].add(note.filename)

    return inbound


def _rewrite_tags_in_file(filepath: str, old_tags: list, new_tags: list):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    if not new_tags:
        new_tags_str = "tags: []"
    else:
        items = "\n".join(f"  - {t}" for t in new_tags)
        new_tags_str = f"tags:\n{items}"

    content = re.sub(r'tags:\s*\[.*?\]', new_tags_str, content)
    content = re.sub(r'tags:\n(  - .+\n)*', new_tags_str + "\n", content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def _print_text_report(issues: dict, total: int, auto_fixable: int):
    today = date.today().isoformat()
    print(f"wiki:lint report — {today}")
    print("=" * 50)
    print()

    severity_order = [
        ("broken-links",    "ERROR"),
        ("index-dead",      "ERROR"),
        ("index-sync",      "ERROR"),
        ("metadata",        "WARNING"),
        ("type-invalid",    "WARNING"),
        ("tags",            "WARNING"),
        ("orphans",         "WARNING"),
        ("missing-related", "INFO"),
        ("stale",           "INFO"),
    ]

    for target, label in severity_order:
        items = issues.get(target, [])
        if not items:
            continue
        print(f"[{label}] {target}: {len(items)}개")
        for item in items[:10]:
            fname = item.get("filename", "")
            if target in ("broken-links", "index-dead"):
                print(f"  - {fname} → {item.get('broken_link')} 대상 없음")
            elif target == "index-sync":
                print(f"  - {fname} ({item.get('reason', '')})")
            elif target == "orphans":
                print(f"  - {fname} (인바운드 링크 0개)")
            elif target == "stale":
                print(f"  - {fname} ({item.get('reason', '')})")
            elif target == "metadata":
                missing = ", ".join(item.get("missing_fields", []))
                print(f"  - {fname} — {missing} 누락")
            elif target == "type-invalid":
                cur = item.get("current_type", "")
                valid = "|".join(item.get("valid_types", []))
                print(f"  - {fname}: type='{cur}' (허용: {valid})")
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
        print(f"auto-fix 가능: tags 정규화 {auto_fixable}개 → wiki-lint.py fix --target tags")


def _parse_targets(target_str: str) -> set:
    all_targets = {
        "broken-links", "index-sync", "index-dead",
        "metadata", "type-invalid", "tags",
        "orphans", "missing-related", "stale",
    }
    if not target_str or target_str == "all":
        return all_targets
    return {t.strip() for t in target_str.split(",")} & all_targets


def main():
    parser = argparse.ArgumentParser(description="LLM Wiki 정합성 검증")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="이슈 검사")
    p_check.add_argument(
        "--target", default="all",
        help="검사 항목: broken-links|index-sync|index-dead|metadata|type-invalid|tags|orphans|missing-related|stale|all",
    )
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
