#!/usr/bin/env python3
"""codex 독립 리서치와 교차 검토. research:deep 실행 폴더에서 Claude 수집과 짝을 이룬다.

  codex_research.py collect <research_run>        서브질문별 codex 독립 수집(병렬, --search)
  codex_research.py cross-review <research_run>   codex가 Claude 수집(notes/, claims.jsonl)을 검토

입력: <research_run>/subquestions.md  ("## q1 ..." 헤더로 서브질문을 나눈 파일)
출력:
  <research_run>/codex/collect-<qN>.json   findings(주장·원문 인용·URL), gaps
  <research_run>/codex/cross-review.json  Claude 자료의 오류·공백
- collect는 <research_run>/codex/ws-<qN>/ 빈 작업 폴더에서 실행해 Claude 자료를 보지 않게 한다(독립 수집)
- 항상 `-s read-only --ephemeral`, 셸 alias를 거치지 않는다. 기본 모델 gpt-6.1-sol, effort는 collect medium, cross-review high

stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def run_codex(cwd: Path, prompt: str, schema: Path, out: Path, log: Path, a) -> tuple[bool, str]:
    cmd = ["codex", "--search", "exec", "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C", str(cwd),
           "-c", f"model_reasoning_effort={a.effort}", "--disable", "hooks", "--disable", "memories",
           "--output-schema", str(schema), "-o", str(out)]
    if a.model:
        cmd += ["-m", a.model]
    cmd.append("-")
    started = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=a.timeout)
    except subprocess.TimeoutExpired as e:
        log.write_text(f"TIMEOUT after {a.timeout}s\n{e.stdout or ''}\n{e.stderr or ''}", encoding="utf-8")
        return False, f"timeout {a.timeout}s"
    elapsed = round(time.time() - started)
    log.write_text(f"$ {' '.join(cmd)}\nexit={proc.returncode} elapsed={elapsed}s\n"
                   f"--- stdout\n{proc.stdout}\n--- stderr\n{proc.stderr}", encoding="utf-8")
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        limit = re.search(r"usage limit.*?(try again at [^.\n]+)", proc.stdout + proc.stderr)
        return False, (f"codex_usage_limit ({limit.group(1)})" if limit
                       else (f"exit {proc.returncode}" if proc.returncode else "empty output"))
    return True, f"{elapsed}s"


def split_subquestions(text: str) -> dict[str, str]:
    parts = re.split(r"^##\s+(q\d+)\b", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def cmd_collect(a) -> int:
    run = Path(a.research_run).expanduser().resolve()
    subqs = split_subquestions((run / "subquestions.md").read_text(encoding="utf-8"))
    if a.only:
        subqs = {k: v for k, v in subqs.items() if k in set(a.only.split(","))}
    if not subqs:
        print("no subquestions (## qN headers) in subquestions.md", file=sys.stderr)
        return 1
    cdir = run / "codex"
    cdir.mkdir(exist_ok=True)
    tmpl = (ASSETS / "codex-research-prompt.md").read_text(encoding="utf-8")
    anchor = a.version_anchor or "없음"

    def one(item: tuple[str, str]) -> dict:
        qid, body = item
        ws = cdir / f"ws-{qid}"
        if ws.exists():
            shutil.rmtree(ws)
        ws.mkdir()
        prompt = tmpl.replace("{subq_id}", qid).replace("{subq}", body).replace("{version_anchor}", anchor)
        out = cdir / f"collect-{qid}.json"
        ok, msg = run_codex(ws, prompt, ASSETS / "codex-research.schema.json", out, cdir / f"collect-{qid}.log", a)
        if not ok:
            return {"subq": qid, "ok": False, "reason": msg}
        data = json.loads(out.read_text(encoding="utf-8"))
        return {"subq": qid, "ok": True, "elapsed": msg, "findings": len(data.get("findings", [])),
                "gaps": len(data.get("gaps", []))}

    with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
        results = list(ex.map(one, sorted(subqs.items())))
    print(json.dumps({"results": results}, ensure_ascii=False, indent=1))
    return 0 if all(r["ok"] for r in results) else 1


def cmd_cross_review(a) -> int:
    run = Path(a.research_run).expanduser().resolve()
    if not list((run / "notes").glob("*.md")):
        print("notes/*.md not found", file=sys.stderr)
        return 1
    (run / "codex").mkdir(exist_ok=True)
    prompt = (ASSETS / "codex-crossreview-prompt.md").read_text(encoding="utf-8")
    out = run / "codex" / "cross-review.json"
    ok, msg = run_codex(run, prompt, ASSETS / "codex-crossreview.schema.json", out,
                        run / "codex" / "cross-review.log", a)
    if not ok:
        print(json.dumps({"ok": False, "reason": msg}), file=sys.stderr)
        return 1
    data = json.loads(out.read_text(encoding="utf-8"))
    print(json.dumps({"ok": True, "elapsed": msg, "errors": len(data.get("errors", [])),
                      "gaps": len(data.get("gaps", [])), "summary": data.get("summary", "")},
                     ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="gpt-6.1-sol")
    p.add_argument("--effort", default="", help="기본: collect는 medium(검색·인용 위주), cross-review는 high(판단)")
    p.add_argument("--timeout", type=int, default=2400)
    sub = p.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("collect")
    s.add_argument("research_run")
    s.add_argument("--only", default="", help="쉼표로 구분한 서브질문 id만")
    s.add_argument("--parallel", type=int, default=5)
    s.add_argument("--version-anchor", default="")
    s.set_defaults(func=cmd_collect)
    s = sub.add_parser("cross-review")
    s.add_argument("research_run")
    s.set_defaults(func=cmd_cross_review)
    a = p.parse_args()
    if not a.effort:
        a.effort = "medium" if a.mode == "collect" else "high"
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
