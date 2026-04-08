#!/usr/bin/env python3
"""
Obsidian 노트 생성 스크립트.
02. Notes/engineering/ 또는 02. Notes/others/ 에 마크다운 파일을 생성한다.
frontmatter에 last_reviewed, status, type, aliases 필드를 포함한다.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

# 공통 태그 유틸리티 임포트
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
from tags import TAG_DOMAIN_MAP, AWS_SERVICES, normalize_tags  # noqa: E402

VAULT_BASE = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"
VAULT_ROOT = Path(VAULT_BASE)
NOTES_BASE = f"{VAULT_BASE}/02. Notes"
NOTES_SUBDIRS = ["engineering", "others", "history"]

# Resources 타입 라우팅
RESOURCE_TYPES = {"runbook", "troubleshooting", "cheatsheet"}
TYPE_DIR_MAP = {
    "runbook": "03. Resources/runbooks",
    "troubleshooting": "03. Resources/troubleshooting",
    "cheatsheet": "03. Resources/cheatsheets",
}



def remove_hr(content: str) -> str:
    """코드블록 밖의 standalone `---` 수평선을 제거한다."""
    lines = content.split("\n")
    result = []
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
        if not in_code_block and stripped == "---":
            continue
        result.append(line)
    return "\n".join(result)


def slugify(title: str) -> str:
    """제목을 파일명으로 변환 (공백 유지, 특수문자 제거)."""
    slug = re.sub(r"[^\w\s가-힣-]", "", title)
    slug = re.sub(r"\s+", " ", slug.strip())
    return slug


HISTORY_TYPE = "history"


def get_save_dir(note_type: str, category: str) -> str:
    """노트 타입에 따라 저장 디렉토리를 결정한다."""
    if note_type in RESOURCE_TYPES:
        return os.path.join(VAULT_BASE, TYPE_DIR_MAP[note_type])
    if note_type == HISTORY_TYPE:
        return os.path.join(NOTES_BASE, "history")
    return os.path.join(NOTES_BASE, category)


def append_to_daily_note(note_slug: str, tags: list[str]) -> dict:
    """노트 생성 후 오늘 Daily Note의 ## Notes 섹션에 wikilink 추가."""
    today = datetime.now().strftime("%Y-%m-%d")
    daily_path = VAULT_ROOT / "01. Daily" / f"{today}.md"

    if not daily_path.exists():
        return {"linked": False, "reason": "daily_note_not_found"}

    content = daily_path.read_text(encoding="utf-8")

    # 중복 방지: 이미 동일 wikilink가 존재하면 skip
    wikilink = f"[[{note_slug}]]"
    if wikilink in content:
        return {"linked": False, "reason": "already_linked"}

    lines = content.splitlines()

    # ## Notes 섹션 인덱스 탐색
    notes_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Notes":
            notes_idx = i
            break

    if notes_idx is None:
        return {"linked": False, "reason": "notes_section_not_found"}

    # domain 태그 요약 (최대 2개)
    domain_tags = [t for t in tags if t.startswith("domain/")]
    tags_str = ", ".join(domain_tags[:2]) if domain_tags else ""
    entry = f"- {wikilink}" + (f" {tags_str}" if tags_str else "")

    # Notes 섹션 다음 줄 분석: 빈 섹션(placeholder `-`)이면 교체, 아니면 마지막 항목 뒤에 append
    # Notes 섹션 끝(다음 ## 헤딩 또는 파일 끝)까지의 범위 확인
    section_end = len(lines)
    for i in range(notes_idx + 1, len(lines)):
        if lines[i].startswith("##"):
            section_end = i
            break

    # 섹션 내용 (빈 줄 제외)
    section_lines = lines[notes_idx + 1:section_end]
    non_empty = [l for l in section_lines if l.strip()]

    if non_empty == ["-"] or non_empty == [] :
        # 빈 섹션: placeholder 교체 (첫 번째 `-` 줄을 entry로 교체, 나머지 삭제)
        # notes_idx + 1 ~ section_end - 1 범위를 entry 한 줄로 교체
        new_lines = lines[:notes_idx + 1] + [entry, ""] + lines[section_end:]
    else:
        # 기존 항목 있음: 섹션 마지막 항목 뒤에 append
        # section_end 직전(빈 줄 고려)에 삽입
        insert_at = section_end
        # 섹션 끝 바로 앞 빈 줄들 건너뜀
        while insert_at > notes_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new_lines = lines[:insert_at] + [entry] + lines[insert_at:]

    daily_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {"linked": True, "daily_note": str(daily_path)}


def find_related_notes(tags: list[str], exclude_filename: str) -> list[dict]:
    """태그가 겹치는 기존 노트를 찾아 반환한다 (engineering/others/Resources 모두 탐색)."""
    tag_set = set(tags)
    related = []

    # 탐색 범위: 02. Notes 하위 + 03. Resources 하위
    search_dirs = [os.path.join(NOTES_BASE, s) for s in NOTES_SUBDIRS]
    search_dirs += [os.path.join(VAULT_BASE, d) for d in TYPE_DIR_MAP.values()]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for filename in os.listdir(search_dir):
            if not filename.endswith(".md") or filename == exclude_filename:
                continue

            filepath = os.path.join(search_dir, filename)
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
                                val = line.strip()[2:]
                                if val.startswith("domain/"):
                                    note_tags.append(val)
            except (OSError, UnicodeDecodeError):
                continue

            common_tags = tag_set & set(note_tags)
            if common_tags:
                related.append({
                    "title": note_title,
                    "slug": os.path.splitext(filename)[0],
                    "common_tags": sorted(common_tags),
                })

    related.sort(key=lambda x: len(x["common_tags"]), reverse=True)
    return related[:5]  # 최대 5개


