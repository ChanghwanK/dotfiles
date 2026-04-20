#!/usr/bin/env python3
"""
manage_skill.py — Skill lifecycle management CLI
Commands: list, show, create, validate, update-frontmatter, delete, restore
stdlib only: argparse, json, pathlib, shutil, re, os, datetime
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILLS_DIR = Path.home() / ".claude" / "skills"
BACKUPS_DIR = SKILLS_DIR / ".backups"

REQUIRED_FIELDS = {"name", "description"}
ALLOWED_FIELDS = {"name", "description", "model", "allowed-tools", "license", "metadata"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+([:-][a-z0-9]+)*$")
MAX_NAME_LEN = 64


# ─── Frontmatter Parsing ────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from skill content. Returns (fields, body)."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    fields = {}

    i = 0
    lines = raw.splitlines()
    while i < len(lines):
        line = lines[i]
        # Skip blank lines
        if not line.strip():
            i += 1
            continue

        # Key: value or key: |
        m = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue

        key = m.group(1)
        val = m.group(2).strip()

        if val == "|":
            # Block scalar — collect indented lines
            block_lines = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith("  ")):
                block_lines.append(lines[i][2:] if lines[i].startswith("  ") else "")
                i += 1
            fields[key] = "\n".join(block_lines).strip()
        elif not val:
            # Possibly a list follows
            items = []
            i += 1
            while i < len(lines) and re.match(r"^\s+-\s+", lines[i]):
                items.append(re.sub(r"^\s+-\s+", "", lines[i]))
                i += 1
            fields[key] = items if items else ""
        else:
            fields[key] = val
            i += 1

    return fields, body


def build_frontmatter(fields: dict) -> str:
    """Serialize fields back to YAML frontmatter block."""
    lines = ["---"]
    for key, val in fields.items():
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        elif isinstance(val, str) and "\n" in val:
            lines.append(f"{key}: |")
            for sub in val.splitlines():
                lines.append(f"  {sub}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def read_skill_file(skill_path: Path) -> tuple[dict, str, str]:
    """Read SKILL.md and return (frontmatter, body, raw_text)."""
    skill_md = skill_path / "SKILL.md"
    raw = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    return fm, body, raw


# ─── Helpers ────────────────────────────────────────────────────────────────

def ok(data: dict):
    print(json.dumps({"success": True, **data}, ensure_ascii=False, indent=2))


def err(msg: str, **extra):
    print(json.dumps({"success": False, "error": msg, **extra}, ensure_ascii=False, indent=2))
    sys.exit(1)


def skill_path(name: str) -> Path:
    return SKILLS_DIR / name


def list_skill_dirs() -> list[Path]:
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        [p for p in SKILLS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name,
    )


def file_info(p: Path) -> dict:
    stat = p.stat()
    return {
        "name": p.name,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_list(args):
    skills = []
    for d in list_skill_dirs():
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm, _, _ = read_skill_file(d)
        except Exception:
            fm = {}

        scripts_dir = d / "scripts"
        script_files = list(scripts_dir.glob("*.py")) if scripts_dir.exists() else []

        stat = skill_md.stat()
        skills.append({
            "name": fm.get("name", d.name),
            "description": (fm.get("description", "")[:80].replace("\n", " ") + "...")
                           if len(fm.get("description", "")) > 80 else fm.get("description", ""),
            "model": fm.get("model", "default"),
            "path": str(d),
            "has_scripts": scripts_dir.exists(),
            "script_count": len(script_files),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })

    ok({"count": len(skills), "skills": skills})


def cmd_show(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found", path=str(sp))

    skill_md = sp / "SKILL.md"
    if not skill_md.exists():
        err(f"SKILL.md not found in '{name}'")

    fm, body, _ = read_skill_file(sp)

    # File listing
    all_files = []
    for f in sorted(sp.rglob("*")):
        if f.is_file():
            rel = f.relative_to(sp)
            all_files.append(file_info(f) | {"path": str(rel)})

    # Validate inline
    checks, warnings, info = _validate_checks(name, sp, fm, body)
    valid = all(c["passed"] for c in checks)

    ok({
        "name": name,
        "frontmatter": fm,
        "body_preview": body[:200].replace("\n", "\\n") + ("..." if len(body) > 200 else ""),
        "body_length": len(body),
        "files": all_files,
        "validation": {
            "valid": valid,
            "checks": checks,
            "warnings": warnings,
            "info": info,
        },
    })


DESTRUCTIVE_KEYWORDS = re.compile(
    r"\b(delete|drop|destroy|remove|rm\s+-rf|truncate|purge|reset)\b|삭제|파괴|초기화",
    re.IGNORECASE,
)
CONFIRMATION_KEYWORDS = re.compile(
    r"\b(confirm|confirmation|dry[\s-]?run|preview|--apply)\b|확인|동의|미리보기|되돌릴",
    re.IGNORECASE,
)
VALIDATION_KEYWORDS = re.compile(r"검증|validate|verify|확인", re.IGNORECASE)


def _validate_checks(name: str, sp: Path, fm: dict, body: str) -> tuple[list, list, list]:
    checks = []
    warnings = []
    info = []

    def chk(rule: str, passed: bool, detail: str = ""):
        checks.append({"rule": rule, "passed": passed, "detail": detail})

    # 1. SKILL.md exists
    chk("skill_md_exists", (sp / "SKILL.md").exists(), str(sp / "SKILL.md"))

    # 2. Frontmatter starts with ---
    raw = (sp / "SKILL.md").read_text(encoding="utf-8") if (sp / "SKILL.md").exists() else ""
    chk("frontmatter_present", raw.startswith("---"), "File must start with ---")

    # 3. Required fields
    missing = REQUIRED_FIELDS - set(fm.keys())
    chk("required_fields", not missing,
        f"Missing: {', '.join(sorted(missing))}" if missing else "name, description present")

    # 4. No unknown fields
    unknown = set(fm.keys()) - ALLOWED_FIELDS
    chk("no_unknown_fields", not unknown,
        f"Unknown: {', '.join(sorted(unknown))}" if unknown else "All fields allowed")

    # 5. Name matches directory
    fm_name = fm.get("name", "")
    chk("name_matches_dir", fm_name == name,
        f"frontmatter name='{fm_name}' vs dir='{name}'" if fm_name != name else "match")

    # 6. Name format
    chk("name_format", bool(NAME_PATTERN.match(fm_name)) if fm_name else False,
        f"'{fm_name}' must match ^[a-z0-9]+([:-][a-z0-9]+)*$ and be ≤{MAX_NAME_LEN} chars")

    # 7. Description not empty
    desc = fm.get("description", "")
    chk("description_not_empty", bool(desc.strip()), "description must not be blank")

    # 8. allowed-tools script paths exist (python3 .py and bash .sh)
    tools = fm.get("allowed-tools", [])
    if isinstance(tools, list):
        missing_scripts = []
        for tool in tools:
            m_py = re.search(r"python3\s+(/[^\s]+\.py)", tool)
            if m_py:
                script_p = Path(m_py.group(1))
                if not script_p.exists():
                    missing_scripts.append(str(script_p))
            m_sh = re.search(r"bash\s+(/[^\s]+\.sh)", tool)
            if m_sh:
                script_p = Path(m_sh.group(1))
                if not script_p.exists():
                    missing_scripts.append(str(script_p))
        chk("script_files_exist", not missing_scripts,
            f"Missing: {missing_scripts}" if missing_scripts else "All referenced scripts exist")
    else:
        chk("script_files_exist", True, "No allowed-tools to check")

    # 9. Body not empty
    chk("body_not_empty", bool(body.strip()), "SKILL.md body must not be empty")

    # Warnings (non-blocking)
    if "TODO" in body or "TODO" in str(fm):
        warnings.append("TODO placeholders still present in SKILL.md")
    if len(desc) > 300:
        warnings.append(f"description is long ({len(desc)} chars) — consider shortening")

    # Quality warnings (Rule 2, 3, 5 — references/skill-conventions.md Section 5)
    body_lines = body.splitlines()
    if len(body_lines) > 500:
        warnings.append(
            f"body is {len(body_lines)} lines — Rule 3: keep under 500 lines, split details into references/"
        )
    trigger_pattern = re.compile(r"이 스킬은.{0,20}(할 때|씁니다|사용합니다)")
    if trigger_pattern.search(body):
        warnings.append(
            "body may contain trigger description — Rule 2: 'when to use' belongs in description only"
        )
    always_count = len(re.findall(r"\balways\b|\b항상\b", body))
    if always_count > 0:
        warnings.append(
            f"found {always_count} 'always'/'항상' in body — Rule 5: use 'MUST' or '반드시' instead"
        )

    # Separation of concerns warnings (Rule 6 — references/skill-conventions.md Section 5.6)
    # W1: raw system commands in allowed-tools (should be wrapped in scripts/)
    if isinstance(tools, list):
        SAFE_BASH = [
            re.compile(r"^Bash\(python3\s+/"),
            re.compile(r"^Bash\(bash\s+/"),
            re.compile(r"^Bash\(kubectl\s+"),
        ]
        NON_BASH = {"Read", "Write", "Edit", "Glob", "Grep"}
        for tool in tools:
            if tool in NON_BASH:
                continue
            if not tool.startswith("Bash("):
                continue
            if not any(p.match(tool) for p in SAFE_BASH):
                warnings.append(
                    f"allowed-tools에 raw 시스템 명령 '{tool}' 발견 — scripts/로 래핑 권장"
                )

    # W2: large code blocks in body (>= 15 lines should go to assets/ or references/)
    fenced_blocks = re.findall(r"```[^\n]*\n(.*?)```", body, re.DOTALL)
    for block in fenced_blocks:
        line_count = len(block.splitlines())
        if line_count >= 15:
            warnings.append(
                f"body에 {line_count}줄짜리 코드 블록 발견 — assets/ 또는 references/로 분리 권장"
            )

    # W3: agents/ directory is empty (no .md files)
    agents_dir = sp / "agents"
    has_agent_files = False
    if agents_dir.exists() and agents_dir.is_dir():
        agent_files = list(agents_dir.glob("*.md"))
        has_agent_files = bool(agent_files)
        if not agent_files:
            warnings.append(
                "agents/ 디렉토리가 비어 있음 — .md 프롬프트 파일을 추가하거나 디렉토리를 삭제하세요"
            )
        else:
            # W4: agents/*.md files not referenced in body
            for agent_file in agent_files:
                if agent_file.name not in body:
                    warnings.append(
                        f"agents/{agent_file.name}가 body에서 참조되지 않음 — SKILL.md에서 Read로 참조하세요"
                    )

    # ─── BP semantic checks ──────────────────────────────────────────────
    # BP1: description must include "사용 시점:" + "트리거 키워드:" literals
    if desc and "사용 시점" not in desc:
        warnings.append("[BP] description에 '사용 시점:' 누락 — 트리거 판단을 위해 필수")
    if desc and "트리거 키워드" not in desc and "트리거" not in desc:
        warnings.append("[BP] description에 '트리거 키워드:' 누락 — 활성화 정확도 저하")

    # BP2: description length cap (Anthropic BP: ≤ 1024 chars)
    if len(desc) > 1024:
        warnings.append(f"[BP] description {len(desc)}자 — 1024자 초과, 핵심만 남기기")

    # BP3: references one-level deep (no nested subdirs)
    refs_dir = sp / "references"
    if refs_dir.exists():
        nested = [p for p in refs_dir.rglob("*") if p.is_file() and p.parent != refs_dir]
        if nested:
            sample = ", ".join(str(p.relative_to(sp)) for p in nested[:3])
            warnings.append(
                f"[BP] references/ 하위 중첩 디렉토리 발견 ({sample}) — one-level deep 권장"
            )

    # ─── Parallelism (Agent) cross-check ─────────────────────────────────
    tools_str = " ".join(tools) if isinstance(tools, list) else str(tools)
    has_agent_tool = "Agent" in (tools if isinstance(tools, list) else [tools_str])
    if has_agent_files and not has_agent_tool:
        warnings.append(
            "[parallelism] agents/ 존재하나 frontmatter allowed-tools에 Agent 없음 — 추가 필요"
        )
    if has_agent_tool and not has_agent_files:
        warnings.append(
            "[parallelism] allowed-tools에 Agent 있으나 agents/*.md 없음 — 인라인 프롬프트는 10줄 이상 시 분리 권장"
        )

    # ─── Harness checks (destructive/confirmation/dry-run) ───────────────
    # H1: destructive keywords in body must mention confirmation pattern
    if DESTRUCTIVE_KEYWORDS.search(body) and not CONFIRMATION_KEYWORDS.search(body):
        warnings.append(
            "[harness] body에 파괴적 작업(delete/drop/삭제 등) 언급 — confirmation/dry-run 패턴 명시 필요"
        )

    # H2: workflow last step should mention validation/verification
    step_pattern = re.compile(r"^###\s+Step\s+\d+", re.MULTILINE)
    steps = list(step_pattern.finditer(body))
    if len(steps) >= 2:
        last_step_start = steps[-1].start()
        last_step_chunk = body[last_step_start:]
        if not VALIDATION_KEYWORDS.search(last_step_chunk):
            info.append(
                "[harness] 마지막 Step에 검증/validate 키워드 없음 — Rule 5.5 검증 루프 권장"
            )

    # H3: scripts that mutate state should support --dry-run
    scripts_dir = sp / "scripts"
    if scripts_dir.exists():
        for script in scripts_dir.glob("*.py"):
            try:
                src = script.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            mutates = re.search(r"\b(write_text|mkdir|unlink|rmtree|copytree|os\.remove|shutil\.move)\b", src)
            has_dry_run = "dry-run" in src or "dry_run" in src
            if mutates and not has_dry_run:
                info.append(
                    f"[harness] scripts/{script.name}가 파일을 변경하나 --dry-run 없음 — 안전성 강화 권장"
                )

    return checks, warnings, info


def cmd_validate(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found")

    skill_md = sp / "SKILL.md"
    if not skill_md.exists():
        err(f"SKILL.md not found for '{name}'")

    fm, body, _ = read_skill_file(sp)
    checks, warnings, info = _validate_checks(name, sp, fm, body)
    valid = all(c["passed"] for c in checks)

    ok({"valid": valid, "checks": checks, "warnings": warnings, "info": info})


def _classify_finding(msg: str) -> str:
    """Bucket warnings/info into BP / parallelism / harness / quality."""
    if "[BP]" in msg:
        return "bp"
    if "[parallelism]" in msg:
        return "parallelism"
    if "[harness]" in msg:
        return "harness"
    return "quality"


def cmd_review(args):
    """Score a skill across BP / parallelism / harness dimensions.

    Read-only — no mutations. Designed to be the structural input for
    Claude's parallel-agent qualitative review (see SKILL.md Review workflow).
    """
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found")
    if not (sp / "SKILL.md").exists():
        err(f"SKILL.md not found for '{name}'")

    fm, body, _ = read_skill_file(sp)
    checks, warnings, info = _validate_checks(name, sp, fm, body)

    # Bucket findings by dimension
    buckets: dict[str, list[str]] = {"bp": [], "parallelism": [], "harness": [], "quality": []}
    for w in warnings:
        buckets[_classify_finding(w)].append(f"warning: {w}")
    for i in info:
        buckets[_classify_finding(i)].append(f"info: {i}")

    # Scoring: each dimension starts at 100, deductions per finding
    DEDUCTION = {"warning": 15, "info": 5}
    scores = {}
    for dim, items in buckets.items():
        score = 100
        for it in items:
            kind = it.split(":", 1)[0]
            score -= DEDUCTION.get(kind, 5)
        scores[dim] = max(0, score)

    # Failing structural checks → BP score floor of 0
    failed_checks = [c for c in checks if not c["passed"]]
    if failed_checks:
        scores["bp"] = 0

    overall = round(sum(scores.values()) / len(scores))

    # Inventory snapshot — feeds Claude's qualitative review agents
    body_lines = body.splitlines()
    agents_dir = sp / "agents"
    refs_dir = sp / "references"
    scripts_dir = sp / "scripts"
    # Extract per-agent model assignment from each agent file
    agent_inventory = []
    if agents_dir.exists():
        model_re = re.compile(r"\*\*Recommended model\*\*:\s*`?(\w+)`?")
        for agent_file in sorted(agents_dir.glob("*.md")):
            try:
                txt = agent_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = model_re.search(txt)
            agent_inventory.append({
                "file": agent_file.name,
                "model": m.group(1) if m else None,
                "first_50_chars": txt[:50].replace("\n", " "),
            })

    inventory = {
        "body_lines": len(body_lines),
        "body_lines_limit": 500,
        "description_chars": len(fm.get("description", "")),
        "description_chars_limit": 1024,
        "allowed_tools": fm.get("allowed-tools", []),
        "has_agents_dir": agents_dir.exists(),
        "agent_files": [p.name for p in agents_dir.glob("*.md")] if agents_dir.exists() else [],
        "agents": agent_inventory,
        "reference_files": [p.name for p in refs_dir.glob("*.md")] if refs_dir.exists() else [],
        "script_files": [p.name for p in scripts_dir.iterdir()] if scripts_dir.exists() else [],
    }

    ok({
        "name": name,
        "overall_score": overall,
        "scores": scores,
        "structural_pass": not failed_checks,
        "findings_by_dimension": buckets,
        "inventory": inventory,
        "next_step": (
            "Claude는 이 점수를 출발점으로, SKILL.md Review 워크플로우에 명시된 3개 Agent를 "
            "병렬 호출하여 정성 평가(BP 깊이, 컨텍스트 효율, 하네스 강건성)를 보완하세요."
        ),
    })


def _make_scaffold(name: str, description: str, model: str, skill_type: str,
                   with_agents: bool = False) -> str:
    """Generate a Korean-language SKILL.md scaffold with TODO placeholders."""
    model_line = f"\nmodel: {model}" if model else ""
    abs_scripts = f"/Users/changhwan/.claude/skills/{name}/scripts"

    frontmatter_lines = [
        "---",
        f"name: {name}",
        f"description: |",
        f"  {description}",
        f"  사용 시점: (1) TODO - 사용 상황 1, (2) TODO - 사용 상황 2.",
        f"  트리거 키워드: \"TODO\", \"TODO\", \"/{name}\".",
    ]
    if model:
        frontmatter_lines.append(f"model: {model}")
    frontmatter_lines += [
        f"allowed-tools:",
        f"  - Bash(python3 {abs_scripts}/TODO_script.py *)",
        f"  - Read",
        f"  - Write",
    ]
    if with_agents:
        frontmatter_lines.append(f"  - Agent")
    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    if skill_type == "workflow":
        body = f"""
