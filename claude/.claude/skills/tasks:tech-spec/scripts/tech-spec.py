#!/usr/bin/env python3
"""
Tech Spec 관리 스크립트.
Obsidian tech-specs 디렉토리에 구조화된 Tech Spec 문서를 생성/관리한다.
5-Phase 워크플로우 지원: 생성, 상태 관리, 실행 기록 추가, 검증, 마이그레이션.
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
SPEC_DIR = f"{VAULT_BASE}/03. Resources/tech-specs"
NOTES_BASE = f"{VAULT_BASE}/02. Notes"
NOTES_SUBDIRS = ["engineering", "others"]
RESOURCE_TYPE_DIRS = {
    "runbook": "03. Resources/runbooks",
    "troubleshooting": "03. Resources/troubleshooting",
    "cheatsheet": "03. Resources/cheatsheets",
    "tech-spec": "03. Resources/tech-specs",
}

REQUIRED_SECTIONS = [
    "왜 이걸 해야 하는가?",
    "현재 상태와 목표",
    "실행 계획",
    "임팩트 측정",
]

VALID_SPEC_TYPES = {
    "terraform", "k8s-manifest", "k8s-crd", "helm-chart",
    "jsonnet", "kyverno-policy", "alert-rule", "api-spec", "ops-change",
}



def slugify(title: str) -> str:
    """제목을 파일명으로 변환 (공백 유지, 특수문자 제거)."""
    slug = re.sub(r"[^\w\s가-힣]", "", title)
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
            in_spec_type = False
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
                        in_tags = in_aliases = in_spec_type = False
                    elif line.startswith("status:"):
                        fields["status"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = in_spec_type = False
                    elif line.startswith("date:"):
                        fields["date"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = in_spec_type = False
                    elif line.startswith("last_reviewed:"):
                        fields["last_reviewed"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = in_spec_type = False
                    elif line.startswith("type:"):
                        fields["type"] = line.split(":", 1)[1].strip()
                        in_tags = in_aliases = in_spec_type = False
                    elif line.startswith("tags:"):
                        rest = line.split(":", 1)[1].strip()
                        if rest == "[]":
                            fields["tags"] = []
                        else:
                            fields.setdefault("tags", [])
                            in_tags = True
                        in_aliases = in_spec_type = False
                    elif line.startswith("aliases:"):
                        rest = line.split(":", 1)[1].strip()
                        if rest == "[]":
                            fields["aliases"] = []
                        else:
                            fields.setdefault("aliases", [])
                            in_aliases = True
                        in_tags = in_spec_type = False
                    elif line.startswith("spec_type:"):
                        rest = line.split(":", 1)[1].strip()
                        if rest == "[]":
                            fields["spec_type"] = []
                        else:
                            fields.setdefault("spec_type", [])
                            in_spec_type = True
                        in_tags = in_aliases = False
                    elif line.startswith("  - "):
                        val = line.strip()[2:]
                        if in_tags:
                            fields.setdefault("tags", []).append(val)
                        elif in_aliases:
                            fields.setdefault("aliases", []).append(val)
                        elif in_spec_type:
                            fields.setdefault("spec_type", []).append(val)
                    else:
                        in_tags = in_aliases = in_spec_type = False
    except (OSError, UnicodeDecodeError):
        pass
    return fields


def find_related_specs(tags: list[str], exclude_filename: str) -> list[dict]:
    """태그가 겹치는 기존 스펙/노트를 찾아 반환한다."""
    tag_set = set(tags)
    related = []

    # tech-specs + Notes 디렉토리 모두 탐색
    search_dirs = [SPEC_DIR]
    search_dirs += [os.path.join(NOTES_BASE, s) for s in NOTES_SUBDIRS]
    search_dirs += [os.path.join(VAULT_BASE, d) for d in RESOURCE_TYPE_DIRS.values()
                    if d != "03. Resources/tech-specs"]

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
    return related[:5]


def create_spec(title: str, tags: list[str], content: str, spec_types: list[str] | None = None, aliases: list[str] | None = None) -> dict:
    """Tech Spec 문서를 생성한다. 태그 정규화, spec_type 포함."""
    today = date.today().isoformat()

    # 태그 정규화
    domain_tags = normalize_tags(tags)

    aliases = aliases or []

    # frontmatter 생성
    fm_lines = [
        "---",
        f'title: "{title}"',
        f"date: {today}",
        f"last_reviewed: {today}",
        "status: 시작전",
        "type: tech-spec",
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

    spec_types = spec_types or []
    fm_lines.append("spec_type:")
    if spec_types:
        fm_lines.extend(f"  - {st}" for st in spec_types)
    else:
        fm_lines[-1] = "spec_type: []"

    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    toc_block = "```table-of-contents\n```"
    body = f"{frontmatter}\n\n{toc_block}\n\n{content.strip()}\n"

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

    # 관련 스펙 링크
    related = find_related_specs(domain_tags, filename)
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
        "tags": domain_tags,
        "aliases": aliases,
        "spec_type": spec_types,
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
            "spec_type": fm.get("spec_type", []),
            "status": spec_status,
            "filename": filename,
        })

    specs.sort(key=lambda x: x["date"] or x["filename"], reverse=True)
    specs = specs[:limit]

    return {"success": True, "specs": specs}


def update_status(filename: str, new_status: str) -> dict:
    """Tech Spec의 status를 변경하고 last_reviewed도 갱신한다."""
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

    # status 갱신
    new_content, count = re.subn(
        r"^status:\s*.+$",
        f"status: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        return {"success": False, "error": f"status 필드를 찾을 수 없습니다: {filename}"}

    # last_reviewed 갱신
    today = date.today().isoformat()
    new_content, lr_count = re.subn(
        r"^last_reviewed:\s*.+$",
        f"last_reviewed: {today}",
        new_content,
        count=1,
        flags=re.MULTILINE,
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    fm = parse_frontmatter(filepath)
    return {
        "success": True,
        "filename": filename,
        "title": fm.get("title", filename),
        "status": new_status,
        "last_reviewed": today,
        "filepath": filepath,
    }


def validate_spec(filename: str) -> dict:
    """Tech Spec 문서의 품질을 5개 항목으로 검증한다."""
    filepath = os.path.join(SPEC_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(filepath)
    checks = []

    # 1. 필수 H2 섹션 존재 확인
    h2_sections = re.findall(r'^## (.+)$', content, re.MULTILINE)
    h2_titles = [s.strip() for s in h2_sections]
    missing_sections = [s for s in REQUIRED_SECTIONS if s not in h2_titles]
    checks.append({
        "name": "required_sections",
        "pass": len(missing_sections) == 0,
        "detail": f"누락: {', '.join(missing_sections)}" if missing_sections else "4개 필수 섹션 존재",
    })

    # 2. 임팩트에 숫자 또는 Before/After 패턴 존재
    impact_match = re.search(r'## 임팩트 측정\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    impact_text = impact_match.group(1) if impact_match else ""
    has_numbers = bool(re.search(r'\d+', impact_text))
    has_before_after = bool(re.search(r'[Bb]efore|[Aa]fter|이전|이후|현재|목표', impact_text))
    impact_ok = has_numbers or has_before_after
    checks.append({
        "name": "impact_measurable",
        "pass": impact_ok,
        "detail": "측정 가능한 수치 포함" if impact_ok else "숫자 또는 Before/After 패턴 없음",
    })

    # 3. 실행 계획에 롤백 언급
    plan_match = re.search(r'## 실행 계획\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    plan_text = plan_match.group(1) if plan_match else ""
    has_rollback = bool(re.search(r'롤백|rollback|되돌리|복구|revert', plan_text, re.IGNORECASE))
    checks.append({
        "name": "rollback_mentioned",
        "pass": has_rollback,
        "detail": "롤백 절차 포함" if has_rollback else "롤백/복구 언급 없음",
    })

    # 4. domain/ 태그 1개 이상 존재
    tags = fm.get("tags", [])
    domain_tags = [t for t in tags if t.startswith("domain/")]
    checks.append({
        "name": "domain_tags",
        "pass": len(domain_tags) >= 1,
        "detail": f"{len(domain_tags)}개 domain 태그: {', '.join(domain_tags)}" if domain_tags else "domain/ 태그 없음",
    })

    # 5. Non-Goals 섹션 존재
    has_nongoals = bool(re.search(r'###\s*Non-Goals|###\s*이번에는 안 하는 것', content))
    checks.append({
        "name": "non_goals",
        "pass": has_nongoals,
        "detail": "Non-Goals 섹션 존재" if has_nongoals else "Non-Goals 섹션 없음 (권장)",
    })

    # 6. 스펙 아티팩트 참조 (spec_type이 ops-change가 아닌 경우)
    spec_types = fm.get("spec_type", [])
    is_ops = not spec_types or spec_types == ["ops-change"]
    has_artifacts = bool(re.search(r'###\s*스펙 아티팩트', content))

    if is_ops:
        detail = "운영 변경 — 스펙 아티팩트 불필요"
        passed = True
    else:
        passed = has_artifacts
        detail = "스펙 아티팩트 테이블 존재" if passed else "스펙 아티팩트 섹션 없음 (권장)"

    checks.append({"name": "spec_artifacts", "pass": passed, "detail": detail})

    pass_count = sum(1 for c in checks if c["pass"])
    return {
        "success": True,
        "filename": filename,
        "title": fm.get("title", filename),
        "status": fm.get("status", ""),
        "pass_count": pass_count,
        "total_checks": len(checks),
        "checks": checks,
    }


def validate_all() -> dict:
    """모든 Tech Spec을 검증한다."""
    if not os.path.isdir(SPEC_DIR):
        return {"success": False, "error": f"디렉토리를 찾을 수 없습니다: {SPEC_DIR}"}

    results = []
    for filename in sorted(os.listdir(SPEC_DIR)):
        if not filename.endswith(".md"):
            continue
        results.append(validate_spec(filename))

    return {"success": True, "results": results}


def update_content(filename: str, section: str, content_file: str) -> dict:
    """H2 섹션의 내용을 교체한다."""
    filepath = os.path.join(SPEC_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(content_file, encoding="utf-8") as f:
        new_section_content = f.read().strip()

    with open(filepath, encoding="utf-8") as f:
        doc = f.read()

    # H2 섹션 패턴: ## 섹션명\n내용...\n(다음 ## 또는 EOF)
    # \n?\Z 로 파일 끝에 개행이 없어도 마지막 섹션을 올바르게 매칭
    pattern = rf'(## {re.escape(section)}\s*\n)(.*?)(?=\n## |\n?\Z)'
    match = re.search(pattern, doc, re.DOTALL)
    if not match:
        return {"success": False, "error": f"섹션을 찾을 수 없습니다: ## {section}"}

    new_doc = doc[:match.start()] + f"## {section}\n\n{new_section_content}\n" + doc[match.end():]

    # last_reviewed 갱신
    today = date.today().isoformat()
    new_doc = re.sub(
        r"^last_reviewed:\s*.+$",
        f"last_reviewed: {today}",
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
        "section": section,
        "action": "replaced",
        "last_reviewed": today,
    }


def append_content(filename: str, section: str, content_file: str) -> dict:
    """H2 섹션 끝에 내용을 추가한다 (실행 기록 등에 사용)."""
    filepath = os.path.join(SPEC_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    with open(content_file, encoding="utf-8") as f:
        append_text = f.read().strip()

    with open(filepath, encoding="utf-8") as f:
        doc = f.read()

    # H2 섹션의 끝 위치 찾기
    # \n?\Z 로 파일 끝에 개행이 없어도 마지막 섹션을 올바르게 매칭
    pattern = rf'(## {re.escape(section)}\s*\n)(.*?)(?=\n## |\n?\Z)'
    match = re.search(pattern, doc, re.DOTALL)
    if not match:
        return {"success": False, "error": f"섹션을 찾을 수 없습니다: ## {section}"}

    existing_content = match.group(2).rstrip()
    new_section = f"## {section}\n{existing_content}\n\n{append_text}\n"
    new_doc = doc[:match.start()] + new_section + doc[match.end():]

    # last_reviewed 갱신
    today = date.today().isoformat()
    new_doc = re.sub(
        r"^last_reviewed:\s*.+$",
        f"last_reviewed: {today}",
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
        "section": section,
        "action": "appended",
        "last_reviewed": today,
    }


def search_specs(query: str, limit: int = 10) -> dict:
    """키워드로 Tech Spec을 검색한다. title > tags > aliases > 본문 순 우선순위."""
    if not os.path.isdir(SPEC_DIR):
        return {"success": False, "error": f"디렉토리를 찾을 수 없습니다: {SPEC_DIR}"}

    query_lower = query.lower()
    results = []

    for filename in os.listdir(SPEC_DIR):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(SPEC_DIR, filename)
        fm = parse_frontmatter(filepath)
        title = fm.get("title", os.path.splitext(filename)[0])
        tags = fm.get("tags", [])
        aliases = fm.get("aliases", [])

        # 매칭 우선순위 결정
        match_source = None
        if query_lower in title.lower():
            match_source = "title"
        elif any(query_lower in t.lower() for t in tags):
            match_source = "tags"
        elif any(query_lower in a.lower() for a in aliases):
            match_source = "aliases"
        else:
            # 본문 검색 (처음 5000자)
            try:
                with open(filepath, encoding="utf-8") as f:
                    body = f.read(5000)
                if query_lower in body.lower():
                    match_source = "body"
            except (OSError, UnicodeDecodeError):
                pass

        if match_source:
            results.append({
                "filename": filename,
                "title": title,
                "status": fm.get("status", ""),
                "tags": tags,
                "match_source": match_source,
                "filepath": filepath,
            })

    # 우선순위 정렬: title > tags > aliases > body
    priority = {"title": 0, "tags": 1, "aliases": 2, "body": 3}
    results.sort(key=lambda x: priority.get(x["match_source"], 9))
    results = results[:limit]

    return {
        "success": True,
        "query": query,
        "count": len(results),
        "results": results,
    }


def read_section(filename: str, section: str, level: int = 2) -> dict:
    """특정 섹션의 내용을 반환한다. section='frontmatter'이면 frontmatter dict 반환."""
    filepath = os.path.join(SPEC_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {filename}"}

    # frontmatter 특수 처리
    if section.lower() == "frontmatter":
        fm = parse_frontmatter(filepath)
        return {
            "success": True,
            "section": "frontmatter",
            "level": 0,
            "content": fm,
            "filepath": filepath,
        }

    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    heading_prefix = "#" * level + " "
    # H3은 H2 또는 H3가 경계, H2는 H2가 경계
    boundary_prefixes = ["## "] if level == 2 else ["## ", "### "]

    in_section = False
    section_lines = []

    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith(heading_prefix) and stripped[level + 1:].strip() == section:
            in_section = True
            continue
        if in_section:
            # 섹션 종료 조건: 같은 레벨 또는 상위 레벨 헤딩
            is_boundary = any(stripped.startswith(p) for p in boundary_prefixes)
            if is_boundary and not stripped.startswith(heading_prefix + section):
                break
            section_lines.append(line.rstrip("\n"))

    if not in_section:
        return {
            "success": False,
            "error": f"섹션을 찾을 수 없습니다: {'#' * level} {section}",
        }

    content = "\n".join(section_lines).strip()
    return {
        "success": True,
        "section": section,
        "level": level,
        "content": content,
        "filepath": filepath,
    }


def migrate_spec(filepath: str, dry_run: bool = True) -> dict:
    """기존 Tech Spec을 새 표준으로 마이그레이션한다.
    - 태그를 domain/ 형식으로 정규화
    - aliases 자동 추출
    - last_reviewed 추가 (없으면)
    - type: tech-spec 추가 (없으면)
    - '실행 기록' 섹션 추가 (없으면)
    """
    filename = os.path.basename(filepath)
    fm = parse_frontmatter(filepath)
    changes = []

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    new_content = content

    # 1. 태그 정규화
    old_tags = fm.get("tags", [])
    new_tags = normalize_tags(old_tags)
    if set(old_tags) != set(new_tags) and new_tags:
        changes.append(f"tags: {old_tags} → {new_tags}")
        if not dry_run:
            # tags 블록 교체 (\n? 로 마지막 줄에 개행 없어도 매칭)
            tag_yaml = "\n".join(f"  - {t}" for t in new_tags)
            new_content = re.sub(
                r'^tags:\s*\n(?:  - .+\n?)*',
                f"tags:\n{tag_yaml}\n",
                new_content,
                count=1,
                flags=re.MULTILINE,
            )
            # tags: [] 형식도 처리
            if "tags: []" in new_content:
                new_content = new_content.replace(
                    "tags: []",
                    f"tags:\n{tag_yaml}",
                    1,
                )

    # 2. aliases — migrate 시에는 기존 값 유지 (수동 지정 필요)

    # 3. last_reviewed 추가
    if "last_reviewed:" not in content:
        today = date.today().isoformat()
        doc_date = fm.get("date", today)
        changes.append(f"last_reviewed: (추가) {doc_date}")
        if not dry_run:
            new_content = new_content.replace(
                f"\ndate: {doc_date}\n",
                f"\ndate: {doc_date}\nlast_reviewed: {doc_date}\n",
                1,
            )

    # 4. type: tech-spec 추가
    if "type:" not in content:
        changes.append("type: tech-spec (추가)")
        if not dry_run:
            new_content = re.sub(
                r'^(status:\s*.+)$',
                r'\1\ntype: tech-spec',
                new_content,
                count=1,
                flags=re.MULTILINE,
            )

    # 5. spec_type 필드 추가 (없으면)
    if "spec_type:" not in content:
        changes.append("spec_type: [] (추가)")
        if not dry_run:
            new_content = re.sub(
                r'^(type:\s*.+)$', r'\1\nspec_type: []',
                new_content, count=1, flags=re.MULTILINE,
            )

    # 6. '실행 기록' 섹션 추가
    if "## 실행 기록" not in content:
        changes.append("'실행 기록' 섹션 추가")
        if not dry_run:
            # '실제 결과' 앞에 삽입, 없으면 문서 끝에 추가
            if "## 실제 결과" in new_content:
                new_content = new_content.replace(
                    "## 실제 결과",
                    "## 실행 기록\n\n> 실행 시작 후 기록\n\n## 실제 결과",
                )
            else:
                new_content = new_content.rstrip() + "\n\n## 실행 기록\n\n> 실행 시작 후 기록\n"

    if not dry_run and changes:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return {
        "filename": filename,
        "title": fm.get("title", filename),
        "changes": changes,
        "changed": len(changes) > 0,
    }


def migrate_all(dry_run: bool = True) -> dict:
    """모든 Tech Spec을 마이그레이션한다."""
    if not os.path.isdir(SPEC_DIR):
        return {"success": False, "error": f"디렉토리를 찾을 수 없습니다: {SPEC_DIR}"}

    results = []
    for filename in sorted(os.listdir(SPEC_DIR)):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(SPEC_DIR, filename)
        results.append(migrate_spec(filepath, dry_run))

    changed_count = sum(1 for r in results if r["changed"])
    return {
        "success": True,
        "dry_run": dry_run,
        "total": len(results),
        "changed": changed_count,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Tech Spec 관리")
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Tech Spec 생성")
    p_create.add_argument("--title", required=True, help="스펙 제목")
    p_create.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_create.add_argument("--aliases", default="", help="aliases 키워드 3개 (콤마 구분, 예: Karpenter,NodePool,스케줄링)")
    p_create.add_argument("--content-file", default="", help="본문 파일 경로")
    p_create.add_argument("--spec-type", default="", help="스펙 유형 (콤마 구분)")

    # list
    p_list = sub.add_parser("list", help="Tech Spec 목록")
    p_list.add_argument("--limit", type=int, default=10)
    p_list.add_argument("--status", default="", help="상태 필터 (시작전, 진행중, 완료)")

    # update-status
    p_status = sub.add_parser("update-status", help="상태 변경")
    p_status.add_argument("--filename", required=True, help="대상 파일명")
    p_status.add_argument("--status", required=True, help="새 상태 (시작전, 진행중, 완료)")

    # validate
    p_validate = sub.add_parser("validate", help="품질 검증")
    p_validate.add_argument("--filename", default="", help="대상 파일명 (없으면 전체)")
    p_validate.add_argument("--all", action="store_true", help="전체 검증")

    # update-content
    p_update = sub.add_parser("update-content", help="H2 섹션 내용 교체")
    p_update.add_argument("--filename", required=True, help="대상 파일명")
    p_update.add_argument("--section", required=True, help="H2 섹션명")
    p_update.add_argument("--content-file", required=True, help="새 내용 파일")

    # append-content
    p_append = sub.add_parser("append-content", help="H2 섹션에 내용 추가")
    p_append.add_argument("--filename", required=True, help="대상 파일명")
    p_append.add_argument("--section", required=True, help="H2 섹션명")
    p_append.add_argument("--content-file", required=True, help="추가할 내용 파일")

    # migrate
    p_migrate = sub.add_parser("migrate", help="기존 문서 마이그레이션")
    p_migrate.add_argument("--dry-run", action="store_true", help="변경 미적용 (미리보기)")
    p_migrate.add_argument("--apply", action="store_true", help="변경 적용")

    # search
    p_search = sub.add_parser("search", help="키워드로 스펙 검색")
    p_search.add_argument("--query", required=True, help="검색 키워드")
    p_search.add_argument("--limit", type=int, default=10, help="최대 결과 수")

    # read-section
    p_read = sub.add_parser("read-section", help="특정 섹션 읽기")
    p_read.add_argument("--filename", required=True, help="대상 파일명")
    p_read.add_argument("--section", required=True, help="섹션명 (또는 'frontmatter')")
    p_read.add_argument("--level", type=int, default=2, choices=[2, 3], help="헤딩 레벨")

    args = parser.parse_args()

    if args.command == "create":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        aliases = [a.strip() for a in args.aliases.split(",") if a.strip()][:3] if args.aliases else []
        spec_types = [s.strip() for s in args.spec_type.split(",") if s.strip()] if args.spec_type else []
        invalid_types = [s for s in spec_types if s not in VALID_SPEC_TYPES]
        if invalid_types:
            print(json.dumps({
                "success": False,
                "error": f"유효하지 않은 spec_type: {invalid_types}. 허용값: {sorted(VALID_SPEC_TYPES)}",
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
        content = ""
        if args.content_file and os.path.exists(args.content_file):
            with open(args.content_file, encoding="utf-8") as f:
                raw = f.read()
            try:
                data = json.loads(raw)
                content = data.get("blocks", raw)
            except json.JSONDecodeError:
                content = raw
        result = create_spec(args.title, tags, content, spec_types, aliases)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "list":
        result = list_specs(args.limit, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "update-status":
        result = update_status(args.filename, args.status)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "validate":
        if args.all or not args.filename:
            result = validate_all()
        else:
            result = validate_spec(args.filename)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "update-content":
        result = update_content(args.filename, args.section, args.content_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "append-content":
        result = append_content(args.filename, args.section, args.content_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "migrate":
        dry_run = not args.apply
        result = migrate_all(dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "search":
        result = search_specs(args.query, args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "read-section":
        result = read_section(args.filename, args.section, args.level)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
