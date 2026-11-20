#!/usr/bin/env python3
"""
Engineering Feedback 격주 회고용 CLI.

Usage:
  python3 feedback-log.py candidates [--days 14]
  python3 feedback-log.py pending-changes
  python3 feedback-log.py append-takeaway --coach career|tech --case "..." --source "..." --keep "..." [--change "..."]
  python3 feedback-log.py append-check --items '[{"id": "2026-11-20-1", "verdict": "지킴", "note": "..."}]'

- candidates: 지난 N일의 Notion 일지(고민들, Problem, Lesson Learn)와 Claude 세션 로그에서
  사례 후보 재료를 모은다. 읽기 전용이다. 후보를 고르는 판단은 스킬(메인 대화)이 한다.
- 기록 파일은 Obsidian 볼트의 FEEDBACK_LOG_PATH 하나뿐이고, 덧붙이기만 한다. 기존 줄은 고치거나 지우지 않는다.
  dotfiles 리포는 GitHub에 올라가므로 개인 피드백 기록을 스킬 디렉터리에 두지 않는다.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta

SKILLS_DIR = os.path.expanduser("~/.claude/skills")
NOTION_DAILY_SCRIPT = f"{SKILLS_DIR}/daily:retrospective/scripts/notion-daily.py"
SESSION_LOG_SCRIPT = f"{SKILLS_DIR}/daily:retrospective/scripts/extract-work.py"
# 환경 변수는 테스트에서 실제 기록을 건드리지 않기 위한 것이다
FEEDBACK_LOG_PATH = os.environ.get("FEEDBACK_LOG_PATH") or os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/"
    "03. Resources/Engineering Feedback Log.md"
)

DEFAULT_LOOKBACK_DAYS = 14
# 회고 칸 중 "내가 한 판단이나 행동"이 담기는 칸만 쓴다. Keep/Try는 다짐이나 도구 감상이 많아 제외한다.
NOTION_RETRO_SECTIONS = ("Problem", "Lesson Learn")
# 세션 로그에서 사용자가 선택지를 저울질하거나 자기 판단을 의심한 흔적
DECISION_PATTERN = re.compile(
    r"(할까|맞을까|맞나|맞아\?|어느 ?쪽|vs\.?|우선순위|판단|트레이드|trade-?off|괜찮을까|과했|부족했|잘한 건지|왜 .{0,20}(했|하지))",
    re.IGNORECASE,
)
# 세션 제목 생성, 명령 래퍼처럼 사용자가 직접 쓰지 않은 메시지
NON_USER_MESSAGE_PREFIXES = (
    "Name this chat", "<command", "<local-command", "<system", "<task-notification", "Caveat:", "[Request interrupted",
)
SESSION_MESSAGE_MAX_CHARS = 240
SESSION_MESSAGES_PER_DAY = 5

VERDICT_KEPT = "지킴"
VERDICT_MISSED = "못 지킴"
VERDICT_NO_SITUATION = "상황 없음"  # 판정할 상황이 없었으므로 다음 회고에서 다시 점검한다
VALID_VERDICTS = (VERDICT_KEPT, VERDICT_MISSED, VERDICT_NO_SITUATION)

LOG_HEADER = (
    "# Engineering Feedback Log\n\n"
    "engineering-feedback 스킬이 덧붙이는 기록입니다. 코칭 마무리(Keep/Change)와 격주 회고의 Change 점검이 쌓입니다.\n"
    "점검 판정은 사용자가 합니다. 직접 고쳐도 되지만, 항목 제목의 ID는 바꾸지 마세요(점검이 ID로 이어집니다).\n"
)
TAKEAWAY_HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2}-\d+) (Career|Tech) Coach\s*$")
CHECK_HEADING = re.compile(r"^## \d{4}-\d{2}-\d{2} Change 점검\s*$")
CHECK_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}-\d+): (.+?)(?: \| .*)?$")


def run_json(script, *args):
    completed = subprocess.run([sys.executable, script, *args], capture_output=True, text=True)
    if completed.returncode != 0:
        return None, completed.stderr.strip()[:300]
    try:
        return json.loads(completed.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


# ---------- candidates ----------

def notion_materials(day):
    """그날 일지에서 판단·행동이 담긴 칸만 뽑는다. 페이지가 없으면 빈 목록."""
    log, err = run_json(NOTION_DAILY_SCRIPT, "read", "--date", day)
    if err or not log or "error" in log:
        return [], err or (log or {}).get("error")
    body = log.get("body", {})
    items = [
        {"date": day, "section": "고민들", "text": w.get("title", ""), "detail": w.get("detail", "")}
        for w in body.get("worries", [])
    ]
    for section in NOTION_RETRO_SECTIONS:
        items += [
            {"date": day, "section": section, "text": r.get("text", ""), "detail": r.get("detail", "")}
            for r in body.get("retro", {}).get(section, [])
        ]
    return [i for i in items if i["text"].strip()], None


def is_decision_message(message):
    stripped = message.strip()
    if not stripped or stripped.startswith(NON_USER_MESSAGE_PREFIXES):
        return False
    return bool(DECISION_PATTERN.search(stripped))


def session_materials(day):
    log, err = run_json(SESSION_LOG_SCRIPT, "--date", day)
    if err or not log:
        return [], err
    picked = []
    for session in log.get("sessions", []):
        for message in session.get("user_messages", []):
            if is_decision_message(message):
                picked.append({
                    "date": day,
                    "project": session.get("project", ""),
                    "message": message.strip()[:SESSION_MESSAGE_MAX_CHARS],
                })
    return picked[:SESSION_MESSAGES_PER_DAY], None


def cmd_candidates(args):
    today = date.today()
    days = [(today - timedelta(days=i)).isoformat() for i in range(1, args.days + 1)]
    notion, sessions, notion_missing, errors = [], [], [], []
    seen_messages = set()  # 여러 날에 걸친 세션은 같은 메시지가 날짜마다 다시 잡힌다
    for day in days:
        items, err = notion_materials(day)
        if err:
            notion_missing.append(day)
        notion += items
        picked, err = session_materials(day)
        if err:
            errors.append(f"session {day}: {err}")
        for item in picked:
            if item["message"] not in seen_messages:
                seen_messages.add(item["message"])
                sessions.append(item)
    print(json.dumps({
        "period": {"from": days[-1], "to": days[0]},
        "notion": notion,
        "sessions": sessions,
        "notion_days_without_page": notion_missing,
        "errors": errors,
    }, ensure_ascii=False, indent=2))


# ---------- log ----------

def read_log_lines():
    if not os.path.exists(FEEDBACK_LOG_PATH):
        return []
    with open(FEEDBACK_LOG_PATH, encoding="utf-8") as f:
        return f.read().splitlines()


def append_to_log(block):
    os.makedirs(os.path.dirname(FEEDBACK_LOG_PATH), exist_ok=True)
    is_new = not os.path.exists(FEEDBACK_LOG_PATH)
    with open(FEEDBACK_LOG_PATH, "a", encoding="utf-8") as f:
        if is_new:
            f.write(LOG_HEADER)
        f.write("\n" + block.rstrip() + "\n")


def parse_log(lines):
    """takeaway 항목(ID별 Change)과 ID별 마지막 점검 판정을 돌려준다."""
    takeaways, latest_verdict = {}, {}
    current_id, in_check = None, False
    for line in lines:
        heading = TAKEAWAY_HEADING.match(line)
        if heading:
            current_id, in_check = heading.group(1), False
            takeaways[current_id] = {"id": current_id, "coach": heading.group(2)}
            continue
        if CHECK_HEADING.match(line):
            current_id, in_check = None, True
            continue
        if line.startswith("## "):
            current_id, in_check = None, False
            continue
        if current_id:
            for field, prefix in (("case", "- 사례: "), ("change", "- Change: ")):
                if line.startswith(prefix):
                    takeaways[current_id][field] = line[len(prefix):].strip()
        elif in_check:
            check = CHECK_LINE.match(line)
            if check:
                latest_verdict[check.group(1)] = check.group(2).strip()
    return takeaways, latest_verdict


def cmd_pending_changes(_args):
    takeaways, latest_verdict = parse_log(read_log_lines())
    pending = [
        {**t, "last_verdict": latest_verdict.get(t["id"])}
        for t in takeaways.values()
        if t.get("change") and latest_verdict.get(t["id"]) in (None, VERDICT_NO_SITUATION)
    ]
    print(json.dumps({"log_path": FEEDBACK_LOG_PATH, "pending": pending}, ensure_ascii=False, indent=2))


def one_line(text):
    """기록은 줄 단위로 파싱하므로 값 안의 줄바꿈을 공백으로 바꾼다."""
    return " ".join((text or "").split())


def next_takeaway_id(lines, today):
    used = [m.group(1) for m in map(TAKEAWAY_HEADING.match, lines) if m and m.group(1).startswith(today)]
    return f"{today}-{len(used) + 1}"


def cmd_append_takeaway(args):
    today = date.today().isoformat()
    entry_id = next_takeaway_id(read_log_lines(), today)
    coach = "Career" if args.coach == "career" else "Tech"
    lines = [
        f"## {entry_id} {coach} Coach",
        f"- 사례: {one_line(args.case)}",
        f"- 출처: {one_line(args.source)}",
        f"- Keep: {one_line(args.keep)}",
    ]
    if args.change:
        lines.append(f"- Change: {one_line(args.change)}")
    append_to_log("\n".join(lines))
    print(json.dumps({"appended": entry_id, "log_path": FEEDBACK_LOG_PATH}, ensure_ascii=False))


def cmd_append_check(args):
    items = json.loads(args.items)
    known_ids, _ = parse_log(read_log_lines())
    bad = [i for i in items if i.get("id") not in known_ids or i.get("verdict") not in VALID_VERDICTS]
    if bad:
        print(json.dumps({"error": "unknown id or invalid verdict", "items": bad, "valid_verdicts": VALID_VERDICTS},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    lines = [f"## {date.today().isoformat()} Change 점검"]
    for item in items:
        note = f" | {one_line(item['note'])}" if item.get("note") else ""
        lines.append(f"- {item['id']}: {item['verdict']}{note}")
    append_to_log("\n".join(lines))
    print(json.dumps({"appended_checks": len(items), "log_path": FEEDBACK_LOG_PATH}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Engineering Feedback biweekly review CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("candidates", help="지난 N일의 사례 후보 재료 수집 (읽기 전용)")
    p.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    p.set_defaults(func=cmd_candidates)

    p = sub.add_parser("pending-changes", help="아직 점검하지 않은 Change 목록")
    p.set_defaults(func=cmd_pending_changes)

    p = sub.add_parser("append-takeaway", help="코칭 마무리 Keep/Change 기록")
    p.add_argument("--coach", choices=("career", "tech"), required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--keep", required=True)
    p.add_argument("--change")
    p.set_defaults(func=cmd_append_takeaway)

    p = sub.add_parser("append-check", help="격주 회고의 Change 점검 판정 기록")
    p.add_argument("--items", required=True)
    p.set_defaults(func=cmd_append_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
