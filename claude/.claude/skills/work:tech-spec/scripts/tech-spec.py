#!/usr/bin/env python3
"""
Tech Spec 관리 스크립트.
Obsidian tech_spec 디렉토리에 구조화된 Tech Spec 문서를 생성/관리한다.
"""

import argparse
import json
import os
import re
import sys
from datetime import date

SPEC_DIR = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Engineering/tech_spec"


def slugify(title: str) -> str:
    """제목을 파일명으로 변환 (공백→하이픈, 특수문자 제거)."""
    slug = title.lower()
    slug = re.sub(r"[^\w\s가-힣-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def parse_frontmatter(filepath: str) -> dict:
    """파일의 YAML frontmatter를 파싱하여 dict로 반환한다."""
    fields = {}
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
                        fields["title"] = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("status:"):
                        fields["status"] = line.split(":", 1)[1].strip()
                    elif line.startswith("date:"):
                        fields["date"] = line.split(":", 1)[1].strip()
                    elif line.startswith("  - "):
                        fields.setdefault("tags", []).append(line.strip()[2:])
    except (OSError, UnicodeDecodeError):
        pass
    return fields


def find_related_specs(tags: list[str], exclude_filename: str) -> list[dict]:
    """태그가 겹치는 기존 스펙을 찾아 반환한다."""
    if not os.path.isdir(SPEC_DIR):
        return []

    tag_set = set(tags)
    related = []

    for filename in os.listdir(SPEC_DIR):
        if not filename.endswith(".md") or filename == exclude_filename:
            continue

        filepath = os.path.join(SPEC_DIR, filename)
        fm = parse_frontmatter(filepath)
        note_tags = fm.get("tags", [])
        note_title = fm.get("title", os.path.splitext(filename)[0])
        note_status = fm.get("status", "")

        common_tags = tag_set & set(note_tags)
        if common_tags:
            related.append({
                "title": note_title,
                "slug": os.path.splitext(filename)[0],
                "status": note_status,
                "common_tags": sorted(common_tags),
            })

    related.sort(key=lambda x: len(x["common_tags"]), reverse=True)
    return related


def create_spec(title: str, tags: list[str], content: str) -> dict:
    """Tech Spec 문서를 생성한다."""
    today = date.today().isoformat()
    tag_yaml = "\n".join(f"  - {t}" for t in tags)
    frontmatter = f"""---
title: "{title}"
tags:
{tag_yaml}
status: 시작전
date: {today}
---"""

    toc_block = "```table-of-contents\n```"
    body = f"{frontmatter}\n\n{toc_block}\n\n{content.strip()}\n"

    # 디렉토리 생성
    os.makedirs(SPEC_DIR, exist_ok=True)

    filename = f"{slugify(title)}.md"
    filepath = os.path.join(SPEC_DIR, filename)

    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        i = 2
        while os.path.exists(os.path.join(SPEC_DIR, f"{base}-{i}{ext}")):
            i += 1
        filename = f"{base}-{i}{ext}"
        filepath = os.path.join(SPEC_DIR, filename)

    # 태그 기반 관련 스펙 탐색 및 링크 추가
    related = find_related_specs(tags, filename)
    if related:
        related_section = "\n\n## 관련 스펙\n\n"
        for spec in related:
            tags_str = " ".join(f"#{t}" for t in spec["common_tags"])
            status_str = f" `{spec['status']}`" if spec["status"] else ""
            related_section += f"- [[{spec['slug']}|{spec['title']}]]{status_str} — {tags_str}\n"
        body = body.rstrip() + related_section + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body)

    return {
        "success": True,
        "title": title,
        "tags": tags,
        "status": "시작전",
        "date": today,
        "filename": filename,
        "filepath": filepath,
        "related_count": len(related),
    }


def list_specs(limit: int = 10, status_filter: str = "") -> dict:
    """Tech Spec 목록을 반환한다."""
    if not os.path.isdir(SPEC_DIR):
        return {"success": False, "error": f"디렉토리를 찾을 수 없습니다: {SPEC_DIR}"}

    specs = []
    for filename in os.listdir(SPEC_DIR):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(SPEC_DIR, filename)
        fm = parse_frontmatter(filepath)

        spec_status = fm.get("status", "")
        if status_filter and spec_status != status_filter:
            continue

        specs.append({
            "title": fm.get("title", filename),
            "date": fm.get("date", ""),
            "tags": fm.get("tags", []),
            "status": spec_status,
            "filename": filename,
        })

    specs.sort(key=lambda x: x["date"] or x["filename"], reverse=True)
    specs = specs[:limit]

    return {"success": True, "specs": specs}


def update_status(filename: str, new_status: str) -> dict:
    """Tech Spec의 status를 변경한다."""
    valid_statuses = {"시작전", "진행중", "완료"}
    if new_status not in valid_statuses:
        return {
            "success": False,
            "error": f"유효하지 않은 상태: '{new_status}'. 허용값: {', '.join(sorted(valid_statuses))}",
        }

    filepath = os.path.join(SPEC_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content, count = re.subn(
        r"^status:\s*.+$",
        f"status: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if count == 0:
        return {"success": False, "error": f"status 필드를 찾을 수 없습니다: {filename}"}

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    fm = parse_frontmatter(filepath)
    return {
        "success": True,
        "filename": filename,
        "title": fm.get("title", filename),
        "status": new_status,
        "filepath": filepath,
    }


def main():
    parser = argparse.ArgumentParser(description="Tech Spec 관리")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="Tech Spec 생성")
    p_create.add_argument("--title", required=True, help="스펙 제목")
    p_create.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_create.add_argument("--content-file", default="", help="본문 파일 경로 (JSON {blocks: str} 또는 plain text)")

    p_list = sub.add_parser("list", help="Tech Spec 목록")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--status", default="", help="상태 필터 (시작전, 진행중, 완료)")

    p_status = sub.add_parser("update-status", help="상태 변경")
    p_status.add_argument("--filename", required=True, help="대상 파일명")
    p_status.add_argument("--status", required=True, help="새 상태 (시작전, 진행중, 완료)")

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

        result = create_spec(args.title, tags, content)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_specs(args.limit, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "update-status":
        result = update_status(args.filename, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