# {name} Skill

TODO: 이 스킬이 무엇을 하는지 한 문장으로 설명하세요.

---

## 핵심 원칙

- TODO: 원칙 1
- TODO: 원칙 2
- 스크립트만 호출한다. 직접 API 호출 금지.

---

## 워크플로우

### Step 1 — TODO: 첫 번째 단계

TODO: 단계 설명

```bash
python3 {abs_scripts}/TODO_script.py subcommand --option value
```

### Step 2 — TODO: 두 번째 단계

TODO: 단계 설명

---

## 결과 출력 형식

```
TODO: 완료 메시지
- 항목: {{value}}
```

---

## 주의사항

- TODO: 주의사항 1
"""
    elif skill_type == "reference":
        body = f"""
# {name} Reference

TODO: 이 레퍼런스 스킬의 목적을 설명하세요.

---

## 도메인 지식

### TODO: 주요 개념

TODO: 개념 설명

---

## 사용 가이드

### TODO: 사용 시나리오

1. TODO: 시나리오 설명

```bash
TODO: 예시 명령
```

---

## 참고 자료

- TODO: 링크 또는 문서
"""
    else:  # tool
        body = f"""
# {name} Tool

TODO: 이 도구가 무엇을 감싸는지 설명하세요.

---

## 사용법

