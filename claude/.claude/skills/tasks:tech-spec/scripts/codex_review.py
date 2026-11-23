#!/usr/bin/env python3
"""codex CLI로 1차 계획(plan)과 Tech Spec(spec)을 리뷰한다.

  codex_review.py plan <run_dir> --round N [--no-search]
  codex_review.py spec <run_dir> --round N [--no-search]

- 결과: <run_dir>/reviews/codex-<stage>-r<N>.json (assets/review.schema.json 형식), 로그는 같은 이름 .log
- subprocess로 codex 바이너리를 직접 실행해 셸 alias(--dangerously-bypass-...)를 거치지 않는다
- 항상 `-s read-only --ephemeral`, 기본으로 `--search`를 켠다(사실 확인용)
- codex에는 파일 경로만 주고, Claude의 판단·기대 결론은 주지 않는다(블라인드)

stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=["plan", "spec"])
    p.add_argument("run_dir")
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--no-search", action="store_true")
    p.add_argument("--effort", default="high")
    p.add_argument("--timeout", type=int, default=1500, help="codex 호출 제한(초)")
    p.add_argument("--model", default="gpt-6.1-sol", help="codex 모델(빈 값이면 ~/.codex/config.toml의 model)")
    a = p.parse_args()

    run = Path(a.run_dir).expanduser().resolve()
    target = run / ("plan.md" if a.stage == "plan" else "spec.md")
    if not target.exists():
        print(f"{target.name} not found", file=sys.stderr)
        return 1
    (run / "reviews").mkdir(exist_ok=True)
    prompt = (ASSETS / f"codex-{a.stage}-review-prompt.md").read_text(encoding="utf-8")
    prompt = prompt.replace("{round}", str(a.round))
    outp = run / "reviews" / f"codex-{a.stage}-r{a.round}.json"
    log = outp.with_suffix(".log")

    cmd = ["codex"]
    if not a.no_search:
        cmd.append("--search")
    cmd += ["exec", "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C", str(run),
            "-c", f"model_reasoning_effort={a.effort}", "--disable", "hooks", "--disable", "memories",
            "--output-schema", str(ASSETS / "review.schema.json"), "-o", str(outp)]
    if a.model:
        cmd += ["-m", a.model]
    cmd.append("-")

    started = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=a.timeout)
    except subprocess.TimeoutExpired as e:
        log.write_text(f"TIMEOUT after {a.timeout}s\n{e.stdout or ''}\n{e.stderr or ''}", encoding="utf-8")
        print(json.dumps({"ok": False, "reason": f"timeout {a.timeout}s"}), file=sys.stderr)
        return 1
    elapsed = round(time.time() - started)
    log.write_text(f"$ {' '.join(cmd)}\nexit={proc.returncode} elapsed={elapsed}s\n"
                   f"--- stdout\n{proc.stdout}\n--- stderr\n{proc.stderr}", encoding="utf-8")
    if proc.returncode != 0 or not outp.exists() or outp.stat().st_size == 0:
        outp.unlink(missing_ok=True)
        limit = re.search(r"usage limit.*?(try again at [^.\n]+)", proc.stdout + proc.stderr)
        reason = f"codex_usage_limit ({limit.group(1)})" if limit else (f"exit {proc.returncode}" if proc.returncode else "empty output")
        print(json.dumps({"ok": False, "reason": reason, "log": str(log)}), file=sys.stderr)
        return 1
    try:
        data = json.loads(outp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "reason": f"invalid json: {e}", "log": str(log)}), file=sys.stderr)
        return 1
    counts: dict[str, int] = {}
    for it in data.get("issues", []):
        counts[it.get("severity", "?")] = counts.get(it.get("severity", "?"), 0) + 1
    print(json.dumps({"ok": True, "elapsed": f"{elapsed}s", "file": str(outp), "verdict": data.get("verdict"),
                      "by_severity": counts, "expected_questions": len(data.get("expected_questions", [])),
                      "summary": data.get("summary", "")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
