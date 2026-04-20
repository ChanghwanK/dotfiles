#!/usr/bin/env python3
"""
Obsidian vault 공유 유틸리티.
obsidian:query, obsidian:lint 스킬에서 공통으로 사용한다.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

VAULT_BASE = "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home"

SCAN_DIRS = {
    # LLM Wiki 구조 (현재)
    "wiki":      "04. Wiki",
    "sources":   "02. Sources",
    "resources": "03. Resources",
    "daily":     "01. Daily",
    "inbox":     "00. Inbox",
    # 레거시 (디렉터리 미존재 — 하위 호환용)
    "notes":     "02. Notes",
    "moc":       "04. MOC",
}

REQUIRED_METADATA = {"title", "date", "type", "tags"}
VALID_STATUSES = {"active", "draft", "archived"}
VALID_TYPES = {
    # LLM Wiki 타입
    "concept", "system", "incident", "synthesis", "career",
    # 리소스 타입
    "runbook", "troubleshooting", "cheatsheet",
    # 레거시 (하위 호환)
    "daily", "weekly", "learning-note", "tech-spec", "history",
}


@dataclass
class NoteInfo:
    filename: str
    filepath: str
    title: str
    date_str: str
    last_reviewed: str
    status: str
    note_type: str
    tags: list
    aliases: list
    outlinks: set = field(default_factory=set)
    content_text: str = ""

    @property
    def domain_tags(self) -> set:
        return {t for t in self.tags if t.startswith("domain/")}


class VaultScanner:
    def __init__(self, vault_base: str = VAULT_BASE):
        self.vault_base = vault_base
        self._notes: Optional[list] = None
        self._filename_map: Optional[dict] = None
        self._alias_index: Optional[dict] = None

    def scan_all(self, scopes=("notes", "resources")) -> list:
        if self._notes is not None:
            return self._notes

        notes = []
        for scope in scopes:
            dir_rel = SCAN_DIRS.get(scope)
            if not dir_rel:
                continue
            dir_abs = os.path.join(self.vault_base, dir_rel)
            if not os.path.isdir(dir_abs):
                continue
            for root, _, files in os.walk(dir_abs):
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        note = self._parse_note(fpath, fname)
                        if note:
                            notes.append(note)
                    except Exception:
                        pass

        self._notes = notes
        return notes

    def scan_scope(self, scope: str) -> list:
        dir_rel = SCAN_DIRS.get(scope)
        if not dir_rel:
            return []
        dir_abs = os.path.join(self.vault_base, dir_rel)
        if not os.path.isdir(dir_abs):
            return []
        notes = []
        for root, _, files in os.walk(dir_abs):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    note = self._parse_note(fpath, fname)
                    if note:
                        notes.append(note)
                except Exception:
                    pass
        return notes

    def _parse_note(self, filepath: str, filename: str) -> Optional["NoteInfo"]:
        fm, body = parse_frontmatter(filepath)
        outlinks = extract_wikilinks(body)
        return NoteInfo(
            filename=filename,
            filepath=filepath,
            title=fm.get("title", filename.replace(".md", "")),
            date_str=str(fm.get("date", "")),
            last_reviewed=str(fm.get("last_reviewed", "")),
            status=str(fm.get("status", "active")),
            note_type=str(fm.get("type", "")),
            tags=_to_list(fm.get("tags", [])),
            aliases=_to_list(fm.get("aliases", [])),
            outlinks=set(outlinks),
            content_text=body,
        )

    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

    def build_filename_map(self) -> dict:
        """filename (stem) → filepath 매핑 (슬러그 정규화 포함). 이미지 파일은 전체 파일명으로 매핑."""
        if self._filename_map is not None:
            return self._filename_map

        result = {}
        for root, _, files in os.walk(self.vault_base):
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()
                if fname.endswith(".md"):
                    stem = fname[:-3]
                    result[stem] = fpath
                    slug = slugify_for_match(stem)
                    if slug not in result:
                        result[slug] = fpath
                elif ext in self._IMAGE_EXTS:
                    result[fname] = fpath

        self._filename_map = result
        return result

    def build_alias_index(self) -> dict:
        """alias/title → [NoteInfo] 역방향 인덱스. 검색 엔트리포인트."""
        if self._alias_index is not None:
            return self._alias_index

        notes = self.scan_all()
        index: dict = {}

        for note in notes:
            # title을 검색 키로
            for key in [note.title] + note.aliases:
                if not key:
                    continue
                k = key.lower()
                index.setdefault(k, [])
                if note not in index[k]:
                    index[k].append(note)

        self._alias_index = index
        return index

    def resolve_link(self, link_text: str) -> Optional[str]:
        """[[link_text]] 또는 [[link_text|alias]] → 절대 파일 경로"""
        pipe = link_text.find("|")
        target = link_text[:pipe] if pipe != -1 else link_text
        target = target.strip()

        fmap = self.build_filename_map()
        if target in fmap:
            return fmap[target]
        slug = slugify_for_match(target)
        return fmap.get(slug)

    def build_link_graph(self) -> dict:
        """filename → inbound links set (역방향 링크 그래프)"""
        notes = self.scan_all(scopes=("wiki", "resources"))
        inbound: dict = {}

        for note in notes:
            inbound.setdefault(note.filename, set())

        for note in notes:
            for raw_link in note.outlinks:
                resolved = self.resolve_link(raw_link)
                if resolved:
                    target_fname = os.path.basename(resolved)
                    inbound.setdefault(target_fname, set())
                    inbound[target_fname].add(note.filename)

        return inbound


def parse_frontmatter(path: str) -> tuple:
    """파일에서 YAML frontmatter와 body를 분리해 반환한다."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return {}, ""

    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    yaml_str = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")

    fm = _parse_simple_yaml(yaml_str)
    return fm, body