def create_note(title: str, tags: list[str], content: str, note_type: str = "learning-note", category: str = "engineering", aliases: list[str] | None = None) -> dict:
    today = date.today().isoformat()

    # 카테고리 검증 및 저장 디렉토리 결정
    if category not in NOTES_SUBDIRS:
        category = "engineering"
    notes_dir = get_save_dir(note_type, category)
    os.makedirs(notes_dir, exist_ok=True)

    # 태그 정규화
    domain_tags = normalize_tags(tags)

    aliases = aliases or []

    # frontmatter 생성
    frontmatter_lines = [
        "---",
        f'title: "{title}"',
        f"date: {today}",
        f"last_reviewed: {today}",
        f"status: active",
        f"type: {note_type}",
        "tags:",
    ]
    if domain_tags:
        frontmatter_lines.extend(f"  - {t}" for t in domain_tags)
    else:
        frontmatter_lines[-1] = "tags: []"

    frontmatter_lines.append("aliases:")
    if aliases:
        frontmatter_lines.extend(f"  - {a}" for a in aliases)
    else:
        frontmatter_lines[-1] = "aliases: []"

    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    toc_block = "```table-of-contents\n```"
    clean_content = remove_hr(content.strip())
    body = f"{frontmatter}\n\n{toc_block}\n\n{clean_content}\n"

    filename = f"{slugify(title)}.md"
    filepath = os.path.join(notes_dir, filename)

    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        i = 2
        while os.path.exists(os.path.join(notes_dir, f"{base}-{i}{ext}")):
            i += 1
        filename = f"{base}-{i}{ext}"
        filepath = os.path.join(notes_dir, filename)

    # 태그 기반 관련 노트 탐색 및 링크 추가
    related = find_related_notes(domain_tags, filename)
    if related:
        related_section = "\n\n## 관련 노트\n\n"
        for note in related:
            tags_str = " ".join(f"#{t}" for t in note["common_tags"])
            related_section += f"- [[{note['slug']}|{note['title']}]] {tags_str}\n"
        body = body.rstrip() + related_section + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body)

    # Daily Note에 wikilink 추가 (실패해도 노트 생성에 영향 없음)
    note_slug = os.path.splitext(filename)[0]
    try:
        daily_result = append_to_daily_note(note_slug, domain_tags)
    except Exception:
        daily_result = {"linked": False, "reason": "error"}

    return {
        "success": True,
        "title": title,
        "category": category if note_type not in RESOURCE_TYPES else f"03. Resources/{TYPE_DIR_MAP[note_type].split('/')[-1]}",
        "tags": domain_tags,
        "aliases": aliases,
        "type": note_type,
        "date": today,
        "filename": filename,
        "filepath": filepath,
        "related_count": len(related),
        "daily_linked": daily_result.get("linked", False),
    }


def list_notes(limit: int = 10) -> dict:
    notes = []

    for subdir in NOTES_SUBDIRS:
        search_dir = os.path.join(NOTES_BASE, subdir)
        if not os.path.isdir(search_dir):
            continue

        for filename in os.listdir(search_dir):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(search_dir, filename)
            tags = []
            title = filename
            date_str = ""
            note_type = ""

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
                            elif line.startswith("type:"):
                                note_type = line.split(":", 1)[1].strip()
                            elif line.startswith("  - ") and line.strip()[2:].startswith("domain/"):
                                tags.append(line.strip()[2:])
            except (OSError, UnicodeDecodeError):
                continue

            notes.append({
                "title": title,
                "date": date_str,
                "type": note_type,
                "tags": tags,
                "filename": filename,
            })

    notes.sort(key=lambda x: x["date"] or x["filename"], reverse=True)
    notes = notes[:limit]

    return {"success": True, "notes": notes}


def main():
    parser = argparse.ArgumentParser(description="Obsidian 노트 관리")
    sub = parser.add_subparsers(dest="command")

    p_create = sub.add_parser("create", help="노트 생성")
    p_create.add_argument("--title", required=True, help="노트 제목")
    p_create.add_argument("--tags", default="", help="태그 (콤마 구분, 예: Kubernetes,Network)")
    p_create.add_argument("--aliases", default="", help="aliases 키워드 3개 (콤마 구분, 예: Karpenter,NodePool,스케줄링)")
    p_create.add_argument("--content-file", default="", help="본문 파일 경로 (JSON {blocks: str} 또는 plain text)")
    p_create.add_argument("--type", default="learning-note", help="노트 유형 (learning-note, troubleshooting 등)")
    p_create.add_argument("--category", default="engineering", choices=["engineering", "others", "history"],
                          help="저장 카테고리 (기본값: engineering)")

    p_list = sub.add_parser("list", help="최근 노트 목록")
    p_list.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()

    if args.command == "create":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        aliases = [a.strip() for a in args.aliases.split(",") if a.strip()][:3] if args.aliases else []
        content = ""
        raw = ""
        if args.content_file == "-":
            raw = sys.stdin.read()
        elif args.content_file and os.path.exists(args.content_file):
            with open(args.content_file, encoding="utf-8") as f:
                raw = f.read()
        if raw:
            try:
                data = json.loads(raw)
                content = data.get("blocks", raw)
            except json.JSONDecodeError:
                content = raw

        result = create_note(args.title, tags, content, getattr(args, "type", "learning-note"), getattr(args, "category", "engineering"), aliases)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_notes(args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