```bash
python3 {abs_scripts}/TODO_script.py --help
```

---

## 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--TODO` | TODO 설명 | - |

---

## 예시

```bash
python3 {abs_scripts}/TODO_script.py --option value
```

출력:
```json
{{"success": true, "TODO": "값"}}
```

---

## 주의사항

- TODO: 주의사항
"""

    return frontmatter + "\n" + body.lstrip("\n")


def cmd_create(args):
    name = args.name
    description = args.description or "TODO: 스킬 설명을 작성하세요."
    model = args.model or ""
    skill_type = args.type or "workflow"
    agent_specs = []  # list of (role, model) tuples
    if args.with_agents:
        for entry in args.with_agents.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                role, model = entry.split(":", 1)
                role, model = role.strip(), model.strip()
            else:
                role, model = entry, "sonnet"
            if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", role):
                err(f"Invalid agent role '{role}'. Must be lowercase hyphen-case")
            if model not in ("haiku", "sonnet", "opus"):
                err(f"Invalid agent model '{model}' for role '{role}'. Choose haiku/sonnet/opus")
            agent_specs.append((role, model))
    agent_roles = [r for r, _ in agent_specs]

    # Validate name
    if not NAME_PATTERN.match(name):
        err(f"Invalid skill name '{name}'. Must match ^[a-z0-9]+(-[a-z0-9]+)*$")
    if len(name) > MAX_NAME_LEN:
        err(f"Skill name too long ({len(name)} > {MAX_NAME_LEN})")

    sp = skill_path(name)
    if sp.exists():
        err(f"Skill '{name}' already exists", path=str(sp))

    # Create directories
    (sp / "scripts").mkdir(parents=True)
    (sp / "references").mkdir(parents=True)
    (sp / "assets").mkdir(parents=True)

    # Agent scaffolding (opt-in via --with-agents)
    agent_files_created = []
    if agent_specs:
        (sp / "agents").mkdir(parents=True)
        model_hints = {
            "haiku": "단순 변환/추출/형식화 작업에 적합",
            "sonnet": "일반 분석/패턴 매칭/파일 탐색 (기본값)",
            "opus": "깊은 판단/BP 해석/아키텍처 설계가 필요한 작업",
        }
        for role, model in agent_specs:
            agent_path = sp / "agents" / f"agent-{role}.md"
            agent_path.write_text(
                f"# {role.replace('-', ' ').title()} 에이전트\n\n"
                f"**Recommended model**: `{model}` — {model_hints[model]}\n"
                f"**역할**: TODO — 이 에이전트가 무엇을 책임지는지 한 문장으로 작성.\n\n"
                f"**입력 변수** (SKILL.md에서 치환):\n"
                f"- `{{TODO_var1}}`: TODO 설명\n"
                f"- `{{TODO_var2}}`: TODO 설명\n\n"
                f"## 절차\n\n"
                f"1. TODO: 첫 번째 단계\n"
                f"2. TODO: 두 번째 단계\n"
                f"3. TODO: 결과를 JSON으로 반환\n\n"
                f"## 출력 형식\n\n"
                f"```json\n"
                f'{{\n  "summary": "...",\n  "findings": []\n}}\n'
                f"```\n\n"
                f"---\n"
                f"**호출 시**: SKILL.md에서 Agent tool 호출 시 `model: \"{model}\"` 명시\n",
                encoding="utf-8",
            )
            agent_files_created.append(str(agent_path))

    # Write scaffold SKILL.md (with Agent in allowed-tools if agents/ created)
    scaffold = _make_scaffold(name, description, model, skill_type, with_agents=bool(agent_roles))
    (sp / "SKILL.md").write_text(scaffold, encoding="utf-8")

    # Write placeholder script
    abs_scripts = sp / "scripts"
    placeholder_script = abs_scripts / "TODO_script.py"
    placeholder_script.write_text(
        '#!/usr/bin/env python3\n'
        '"""TODO: Replace this placeholder script.\n\n'
        'Harness conventions (do not remove):\n'
        '- Mutating subcommands MUST honor --dry-run (preview-only, no side effects).\n'
        '- Destructive operations MUST require an explicit --confirm flag.\n'
        '- All output: JSON via ok()/err() helpers.\n'
        '"""\n'
        'import argparse, json, sys\n\n'
        'def ok(data):\n'
        '    print(json.dumps({"success": True, **data}, ensure_ascii=False, indent=2))\n\n'
        'def err(msg, **extra):\n'
        '    print(json.dumps({"success": False, "error": msg, **extra}, ensure_ascii=False, indent=2))\n'
        '    sys.exit(1)\n\n'
        'def cmd_run(args):\n'
        '    if args.dry_run:\n'
        '        ok({"dry_run": True, "would_do": "TODO: describe planned action"})\n'
        '        return\n'
        '    # TODO: implement actual mutation here\n'
        '    ok({"message": "TODO: implement"})\n\n'
        'def main():\n'
        '    parser = argparse.ArgumentParser()\n'
        '    sub = parser.add_subparsers(dest="command", required=True)\n'
        '    p_run = sub.add_parser("run")\n'
        '    p_run.add_argument("--dry-run", action="store_true",\n'
        '                       help="Preview without making changes")\n'
        '    args = parser.parse_args()\n'
        '    {"run": cmd_run}[args.command](args)\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n',
        encoding="utf-8",
    )

    ok({
        "name": name,
        "path": str(sp),
        "files_created": [
            str(sp / "SKILL.md"),
            str(placeholder_script),
        ] + agent_files_created,
        "agents_scaffolded": [{"role": r, "model": m} for r, m in agent_specs],
        "message": (
            f"Scaffold created. Next: fill in SKILL.md body, write scripts, "
            f"then validate with: python3 {__file__} validate {name}"
        ),
    })


