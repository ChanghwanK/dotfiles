#!/usr/bin/env python3
"""
학습 로드맵 관리 스크립트.
02. Notes/engineering/ 에 type: roadmap 마크다운 파일을 생성/관리한다.
체크박스 기반 진행 추적 지원 (Obsidian Tasks 호환).
"""

import argparse
import json
import os
import re
import sys
from datetime import date

VAULT_BASE = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"
NOTES_BASE = f"{VAULT_BASE}/02. Notes"
NOTES_SUBDIRS = ["engineering", "others"]
ROADMAP_DIR = f"{NOTES_BASE}/engineering"

# 참조 탐색 디렉토리 (관련 노트 검색용)
RESOURCE_TYPE_DIRS = {
    "runbook": "03. Resources/runbooks",
    "troubleshooting": "03. Resources/troubleshooting",
    "cheatsheet": "03. Resources/cheatsheets",
    "tech-spec": "03. Resources/tech-specs",
}

# 태그 키워드 → 정규화 태그 매핑
TAG_DOMAIN_MAP = {
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "aws": "aws",
    "terraform": "terraform",
    "infra": None,
    "network": "networking",
    "networking": "networking",
    "istio": "networking",
    "envoy": "networking",
    "servicemesh": "networking",
    "observability": "observability",
    "grafana": "observability",
    "prometheus": "observability",
    "loki": "observability",
    "tracing": "observability",
    "database": "database",
    "on-premise": "on-premise",
    "onpremise": "on-premise",
    "gpu": "on-premise",
    "security": "security",
    "tls": "security",
    "pki": "security",
    "ai": "ai",
    "llm": "ai",
    "ml": "ai",
    "machinelearning": "ai",
    "agent": "ai",
}

AWS_SERVICES = {
    "cloudfront", "route53", "aurora", "rds", "alb", "elb",
    "ecs", "eks", "ec2", "s3", "cloudwatch", "iam", "vpc",
    "natgateway", "transitgateway", "lambda", "sqs", "sns",
}


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """기존 태그를 domain/ 네임스페이스로 정규화."""
    domain_tags = set()
    for tag in raw_tags:
        key = tag.lower().replace(" ", "").replace("_", "").replace("-", "")
        mapped = TAG_DOMAIN_MAP.get(key)
        if mapped:
            domain_tags.add(mapped)
        elif tag.startswith("domain/"):
            domain_tags.add(tag)
        elif key in AWS_SERVICES:
            domain_tags.add("domain/aws")
    return sorted(domain_tags)


def extract_aliases(title: str, content: str, existing_tags: list[str]) -> list[str]:
    """노트 제목과 본문에서 핵심 키워드를 추출하여 aliases를 생성한다."""
    aliases = set()

    # 1. 제목에서 고유명사
    proper_nouns = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', title)
    for noun in proper_nouns:
        if noun not in {"The", "And", "For", "With", "From", "Roadmap"}:
            aliases.add(noun)

    # 대문자 약어 (2자 이상)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', title)
    aliases.update(acronyms)

    # 2. 본문에서 추출 (처음 3000자만)
    sample = content[:3000] if content else ""

    # 백틱 기술 용어
    backtick_terms = re.findall(r'`([^`\n]{2,30})`', sample)
    for term in backtick_terms:
        if re.match(r'^[A-Za-z][A-Za-z0-9_\-\.]{1,25}$', term):
            aliases.add(term)

    # 대문자 약어 (본문)
    skip_acronyms = {"HTTP", "HTTPS", "API", "URL", "SQL", "JSON", "YAML",
                     "CLI", "GUI", "CPU", "RAM", "SSD", "TCP", "UDP", "DNS",
                     "SSH", "TLS", "SSL", "EOF", "OCI", "VM", "OS", "KV"}
    acronyms_body = re.findall(r'\b([A-Z]{2,8})\b', sample)
    for acr in acronyms_body:
        if acr not in skip_acronyms:
            aliases.add(acr)

    # 3. 한국어 키워드 (제목)
    korean_words = re.findall(r'[\uAC00-\uD7A3]{2,}', title)
    for word in korean_words:
        if len(word) >= 2:
            aliases.add(word)

    # 제목 자체도 alias
    title_clean = title.strip('"').strip()
    if title_clean:
        aliases.add(title_clean)

    # 정제
    skip_words = {"AND", "OR", "NOT", "FOR", "THE", "IN", "ON", "AT",
                  "BY", "TO", "IS", "AS", "BE", "IF", "MS", "ID", "OK"}
    aliases = {a for a in aliases if a not in skip_words and len(a) >= 2}

    return sorted(aliases)[:20]


