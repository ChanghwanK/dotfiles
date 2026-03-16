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
    checks, warnings = _validate_checks(name, sp, fm, body)
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
        },
    })


def _validate_checks(name: str, sp: Path, fm: dict, body: str) -> tuple[list, list]:
    checks = []
    warnings = []

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
    if agents_dir.exists() and agents_dir.is_dir():
        agent_files = list(agents_dir.glob("*.md"))
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

    return checks, warnings


def cmd_validate(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found")

    skill_md = sp / "SKILL.md"
    if not skill_md.exists():
        err(f"SKILL.md not found for '{name}'")

    fm, body, _ = read_skill_file(sp)
    checks, warnings = _validate_checks(name, sp, fm, body)
    valid = all(c["passed"] for c in checks)

    ok({"valid": valid, "checks": checks, "warnings": warnings})


def _make_scaffold(name: str, description: str, model: str, skill_type: str) -> str:
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
        f"---",
    ]
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

    # Write scaffold SKILL.md
    scaffold = _make_scaffold(name, description, model, skill_type)
    (sp / "SKILL.md").write_text(scaffold, encoding="utf-8")

    # Write placeholder script
    abs_scripts = sp / "scripts"
    placeholder_script = abs_scripts / "TODO_script.py"
    placeholder_script.write_text(
        '#!/usr/bin/env python3\n"""TODO: Replace this placeholder script."""\n'
        'import argparse, json, sys\n\n'
        'def main():\n'
        '    parser = argparse.ArgumentParser()\n'
        '    parser.add_argument("subcommand")\n'
        '    args = parser.parse_args()\n'
        '    print(json.dumps({"success": True, "message": "TODO: implement"}))\n\n'
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
        ],
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
    skill_md.write_text(new_content, encoding="utf-8")

    # Auto-validate
    fm2, body2, _ = read_skill_file(sp)
    checks, warnings = _validate_checks(name, sp, fm2, body2)
    valid = all(c["passed"] for c in checks)

    ok({
        "name": name,
        "changed": changed,
        "validation": {"valid": valid, "checks": checks, "warnings": warnings},
    })


def cmd_delete(args):
    name = args.name
    sp = skill_path(name)
    if not sp.exists():
        err(f"Skill '{name}' not found", path=str(sp))

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
    checks, warnings = _validate_checks(name, sp, fm, body)
    valid = all(c["passed"] for c in checks)

    ok({
        "name": name,
        "restored_from": latest.name,
        "path": str(sp),
        "validation": {"valid": valid, "checks": checks, "warnings": warnings},
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

    # validate
    p_val = sub.add_parser("validate", help="Validate skill structure")
    p_val.add_argument("name", help="Skill name")

    # update-frontmatter
    p_uf = sub.add_parser("update-frontmatter", help="Modify frontmatter fields")
    p_uf.add_argument("name", help="Skill name")
    p_uf.add_argument("--set-description", help="New description")
    p_uf.add_argument("--set-model", choices=["sonnet", "opus", "haiku"], help="New model")
    p_uf.add_argument("--add-tool", help="Add an allowed-tool entry")
    p_uf.add_argument("--remove-tool", help="Remove an allowed-tool entry")

    # delete
    p_del = sub.add_parser("delete", help="Delete a skill (with backup by default)")
    p_del.add_argument("name", help="Skill name")
    p_del.add_argument("--no-backup", action="store_true", help="Skip backup")

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
        "update-frontmatter": cmd_update_frontmatter,
        "delete": cmd_delete,
        "restore": cmd_restore,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
