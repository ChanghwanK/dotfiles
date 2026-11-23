#!/usr/bin/env python3
"""codex CLI로 주장 원장(claims)과 초안(draft)을 교차 검증한다.

  codex_verify.py claims <run_dir> [--only id1,id2] [--chunk 15] [--parallel 4]
  codex_verify.py draft  <run_dir>

- subprocess로 codex 바이너리를 직접 실행하므로 셸 alias(--dangerously-bypass-...)를 거치지 않는다
- 항상 `-s read-only --ephemeral`로 실행하고, claims 모드만 `--search`를 켠다
- codex에는 주장·URL·스냅샷 경로만 주고 우리 쪽 인용·등급·확신은 주지 않는다(블라인드)

stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
VERDICTS = {"SUPPORTED", "PARTIAL", "REFUTED", "UNVERIFIABLE"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_codex(run: Path, prompt: str, schema: Path, out: Path, log: Path,
              search: bool, effort: str, timeout: int, model: str) -> tuple[bool, str]:
    cmd = ["codex"]
    if search:
        cmd.append("--search")
    cmd += ["exec", "-s", "read-only", "--ephemeral", "--skip-git-repo-check",
            "-C", str(run), "-c", f"model_reasoning_effort={effort}",
            "--disable", "hooks", "--disable", "memories",
            "--output-schema", str(schema), "-o", str(out)]
    if model:
        cmd += ["-m", model]
    cmd.append("-")
    started = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        log.write_text(f"TIMEOUT after {timeout}s\n{e.stdout or ''}\n{e.stderr or ''}", encoding="utf-8")
        return False, f"timeout {timeout}s"
    elapsed = round(time.time() - started)
    log.write_text(f"$ {' '.join(cmd)}\nexit={proc.returncode} elapsed={elapsed}s\n"
                   f"--- stdout\n{proc.stdout}\n--- stderr\n{proc.stderr}", encoding="utf-8")
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)  # 실패 시 빈 출력 파일을 남기지 않는다
        limit = re.search(r"usage limit.*?(try again at [^.\n]+)", proc.stdout + proc.stderr)
        if limit:
            return False, f"codex_usage_limit ({limit.group(1)})"
        return False, f"exit {proc.returncode}" if proc.returncode else "empty output"
    return True, f"{elapsed}s"


# ---------------------------------------------------------------- claims

def claim_payload(claims: list[dict], sources: dict[str, dict]) -> list[dict]:
    rows = []
    for c in claims:
        src = sources.get(c.get("source_id", ""), {})
        snap = ""
        if src.get("status") == "ok":
            snap = src.get("text") or src.get("snapshot", "")
        rows.append({"claim_id": c["claim_id"], "claim": c["claim"],
                     "url": c.get("url") or src.get("url", ""), "snapshot": snap})
    return rows


def validate_verdicts(out: Path, want: set[str]) -> tuple[list[dict], set[str]]:
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
        got = [v for v in data.get("verdicts", []) if v.get("claim_id") in want
               and v.get("verdict") in VERDICTS]
    except (json.JSONDecodeError, OSError):
        return [], set(want)
    seen = {v["claim_id"] for v in got}
    return got, want - seen


def verify_chunk(idx: int, chunk: list[dict], run: Path, args) -> dict:
    vdir = run / "verdicts"
    tmpl = (ASSETS / "codex-claims-prompt.md").read_text(encoding="utf-8")
    schema = ASSETS / "claim-verdict.schema.json"
    out = vdir / f"chunk-{idx:02d}.json"
    pending = chunk
    collected: list[dict] = []
    notes = []
    for attempt in (1, 2):
        prompt = tmpl.replace("{claims_json}", json.dumps(pending, ensure_ascii=False, indent=1))
        (vdir / f"chunk-{idx:02d}.prompt.md").write_text(prompt, encoding="utf-8")
        raw = vdir / f"chunk-{idx:02d}.try{attempt}.json"
        ok, msg = run_codex(run, prompt, schema, raw, vdir / f"chunk-{idx:02d}.try{attempt}.log",
                            True, args.effort, args.timeout, args.model)
        notes.append(f"try{attempt}: {msg}")
        if ok:
            got, missing = validate_verdicts(raw, {c["claim_id"] for c in pending})
            collected += got
            pending = [c for c in pending if c["claim_id"] in missing]
        if not pending:
            break
    for c in pending:
        collected.append({"claim_id": c["claim_id"], "verdict": "UNVERIFIABLE", "url_opened": False,
                          "quote": "", "counter_evidence": [],
                          "note": "codex_failed: " + "; ".join(notes)})
    out.write_text(json.dumps({"verdicts": collected}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"chunk": idx, "claims": len(chunk), "failed": len(pending), "runs": notes}


def cmd_claims(args) -> int:
    run = Path(args.run_dir).expanduser().resolve()
    claims = read_jsonl(run / "claims.jsonl")
    if args.only:
        only = set(args.only.split(","))
        claims = [c for c in claims if c["claim_id"] in only]
    if not claims:
        print("no claims to verify", file=sys.stderr)
        return 1
    sources = {s["id"]: s for s in read_jsonl(run / "sources.jsonl")}
    payload = claim_payload(claims, sources)
    chunks = [payload[i:i + args.chunk] for i in range(0, len(payload), args.chunk)]
    start = args.start_index
    (run / "verdicts").mkdir(exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        results = list(ex.map(lambda p: verify_chunk(p[0], p[1], run, args),
                              [(start + i, c) for i, c in enumerate(chunks)]))
    counts: dict[str, int] = {}
    for f in sorted((run / "verdicts").glob("chunk-??.json")):
        for v in json.loads(f.read_text(encoding="utf-8"))["verdicts"]:
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print(json.dumps({"chunks": results, "verdict_counts": counts}, ensure_ascii=False, indent=1))
    return 0


# ---------------------------------------------------------------- draft

def cmd_draft(args) -> int:
    run = Path(args.run_dir).expanduser().resolve()
    if not (run / "draft.md").exists():
        print("draft.md not found", file=sys.stderr)
        return 1
    prompt = (ASSETS / "codex-draft-prompt.md").read_text(encoding="utf-8")
    out = run / "draft-review.json"
    ok, msg = run_codex(run, prompt, ASSETS / "draft-review.schema.json", out,
                        run / "draft-review.log", False, args.effort, args.timeout, args.model)
    if not ok:
        print(json.dumps({"ok": False, "reason": msg}), file=sys.stderr)
        return 1
    data = json.loads(out.read_text(encoding="utf-8"))
    kinds: dict[str, int] = {}
    for i in data.get("issues", []):
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    print(json.dumps({"ok": True, "elapsed": msg, "issues": len(data.get("issues", [])),
                      "by_kind": kinds, "summary": data.get("summary", "")}, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--effort", default="high")
    p.add_argument("--timeout", type=int, default=1200, help="codex 호출 1회 제한(초)")
    p.add_argument("--model", default="gpt-6.1-sol", help="codex 모델(빈 값이면 ~/.codex/config.toml의 model)")
    sub = p.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("claims")
    s.add_argument("run_dir")
    s.add_argument("--only", default="", help="쉼표로 구분한 claim_id만 재검증")
    s.add_argument("--chunk", type=int, default=15)
    s.add_argument("--parallel", type=int, default=4)
    s.add_argument("--start-index", type=int, default=1, help="재검증 시 기존 chunk 파일을 덮지 않도록 시작 번호 지정")
    s.set_defaults(func=cmd_claims)
    s = sub.add_parser("draft")
    s.add_argument("run_dir")
    s.set_defaults(func=cmd_draft)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