def slugify(title: str) -> str:
    """제목을 파일명으로 변환 (공백 유지, 특수문자 제거)."""
    slug = re.sub(r"[^\w\s가-힣-]", "", title)
    slug = re.sub(r"\s+", " ", slug.strip())
    return slug


def parse_frontmatter(filepath: str) -> dict:
    """파일의 YAML frontmatter를 파싱하여 dict로 반환한다."""
    fields = {}
    try:
        with open(filepath, encoding="utf-8") as f:
            in_fm = False
            in_tags = False
            in_aliases = False
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
                        in_tags = in_aliases = False
                    elif line.startswith("status:"):
                        fields["status"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = False
                    elif line.startswith("date:"):
                        fields["date"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = False
                    elif line.startswith("last_reviewed:"):
                        fields["last_reviewed"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = False
                    elif line.startswith("type:"):
                        fields["type"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = False
                    elif line.startswith("mode:"):
                        fields["mode"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = False
                    elif line.startswith("progress:"):
                        fields["progress"] = line.split(":", 1)[1].strip().strip('"')
                        in_tags = in_aliases = False
                    elif line.startswith("tags:"):
                        rest = line.split(":", 1)[1].strip()
                        if rest == "[]":
                            fields["tags"] = []
                        else:
                            fields.setdefault("tags", [])
                            in_tags = True
                        in_aliases = False
                    elif line.startswith("aliases:"):
                        rest = line.split(":", 1)[1].strip()
                        if rest == "[]":
                            fields["aliases"] = []
                        else:
                            fields.setdefault("aliases", [])
                            in_aliases = True
                        in_tags = False
                    elif line.startswith("  - "):
                        val = line.strip()[2:]
                        if in_tags:
                            fields.setdefault("tags", []).append(val)
                        elif in_aliases:
                            fields.setdefault("aliases", []).append(val)
                    else:
                        in_tags = in_aliases = False
    except (OSError, UnicodeDecodeError):
        pass
    return fields


def find_related_notes(tags: list[str], exclude_filename: str) -> list[dict]:
    """태그가 겹치는 기존 노트를 찾아 반환한다 (engineering/others/Resources 모두 탐색)."""
    tag_set = set(tags)
    related = []

    search_dirs = [os.path.join(NOTES_BASE, s) for s in NOTES_SUBDIRS]
    search_dirs += [os.path.join(VAULT_BASE, d) for d in RESOURCE_TYPE_DIRS.values()]

    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for filename in os.listdir(search_dir):
            if not filename.endswith(".md") or filename == exclude_filename:
                continue
            filepath = os.path.join(search_dir, filename)
            fm = parse_frontmatter(filepath)
            note_tags = fm.get("tags", [])
            note_title = fm.get("title", os.path.splitext(filename)[0])

            common_tags = tag_set & set(note_tags)
            if common_tags:
                related.append({
                    "title": note_title,
                    "slug": os.path.splitext(filename)[0],
                    "common_tags": sorted(common_tags),
                })

    related.sort(key=lambda x: len(x["common_tags"]), reverse=True)
    return related[:5]


def count_checkboxes(content: str) -> dict:
    """본문의 체크박스 상태를 카운트한다."""
    # frontmatter 제거
    body = re.sub(r'^---.*?---\s*', '', content, count=1, flags=re.DOTALL)

    total = 0
    done = 0
    in_progress = 0
    todo = 0

    for line in body.split("\n"):
        if re.match(r'^\s*- \[x\]', line, re.IGNORECASE):
            done += 1
            total += 1
        elif re.match(r'^\s*- \[/\]', line):
            in_progress += 1
            total += 1
        elif re.match(r'^\s*- \[ \]', line):
            todo += 1
            total += 1

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "todo": todo,
        "percent": round(done / total * 100, 1) if total > 0 else 0,
    }


def create_roadmap(title: str, tags: list[str], content: str, mode: str = "101") -> dict:
    """로드맵 문서를 생성한다."""
    today = date.today().isoformat()

    # 태그 정규화
    domain_tags = normalize_tags(tags)

    # aliases 자동 추출
    aliases = extract_aliases(title, content, domain_tags)

    # 체크박스 카운트 (초기 진행률)
    cb = count_checkboxes(content)
    progress_str = f"{cb['done']}/{cb['total']}"

    # frontmatter 생성
    fm_lines = [
        "---",
        f'title: "{title}"',
        f"date: {today}",
        f"last_reviewed: {today}",
        f"status: active",
        f"type: roadmap",
        f"mode: {mode}",
        f'progress: "{progress_str}"',
        "tags:",
    ]
    if domain_tags:
        fm_lines.extend(f"  - {t}" for t in domain_tags)
    else:
        fm_lines[-1] = "tags: []"

    fm_lines.append("aliases:")
    if aliases:
        fm_lines.extend(f"  - {a}" for a in aliases)
    else:
        fm_lines[-1] = "aliases: []"

    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    toc_block = "```table-of-contents\n```"
    body = f"{frontmatter}\n\n{toc_block}\n\n{content.strip()}\n"

    os.makedirs(ROADMAP_DIR, exist_ok=True)

    filename = f"{slugify(title)}.md"
    filepath = os.path.join(ROADMAP_DIR, filename)

    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        i = 2
        while os.path.exists(os.path.join(ROADMAP_DIR, f"{base}-{i}{ext}")):
            i += 1
        filename = f"{base}-{i}{ext}"
        filepath = os.path.join(ROADMAP_DIR, filename)

    # 관련 노트 링크
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
        "mode": mode,
        "tags": domain_tags,
        "aliases": aliases,
        "type": "roadmap",
        "progress": progress_str,
        "date": today,
        "filename": filename,
        "filepath": filepath,
        "related_count": len(related),
        "checkboxes": cb,
    }


def list_roadmaps(limit: int = 10) -> dict:
    """type: roadmap인 파일 목록을 반환한다."""
    roadmaps = []

    for subdir in NOTES_SUBDIRS:
        search_dir = os.path.join(NOTES_BASE, subdir)
        if not os.path.isdir(search_dir):
            continue
        for filename in os.listdir(search_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(search_dir, filename)
            fm = parse_frontmatter(filepath)

            if fm.get("type") != "roadmap":
                continue

            roadmaps.append({
                "title": fm.get("title", filename),
                "date": fm.get("date", ""),
                "mode": fm.get("mode", ""),
                "progress": fm.get("progress", "?/?"),
                "tags": fm.get("tags", []),
                "status": fm.get("status", ""),
                "filename": filename,
                "filepath": filepath,
            })

    roadmaps.sort(key=lambda x: x["date"] or x["filename"], reverse=True)
    return {"success": True, "roadmaps": roadmaps[:limit]}


def show_progress(filename: str) -> dict:
    """체크박스 파싱하여 진행률을 반환한다."""
    # 파일 탐색 (engineering / others)
    filepath = None
    for subdir in NOTES_SUBDIRS:
        candidate = os.path.join(NOTES_BASE, subdir, filename)
        if os.path.exists(candidate):
            filepath = candidate
            break

    if not filepath:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(filepath)
    cb = count_checkboxes(content)

    # 다음 추천 항목 (첫 번째 미완료)
    next_items = []
    body = re.sub(r'^---.*?---\s*', '', content, count=1, flags=re.DOTALL)
    for line in body.split("\n"):
        m = re.match(r'^\s*- \[ \]\s+(.+)', line)
        if m and len(next_items) < 3:
            next_items.append(m.group(1).strip())

    return {
        "success": True,
        "filename": filename,
        "title": fm.get("title", filename),
        "mode": fm.get("mode", ""),
        "progress": cb,
        "next_items": next_items,
    }


def update_progress(filename: str, items: str, status: str = "done") -> dict:
    """특정 항목 번호의 체크박스 상태를 변경하고 progress 필드를 갱신한다.

    items: 콤마 구분 항목 번호 문자열 (예: "0.1,1.2,3.1")
    status: "done" | "in_progress" | "todo"
    """
    STATUS_MAP = {
        "done": "x",
        "in_progress": "/",
        "todo": " ",
    }
    if status not in STATUS_MAP:
        return {
            "success": False,
            "error": f"유효하지 않은 상태: '{status}'. 허용값: done, in_progress, todo",
        }
    new_mark = STATUS_MAP[status]

    # 파일 탐색
    filepath = None
    for subdir in NOTES_SUBDIRS:
        candidate = os.path.join(NOTES_BASE, subdir, filename)
        if os.path.exists(candidate):
            filepath = candidate
            break

    if not filepath:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(filepath, encoding="utf-8") as f:
        doc = f.read()

    item_list = [i.strip() for i in items.split(",") if i.strip()]
    updated = []
    new_doc = doc

    for item_num in item_list:
        # 항목 번호 패턴: "- [ ] 0.1 " 또는 "- [x] 0.1 " 등
        escaped_num = re.escape(item_num)
        pattern = rf'^(\s*)- \[[ x/]\] ({escaped_num}[\s\.])'
        replacement = rf'\1- [{new_mark}] \2'
        new_doc, count = re.subn(pattern, replacement, new_doc, flags=re.MULTILINE)
        if count > 0:
            updated.append(item_num)

    if not updated:
        return {
            "success": False,
            "error": f"업데이트된 항목이 없습니다. 항목 번호를 확인하세요: {items}",
        }

    # progress 필드 갱신
    today = date.today().isoformat()
    cb = count_checkboxes(new_doc)
    progress_str = f"{cb['done']}/{cb['total']}"

    new_doc = re.sub(
        r'^progress:\s*"?[^"\n]*"?$',
        f'progress: "{progress_str}"',
        new_doc,
        count=1,
        flags=re.MULTILINE,
    )
    new_doc = re.sub(
        r'^last_reviewed:\s*.+$',
        f'last_reviewed: {today}',
        new_doc,
        count=1,
        flags=re.MULTILINE,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_doc)

    fm = parse_frontmatter(filepath)
    return {
        "success": True,
        "filename": filename,
        "title": fm.get("title", filename),
        "updated_items": updated,
        "status": status,
        "progress": progress_str,
        "checkboxes": cb,
        "last_reviewed": today,
    }


def search_notes(domain: str) -> dict:
    """도메인 키워드로 관련 노트를 탐색한다 (태그 기반)."""
    key = domain.lower().replace(" ", "").replace("-", "")
    mapped_tag = TAG_DOMAIN_MAP.get(key)

    # AWS 서비스명도 확인
    if not mapped_tag and key in AWS_SERVICES:
        mapped_tag = "aws"

    # 이미 정규화된 태그면 그대로 사용
    if not mapped_tag and domain and not domain.startswith("domain/"):
        mapped_tag = domain

    if not mapped_tag:
        # 부분 매칭 시도
        for k, v in TAG_DOMAIN_MAP.items():
            if key in k or k in key:
                if v:
                    mapped_tag = v
                    break

    tags_to_search = [mapped_tag] if mapped_tag else []

    search_dirs = [os.path.join(NOTES_BASE, s) for s in NOTES_SUBDIRS]
    search_dirs += [os.path.join(VAULT_BASE, d) for d in RESOURCE_TYPE_DIRS.values()]

    notes = []
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for filename in os.listdir(search_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(search_dir, filename)
            fm = parse_frontmatter(filepath)
            note_tags = fm.get("tags", [])
            note_title = fm.get("title", os.path.splitext(filename)[0])
            note_type = fm.get("type", "")

            # 태그 매칭 또는 도메인 키워드가 제목/파일명에 포함
            tag_match = bool(tags_to_search and set(tags_to_search) & set(note_tags))
            title_match = key in note_title.lower() or domain.lower() in note_title.lower()

            if tag_match or title_match:
                notes.append({
                    "title": note_title,
                    "slug": os.path.splitext(filename)[0],
                    "type": note_type,
                    "tags": note_tags,
                    "filename": filename,
                })

    return {
        "success": True,
        "domain": domain,
        "mapped_tag": mapped_tag,
        "notes": notes,
    }


def main():
    parser = argparse.ArgumentParser(description="학습 로드맵 관리")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="로드맵 생성")
    p_create.add_argument("--title", required=True, help="로드맵 제목")
    p_create.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_create.add_argument("--content-file", default="", help="본문 파일 경로 (JSON {blocks: str} 또는 plain text)")
    p_create.add_argument("--mode", default="101", choices=["101", "gap"],
                          help="로드맵 모드 (기본값: 101)")

    # list
    p_list = sub.add_parser("list", help="로드맵 목록")
    p_list.add_argument("--limit", type=int, default=10)

    # show-progress
    p_show = sub.add_parser("show-progress", help="진행률 확인")
    p_show.add_argument("--filename", required=True, help="대상 파일명")

    # update-progress
    p_update = sub.add_parser("update-progress", help="체크박스 상태 변경")
    p_update.add_argument("--filename", required=True, help="대상 파일명")
    p_update.add_argument("--items", required=True, help="항목 번호 (콤마 구분, 예: 0.1,1.2)")
    p_update.add_argument("--status", default="done",
                          choices=["done", "in_progress", "todo"],
                          help="새 상태 (기본값: done)")

    # search-notes
    p_search = sub.add_parser("search-notes", help="도메인 관련 노트 탐색")
    p_search.add_argument("--domain", required=True, help="도메인 키워드 (예: kubernetes, aws)")

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
        result = create_roadmap(args.title, tags, content, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_roadmaps(args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "show-progress":
        result = show_progress(args.filename)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "update-progress":
        result = update_progress(args.filename, args.items, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "search-notes":
        result = search_notes(args.domain)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
