#!/usr/bin/env python3
"""
devops:log-analysis — 범용 애플리케이션 로그 분석기
stdin 또는 파일 경로(sys.argv[1])로 로그를 입력받아
6개 모듈(A~F)의 RCA 인사이트를 Markdown으로 출력한다.

사용법:
  kubectl logs {pod} -n {ns} | python3 analyze-logs.py
  python3 analyze-logs.py /path/to/logfile.txt
"""

import json
import re
import sys
import os
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# ──────────────────────────────────────────────
# 외부 API 감지 패턴
# ──────────────────────────────────────────────
EXTERNAL_PATTERNS = {
    "openai/completions": re.compile(r"api\.openai\.com.*completions", re.I),
    "openai/moderations": re.compile(r"api\.openai\.com.*moderations", re.I),
    "openai/other": re.compile(r"api\.openai\.com", re.I),
    "anthropic": re.compile(r"api\.anthropic\.com", re.I),
    "aws-s3": re.compile(r"s3\.amazonaws\.com|\.s3\.", re.I),
    "aws-bedrock": re.compile(r"bedrock.*amazonaws|bedrock-runtime", re.I),
    "aws-other": re.compile(r"\.amazonaws\.com", re.I),
    "grpc": re.compile(r"grpc.*status|status_code.*grpc", re.I),
    "redis": re.compile(r"redis|REDIS", re.I),
    "postgres/db": re.compile(r"psycopg|sqlalchemy|asyncpg|pg.*error", re.I),
}

# ──────────────────────────────────────────────
# 재시도 감지: 같은 user_id + 같은 정규화 path 반복
# ──────────────────────────────────────────────
RETRY_THRESHOLD = 3


