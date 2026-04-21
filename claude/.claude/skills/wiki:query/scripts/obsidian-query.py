#!/usr/bin/env python3
"""
Obsidian 지식 베이스 검색 스크립트.

커맨드:
  search   --query TEXT [--tags TAG ...] [--type TYPE] [--scope SCOPE] [--limit N]
  related  --note FILENAME [--depth N] [--limit N]
  find-issues [--date YYYY-MM-DD] [--days-back N]
"""

import argparse
import json
import os
import re
import sys
from collections import deque
from datetime import date, timedelta

sys.path.insert(0, "/Users/changhwan/.claude/skills/_lib")
from obsidian import VaultScanner, parse_frontmatter, VAULT_BASE, SCAN_DIRS


def cmd_search(args):
    """alias/title 인덱스 기반 검색 — body full scan 없음."""
    scanner = VaultScanner()
    scopes = _parse_scope(args.scope)
    scanner.scan_all(scopes=scopes)

    query_lower = args.query.lower() if args.query else ""
    tag_filters = [t.strip() for t in args.tags] if args.tags else []

    alias_index = scanner.build_alias_index()
    seen = set()
    scored = []

    for key, note_list in alias_index.items():
        if not query_lower:
            break
        if query_lower not in key:
            continue
        exact = key == query_lower
        for note in note_list:
            if note.filename in seen:
                continue
            if args.type and note.note_type != args.type:
                continue
            if tag_filters and not any(tf in note.tags for tf in tag_filters):
                continue
            seen.add(note.filename)
            score = 20 if exact else 10
            for tf in tag_filters:
                if tf in note.tags:
                    score += 3
            scored.append((score, note))

    # tag-only 검색 (query 없음)
    if not query_lower and tag_filters:
        for note in scanner.scan_all(scopes=scopes):
            if note.filename in seen:
                continue
            if args.type and note.note_type != args.type:
                continue
            tag_score = sum(3 for tf in tag_filters if tf in note.tags)
            if tag_score:
                scored.append((tag_score, note))
                seen.add(note.filename)

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, note in scored[:args.limit]:
        results.append({
            "filename": note.filename,
            "title": note.title,
            "type": note.note_type,
            "tags": note.tags,
            "aliases": note.aliases,
            "date": note.date_str,
            "last_reviewed": note.last_reviewed,
            "score": score,
        })

    print(json.dumps({
        "command": "search",
        "query": args.query,
        "tags": tag_filters,
        "total": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2))


def cmd_related(args):
    """wikilink를 따라 연관 노트를 탐색 — 링크 그래프 기반, full scan 없음."""
    scanner = VaultScanner()
    notes = scanner.scan_all(scopes=("notes", "resources"))
    note_map = {n.filename: n for n in notes}

    start_note = _find_note(note_map, args.note)
    if not start_note:
        print(json.dumps({
            "command": "related",
            "error": f"노트를 찾을 수 없습니다: {args.note}",
            "results": [],
        }, ensure_ascii=False, indent=2))
        return

    depth = max(1, min(args.depth, 3))
    visited = {start_note.filename}
    results = []

    # BFS: outlinks만 따라감 (full scan 없음)
    queue = deque([(start_note, 0)])
    while queue:
        current, d = queue.popleft()
        if d >= depth:
            continue
        for raw_link in current.outlinks:
            resolved = scanner.resolve_link(raw_link)
            if not resolved:
                continue
            fname = os.path.basename(resolved)
            if fname in visited or fname not in note_map:
                continue
            visited.add(fname)
            neighbor = note_map[fname]
            results.append({
                "filename": neighbor.filename,
                "title": neighbor.title,
                "type": neighbor.note_type,
                "tags": neighbor.tags,
                "aliases": neighbor.aliases,
                "date": neighbor.date_str,
                "distance": d + 1,
                "via": current.filename,
            })
            queue.append((neighbor, d + 1))

    results = results[:args.limit]
    print(json.dumps({
        "command": "related",
        "source": start_note.filename,
        "depth": depth,
        "total": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2))


def cmd_find_issues(args):
    daily_dir = os.path.join(VAULT_BASE, SCAN_DIRS["daily"])
    if not os.path.isdir(daily_dir):
        print(json.dumps({"command": "find-issues", "error": "Daily 디렉토리 없음", "results": []}, ensure_ascii=False))
        return

    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
            date_range = {target_date}
        except ValueError:
            print(json.dumps({"command": "find-issues", "error": f"날짜 형식 오류: {args.date}"}, ensure_ascii=False))
            return
    else:
        today = date.today()
        days_back = args.days_back if args.days_back else 7
        date_range = {today - timedelta(days=i) for i in range(days_back)}

    issues_result = []
    for fname in sorted(os.listdir(daily_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        stem = fname[:-3]
        try:
            note_date = date.fromisoformat(stem)
        except ValueError:
            continue
        if note_date not in date_range:
            continue

        fpath = os.path.join(daily_dir, fname)
        _, body = parse_frontmatter(fpath)
        issues = _extract_issues_section(body)
        if issues:
            issues_result.append({"date": str(note_date), "issues": issues})

    print(json.dumps({
        "command": "find-issues",
        "total_days": len(issues_result),
        "results": issues_result,
    }, ensure_ascii=False, indent=2))


def _find_note(note_map: dict, query: str):
    if query in note_map:
        return note_map[query]
    query_lower = query.lower()
    for fname, note in note_map.items():
        if query_lower in fname.lower() or query_lower in note.title.lower():
            return note
    return None


def _parse_scope(scope_str: str) -> tuple:
    if not scope_str or scope_str == "all":
        return ("notes", "resources", "wiki")
    mapping = {
        "notes": ("notes",),
        "resources": ("resources",),
        "daily": ("daily",),
        "wiki": ("wiki",),
        "all": ("notes", "resources", "wiki", "daily"),
    }
    return mapping.get(scope_str, ("notes", "resources", "wiki"))


def _extract_issues_section(body: str) -> list:
    """## Issues 섹션에서 아이템 라인을 추출한다."""
    lines = body.split("\n")
    in_issues = False
    items = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^##\s+Issues?', stripped, re.IGNORECASE):
            in_issues = True
            continue
        if in_issues:
            if re.match(r'^##\s+', stripped) and not re.match(r'^##\s+Issues?', stripped, re.IGNORECASE):
                break
            if stripped.startswith("- ") or stripped.startswith("* "):
                items.append(stripped[2:].strip())
    return items


def main():
    parser = argparse.ArgumentParser(description="Obsidian 지식 베이스 검색")
    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search", help="키워드 검색")
    p_search.add_argument("--query", default="", help="검색 키워드")
    p_search.add_argument("--tags", nargs="+", help="태그 필터 (예: domain/kubernetes)")
    p_search.add_argument("--type", help="노트 타입 필터 (예: learning-note)")
    p_search.add_argument("--scope", default="all", help="검색 범위: notes|resources|wiki|daily|all")
    p_search.add_argument("--limit", type=int, default=10)

    p_related = sub.add_parser("related", help="연관 노트 탐색")
    p_related.add_argument("--note", required=True, help="시작 노트 파일명 또는 부분 일치")
    p_related.add_argument("--depth", type=int, default=2, help="BFS 탐색 깊이 (1-3)")
    p_related.add_argument("--limit", type=int, default=10)

    p_issues = sub.add_parser("find-issues", help="Daily Note Issues 섹션 검색")
    p_issues.add_argument("--date", help="특정 날짜 (YYYY-MM-DD)")
    p_issues.add_argument("--days-back", type=int, default=7)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        cmd_search(args)
    elif args.command == "related":
        cmd_related(args)
    elif args.command == "find-issues":
        cmd_find_issues(args)


if __name__ == "__main__":
    main()
