#!/usr/bin/env python3
"""research:deep 실행 폴더의 수집 기록(manifest)을 관리한다.

하위 명령:
  init           실행 폴더 생성
  source         URL 원문을 내려받아 스냅샷과 텍스트를 저장하고 sources.jsonl에 기록
  image          이미지를 내려받아 images.jsonl에 기록
  search         검색 1회를 searches.jsonl에 기록
  stats          실제로 읽은 데이터 양을 집계
  check-claims   claims.jsonl의 인용이 스냅샷 원문에 있는지 확인
  check-verdicts codex 판정의 인용이 스냅샷 원문에 있는지 확인
  ledger         notes/*.jsonl을 합쳐 claims.jsonl 생성(원문 대조 실패는 claims.rejected.jsonl)
  render         draft.md의 [@cNNN]·[@sid] 인용을 번호 링크로 바꿔 final.md와 references.md 생성

stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) research-deep/1.0"
THIN_TEXT_CHARS = 500  # 이보다 짧으면 JS 렌더링 페이지로 보고 raw=false
IMAGE_MAX_BYTES = 8 * 1024 * 1024
EMBEDDABLE_LICENSES = {
    "cc0", "public-domain", "cc-by", "cc-by-4.0", "cc-by-sa", "cc-by-sa-4.0",
    "apache-2.0", "mit", "bsd", "own",
}
SUBDIRS = ("sources", "images", "notes", "verdicts")


# ---------------------------------------------------------------- utils

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def short_id(prefix: str, value: str) -> str:
    return prefix + hashlib.sha1(value.encode()).hexdigest()[:8]


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def curl(url: str, out: Path, timeout: int) -> tuple[int, str, str, str]:
    """(http_code, content_type, effective_url, error)."""
    cmd = [
        "curl", "-sSL", "--compressed", "--max-time", str(timeout),
        "-A", UA, "-o", str(out),
        "-w", "%{http_code}\t%{content_type}\t%{url_effective}",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0, "", url, (proc.stderr.strip() or f"curl exit {proc.returncode}")
    code, ctype, eff = (proc.stdout.split("\t") + ["", "", ""])[:3]
    return int(code or 0), ctype.lower(), eff, ""


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[`*_]+", "", text)  # 마크다운 강조·코드 표시 제거
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------------------------------------------------------------- html → text

class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}
    BLOCK = {"p", "div", "section", "article", "br", "tr", "table", "ul", "ol",
             "dl", "dt", "dd", "blockquote", "figure", "figcaption", "main"}

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.out: list[str] = []
        self.skip_depth = 0
        self.in_pre = 0
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.images: list[dict] = []
        self._last_caption_target: dict | None = None
        self._in_figcaption = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content"):
                self.meta[key] = a["content"]
        if self.skip_depth:
            return
        if tag == "img" and a.get("src"):
            src = urljoin(self.base_url, a["src"])
            if not src.startswith("data:"):
                img = {"src": src, "alt": a.get("alt", ""), "caption": ""}
                self.images.append(img)
                self._last_caption_target = img
        if tag == "figcaption":
            self._in_figcaption = True
        if tag == "pre":
            self.in_pre += 1
            self.out.append("\n```\n")
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag == "figcaption":
            self._in_figcaption = False
        if self.skip_depth:
            return
        if tag == "pre":
            self.in_pre = max(0, self.in_pre - 1)
            self.out.append("\n```\n")
        elif re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip_depth:
            return
        if self._in_figcaption and self._last_caption_target is not None:
            self._last_caption_target["caption"] += data.strip() + " "
        self.out.append(data if self.in_pre else re.sub(r"\s+", " ", data))

    def text(self) -> str:
        raw = "".join(self.out)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


DATE_KEYS = ("article:published_time", "article:modified_time", "og:updated_time",
             "datepublished", "datemodified", "date", "dc.date", "citation_publication_date",
             "citation_date", "last-modified")


# ---------------------------------------------------------------- commands

def cmd_init(args) -> int:
    day = dt.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9-]+", "-", args.slug.lower()).strip("-")[:48] or "run"
    run = Path(args.root).expanduser() / f"{day}-{slug}"
    for d in SUBDIRS:
        (run / d).mkdir(parents=True, exist_ok=True)
    meta = run / "run.json"
    if not meta.exists():
        meta.write_text(json.dumps({"slug": slug, "question": args.question,
                                    "created": now()}, ensure_ascii=False, indent=2))
    print(run)
    return 0


def cmd_source(args) -> int:
    run = Path(args.run_dir)
    manifest = run / "sources.jsonl"
    sid = short_id("s", args.url)
    for row in read_jsonl(manifest):
        if row["id"] == sid and row["status"] in ("ok", "thin", "webfetch"):
            print(json.dumps({**row, "duplicate": True}, ensure_ascii=False))
            return 0

    row = {"id": sid, "url": args.url, "type": args.type, "tier": args.tier,
           "subq": args.subq, "title": args.title or "", "fetched_at": now(),
           "raw": False, "bytes": 0, "text_chars": 0, "status": "failed",
           "fail_reason": "", "date": "", "snapshot": "", "text": ""}

    if args.webfetch:
        # curl이 막힌 페이지를 WebFetch 요약으로만 읽었을 때 기록한다
        row.update(status="webfetch", fail_reason=args.reason or "read via WebFetch only",
                   text_chars=args.chars or 0)
        append_jsonl(manifest, row)
        print(json.dumps(row, ensure_ascii=False))
        return 0

    tmp = run / "sources" / f"{sid}.download"
    code, ctype, eff, err = curl(args.url, tmp, args.timeout)
    row["effective_url"] = eff
    if err or code >= 400 or code == 0:
        row["fail_reason"] = err or f"http {code}"
        tmp.unlink(missing_ok=True)
        append_jsonl(manifest, row)
        print(json.dumps(row, ensure_ascii=False))
        return 1

    size = tmp.stat().st_size
    row["bytes"] = size
    head = tmp.read_bytes()[:5]
    if "pdf" in ctype or head.startswith(b"%PDF"):
        snap = tmp.with_suffix(".pdf")
        tmp.rename(snap)
        row.update(snapshot=str(snap.relative_to(run)), raw=True, status="ok",
                   fail_reason="pdf: read with the Read tool (pages)")
    elif "html" in ctype or head.lstrip().startswith(b"<"):
        snap = tmp.with_suffix(".html")
        tmp.rename(snap)
        html = snap.read_bytes().decode("utf-8", errors="replace")
        ex = TextExtractor(eff)
        ex.feed(html)
        text = ex.text()
        txt = snap.with_suffix(".txt")
        txt.write_text(text, encoding="utf-8")
        row.update(snapshot=str(snap.relative_to(run)), text=str(txt.relative_to(run)),
                   text_chars=len(text), title=row["title"] or ex.title.strip())
        row["date"] = next((ex.meta[k] for k in DATE_KEYS if k in ex.meta), "")
        if ex.images:
            imgs = snap.with_suffix(".images.json")
            imgs.write_text(json.dumps(ex.images, ensure_ascii=False, indent=1), encoding="utf-8")
            row["image_candidates"] = len(ex.images)
        if len(text) >= THIN_TEXT_CHARS:
            row.update(raw=True, status="ok")
        else:
            row.update(status="thin", fail_reason=f"text {len(text)} chars (JS-rendered?)")
    else:
        snap = tmp.with_suffix(".txt")
        tmp.rename(snap)
        text = snap.read_bytes().decode("utf-8", errors="replace")
        heading = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("# ")), "")
        row.update(snapshot=str(snap.relative_to(run)), text=str(snap.relative_to(run)),
                   text_chars=len(text), raw=True, status="ok", title=row["title"] or heading)

    append_jsonl(manifest, row)
    print(json.dumps(row, ensure_ascii=False))
    return 0


def cmd_image(args) -> int:
    run = Path(args.run_dir)
    iid = short_id("i", args.url)
    for row in read_jsonl(run / "images.jsonl"):
        if row["id"] == iid and row["status"] == "ok":
            print(json.dumps({**row, "duplicate": True}, ensure_ascii=False))
            return 0
    tmp = run / "images" / f"{iid}.download"
    code, ctype, eff, err = curl(args.url, tmp, args.timeout)
    lic = (args.license or "unknown").lower()
    row = {"id": iid, "url": args.url, "page": args.page, "source_id": args.source_id or "",
           "subq": args.subq, "caption": args.caption or "", "license": lic,
           "embed": lic in EMBEDDABLE_LICENSES, "fetched_at": now(),
           "status": "failed", "fail_reason": "", "bytes": 0, "file": ""}
    if err or code >= 400 or code == 0 or not ctype.startswith("image/"):
        row["fail_reason"] = err or (f"http {code}" if code >= 400 else f"content-type {ctype}")
        tmp.unlink(missing_ok=True)
    else:
        size = tmp.stat().st_size
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
               "image/webp": ".webp", "image/svg+xml": ".svg"}.get(ctype.split(";")[0], ".img")
        dest = tmp.with_suffix(ext)
        tmp.rename(dest)
        row.update(status="ok", bytes=size, file=str(dest.relative_to(run)))
        if size > IMAGE_MAX_BYTES:
            row.update(embed=False, fail_reason=f"too large ({size} bytes)")
    append_jsonl(run / "images.jsonl", row)
    print(json.dumps(row, ensure_ascii=False))
    return 0 if row["status"] == "ok" else 1


def cmd_search(args) -> int:
    row = {"subq": args.subq, "query": args.query, "engine": args.engine,
           "domains": args.domains or [], "results": args.results, "at": now()}
    append_jsonl(Path(args.run_dir) / "searches.jsonl", row)
    print(json.dumps(row, ensure_ascii=False))
    return 0


def _count(rows: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[str(r.get(key, ""))] = out.get(str(r.get(key, "")), 0) + 1
    return dict(sorted(out.items()))


def _dir_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0


def collect_stats(run: Path) -> dict:
    searches = read_jsonl(run / "searches.jsonl")
    sources = read_jsonl(run / "sources.jsonl")
    images = read_jsonl(run / "images.jsonl")
    claims = read_jsonl(run / "claims.jsonl")
    ok = [s for s in sources if s["status"] == "ok"]
    verdicts: list[dict] = []
    for f in sorted((run / "verdicts").glob("chunk-??.json")):
        try:
            verdicts += json.loads(f.read_text(encoding="utf-8")).get("verdicts", [])
        except (json.JSONDecodeError, OSError):
            pass
    cov = coverage(run, claims, verdicts)
    text_chars = sum(s.get("text_chars") or 0 for s in sources if s["status"] in ("ok", "thin"))
    return {
        "searches": {"count": len(searches), "results_seen": sum(s.get("results") or 0 for s in searches)},
        "sources": {
            "attempted": len(sources),
            "by_status": _count(sources, "status"),
            "by_type": _count(ok, "type"),
            "by_tier": _count(ok, "tier"),
            "raw_snapshots": sum(1 for s in sources if s.get("raw")),
            "pdf": sum(1 for s in ok if s.get("snapshot", "").endswith(".pdf")),
            "bytes_downloaded": sum(s.get("bytes") or 0 for s in sources),
            "text_chars": text_chars,
            "approx_tokens": round(text_chars / 3.5),
            "failures": [{"url": s["url"], "reason": s["fail_reason"]}
                         for s in sources if s["status"] in ("failed", "thin")],
        },
        "images": {
            "attempted": len(images),
            "downloaded": sum(1 for i in images if i["status"] == "ok"),
            "embeddable": sum(1 for i in images if i["status"] == "ok" and i["embed"]),
            "bytes": sum(i.get("bytes") or 0 for i in images if i["status"] == "ok"),
        },
        "disk": {"sources_dir_bytes": _dir_bytes(run / "sources"),
                 "images_dir_bytes": _dir_bytes(run / "images")},
        "claims": {"count": len(claims),
                   "sources_used": len({c.get("source_id") for c in claims})},
        "verdicts": {"count": len(verdicts), "by_verdict": _count(verdicts, "verdict")},
        "draft": cov,
    }


CITE_RE = re.compile(r"\[@((?:s[0-9a-f]{8})|(?:c\d{3,}))\]")


def read_adjudication(run: Path) -> dict[str, str]:
    """adjudication.md의 `cNNN | codex 판정 | 결론 | 근거` 행에서 claim_id → 결론."""
    out: dict[str, str] = {}
    p = run / "adjudication.md"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 3 and re.fullmatch(r"c\d{3,}", cols[0]):
            out[cols[0]] = cols[2]
    return out


def coverage(run: Path, claims: list[dict], verdicts: list[dict]) -> dict:
    """보고서 반영률: 채택 대상 주장 중 초안이 [@cNNN]으로 인용한 비율."""
    latest = {v["claim_id"]: v["verdict"] for v in verdicts}  # 뒤 청크(재검증)가 앞 판정을 덮는다
    adj = read_adjudication(run)
    known = {c["claim_id"]: c for c in claims}
    adoptable, intentional = set(), set()
    for cid in known:
        verdict, concl = latest.get(cid), adj.get(cid, "")
        if concl.startswith("미사용"):
            intentional.add(cid)
            continue
        if concl.startswith("제외") or verdict is None:
            continue
        if verdict in ("SUPPORTED", "PARTIAL") or any(k in concl for k in ("채택", "조건 반영")):
            adoptable.add(cid)
    cited_claims: set[str] = set()
    cited_sources: set[str] = set()
    draft = run / "draft.md"
    if draft.exists():
        for ref in CITE_RE.findall(draft.read_text(encoding="utf-8")):
            if ref.startswith("c"):
                cited_claims.add(ref)
                if ref in known:
                    cited_sources.add(known[ref].get("source_id", ""))
            else:
                cited_sources.add(ref)
    used = cited_claims & adoptable
    return {
        "sources_cited": len(cited_sources - {""}),
        "claims_cited": len(cited_claims),
        "adoptable": len(adoptable),
        "intentional_unused": len(intentional),
        "coverage": round(len(used) / len(adoptable), 3) if adoptable else None,
        "unused": sorted(adoptable - cited_claims),
        "cited_not_adoptable": sorted(cited_claims - adoptable),
    }


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def cmd_stats(args) -> int:
    st = collect_stats(Path(args.run_dir))
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    s, i = st["sources"], st["images"]
    by_status = s["by_status"]
    lines = [
        "| 항목 | 값 |", "|------|----|",
        f"| 검색 횟수 / 본 결과 수 | {st['searches']['count']} / {st['searches']['results_seen']} |",
        f"| 연 URL (시도) | {s['attempted']} |",
        f"| 원문 확보 (ok) | {by_status.get('ok', 0)} (PDF {s['pdf']}) |",
        f"| 본문 빈약 (thin, JS 렌더링 의심) | {by_status.get('thin', 0)} |",
        f"| WebFetch 요약만 | {by_status.get('webfetch', 0)} |",
        f"| 실패 | {by_status.get('failed', 0)} |",
        f"| 종류별 (ok) | {', '.join(f'{k} {v}' for k, v in s['by_type'].items()) or '-'} |",
        f"| 등급별 (ok) | {', '.join(f'{k} {v}' for k, v in s['by_tier'].items()) or '-'} |",
        f"| 내려받은 원문 | {human(s['bytes_downloaded'])} |",
        f"| 추출 텍스트 | {s['text_chars']:,}자 (약 {s['approx_tokens']:,} 토큰, 추정) |",
        f"| 이미지 | 내려받음 {i['downloaded']} / 시도 {i['attempted']}, 게재 가능 {i['embeddable']}, {human(i['bytes'])} |",
        f"| 주장 원장 | {st['claims']['count']}건, 출처 {st['claims']['sources_used']}개 사용 |",
        f"| codex 판정 | {st['verdicts']['count']}건 {st['verdicts']['by_verdict'] or ''} |",
        f"| 초안 인용 출처 | {st['draft']['sources_cited']}개 |",
    ]
    d = st["draft"]
    if d["coverage"] is not None:
        lines.append(f"| 보고서 반영률 | {d['coverage'] * 100:.0f}% (채택 대상 {d['adoptable']}건 중 인용 "
                     f"{d['adoptable'] - len(d['unused'])}건, 의도적 미사용 {d['intentional_unused']}건) |")
    print("\n".join(lines))
    if d["unused"]:
        print(f"\n본문에 쓰지 않은 채택 대상 주장 ({len(d['unused'])}건): {', '.join(d['unused'])}")
    if d["cited_not_adoptable"]:
        print(f"\n채택 대상이 아닌데 인용된 주장: {', '.join(d['cited_not_adoptable'])}")
    if s["failures"]:
        print("\n실패·빈약 URL:")
        for f in s["failures"]:
            print(f"- {f['url']}: {f['reason']}")
    return 0


def _snapshot_text(run: Path, source: dict) -> str | None:
    rel = source.get("text")
    if not rel:
        return None
    p = run / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None


def _check(run: Path, items: list[tuple[str, str, str]]) -> dict:
    """items: (item_id, source_id, quote)."""
    sources = {s["id"]: s for s in read_jsonl(run / "sources.jsonl")}
    cache: dict[str, str | None] = {}
    found, missing, unchecked = [], [], []
    for item_id, sid, quote in items:
        src = sources.get(sid)
        if src is None or not quote:
            unchecked.append({"id": item_id, "source_id": sid, "why": "no source or empty quote"})
            continue
        if sid not in cache:
            t = _snapshot_text(run, src)
            cache[sid] = normalize(t) if t else None
        hay = cache[sid]
        if hay is None:
            unchecked.append({"id": item_id, "source_id": sid, "why": f"no text snapshot ({src['status']})"})
        elif normalize(quote) in hay:
            found.append(item_id)
        else:
            missing.append({"id": item_id, "source_id": sid, "quote": quote[:160]})
    checked = len(found) + len(missing)
    return {"found": len(found), "missing": missing, "unchecked": unchecked,
            "found_ratio": round(len(found) / checked, 3) if checked else None}


def cmd_check_claims(args) -> int:
    run = Path(args.run_dir)
    claims = read_jsonl(run / "claims.jsonl")
    res = _check(run, [(c["claim_id"], c.get("source_id", ""), c.get("quote", "")) for c in claims])
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if not res["missing"] else 2


def cmd_check_verdicts(args) -> int:
    run = Path(args.run_dir)
    claims = {c["claim_id"]: c for c in read_jsonl(run / "claims.jsonl")}
    items = []
    for f in sorted((run / "verdicts").glob("chunk-??.json")):
        for v in json.loads(f.read_text(encoding="utf-8")).get("verdicts", []):
            if args.verdict and v.get("verdict") != args.verdict:
                continue
            sid = claims.get(v["claim_id"], {}).get("source_id", "")
            items.append((v["claim_id"], sid, v.get("quote", "")))
    res = _check(run, items)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def cmd_ledger(args) -> int:
    """notes/*.jsonl → claims.jsonl. 원문 대조에 실패한 줄은 claims.rejected.jsonl로 뺀다."""
    run = Path(args.run_dir)
    sources = {s["id"]: s for s in read_jsonl(run / "sources.jsonl")}
    seen: set[tuple[str, str]] = set()
    rows: list[dict] = []
    for f in sorted((run / "notes").glob("*.jsonl")):
        for r in read_jsonl(f):
            key = (normalize(r.get("claim", "")), r.get("source_id", ""))
            if not r.get("claim") or key in seen:
                continue
            seen.add(key)
            src = sources.get(r.get("source_id", ""), {})
            r.setdefault("url", src.get("url", ""))
            r.setdefault("tier", src.get("tier", ""))
            rows.append(r)
    for i, r in enumerate(rows, 1):
        r["claim_id"] = f"c{i:03d}"
    res = _check(run, [(r["claim_id"], r.get("source_id", ""), r.get("quote", "")) for r in rows])
    missing = {m["id"] for m in res["missing"]}
    kept = [r for r in rows if r["claim_id"] not in missing]
    rejected = [r for r in rows if r["claim_id"] in missing]
    (run / "claims.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
    (run / "claims.rejected.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rejected), encoding="utf-8")
    print(json.dumps({"notes_rows": len(rows), "kept": len(kept), "rejected_quote_mismatch": len(rejected),
                      "unchecked_no_text_snapshot": len(res["unchecked"])}, ensure_ascii=False, indent=2))
    return 0


def cmd_render(args) -> int:
    """draft.md의 [@cNNN](주장 id)·[@sid]를 출처 등장 순서대로 [[n]](url) 링크로 바꾸고 final.md·references.md를 쓴다."""
    run = Path(args.run_dir)
    sources = {s["id"]: s for s in read_jsonl(run / "sources.jsonl")}
    claim_src = {c["claim_id"]: c.get("source_id", "") for c in read_jsonl(run / "claims.jsonl")}
    draft = (run / args.input).read_text(encoding="utf-8")
    unknown_claims = sorted({r for r in CITE_RE.findall(draft) if r.startswith("c") and r not in claim_src})

    def to_sid(ref: str) -> str:
        return claim_src.get(ref, "") if ref.startswith("c") else ref

    order: list[str] = []
    for ref in CITE_RE.findall(draft):
        sid = to_sid(ref)
        if sid and sid not in order:
            order.append(sid)
    unknown = [s for s in order if s not in sources]
    num = {sid: i for i, sid in enumerate(order, 1)}

    def sub(m: re.Match) -> str:
        sid = to_sid(m.group(1))
        if not sid:
            return m.group(0)
        url = sources.get(sid, {}).get("url", "")
        return f"[[{num[sid]}]]({url})" if url else f"[{num[sid]}]"

    body = CITE_RE.sub(sub, draft)
    # 같은 출처 번호가 한 문장에 연달아 붙으면 하나로 줄인다: [[1]](u) [[1]](u) → [[1]](u)
    body = re.sub(r"(\[\[(\d+)\]\]\([^)]*\))(?:\s*\[\[\2\]\]\([^)]*\))+", r"\1", body)
    refs = []
    for sid in order:
        s = sources.get(sid, {})
        date = (s.get("date") or "")[:10] or "날짜 미상"
        title = s.get("title") or s.get("url", sid)
        gh = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/(.+)", s.get("url", ""))
        if gh and (not s.get("title") or s.get("title") == s.get("url")):
            title = f"{gh.group(1)}@{gh.group(2)}: {gh.group(3)}"
        elif gh:
            title = f"{s['title']} ({gh.group(1)}@{gh.group(2)}: {gh.group(3)})"
        refs.append(f"{num[sid]}. [{title}]({s.get('url', '')}) ({s.get('tier', '?')}, {s.get('type', '?')}, {date})")
    (run / "final.md").write_text(body, encoding="utf-8")
    (run / "references.md").write_text("\n".join(refs) + "\n", encoding="utf-8")
    print(json.dumps({"citations": len(order), "unknown_source_ids": unknown,
                      "unknown_claim_ids": unknown_claims,
                      "final": str(run / "final.md"), "references": str(run / "references.md")},
                     ensure_ascii=False, indent=2))
    return 0 if not (unknown or unknown_claims) else 2


# ---------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init")
    s.add_argument("slug")
    s.add_argument("--question", default="")
    s.add_argument("--root", default="~/.claude/research-runs")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("source")
    s.add_argument("run_dir")
    s.add_argument("url")
    s.add_argument("--type", required=True, choices=["official", "code", "paper", "blog", "other"])
    s.add_argument("--tier", required=True, choices=["T1", "T2", "T3"])
    s.add_argument("--subq", required=True)
    s.add_argument("--title", default="")
    s.add_argument("--timeout", type=int, default=60)
    s.add_argument("--webfetch", action="store_true", help="WebFetch 요약으로만 읽은 소스를 기록")
    s.add_argument("--chars", type=int, default=0, help="--webfetch일 때 반환 텍스트 길이")
    s.add_argument("--reason", default="")
    s.set_defaults(func=cmd_source)

    s = sub.add_parser("image")
    s.add_argument("run_dir")
    s.add_argument("url")
    s.add_argument("--page", required=True)
    s.add_argument("--subq", required=True)
    s.add_argument("--source-id", default="")
    s.add_argument("--caption", default="")
    s.add_argument("--license", default="unknown")
    s.add_argument("--timeout", type=int, default=60)
    s.set_defaults(func=cmd_image)

    s = sub.add_parser("search")
    s.add_argument("run_dir")
    s.add_argument("--subq", required=True)
    s.add_argument("--query", required=True)
    s.add_argument("--engine", default="WebSearch")
    s.add_argument("--domains", nargs="*")
    s.add_argument("--results", type=int, default=0)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("stats")
    s.add_argument("run_dir")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("check-claims")
    s.add_argument("run_dir")
    s.set_defaults(func=cmd_check_claims)

    s = sub.add_parser("check-verdicts")
    s.add_argument("run_dir")
    s.add_argument("--verdict", default="", help="예: SUPPORTED")
    s.set_defaults(func=cmd_check_verdicts)

    s = sub.add_parser("ledger")
    s.add_argument("run_dir")
    s.set_defaults(func=cmd_ledger)

    s = sub.add_parser("render")
    s.add_argument("run_dir")
    s.add_argument("--input", default="draft.md")
    s.set_defaults(func=cmd_render)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
