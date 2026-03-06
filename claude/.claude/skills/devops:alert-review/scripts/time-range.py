#!/usr/bin/env python3
"""시간 범위 계산 유틸리티 — KST 기준 입력을 UTC/epoch/Slack 파라미터로 변환."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
UTC = timezone.utc


def parse_time_expr(expr: str, ref_now: datetime) -> datetime:
    """시간 표현식을 KST datetime으로 변환.

    지원 형식:
      - "now"
      - "now-Nh" (N시간 전)
      - "yesterday HH:MM"
      - "today HH:MM"
      - "YYYY-MM-DD HH:MM"
      - "YYYY-MM-DD"
    """
    expr = expr.strip()

    # now
    if expr == "now":
        return ref_now

    # now-Nh
    m = re.match(r"^now-(\d+)h$", expr, re.IGNORECASE)
    if m:
        return ref_now - timedelta(hours=int(m.group(1)))

    # yesterday HH:MM
    m = re.match(r"^yesterday\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        yesterday = ref_now - timedelta(days=1)
        return yesterday.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # today HH:MM
    m = re.match(r"^today\s+(\d{1,2}):(\d{2})$", expr, re.IGNORECASE)
    if m:
        return ref_now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)

    # YYYY-MM-DD HH:MM
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})$", expr)
    if m:
        d = datetime.strptime(m.group(1), "%Y-%m-%d")
        return d.replace(hour=int(m.group(2)), minute=int(m.group(3)), second=0, microsecond=0, tzinfo=KST)

    # YYYY-MM-DD (자정)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})$", expr)
    if m:
        d = datetime.strptime(m.group(1), "%Y-%m-%d")
        return d.replace(tzinfo=KST)

    print(json.dumps({"success": False, "error": f"지원하지 않는 시간 형식: '{expr}'"}), flush=True)
    sys.exit(1)


def fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def fmt_readable(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M KST")


def cmd_calc(args):
    now_kst = datetime.now(KST)

    from_kst = parse_time_expr(args.from_expr, now_kst)
    to_kst = parse_time_expr(args.to_expr, now_kst)

    # KST timezone 보장
    if from_kst.tzinfo is None:
        from_kst = from_kst.replace(tzinfo=KST)
    if to_kst.tzinfo is None:
        to_kst = to_kst.replace(tzinfo=KST)

    from_utc = from_kst.astimezone(UTC)
    to_utc = to_kst.astimezone(UTC)

    from_epoch = str(int(from_kst.timestamp()))
    to_epoch = str(int(to_kst.timestamp()))

    result = {
        "success": True,
        "from_kst": fmt_readable(from_kst),
        "to_kst": fmt_readable(to_kst),
        "from_utc": fmt_iso(from_utc),
        "to_utc": fmt_iso(to_utc),
        "from_epoch": from_epoch,
        "to_epoch": to_epoch,
        "slack_oldest": from_epoch,
        "slack_latest": to_epoch,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="KST 시간 범위 → UTC/epoch 변환")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("calc", help="시간 범위 계산")
    p.add_argument("--from", dest="from_expr", default="yesterday 22:00",
                    help='시작 시간 (KST). 예: "yesterday 22:00", "now-12h", "2026-03-01 22:00"')
    p.add_argument("--to", dest="to_expr", default="now",
                    help='종료 시간 (KST). 예: "now", "today 09:00", "2026-03-02 09:00"')

    args = parser.parse_args()
    {"calc": cmd_calc}[args.command](args)


if __name__ == "__main__":
    main()
