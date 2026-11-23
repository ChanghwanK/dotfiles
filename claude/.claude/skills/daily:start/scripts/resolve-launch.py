#!/usr/bin/env python3
"""
브리핑 데이터(JSON)의 열린 작업마다 Orca 채팅을 여는 실행 명령을 계산해 넣는다.

사용법:
  python3 resolve-launch.py --data <brief.json>          # launch 필드를 써 넣는다
  python3 resolve-launch.py --data <brief.json> --check  # 쓰지 않고 판정 표만 출력한다

대상: top3 전부 + 완료가 아닌 yesterday.threads
판정:
  - cwd가 Orca가 아는 워크스페이스면  orca agent launch --worktree path:<cwd>
  - 아니면(작업 뒤 지운 워크스페이스 등) 같은 repo의 메인 워크스페이스에서
    orca worktree create --repo path:<main> --name <지운 워크스페이스 이름 | pickup-<id>>
  - repo를 못 찾으면 launch=null, launch_error에 이유
공통 인자: --agent claude --surface chat --prompt "/task:resume <date> <id> <의도>" --json

Orca 조회가 실패해도 브리핑을 막지 않는다. 모든 항목에 launch_error를 남기고 exit 0으로 끝낸다.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

INTENTS = ("구체화", "실행")
ORCA_WS_RE = re.compile(r"/orca/workspaces/([^/]+)/([^/]+)/?$")


def orca_worktrees():
    """Orca가 아는 워크스페이스 목록. 실패하면 (None, 이유)"""
    cli = os.environ.get("ORCA_CLI_COMMAND", "orca")
    try:
        out = subprocess.run([cli, "worktree", "ps", "--json"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"orca 조회 실패: {e}"
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None, f"orca 응답을 읽지 못함 (exit {out.returncode})"
    if not data.get("ok", True) or "result" not in data:
        return None, f"orca 오류: {data.get('error', {}).get('code', 'unknown')}"
    return data["result"].get("worktrees", []), None


def repo_name_for(cwd, project):
    m = ORCA_WS_RE.search(cwd or "")
    if m:
        return m.group(1)
    if project:
        return project.split("/")[-1].split(" ")[0].strip()
    return None


def command(mode, target, name, prompt):
    base = ["orca"]
    if mode == "agent launch":
        base += ["agent", "launch", "--worktree", f"path:{target}"]
    else:
        base += ["worktree", "create", "--repo", f"path:{target}", "--name", name, "--no-parent", "--activate"]
    base += ["--agent", "claude", "--surface", "chat", "--prompt", prompt, "--json"]
    return " ".join(shlex.quote(a) for a in base)


def resolve(item_id, cwd, project, date, known_paths, mains):
    if cwd and cwd.rstrip("/") in known_paths:
        mode, target, name = "agent launch", cwd.rstrip("/"), Path(cwd).name
    else:
        repo = repo_name_for(cwd, project)
        main = mains.get(repo) if repo else None
        if not main:
            return None, f"repo를 Orca에서 찾지 못함 (cwd={cwd or '-'}, project={project or '-'})"
        m = ORCA_WS_RE.search(cwd or "")
        name = m.group(2) if m else f"pickup-{item_id}"
        mode, target = "worktree create", main
    launch = {"mode": mode, "target": target, "name": name}
    for intent in INTENTS:
        launch[intent] = command(mode, target, name, f"/task:resume {date} {item_id} {intent}")
    return launch, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    path = Path(args.data)
    data = json.loads(path.read_text(encoding="utf-8"))
    date = data.get("date")
    threads = (data.get("yesterday") or {}).get("threads") or []
    by_id = {t.get("id"): t for t in threads}

    rows, err = orca_worktrees()
    known_paths = {r.get("path", "").rstrip("/") for r in rows or []}
    mains = {r.get("repo"): r.get("path") for r in rows or [] if r.get("isMainWorktree")}

    targets = []
    for i, t in enumerate(data.get("top3") or []):
        tid = t.get("thread_id")
        src = by_id.get(tid, {})
        targets.append((t, tid or f"top{i + 1}", t.get("cwd") or src.get("cwd"), src.get("project") or t.get("project")))
    for t in threads:
        if t.get("status") != "완료":
            targets.append((t, t.get("id"), t.get("cwd"), t.get("project")))

    table = []
    for item, item_id, cwd, project in targets:
        if err:
            launch, why = None, err
        else:
            launch, why = resolve(item_id, cwd, project, date, known_paths, mains)
        table.append((item_id, launch["mode"] if launch else "-", (launch or {}).get("target") or why))
        if not args.check:
            item["launch"] = launch
            if why:
                item["launch_error"] = why
            else:
                item.pop("launch_error", None)

    if args.check:
        for row in table:
            print("\t".join(str(c) for c in row))
        return 0
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in table if r[1] != "-")
    print(json.dumps({"success": True, "resolved": ok, "total": len(table), "orca_error": err}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