def cmd_update_frontmatter(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found")

    skill_md = sp / "SKILL.md"
    fm, body, raw = read_skill_file(sp)

    # Snapshot before mutations for diff output
    fm_before = {k: (list(v) if isinstance(v, list) else v) for k, v in fm.items()}
    changed = []

    if args.set_description:
        fm["description"] = args.set_description
        changed.append("description")

    if args.set_model:
        fm["model"] = args.set_model
        changed.append("model")

    if args.add_tool:
        tools = fm.get("allowed-tools", [])
        if isinstance(tools, str):
            tools = [tools] if tools else []
        if args.add_tool not in tools:
            tools.append(args.add_tool)
            fm["allowed-tools"] = tools
            changed.append(f"added tool: {args.add_tool}")

    if args.remove_tool:
        tools = fm.get("allowed-tools", [])
        if isinstance(tools, list):
            before = len(tools)
            tools = [t for t in tools if t != args.remove_tool]
            if len(tools) < before:
                fm["allowed-tools"] = tools
                changed.append(f"removed tool: {args.remove_tool}")
            else:
                changed.append(f"tool not found (no change): {args.remove_tool}")

    if not changed:
        ok({"name": name, "changed": [], "message": "No changes made."})
        return

    # Reconstruct SKILL.md: new frontmatter + original body
    new_content = build_frontmatter(fm) + "\n\n" + body

    # Dry-run: preview changes without writing
    if args.dry_run:
        ok({
            "name": name,
            "dry_run": True,
            "changed": changed,
            "frontmatter_before": fm_before,
            "frontmatter_after": fm,
            "message": "DRY RUN — 변경사항 미리보기. 실제 적용하려면 --dry-run 없이 재실행하세요.",
        })
        return

    skill_md.write_text(new_content, encoding="utf-8")

    # Auto-validate
    fm2, body2, _ = read_skill_file(sp)
    checks, warnings, info = _validate_checks(name, sp, fm2, body2)
    valid = all(c["passed"] for c in checks)

    ok({
        "name": name,
        "changed": changed,
        "validation": {"valid": valid, "checks": checks, "warnings": warnings, "info": info},
    })


def cmd_delete(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found", path=str(sp))

    # Dry-run: list what would be removed without acting
    if args.dry_run:
        files = sorted([str(p.relative_to(sp)) for p in sp.rglob("*") if p.is_file()])
        ok({
            "name": name,
            "dry_run": True,
            "would_delete": str(sp),
            "would_backup": not args.no_backup,
            "file_count": len(files),
            "files": files[:20] + (["..."] if len(files) > 20 else []),
            "message": "DRY RUN — 실제 삭제하려면 --dry-run 없이 재실행하세요.",
        })
        return

    # Harness: --no-backup requires explicit double-opt-in to prevent accidental loss
    if args.no_backup and not args.confirm_no_backup:
        err(
            "백업 없이 삭제하려면 --confirm-no-backup 플래그를 추가로 지정해야 합니다 (실수 방지)",
            hint=f"안전한 삭제: python3 {__file__} delete {name}",
        )

    backup_path = None
    if not args.no_backup:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = BACKUPS_DIR / f"{name}-{ts}"
        shutil.copytree(str(sp), str(backup_path))

    shutil.rmtree(str(sp))

    ok({
        "name": name,
        "deleted": str(sp),
        "backup": str(backup_path) if backup_path else None,
    })


def cmd_restore(args):
    name = args.name

    if not BACKUPS_DIR.exists():
        err(f"No backups directory found", path=str(BACKUPS_DIR))

    # Find all backups for this skill (format: <name>-YYYYMMDD-HHMMSS)
    pattern = re.compile(rf"^{re.escape(name)}-(\d{{8}}-\d{{6}})$")
    backups = sorted(
        [d for d in BACKUPS_DIR.iterdir() if d.is_dir() and pattern.match(d.name)],
        key=lambda d: d.name,
    )

    if not backups:
        err(f"No backups found for skill '{name}'", backups_dir=str(BACKUPS_DIR))

    if args.list:
        entries = []
        for b in reversed(backups):
            m = pattern.match(b.name)
            ts_raw = m.group(1)  # YYYYMMDD-HHMMSS
            ts = f"{ts_raw[:4]}-{ts_raw[4:6]}-{ts_raw[6:8]} {ts_raw[9:11]}:{ts_raw[11:13]}:{ts_raw[13:]}"
            entries.append({"backup": b.name, "timestamp": ts, "path": str(b)})
        ok({"name": name, "count": len(entries), "backups": entries})
        return

    # Restore latest backup
    latest = backups[-1]
    sp = skill_path(name)

    if sp.exists():
        err(
            f"Skill '{name}' already exists — delete it first before restoring",
            existing_path=str(sp),
            latest_backup=latest.name,
        )

    shutil.copytree(str(latest), str(sp))

    # Auto-validate after restore
    fm, body, _ = read_skill_file(sp)
    checks, warnings, info = _validate_checks(name, sp, fm, body)
    valid = all(c["passed"] for c in checks)

    ok({
        "name": name,
        "restored_from": latest.name,
        "path": str(sp),
        "validation": {"valid": valid, "checks": checks, "warnings": warnings, "info": info},
    })


# ─── Entry Point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="manage_skill.py",
        description="Skill lifecycle management (CRUD + validate + restore)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    sub.add_parser("list", help="List all skills")

    # show
    p_show = sub.add_parser("show", help="Show skill details")
    p_show.add_argument("name", help="Skill name")

    # create
    p_create = sub.add_parser("create", help="Scaffold a new skill")
    p_create.add_argument("name", help="Skill name (hyphen-case)")
    p_create.add_argument("--description", "-d", help="Short description")
    p_create.add_argument("--model", "-m", choices=["sonnet", "opus", "haiku"], help="Model override")
    p_create.add_argument("--type", "-t", choices=["workflow", "reference", "tool"],
                          default="workflow", help="Skill template type (default: workflow)")
    p_create.add_argument("--with-agents",
                          help="Comma-separated agent roles with optional model: 'role[:model]'. "
                               "model ∈ {haiku, sonnet, opus}, default sonnet. "
                               "Example: --with-agents 'collector:haiku,strategist:opus,parser'. "
                               "Creates agents/agent-<role>.md (with model annotation) and adds Agent to allowed-tools.")

    # validate
    p_val = sub.add_parser("validate", help="Validate skill structure")
    p_val.add_argument("name", help="Skill name")

    # review
    p_rev = sub.add_parser("review",
                           help="Score a skill (BP/parallelism/harness) — read-only")
    p_rev.add_argument("name", help="Skill name")

    # update-frontmatter
    p_uf = sub.add_parser("update-frontmatter", help="Modify frontmatter fields")
    p_uf.add_argument("name", help="Skill name")
    p_uf.add_argument("--set-description", help="New description")
    p_uf.add_argument("--set-model", choices=["sonnet", "opus", "haiku"], help="New model")
    p_uf.add_argument("--add-tool", help="Add an allowed-tool entry")
    p_uf.add_argument("--remove-tool", help="Remove an allowed-tool entry")
    p_uf.add_argument("--dry-run", action="store_true",
                      help="Preview frontmatter changes without writing")

    # delete
    p_del = sub.add_parser("delete", help="Delete a skill (with backup by default)")
    p_del.add_argument("name", help="Skill name")
    p_del.add_argument("--no-backup", action="store_true", help="Skip backup (REQUIRES --confirm-no-backup)")
    p_del.add_argument("--confirm-no-backup", action="store_true",
                       help="Required gate when using --no-backup (prevents accidental data loss)")
    p_del.add_argument("--dry-run", action="store_true",
                       help="List files that would be removed without acting")

    # restore
    p_rst = sub.add_parser("restore", help="Restore skill from latest backup")
    p_rst.add_argument("name", help="Skill name")
    p_rst.add_argument("--list", action="store_true", help="List available backups without restoring")

    args = parser.parse_args()

    dispatch = {
        "list": cmd_list,
        "show": cmd_show,
        "create": cmd_create,
        "validate": cmd_validate,
        "review": cmd_review,
        "update-frontmatter": cmd_update_frontmatter,
        "delete": cmd_delete,
        "restore": cmd_restore,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
