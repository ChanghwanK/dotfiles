#!/usr/bin/env python3
"""
성장 기록 CLI (daily:retrospective의 성장 증거와 성장 판정용).

Usage:
  python3 growth-log.py append-day --date D --evidence '[{"type": "알게 된 것", "text": "..."}]' \
      [--prediction '{"text": "...", "check_by": "YYYY-MM-DD"}']
  python3 growth-log.py due-predictions --date D
  python3 growth-log.py score-prediction --date D --items '[{"id": "P-2026-11-20-1", "verdict": "맞음", "note": "..."}]'
  python3 growth-log.py status --date D
  python3 growth-log.py period --from D --to D
  python3 growth-log.py append-judgment --date D --period-from D --hit-rate "3/5" --verdict "..." [--notes '["...", "..."]']
  python3 growth-log.py append-defer --date D

- 매일은 성장 여부(증거 한 줄), 2~4주마다는 성장 크기(판정)를 남긴다.
- 판정 시점은 달력이 아니라 마지막 판정 후 경과일(status)로 정한다. 회고를 며칠 건너뛰어도 경과일은 쌓인다.
- 기록 파일은 Obsidian 볼트의 GROWTH_LOG_PATH 하나뿐이고, 덧붙이기만 한다. 기존 줄은 고치거나 지우지 않는다.
  dotfiles 리포는 GitHub에 올라가므로 개인 기록을 스킬 디렉터리에 두지 않는다.
"""

import argparse
import json
import os
import re
import sys
from datetime import date

# 환경 변수는 테스트에서 실제 기록을 건드리지 않기 위한 것이다
GROWTH_LOG_PATH = os.environ.get("GROWTH_LOG_PATH") or os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/03. Resources/Growth Log.md"
)

# 판정 단계 경계(경과일). 2층 구조의 "2~4주"를 그대로 옮긴 값이다
JUDGMENT_DUE_DAYS = 14
JUDGMENT_OVERDUE_DAYS = 28
STAGE_NORMAL, STAGE_DUE, STAGE_OVERDUE = "normal", "due", "overdue"

EVIDENCE_TYPES = ("알게 된 것", "할 수 있게 된 것", "약점", "채점된 예측")
NO_EVIDENCE = "없음"
VERDICT_HIT, VERDICT_MISS, VERDICT_UNKNOWN = "맞음", "틀림", "판정 못 함"
VALID_VERDICTS = (VERDICT_HIT, VERDICT_MISS, VERDICT_UNKNOWN)

LOG_HEADER = (
    "# Growth Log\n\n"
    "daily:retrospective가 덧붙이는 성장 기록입니다. 매일의 증거와 예측, 예측 채점, 2~4주 성장 판정이 쌓입니다.\n"
    "직접 고쳐도 되지만, 헤딩 형식과 예측 ID는 바꾸지 마세요(채점과 판정이 이 형식으로 이어집니다).\n"
)

HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}) (성장 기록|예측 채점|성장 판정|판정 미룸)\s*$")
EVIDENCE_LINE = re.compile(r"^- 증거(?:\((.+?)\))?: (.+)$")
PREDICTION_LINE = re.compile(r"^- 예측 (P-\d{4}-\d{2}-\d{2}-\d+) \(확인 (\d{4}-\d{2}-\d{2})\): (.+)$")
SCORE_LINE = re.compile(r"^- (P-\d{4}-\d{2}-\d{2}-\d+): (.+?)(?: \| (.*))?$")


def one_line(text):
    """기록은 줄 단위로 파싱하므로 값 안의 줄바꿈을 공백으로 바꾼다."""
    return " ".join((text or "").split())


def parse_date(value):
    # notion-daily.py와 같이 "today"를 받는다
    return date.today() if value == "today" else date.fromisoformat(value)


