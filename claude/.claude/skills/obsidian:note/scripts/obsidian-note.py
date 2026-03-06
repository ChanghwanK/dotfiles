#!/usr/bin/env python3
"""
Obsidian 노트 생성 스크립트.
Engineering notes 디렉토리에 마크다운 파일을 생성한다.
"""

import argparse
import json
import os
import re
import sys
from datetime import date

NOTES_DIR = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Engineering/notes"


def slugify(title: str) -> str:
    """제목을 파일명으로 변환 (공백→하이픈, 특수문자 제거)."""
    slug = title.lower()
    slug = re.sub(r"[^\w\s가-힣-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def find_related_notes(tags: list[str], exclude_filename: str) -> list[dict]:
    """태그가 겹치는 기존 노트를 찾아 반환한다."""
    if not os.path.isdir(NOTES_DIR):
        return []

    tag_set = set(tags)
    related = []

    for filename in os.listdir(NOTES_DIR):
        if not filename.endswith(".md") or filename == exclude_filename:
            continue

        filepath = os.path.join(NOTES_DIR, filename)
        note_tags = []
        note_title = os.path.splitext(filename)[0]  # fallback

        try:
            with open(filepath, encoding="utf-8") as f:
                in_fm = False
                for line in f:
                    line = line.rstrip()
                    if line == "---":
                        if not in_fm:
                            in_fm = True
                            continue
                        else:
                            break
                    if in_fm:
                        if line.startswith("title:"):
                            note_title = line.split(":", 1)[1].strip().strip('"')
                        elif line.startswith("  - "):
                            note_tags.append(line.strip()[2:])
        except (OSError, UnicodeDecodeError):
            continue

        common_tags = tag_set & set(note_tags)
        if common_tags:
            related.append({
                "title": note_title,
                "slug": os.path.splitext(filename)[0],
                "common_tags": sorted(common_tags),
            })

    # 공통 태그 수 기준 내림차순 정렬
    related.sort(key=lambda x: len(x["common_tags"]), reverse=True)
    return related


def create_note(title: str, tags: list[str], content: str) -> dict:
    today = date.today().isoformat()
    tag_yaml = "\n".join(f"  - {t}" for t in tags)
    frontmatter = f"""---
title: "{title}"
tags:
{tag_yaml}
date: {today}
---"""

    toc_block = "```table-of-contents\n```"
    body = f"{frontmatter}\n\n{toc_block}\n\n{content.strip()}\n"

    filename = f"{slugify(title)}.md"
    filepath = os.path.join(NOTES_DIR, filename)

    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        i = 2
        while os.path.exists(os.path.join(NOTES_DIR, f"{base}-{i}{ext}")):
            i += 1
        filename = f"{base}-{i}{ext}"
        filepath = os.path.join(NOTES_DIR, filename)

    # 태그 기반 관련 노트 탐색 및 링크 추가
    related = find_related_notes(tags, filename)
    if related:
        related_section = "\n\n## 관련 노트\n\n"
        for note in related:
            tags_str = " ".join(f"#{t}" for t in note["common_tags"])
            related_section += f"- [[{note['slug']}|{note['title']}]] — {tags_str}\n"
        body = body.rstrip() + related_section + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body)

    return {
        "success": True,
        "title": title,
        "tags": tags,
        "date": today,
        "filename": filename,
        "filepath": filepath,
        "related_count": len(related),
    }


def list_notes(limit: int = 10) -> dict:
    if not os.path.isdir(NOTES_DIR):
        return {"success": False, "error": f"디렉토리를 찾을 수 없습니다: {NOTES_DIR}"}

    notes = []
    for filename in os.listdir(NOTES_DIR):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(NOTES_DIR, filename)
        tags = []
        title = filename
        date_str = ""

        try:
            with open(filepath, encoding="utf-8") as f:
                in_fm = False
                for line in f:
                    line = line.rstrip()
                    if line == "---":
                        if not in_fm:
                            in_fm = True
                            continue
                        else:
                            break
                    if in_fm:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"')
                        elif line.startswith("date:"):
                            date_str = line.split(":", 1)[1].strip()
                        elif line.startswith("  - "):
                            tags.append(line.strip()[2:])
        except (OSError, UnicodeDecodeError):
            continue

        notes.append({
            "title": title,
            "date": date_str,
            "tags": tags,
            "filename": filename,
        })

    # frontmatter의 date 기준 내림차순 정렬 (없으면 파일명)
    notes.sort(key=lambda x: x["date"] or x["filename"], reverse=True)
    notes = notes[:limit]

    return {"success": True, "notes": notes}


def main():
    parser = argparse.ArgumentParser(description="Obsidian 노트 관리")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="노트 생성")
    p_create.add_argument("--title", required=True, help="노트 제목")
    p_create.add_argument("--tags", default="", help="태그 (콤마 구분, 예: Kubernetes,Network)")
    p_create.add_argument("--content-file", default="", help="본문 파일 경로 (JSON {blocks: str} 또는 plain text)")

    p_list = sub.add_parser("list", help="최근 노트 목록")
    p_list.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.command == "create":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        content = ""
        if args.content_file and os.path.exists(args.content_file):
            with open(args.content_file, encoding="utf-8") as f:
                raw = f.read()
            try:
                data = json.loads(raw)
                content = data.get("blocks", raw)
            except json.JSONDecodeError:
                content = raw

        result = create_note(args.title, tags, content)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_notes(args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
