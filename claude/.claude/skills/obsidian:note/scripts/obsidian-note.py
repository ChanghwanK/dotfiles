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
from datetime import date

# 공통 태그 유틸리티 임포트
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../_lib"))
from tags import TAG_DOMAIN_MAP, AWS_SERVICES, normalize_tags  # noqa: E402

VAULT_BASE = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"
NOTES_BASE = f"{VAULT_BASE}/02. Notes"
NOTES_SUBDIRS = ["engineering", "others", "history"]

# Resources 타입 라우팅
RESOURCE_TYPES = {"runbook", "troubleshooting", "cheatsheet"}
TYPE_DIR_MAP = {
    "runbook": "03. Resources/runbooks",
    "troubleshooting": "03. Resources/troubleshooting",
    "cheatsheet": "03. Resources/cheatsheets",
}


def extract_aliases(title: str, content: str, existing_tags: list[str]) -> list[str]:
    """
    제목에서 복합 구(compound phrase) 위주로 aliases를 추출한다.
    연속된 대문자 단어 시퀀스를 하나의 구로 묶어 개별 토크나이징을 최소화한다.

    전략:
    - 연속 2단어 시퀀스 → "Karpenter NodePool" 형태로 통째로 추출
    - 연속 3+단어 시퀀스 → acronym 포함 bigram 우선 ("OIDC Federated" 등)
    - 단독 단어 → 약어(IRSA)나 고유명사(Git)만 보조로 추가
    - domain/ 태그 → 카테고리 키워드 1개
    """
    result: list[str] = []
    seen: set[str] = set()

    def add(a: str) -> None:
        a = a.strip()
        if a and a not in seen and len(a) >= 2:
            seen.add(a)
            result.append(a)

    # 1. 제목 그대로 (항상 포함)
    add(title.strip('"').strip())

    # 2. 제목에서 연속 대문자 단어 시퀀스 추출
    # CamelCase(NodePool), acronym(OIDC), TitleCase(Federated) 모두 하나의 토큰으로 인식
    token_re = re.compile(r'\b[A-Z][A-Za-z0-9]+\b')
    acronym_re = re.compile(r'^[A-Z]{2,}$')
    skip_words = {"The", "And", "For", "With", "From", "When", "That", "This",
                  "What", "How", "Why", "Are", "Was", "Were", "Not", "But",
                  "Has", "Had", "Its"}

    matches = list(token_re.finditer(title))
    sequences: list[list[str]] = []
    if matches:
        current = [matches[0]]
        for i in range(1, len(matches)):
            between = title[matches[i - 1].end():matches[i].start()]
            if re.match(r'^\s+$', between):   # 공백만 있으면 같은 시퀀스
                current.append(matches[i])
            else:                              # 한국어·특수문자가 끼면 시퀀스 분리
                sequences.append([m.group() for m in current])
                current = [matches[i]]
        sequences.append([m.group() for m in current])

    phrases: list[str] = []
    lone_keywords: list[str] = []
    for seq in sequences:
        words = [m for m in seq]
        if len(words) == 1:
            w = words[0]
            # 약어(PR, JWT)는 항상, TitleCase는 3자 이상 고유명사만
            if w not in skip_words and (acronym_re.match(w) or len(w) >= 3):
                lone_keywords.append(w)
        elif len(words) == 2:
            phrases.append(" ".join(words))
        else:
            # 3+단어: acronym 포함 bigram 우선
            has_bigram = False
            for i in range(len(words) - 1):
                w1, w2 = words[i], words[i + 1]
                if acronym_re.match(w1) or acronym_re.match(w2):
                    phrases.append(f"{w1} {w2}")
                    has_bigram = True
            if not has_bigram:
                phrases.append(" ".join(words[:2]))  # acronym 없으면 앞 2단어

    # phrases 최대 2개 → lone_keywords 최대 1개
    for p in phrases[:2]:
        add(p)
    for kw in lone_keywords[:1]:
        add(kw)

    # 3. domain/ 태그 첫 번째만 (카테고리 키워드)
    _acronym_domains = {"aws", "ai", "ml", "gcp", "eks", "iam", "k8s", "vpc"}
    for tag in existing_tags:
        if tag.startswith("domain/"):
            parts = tag.split("/", 1)[1].split("-")
            add("-".join(p.upper() if p in _acronym_domains else p.capitalize() for p in parts))
            break

    return result[:5]  # 최대 5개


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


def create_note(title: str, tags: list[str], content: str, note_type: str = "learning-note", category: str = "engineering") -> dict:
    today = date.today().isoformat()

    # 카테고리 검증 및 저장 디렉토리 결정
    if category not in NOTES_SUBDIRS:
        category = "engineering"
    notes_dir = get_save_dir(note_type, category)
    os.makedirs(notes_dir, exist_ok=True)

    # 태그 정규화
    domain_tags = normalize_tags(tags)

    # aliases 자동 추출
    aliases = extract_aliases(title, content, domain_tags)

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
            related_section += f"- [[{note['slug']}|{note['title']}]] — {tags_str}\n"
        body = body.rstrip() + related_section + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(body)

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
    p_create.add_argument("--content-file", default="", help="본문 파일 경로 (JSON {blocks: str} 또는 plain text)")
    p_create.add_argument("--type", default="learning-note", help="노트 유형 (learning-note, troubleshooting 등)")
    p_create.add_argument("--category", default="engineering", choices=["engineering", "others", "history"],
                          help="저장 카테고리 (기본값: engineering)")

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

        result = create_note(args.title, tags, content, getattr(args, "type", "learning-note"), getattr(args, "category", "engineering"))
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_notes(args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