def normalize_path(path: str) -> str:
    """숫자 ID, UUID를 {id}로 치환하여 엔드포인트 그룹핑."""
    if not path:
        return ""
    p = re.sub(r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", p := path)
    p = re.sub(r"/\d+", "/{id}", p)
    # query string 제거
    p = p.split("?")[0]
    return p


def detect_format(sample_lines: list[str]) -> str:
    """첫 번째 비어있지 않은 줄로 JSON/plaintext 판별."""
    for line in sample_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                json.loads(line)
                return "json"
            except Exception:
                pass
        return "plaintext"
    return "plaintext"


def parse_json_line(line: str) -> dict | None:
    try:
        return json.loads(line)
    except Exception:
        return None


def parse_plaintext_line(line: str) -> dict | None:
    """plain text 로그에서 timestamp, level, message 추출 시도."""
    # ISO 8601 timestamp
    m = re.match(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*(?:Z|[+-]\d{2}:\d{2})?)", line)
    ts = m.group(1) if m else None
    # level
    level_m = re.search(r"\b(DEBUG|INFO|WARNING|ERROR|CRITICAL|WARN|FATAL)\b", line, re.I)
    level = level_m.group(1).upper() if level_m else None
    # http status
    status_m = re.search(r"\b([2345]\d{2})\b", line)
    status = int(status_m.group(1)) if status_m else None
    # duration (ms or s)
    dur_m = re.search(r"(\d+(?:\.\d+)?)\s*ms\b", line)
    dur = float(dur_m.group(1)) if dur_m else None
    if not dur:
        dur_m2 = re.search(r"(\d+\.\d+)\s*s\b", line)
        dur = float(dur_m2.group(1)) * 1000 if dur_m2 else None
    return {
        "timestamp": ts,
        "log_level": level,
        "message": line.strip(),
        "http_response_code": status,
        "duration_ms": dur,
        "http_request_path": None,
        "user_id": None,
    }


def parse_timestamp(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    # 공통 패턴: Z suffix → +00:00 로 교체 후 파싱
    normalized = ts_str.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
    ]:
        try:
            dt = datetime.strptime(normalized[:32], fmt)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def minute_key(dt) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%H:%M")
    if isinstance(dt, str):
        return dt[:5]
    return "??"


def percentile(sorted_list: list, pct: float) -> float:
    if not sorted_list:
        return 0
    idx = int(len(sorted_list) * pct)
    return sorted_list[min(idx, len(sorted_list) - 1)]


# ──────────────────────────────────────────────
# 메인 분석
# ──────────────────────────────────────────────
def main():
    # 입력 소스 결정
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
    else:
        raw_lines = sys.stdin.readlines()

    if not raw_lines:
        print("## 로그 없음 — 입력 데이터가 비어있습니다.")
        return

    fmt = detect_format(raw_lines[:20])
    total_lines = len(raw_lines)

    # 파싱
    records = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        if fmt == "json":
            d = parse_json_line(line)
            if d is None:
                d = parse_plaintext_line(line)
        else:
            d = parse_plaintext_line(line)
        if d:
            records.append(d)

    # ──────────────────────────────
    # 데이터 집계
    # ──────────────────────────────
    minute_req_count: dict[str, int] = defaultdict(int)
    minute_durs: dict[str, list] = defaultdict(list)
    minute_errors: dict[str, int] = defaultdict(int)
    minute_external: dict[str, int] = defaultdict(int)

    endpoint_count: Counter = Counter()
    endpoint_durs: dict[str, list] = defaultdict(list)
    endpoint_errors: dict[str, int] = defaultdict(int)

    slow_requests: list[dict] = []  # >1000ms
    error_records: list[dict] = []
    external_calls: dict[str, list] = defaultdict(list)  # service -> [record]

    user_endpoint: dict[str, Counter] = defaultdict(Counter)  # user_id -> path Counter

    timestamps_all = []

    for d in records:
        ts_raw = d.get("timestamp")
        dt = parse_timestamp(ts_raw) if ts_raw else None
        mk = minute_key(dt) if dt else "??"

        path = d.get("http_request_path") or ""
        norm = normalize_path(path)
        dur = d.get("duration_ms") or 0
        code = d.get("http_response_code") or 0
        msg = d.get("message") or ""
        uid = d.get("user_id") or ""
        level = d.get("log_level") or ""

        if dt:
            timestamps_all.append(dt)

        # HTTP 요청인 경우
        if norm:
            minute_req_count[mk] += 1
            if dur:
                minute_durs[mk].append(dur)
                endpoint_durs[norm].append(dur)
            endpoint_count[norm] += 1
            if code >= 400:
                minute_errors[mk] += 1
                endpoint_errors[norm] += 1
                error_records.append({"ts": mk, "code": code, "path": path, "dur": dur, "uid": uid, "msg": msg[:120]})
            if dur > 1000:
                slow_requests.append({"ts": mk, "code": code, "path": path, "dur": dur, "uid": uid})
            if uid:
                user_endpoint[uid][norm] += 1

        # 외부 API 감지
        for svc, pattern in EXTERNAL_PATTERNS.items():
            if pattern.search(msg):
                minute_external[mk] += 1
                external_calls[svc].append({"ts": mk, "msg": msg[:100], "code": code})
                break

    # 시간 범위
    if timestamps_all:
        ts_sorted = sorted(timestamps_all)
        start_utc = ts_sorted[0].strftime("%Y-%m-%d %H:%M:%S")
        end_utc = ts_sorted[-1].strftime("%Y-%m-%d %H:%M:%S")
        start_kst = ts_sorted[0].astimezone(KST).strftime("%H:%M:%S")
        end_kst = ts_sorted[-1].astimezone(KST).strftime("%H:%M:%S")
        date_kst = ts_sorted[0].astimezone(KST).strftime("%Y-%m-%d")
        time_range_str = f"{start_utc} ~ {end_utc} UTC  /  {date_kst} {start_kst} ~ {end_kst} KST"
    else:
        time_range_str = "알 수 없음"

    total_http = sum(minute_req_count.values())

    # ──────────────────────────────
    # 스파이크 감지
    # ──────────────────────────────
    all_minutes = sorted(minute_req_count.keys())
    avg_rpm = total_http / max(len(all_minutes), 1)

    # ──────────────────────────────
    # 출력
    # ──────────────────────────────
    print(f"## 로그 분석 결과\n")
    print(f"- **로그 포맷**: `{fmt}`")
    print(f"- **분석 기간**: {time_range_str}")
    print(f"- **총 로그**: {total_lines:,}줄 / **HTTP 요청**: {total_http:,}건")
    print()

    # ── Module A: 트래픽 추이 ──────────────────
    print("---\n### A. 트래픽 추이 (분당, UTC 기준)\n")
    print(f"{'UTC':>6}  {'요청수':>6}  {'avg_ms':>7}  {'p95_ms':>7}  {'max_ms':>7}  {'에러율':>6}  {'외부API':>6}  비고")
    for mk in all_minutes:
        cnt = minute_req_count[mk]
        durs = sorted(minute_durs.get(mk, []))
        avg = sum(durs) / len(durs) if durs else 0
        p95 = percentile(durs, 0.95)
        mx = durs[-1] if durs else 0
        errs = minute_errors.get(mk, 0)
        err_rate = f"{errs/cnt*100:.1f}%" if cnt else "-"
        ext = minute_external.get(mk, 0)
        spike = "<<< SPIKE" if cnt > avg_rpm * 2 and avg_rpm > 0 else ""
        print(f"{mk:>6}  {cnt:>6}  {avg:>7.0f}  {p95:>7.0f}  {mx:>7.0f}  {err_rate:>6}  {ext:>6}  {spike}")
    print()

    # ── Module B: 엔드포인트 랭킹 ─────────────
    print("---\n### B. 엔드포인트 랭킹 TOP 20\n")
    print(f"{'순위':>4}  {'호출수':>6}  {'avg_ms':>7}  {'max_ms':>7}  {'에러수':>6}  엔드포인트")
    for rank, (ep, cnt) in enumerate(endpoint_count.most_common(20), 1):
        durs = sorted(endpoint_durs.get(ep, []))
        avg = sum(durs) / len(durs) if durs else 0
        mx = durs[-1] if durs else 0
        errs = endpoint_errors.get(ep, 0)
        heavy = "  ← 무거움" if mx > 3000 else ""
        print(f"{rank:>4}  {cnt:>6}  {avg:>7.0f}  {mx:>7.0f}  {errs:>6}  {ep}{heavy}")
    print()

    # ── Module C: 슬로우 요청 ─────────────────
    slow_sorted = sorted(slow_requests, key=lambda x: -x["dur"])
    print(f"---\n### C. 슬로우 요청 TOP 20 (>1초, {len(slow_requests)}건 총)\n")
    print(f"{'시각':>6}  {'응답시간':>8}  {'상태':>4}  {'user_id':>10}  경로")
    for r in slow_sorted[:20]:
        print(f"{r['ts']:>6}  {r['dur']:>7.0f}ms  {r['code']:>4}  {str(r['uid']):>10}  {r['path']}")
    print()

    # ── Module D: 에러 패턴 ───────────────────
    print("---\n### D. 에러 패턴\n")
    code_counter: Counter = Counter()
    code_endpoints: dict[int, Counter] = defaultdict(Counter)
    for e in error_records:
        code_counter[e["code"]] += 1
        code_endpoints[e["code"]][normalize_path(e["path"])] += 1

    print("#### HTTP 상태코드별")
    print(f"{'코드':>4}  {'건수':>6}  상위 엔드포인트")
    for code, cnt in sorted(code_counter.items()):
        top_ep = ", ".join(f"{ep}({n})" for ep, n in code_endpoints[code].most_common(3))
        print(f"{code:>4}  {cnt:>6}  {top_ep}")
    print()

    # ── Module E: 외부 API 호출 ───────────────
    print("---\n### E. 외부 API 호출\n")
    if external_calls:
        print(f"{'서비스':>20}  {'호출수':>6}  분당최대  에러수")
        for svc in sorted(external_calls.keys()):
            calls = external_calls[svc]
            cnt = len(calls)
            minute_c: Counter = Counter(c["ts"] for c in calls)
            max_per_min = max(minute_c.values()) if minute_c else 0
            errs = sum(1 for c in calls if (c.get("code") or 0) >= 400)
            print(f"{svc:>20}  {cnt:>6}  {max_per_min:>8}  {errs:>6}")
    else:
        print("외부 API 호출 패턴 미감지 (검출 패턴: openai, anthropic, aws, grpc, redis, postgres)")
    print()

    # ── Module F: 유저 편향 분석 ──────────────
    print("---\n### F. 유저 편향 분석\n")
    user_totals: Counter = Counter({uid: sum(cnt.values()) for uid, cnt in user_endpoint.items()})
    if user_totals:
        print(f"{'user_id':>12}  {'총요청':>6}  주요 엔드포인트 (상위 3개)")
        for uid, total in user_totals.most_common(10):
            top_eps = ", ".join(f"{ep}({n})" for ep, n in user_endpoint[uid].most_common(3))
            # 재시도 감지: 동일 path 3회+ 요청
            retry_eps = [(ep, n) for ep, n in user_endpoint[uid].items() if n >= RETRY_THRESHOLD]
            retry_note = f"  ← 재시도 의심: {retry_eps[0][0]}({retry_eps[0][1]}회)" if retry_eps else ""
            print(f"{str(uid):>12}  {total:>6}  {top_eps}{retry_note}")
    else:
        print("user_id 필드 없음 (plain text 로그 또는 인증 없는 서비스)")
    print()

    print("---")
    print("> **종합 인사이트**: 위 분석 결과를 바탕으로 Claude가 스파이크 원인, 가장 무거운 작업, 권장 조치를 3줄로 요약합니다.")


if __name__ == "__main__":
    main()
