#!/usr/bin/env python3
"""가설 장부(~/.claude/docs/hypothesis-ledger.md) 도구.

서브커맨드:
  overdue            판정일이 된 미판정 행 출력 (SessionStart 훅, --hook 이면 JSON, 하루 한 번만)
  stats              결과별 건수, 판정 완료율, 빗나감률
  import-followups   플랜의 `## 후속 판정` 항목을 장부에 미판정 행으로 추가 (멱등)

세 동작이 같은 장부 스키마를 읽고 쓰므로 파싱을 이 파일 한 곳에 둔다.
장부 행: | 날짜 | 가설 | 검증 기준 | 판정일 | 결과 | 수정된 믿음 | 링크 |
결과 열은 열거값만 쓴다: 적중 / 빗나감 / 미판정 / 검증 불가, 또는 "적용 직후 X, 결과 Y" 두 값.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

HOME = pathlib.Path.home()
LEDGER = HOME / ".claude/docs/hypothesis-ledger.md"
SHOWN_STATE = HOME / ".claude/.ledger-overdue-shown"
DATE = re.compile(r"20\d\d-\d\d-\d\d")
# 셀 안의 `\|`는 구분자가 아니다
CELL_SPLIT = re.compile(r"(?<!\\)\|")
AUTO_PREFIX = "(플랜 후속 판정) "
MAX_LINES = 5


def read_rows():
    rows = []
    for line in LEDGER.read_text().splitlines():
        if not line.startswith("| 20"):
            continue
        cells = [c.strip() for c in CELL_SPLIT.split(line)[1:-1]]
        if len(cells) != 7:
            continue
        rows.append(dict(zip(["date", "hypothesis", "criteria", "due", "result", "belief", "link"], cells)))
    return rows


def pending_due_date(row):
    """아직 판정되지 않은 부분의 판정일. 판정이 끝났으면 None."""
    dates = [dt.date.fromisoformat(d) for d in DATE.findall(row["due"])]
    if not dates:
        return None
    result = row["result"]
    if result == "미판정":
        return dates[0]
    if result.endswith("결과 미판정"):
        return dates[-1]
    return None


def cmd_overdue(args):
    today = dt.date.today()
    items = []
    for row in read_rows():
        due = pending_due_date(row)
        if due and due <= today:
            label = row["hypothesis"].replace(AUTO_PREFIX, "")[:50]
            items.append((due, f"{due} | {label} | {row['link']}"))
    items.sort()
    if not items:
        return
    if args.hook:
        # 매 세션 반복하면 노이즈가 되므로 하루 한 번만 보인다
        stamp = today.isoformat()
        try:
            if SHOWN_STATE.read_text().strip() == stamp:
                return
        except OSError:
            pass
        SHOWN_STATE.write_text(stamp)
    lines = [text for _, text in items[:MAX_LINES]]
    if len(items) > MAX_LINES:
        lines.append(f"외 {len(items) - MAX_LINES}건")
    if not args.hook:
        print("\n".join(lines))
        return
    context = (
        f"[장부] 판정일이 된 미판정 가설 {len(items)}건 (판정일 | 가설 | 링크):\n" + "\n".join(lines) + "\n"
        "첫 응답 끝에 한 줄로 알리고, 판정할지는 사용자가 정한다. 판정하면 장부 행의 결과 열을 채운다."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
                     ensure_ascii=False))


def cmd_stats(_args):
    rows = read_rows()
    counts = {}
    for row in rows:
        counts[row["result"]] = counts.get(row["result"], 0) + 1
    for result, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{n:>4}  {result}")
    judged = sum(n for r, n in counts.items() if r in ("적중", "빗나감", "검증 불가") or r.startswith("적용 직후") and "결과 미판정" not in r)
    missed = sum(n for r, n in counts.items() if "빗나감" in r)
    total = len(rows)
    print(f"전체 {total} | 판정 완료율 {judged / total:.0%} | 빗나감률(판정 완료 대비) {missed / judged:.0%}" if judged else f"전체 {total}")


def parse_plan(path):
    text = path.read_text(errors="ignore")
    fm = re.match(r"(?s)^---\n(.*?)\n---\n", text)
    meta = {}
    if fm:
        for line in fm.group(1).splitlines():
            m = re.match(r"^(plan_id|title|created):\s*'?(.*?)'?\s*$", line)
            if m:
                meta[m.group(1)] = m.group(2)
    section = re.search(r"(?ms)^## 후속 판정[^\n]*\n(.*?)(?=^## |\Z)", text)
    items = []
    if section:
        for line in section.group(1).splitlines():
            m = re.match(r"^- (20\d\d-\d\d-\d\d)[^:]*:\s*(.+)$", line)
            if m:
                items.append((m.group(1), m.group(2).strip()))
    return meta.get("plan_id", path.stem), meta.get("title", path.stem), meta.get("created", "")[:10], items


def already_recorded(rows, plan_id, due, criteria):
    for row in rows:
        if plan_id not in row["link"] or due not in row["due"]:
            continue
        # 사람이 직접 쓴 행은 같은 날짜의 항목 전체를 대신한다
        if not row["hypothesis"].startswith(AUTO_PREFIX):
            return True
        if row["criteria"].startswith(criteria[:40].replace("|", "\\|")):
            return True
    return False


def cmd_import(args):
    rows = read_rows()
    added = []
    for name in args.plans:
        plan_id, title, created, items = parse_plan(pathlib.Path(name).expanduser())
        for due, criteria in items:
            if already_recorded(rows, plan_id, due, criteria):
                continue
            cell = lambda s: s.replace("|", "\\|")
            row = (f"| {created or dt.date.today().isoformat()} | {AUTO_PREFIX}{cell(title)} | {cell(criteria)} "
                   f"| {due} | 미판정 | | 플랜 {plan_id} |")
            added.append(row)
            rows.append({"date": created, "hypothesis": AUTO_PREFIX + title, "criteria": cell(criteria),
                         "due": due, "result": "미판정", "belief": "", "link": f"플랜 {plan_id}"})
    if added:
        with LEDGER.open("a") as f:
            f.write("\n".join(added) + "\n")
    if not args.quiet:
        print(f"[ledger] 후속 판정 {len(added)}건을 장부에 미판정으로 추가했습니다")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("overdue")
    o.add_argument("--hook", action="store_true", help="SessionStart 훅 JSON 출력, 하루 한 번만")
    sub.add_parser("stats")
    i = sub.add_parser("import-followups")
    i.add_argument("plans", nargs="+")
    i.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    try:
        {"overdue": cmd_overdue, "stats": cmd_stats, "import-followups": cmd_import}[args.cmd](args)
    except Exception as exc:  # 훅에서 호출되므로 세션을 막지 않는다
        print(f"[ledger] 오류: {exc}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