def extract_wikilinks(content: str) -> list:
    """본문에서 [[link]] 및 [[link|alias]] 패턴을 추출한다. 코드 블록/인라인 코드 내부는 제외."""
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content = re.sub(r'`[^`\n]*`', '', content)
    pattern = re.compile(r'\[\[([^\]]+)\]\]')
    links = []
    for m in pattern.finditer(content):
        links.append(m.group(1))
    return links


def slugify_for_match(text: str) -> str:
    """링크 해석용 정규화: 공백→하이픈, 소문자, 특수문자 제거."""
    text = text.lower()
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'[^\w\-가-힣]', '', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text


def stale_days(last_reviewed_str: str, ref_date: Optional[date] = None) -> Optional[int]:
    """last_reviewed로부터 경과 일수를 반환한다. 파싱 실패 시 None."""
    if not last_reviewed_str or last_reviewed_str in ("", "None"):
        return None
    ref = ref_date or date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.strptime(str(last_reviewed_str), fmt).date()
            return (ref - d).days
        except ValueError:
            continue
    return None


def _to_list(val) -> list:
    if isinstance(val, list):
        return [str(x) for x in val]
    if val is None or val == "":
        return []
    return [str(val)]


def _parse_simple_yaml(yaml_str: str) -> dict:
    """stdlib만으로 YAML subset 파싱 (list, scalar 지원)."""
    result = {}
    lines = yaml_str.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        colon = line.find(":")
        if colon == -1:
            i += 1
            continue

        key = line[:colon].strip()
        rest = line[colon + 1:].strip()

        if rest == "" or rest == "[]":
            # 다음 줄이 리스트 항목인지 확인
            items = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("  - "):
                item = lines[j].strip()[2:].strip().strip('"').strip("'")
                items.append(item)
                j += 1
            if j > i + 1:
                result[key] = items
                i = j
            else:
                result[key] = []
                i += 1
        elif rest.startswith("["):
            inner = rest.strip("[]")
            if inner:
                items = [x.strip().strip('"').strip("'") for x in inner.split(",")]
                result[key] = [x for x in items if x]
            else:
                result[key] = []
            i += 1
        else:
            val = rest.strip('"').strip("'")
            result[key] = val
            i += 1

    return result