def fail(message, **extra):
    print(json.dumps({"error": message, **extra}, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


# ---------- 기록 파일 ----------

def read_log_lines():
    if not os.path.exists(GROWTH_LOG_PATH):
        return []
    with open(GROWTH_LOG_PATH, encoding="utf-8") as f:
        return f.read().splitlines()


def append_to_log(block):
    os.makedirs(os.path.dirname(GROWTH_LOG_PATH), exist_ok=True)
    is_new = not os.path.exists(GROWTH_LOG_PATH)
    with open(GROWTH_LOG_PATH, "a", encoding="utf-8") as f:
        if is_new:
            f.write(LOG_HEADER)
        f.write("\n" + block.rstrip() + "\n")


def parse_log(lines):
    """기록 파일을 날짜별 일일 기록, 예측, 채점, 판정일, 미룸일로 나눈다."""
    log = {"days": {}, "predictions": {}, "scores": {}, "judgments": [], "defers": []}
    section, section_date = None, None
    for line in lines:
        heading = HEADING.match(line)
        if heading:
            section_date, section = heading.group(1), heading.group(2)
            if section == "성장 기록":
                log["days"].setdefault(section_date, [])
            elif section == "성장 판정":
                log["judgments"].append(section_date)
            elif section == "판정 미룸":
                log["defers"].append(section_date)
            continue
        if line.startswith("## "):
            section = None
            continue
        if section == "성장 기록":
            evidence = EVIDENCE_LINE.match(line)
            if evidence:
                log["days"][section_date].append({"type": evidence.group(1), "text": evidence.group(2).strip()})
                continue
            prediction = PREDICTION_LINE.match(line)
            if prediction:
                pid = prediction.group(1)
                log["predictions"][pid] = {
                    "id": pid, "date": section_date, "check_by": prediction.group(2), "text": prediction.group(3).strip(),
                }
        elif section == "예측 채점":
            score = SCORE_LINE.match(line)
            if score:
                # 같은 예측을 다시 채점하면 마지막 판정을 쓴다
                log["scores"][score.group(1)] = {"verdict": score.group(2).strip(), "note": score.group(3) or "", "date": section_date}
    return log


def has_evidence(entries):
    return any(e["type"] is not None and e["text"] != NO_EVIDENCE for e in entries)


# ---------- 명령 ----------

def next_prediction_id(log, day):
    used = [pid for pid in log["predictions"] if pid.startswith(f"P-{day}-")]
    return f"P-{day}-{len(used) + 1}"


def cmd_append_day(args):
    day = parse_date(args.date).isoformat()
    evidence = json.loads(args.evidence) if args.evidence else []
    bad = [e for e in evidence if e.get("type") not in EVIDENCE_TYPES or not one_line(e.get("text"))]
    if bad:
        fail("invalid evidence", items=bad, valid_types=EVIDENCE_TYPES)
    log = parse_log(read_log_lines())
    if day in log["days"]:
        # 같은 날 회고를 두 번 돌려도 기록이 겹치지 않게 한다
        print(json.dumps({"skipped": "already recorded", "date": day, "log_path": GROWTH_LOG_PATH}, ensure_ascii=False))
        return
    lines = [f"## {day} 성장 기록"]
    if evidence:
        lines += [f"- 증거({e['type']}): {one_line(e['text'])}" for e in evidence]
    else:
        lines.append(f"- 증거: {NO_EVIDENCE}")
    prediction_id = None
    if args.prediction:
        prediction = json.loads(args.prediction)
        check_by = parse_date(prediction["check_by"]).isoformat()
        if not one_line(prediction.get("text")):
            fail("prediction text is empty")
        prediction_id = next_prediction_id(log, day)
        lines.append(f"- 예측 {prediction_id} (확인 {check_by}): {one_line(prediction['text'])}")
    append_to_log("\n".join(lines))
    print(json.dumps({"appended": day, "evidence": len(evidence), "prediction_id": prediction_id,
                      "log_path": GROWTH_LOG_PATH}, ensure_ascii=False))


def unscored_due(log, day):
    return [p for p in log["predictions"].values() if p["check_by"] <= day and p["id"] not in log["scores"]]


def cmd_due_predictions(args):
    day = parse_date(args.date).isoformat()
    due = sorted(unscored_due(parse_log(read_log_lines()), day), key=lambda p: p["check_by"])
    print(json.dumps({"date": day, "due": due}, ensure_ascii=False, indent=2))


def cmd_score_prediction(args):
    day = parse_date(args.date).isoformat()
    items = json.loads(args.items)
    log = parse_log(read_log_lines())
    bad = [i for i in items if i.get("id") not in log["predictions"] or i.get("verdict") not in VALID_VERDICTS]
    if bad:
        fail("unknown id or invalid verdict", items=bad, valid_verdicts=VALID_VERDICTS)
    lines = [f"## {day} 예측 채점"]
    for item in items:
        note = f" | {one_line(item['note'])}" if item.get("note") else ""
        lines.append(f"- {item['id']}: {item['verdict']}{note}")
    append_to_log("\n".join(lines))
    print(json.dumps({"scored": len(items), "log_path": GROWTH_LOG_PATH}, ensure_ascii=False))


def no_evidence_streak(log, day):
    """오늘(포함)부터 거슬러 기록된 날 기준으로 증거 없음이 몇 번 연속인가. 기록 없는 날은 세지 않는다."""
    streak = 0
    for recorded in sorted((d for d in log["days"] if d <= day), reverse=True):
        if has_evidence(log["days"][recorded]):
            break
        streak += 1
    return streak


def judgment_stage(elapsed_days):
    if elapsed_days >= JUDGMENT_OVERDUE_DAYS:
        return STAGE_OVERDUE
    if elapsed_days >= JUDGMENT_DUE_DAYS:
        return STAGE_DUE
    return STAGE_NORMAL


def cmd_status(args):
    today = parse_date(args.date)
    log = parse_log(read_log_lines())
    past_judgments = sorted(j for j in log["judgments"] if j <= today.isoformat())
    recorded_days = sorted(d for d in log["days"] if d <= today.isoformat())
    # 판정을 한 번도 안 했으면 첫 기록일부터 센다. 기록도 없으면 판정할 재료가 없다
    anchor = past_judgments[-1] if past_judgments else (recorded_days[0] if recorded_days else None)
    elapsed = (today - parse_date(anchor)).days if anchor else 0
    defers_since = [d for d in log["defers"] if anchor and anchor < d <= today.isoformat()]
    print(json.dumps({
        "date": today.isoformat(),
        "anchor": anchor,
        "anchor_kind": "judgment" if past_judgments else ("first_record" if anchor else None),
        "elapsed_days": elapsed,
        "stage": judgment_stage(elapsed) if anchor else STAGE_NORMAL,
        "defers_since_anchor": len(defers_since),
        "deferred_today": today.isoformat() in log["defers"],
        "recorded_days_since_anchor": len([d for d in recorded_days if not anchor or d >= anchor]),
        "no_evidence_streak": no_evidence_streak(log, today.isoformat()),
        "log_path": GROWTH_LOG_PATH,
    }, ensure_ascii=False, indent=2))


def cmd_period(args):
    start, end = parse_date(args.from_).isoformat(), parse_date(args.to).isoformat()
    log = parse_log(read_log_lines())
    days = {d: e for d, e in sorted(log["days"].items()) if start <= d <= end}
    evidence = [{"date": d, **e} for d, entries in days.items() for e in entries if e["type"] is not None]
    predictions = [
        {**p, "score": log["scores"].get(p["id"])}
        for p in sorted(log["predictions"].values(), key=lambda p: p["date"])
        if start <= p["date"] <= end
    ]
    scored = [p for p in predictions if p["score"] and p["score"]["verdict"] in (VERDICT_HIT, VERDICT_MISS)]
    hits = [p for p in scored if p["score"]["verdict"] == VERDICT_HIT]
    print(json.dumps({
        "period": {"from": start, "to": end},
        "recorded_days": len(days),
        "days_with_evidence": len([e for e in days.values() if has_evidence(e)]),
        "evidence": evidence,
        "predictions": predictions,
        "hit_rate": f"{len(hits)}/{len(scored)}" if scored else None,
        "unscored": len([p for p in predictions if not p["score"]]),
    }, ensure_ascii=False, indent=2))


def cmd_append_judgment(args):
    day = parse_date(args.date).isoformat()
    period_from = parse_date(args.period_from).isoformat()
    if not one_line(args.verdict):
        fail("verdict is empty")
    lines = [
        f"## {day} 성장 판정",
        f"- 기간: {period_from} ~ {day}",
        f"- 적중률: {args.hit_rate or '채점된 예측 없음'}",
    ]
    lines += [f"- {one_line(n)}" for n in (json.loads(args.notes) if args.notes else []) if one_line(n)]
    lines.append(f"- 판정: {one_line(args.verdict)}")
    append_to_log("\n".join(lines))
    print(json.dumps({"appended_judgment": day, "log_path": GROWTH_LOG_PATH}, ensure_ascii=False))


def cmd_append_defer(args):
    day = parse_date(args.date).isoformat()
    if day in parse_log(read_log_lines())["defers"]:
        print(json.dumps({"skipped": "already deferred today", "date": day}, ensure_ascii=False))
        return
    append_to_log(f"## {day} 판정 미룸")
    print(json.dumps({"appended_defer": day, "log_path": GROWTH_LOG_PATH}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Growth log CLI for daily:retrospective")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("append-day", help="그날의 성장 증거와 예측 기록")
    p.add_argument("--date", required=True)
    p.add_argument("--evidence", help="JSON 배열. 비우면 '증거: 없음'으로 기록")
    p.add_argument("--prediction", help='JSON 객체 {"text": "...", "check_by": "YYYY-MM-DD"}')
    p.set_defaults(func=cmd_append_day)

    p = sub.add_parser("due-predictions", help="확인일이 됐는데 채점하지 않은 예측")
    p.add_argument("--date", required=True)
    p.set_defaults(func=cmd_due_predictions)

    p = sub.add_parser("score-prediction", help="예측 채점 기록")
    p.add_argument("--date", required=True)
    p.add_argument("--items", required=True)
    p.set_defaults(func=cmd_score_prediction)

    p = sub.add_parser("status", help="마지막 판정 후 경과일과 판정 단계 (읽기 전용)")
    p.add_argument("--date", required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("period", help="기간의 증거, 예측, 적중률 (읽기 전용)")
    p.add_argument("--from", dest="from_", required=True)
    p.add_argument("--to", required=True)
    p.set_defaults(func=cmd_period)

    p = sub.add_parser("append-judgment", help="성장 판정 기록")
    p.add_argument("--date", required=True)
    p.add_argument("--period-from", required=True)
    p.add_argument("--hit-rate")
    p.add_argument("--verdict", required=True, help="사용자가 쓴 이번 기간 판정 한 줄")
    p.add_argument("--notes", help="JSON 배열. 판정 질문별 사용자 답 한 줄씩")
    p.set_defaults(func=cmd_append_judgment)

    p = sub.add_parser("append-defer", help="판정 미룸 기록")
    p.add_argument("--date", required=True)
    p.set_defaults(func=cmd_append_defer)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
