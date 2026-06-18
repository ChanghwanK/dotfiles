#!/usr/bin/env python3
"""Claude Code session data helper for session-tui.sh"""

import argparse
import glob
import json
import os
import signal
import sys
import unicodedata
from datetime import datetime, timezone, timedelta

# Terminate silently when downstream consumer (head, less, fzf) closes the pipe
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

SESSIONS_DIR = os.path.expanduser("~/.claude/projects")
ACTIVE_DIR = os.path.expanduser("~/.claude/sessions")


def get_active_session_ids():
    active = set()
    for f in glob.glob(os.path.join(ACTIVE_DIR, "*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)
            sid = data.get("sessionId")
            if sid:
                active.add(sid)
        except Exception:
            pass
    return active


def format_date(dt):
    return dt.astimezone().strftime("%b %d %H:%M")


def format_date_long(dt):
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def format_date_from_iso(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return format_date_long(dt)
    except Exception:
        return "N/A"


def sanitize(s, max_len=None):
    if not s:
        return ""
    s = s.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    if max_len and len(s) > max_len:
        return s[:max_len - 1] + "…"
    return s


def _disp_width(s):
    """터미널 표시 너비 — CJK(한글/한자/전각)는 2칸으로 계산한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def fit_width(s, width):
    """표시 너비(CJK=2) 기준으로 width에 맞춰 자르고 우측 패딩한다.

    한글이 섞인 요약 컬럼을 정렬할 때 len() 기반 패딩은 깨지므로,
    실제 렌더링 너비로 잘라 뒤 컬럼(레포/브랜치)이 어긋나지 않게 한다.
    """
    out, w, truncated = "", 0, False
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if w + cw > width - 1:  # … 자리 확보
            truncated = True
            break
        out += ch
        w += cw
    if truncated:
        out += "…"
        w += 1
    if w < width:
        out += " " * (width - w)
    return out


def get_project_short(project_path):
    if not project_path:
        return "?"
    name = project_path.rstrip("/").split("/")[-1]
    return name[:22] + "…" if len(name) > 23 else name


def extract_jsonl_metadata(jsonl_file):
    """Extract session metadata from the first 60 lines of a JSONL file."""
    sid = os.path.basename(jsonl_file).replace(".jsonl", "")
    stat = os.stat(jsonl_file)

    entry = {
        "sessionId": sid,
        "projectPath": "",
        "gitBranch": "",
        "firstPrompt": "",
        "summary": "",
        "messageCount": 0,
        "isSidechain": False,
        "_mtime": stat.st_mtime,
        "_ctime": getattr(stat, "st_birthtime", stat.st_mtime),
    }

    try:
        with open(jsonl_file) as fp:
            for i, line in enumerate(fp):
                entry["messageCount"] += 1
                if i >= 200:
                    # After collecting metadata, just count remaining lines
                    for _ in fp:
                        entry["messageCount"] += 1
                    break
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                rtype = record.get("type", "")

                if "cwd" in record and not entry["projectPath"]:
                    entry["projectPath"] = record["cwd"]
                if "gitBranch" in record and not entry["gitBranch"]:
                    entry["gitBranch"] = record.get("gitBranch", "")
                if "isSidechain" in record and not entry["isSidechain"]:
                    entry["isSidechain"] = bool(record["isSidechain"])

                if rtype == "user" and not entry["firstPrompt"]:
                    content = record.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                entry["firstPrompt"] = block.get("text", "")
                                break
                    elif isinstance(content, str):
                        entry["firstPrompt"] = content

                if rtype == "ai-title" and not entry["summary"]:
                    entry["summary"] = record.get("title", "")

    except Exception:
        pass

    return entry


def compute_cutoff(days=None, today=False):
    """필터 기준 시각(UTC)을 계산한다.

    today=True면 로컬(KST) 자정 기준 — '오늘 수정된 세션만' 의미.
    아니면 now - days (롤링 N일). days 미지정 시 7일 기본.
    """
    if today:
        local_midnight = datetime.now().astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0)
        return local_midnight.astimezone(timezone.utc)
    return datetime.now(timezone.utc) - timedelta(days=days if days is not None else 7)


def load_all_sessions(cutoff):
    """Gather sessions from index files and direct JSONL scanning."""
    cutoff_ts = cutoff.timestamp()

    sessions = {}  # sessionId -> entry

    # Phase 1: sessions-index.json (older sessions with summary pre-computed)
    for index_file in glob.glob(os.path.join(SESSIONS_DIR, "*", "sessions-index.json")):
        try:
            with open(index_file) as fp:
                data = json.load(fp)
            for entry in data.get("entries", []):
                if entry.get("isSidechain"):
                    continue
                sid = entry.get("sessionId", "")
                if sid:
                    sessions[sid] = entry
        except Exception:
            pass

    # Phase 2: scan JSONL files directly (picks up recent sessions not yet indexed)
    for jsonl_file in glob.glob(os.path.join(SESSIONS_DIR, "*", "*.jsonl")):
        # Skip if already indexed
        sid = os.path.basename(jsonl_file).replace(".jsonl", "")
        if sid in sessions:
            # Update file mtime for indexed sessions too (more accurate)
            try:
                sessions[sid]["_file_mtime"] = os.path.getmtime(jsonl_file)
            except OSError:
                pass
            continue

        # Check mtime before reading content to skip old files fast
        try:
            mtime = os.path.getmtime(jsonl_file)
        except OSError:
            continue
        if mtime < cutoff_ts:
            continue

        entry = extract_jsonl_metadata(jsonl_file)
        if entry and not entry.get("isSidechain"):
            sessions[sid] = entry

    return sessions, cutoff


def resolve_modified(entry):
    """Return modified datetime from entry, preferring file mtime."""
    file_mtime = entry.get("_file_mtime")
    if file_mtime:
        return datetime.fromtimestamp(file_mtime, tz=timezone.utc)
    mtime = entry.get("_mtime")
    if mtime:
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    modified_str = entry.get("modified", "")
    if modified_str:
        try:
            return datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
        except Exception:
            pass
    return None


_SKIP_PATH_FRAGMENTS = ("observer-sessions", ".claude-mem/")


def is_internal_session(entry):
    """Return True for claude-mem observer sessions and other internal sessions."""
    path = entry.get("projectPath", "")
    return any(frag in path for frag in _SKIP_PATH_FRAGMENTS)


def list_sessions(cutoff):
    sessions, cutoff = load_all_sessions(cutoff)
    active_ids = get_active_session_ids()

    entries_with_dt = []
    for sid, entry in sessions.items():
        if is_internal_session(entry):
            continue
        modified = resolve_modified(entry)
        if modified is None or modified < cutoff:
            continue
        entries_with_dt.append((modified, entry))

    # 내림차순(최근 먼저). fzf 기본 레이아웃(프롬프트 아래, 첫 줄을 맨 아래에 배치)과
    # 조합하면 화면상 오래된 게 위, 최근이 아래로 표시되고 커서가 맨 아래(최근)에서 시작한다.
    entries_with_dt.sort(key=lambda x: x[0], reverse=True)

    for modified, entry in entries_with_dt:
        session_id = entry.get("sessionId", "")
        project_path = entry.get("projectPath", "")
        branch = (entry.get("gitBranch", "") or "").strip()
        msg_count = entry.get("messageCount", 0)
        first_prompt = entry.get("firstPrompt", "") or ""
        summary = (entry.get("summary", "") or first_prompt)

        is_active = session_id in active_ids
        status = "●" if is_active else " "

        date_str = format_date(modified)
        project_short = get_project_short(project_path)
        branch_str = f"[{branch[:10]}]" if branch else ""
        summary_str = fit_width(sanitize(summary), 50)

        # 요약(제목)을 날짜 다음 앞쪽에 크게, 레포/브랜치/msg는 뒤로 — 내용 식별 우선
        display = (
            f"{date_str}  {status}  "
            f"{summary_str}  "
            f"{project_short}  {branch_str}  {msg_count:>4}msg"
        )

        print(f"{session_id}\t{project_path}\t{display}")


def show_preview(session_id):
    sessions, _ = load_all_sessions(compute_cutoff(days=365))
    active_ids = get_active_session_ids()

    entry = sessions.get(session_id)
    if not entry:
        print(f"Session not found: {session_id}")
        return

    is_active = session_id in active_ids
    modified = resolve_modified(entry)
    ctime = entry.get("_ctime")
    created_dt = datetime.fromtimestamp(ctime, tz=timezone.utc) if ctime else None

    print(f"Session:  {session_id}")
    print(f"Status:   {'ACTIVE' if is_active else 'inactive'}")
    print(f"Project:  {entry.get('projectPath', 'N/A')}")
    print(f"Branch:   {entry.get('gitBranch', 'N/A') or 'N/A'}")
    print(f"Created:  {format_date_long(created_dt) if created_dt else format_date_from_iso(entry.get('created', ''))}")
    print(f"Modified: {format_date_long(modified) if modified else 'N/A'}")
    print(f"Messages: {entry.get('messageCount', 0)}")

    prompt = entry.get("firstPrompt", "") or ""
    if prompt:
        print()
        print("First prompt:")
        prompt = prompt.replace("\n", " ")
        line = ""
        for word in prompt.split():
            if len(line) + len(word) + 1 > 43:
                print(f"  {line}")
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            print(f"  {line}")


def main():
    parser = argparse.ArgumentParser(description="Claude Code session helper")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--today", action="store_true", help="오늘(로컬 자정 이후) 세션만")
    parser.add_argument("--preview", type=str, metavar="SESSION_ID")
    args = parser.parse_args()

    if args.preview:
        show_preview(args.preview)
    else:
        list_sessions(compute_cutoff(days=args.days, today=args.today))


if __name__ == "__main__":
    main()
