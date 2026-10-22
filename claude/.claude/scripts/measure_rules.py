#!/usr/bin/env python3
"""상시 로드되는 지침의 분량을 잰다.

전역 계열은 고정 목록이 아니라 실제 로딩 규칙으로 센다:
  - ~/.claude/CLAUDE.md 와 그 안의 `@` import (재귀)
  - ~/.claude/rules/*.md 중 `paths:` frontmatter가 없는 파일(항상 로드)
훅으로 주입되거나 Read 지시로 읽는 docs는 상시 로드가 아니라 별도로 표시한다.
"""
import pathlib
import re

HOME = pathlib.Path.home()
CLAUDE_DIR = HOME / ".claude"
REPO = HOME / "workspace/riiid/kubernetes"
MEM = CLAUDE_DIR / "projects/-Users-changhwan-workspace-riiid-kubernetes/memory"
IMPORT = re.compile(r"(?m)^@(\S+)")


def imported(path, seen):
    """파일과 그 파일이 `@`로 import하는 파일을 재귀로 모은다."""
    path = path.expanduser().resolve()
    if path in seen or not path.exists():
        return
    seen.append(path)
    for ref in IMPORT.findall(path.read_text()):
        target = pathlib.Path(ref).expanduser()
        if not target.is_absolute():
            target = path.parent / target
        imported(target, seen)


def always_rules():
    out = []
    for p in sorted((CLAUDE_DIR / "rules").glob("*.md")):
        text = p.read_text()
        if p.stat().st_size and not re.match(r"(?s)^---\n.*?\bpaths:", text):
            out.append(p.resolve())
    return out


def report(title, paths):
    total = 0
    print(f"== {title}")
    for p in paths:
        n = len(p.read_text())
        total += n
        print(f"{n:>7}  {p.name}")
    print(f"{total:>7}  TOTAL\n")
    return total


global_files = []
imported(CLAUDE_DIR / "CLAUDE.md", global_files)
global_total = report("전역 상시 로드 (CLAUDE.md + @import + paths 없는 rules)", global_files + always_rules())

project_files = []
imported(REPO / "CLAUDE.md", project_files)
project_files.append((MEM / "MEMORY.md").resolve())
project_total = report("kubernetes 프로젝트 상시 로드 (CLAUDE.md + @import + MEMORY.md)", project_files)

print(f"kubernetes 세션 합계: {global_total + project_total}\n")

on_demand = sorted(p.resolve() for p in (CLAUDE_DIR / "docs").glob("*.md") if p.resolve() not in global_files)
report("on-demand docs (훅 주입 또는 Read 지시, 상시 로드 아님)", on_demand)

files = [p for p in MEM.glob("*.md") if p.name != "MEMORY.md"]
print("memory files", len(files), "| feedback", sum(p.name.startswith("feedback") for p in files),
      "| MEMORY.md bytes", (MEM / "MEMORY.md").stat().st_size)
