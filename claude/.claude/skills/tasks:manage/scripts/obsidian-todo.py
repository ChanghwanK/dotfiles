#!/usr/bin/env python3
"""
Obsidian Daily Note Todo 관리 스크립트

Usage:
  python3 obsidian-todo.py append --name "Task이름" --priority "P1 - Must Have" --due "YYYY-MM-DD" \
    [--description "부가 설명"] [--date "YYYY-MM-DD"]
  python3 obsidian-todo.py sync-progress [--handoff PATH] [--completed "A,B"] [--in-progress "A,B"] \
    [--next "A,B"] (--dry-run | --apply) [--date "YYYY-MM-DD"]
  python3 obsidian-todo.py auto-progress (--dry-run | --apply) [--date "YYYY-MM-DD"] [--threshold 0.5]

Note: 개별 Todo 업데이트(완료 처리, 메모 추가)는 Claude가 Daily Note를 직접 Read/Edit로 수행.
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

CLAUDE_MEM_DB = Path.home() / ".claude-mem" / "claude-mem.db"

# 한국어 조사 목록 (토큰 추출 시 제거)
KO_PARTICLES = ["에서", "으로", "에게", "한테", "부터", "까지", "이랑", "과의", "와의", "에", "을", "를", "의", "로", "이", "가", "은", "는", "도", "만", "과", "와", "랑"]

DAILY_DIR = Path(
    "/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily"
)


def extract_task_name(line: str) -> str:
    """Todo 라인에서 메타데이터를 제거하고 task 이름만 추출."""
    text = line.strip()
    # 체크박스 제거
    text = re.sub(r"^- \[[ x]\]\s*", "", text)
    # 이모지 메타데이터 제거: 🛫 YYYY-MM-DD, 📅 YYYY-MM-DD, ✅ YYYY-MM-DD, ⏫
    text = re.sub(r"🛫\s*\d{4}-\d{2}-\d{2}\s*", "", text)
    text = re.sub(r"📅\s*\d{4}-\d{2}-\d{2}\s*", "", text)
    text = re.sub(r"✅\s*\d{4}-\d{2}-\d{2}", "", text)
    text = re.sub(r"⏫", "", text)
    return text.strip()


def fuzzy_match(needle: str, haystack: str) -> bool:
    """두 task 이름이 매칭되는지 판별. 정확/포함 관계 비교."""
    n = needle.lower().strip()
    h = haystack.lower().strip()
    if not n or not h:
        return False
    if n == h:
        return True
    if n in h or h in n:
        return True
    return False


def is_top_level_todo(line: str) -> bool:
    """탭/스페이스 들여쓰기 없는 최상위 todo 라인인지 판별."""
    return bool(re.match(r"^- \[[ x]\]", line.strip())) and not line.startswith("\t") and not line.startswith("    ")


def parse_todos_section(lines: list[str], todos_idx: int) -> tuple[int, int, list[dict]]:
    """## Todos 섹션에서 최상위 todo 항목 파싱.

    Returns: (section_start, section_end, todos)
    section_end = ### 서브헤딩 또는 다음 ## 헤딩 직전 (빈 줄 제외)
    todos = [{line_idx, text, done, name}]
    """
    # ### 또는 ## 헤딩으로 todo 리스트 경계 찾기
    boundary_idx = len(lines)
    for i in range(todos_idx + 1, len(lines)):
        stripped = lines[i].rstrip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            boundary_idx = i
            break

    todos = []
    for i in range(todos_idx + 1, boundary_idx):
        line = lines[i]
        if is_top_level_todo(line):
            done = bool(re.match(r"^- \[x\]", line.strip()))
            name = extract_task_name(line)
            todos.append({"line_idx": i, "text": line, "done": done, "name": name})

    # 실제 삽입 위치: boundary 직전의 빈 줄 건너뛰기
    insert_idx = boundary_idx
    while insert_idx > todos_idx + 1 and lines[insert_idx - 1].strip() == "":
        insert_idx -= 1

    return todos_idx, insert_idx, todos


def mark_done(line: str, done_date: str) -> str:
    """- [ ] 라인을 - [x] ... ✅ YYYY-MM-DD 로 변환."""
    newline = line.replace("- [ ]", "- [x]", 1)
    # 기존 ✅ 날짜가 없으면 추가
    if "✅" not in newline:
        newline = newline.rstrip() + f" ✅ {done_date}"
        if not newline.endswith("\n"):
            newline += "\n"
    return newline


def load_handoff(path: str) -> dict:
    """handoff JSON 파일 로드. completed/in_progress/next/notes 추출."""
    p = Path(path)
    if not p.exists():
        return {"error": "handoff_file_not_found", "path": str(p)}
    data = json.loads(p.read_text(encoding="utf-8"))
    completed = data.get("completed", [])
    in_progress_raw = data.get("in_progress", [])
    # in_progress는 [{task, context}] 또는 [str] 형태
    in_progress = []
    for item in in_progress_raw:
        if isinstance(item, dict):
            in_progress.append(item.get("task", str(item)))
        else:
            in_progress.append(str(item))
    return {
        "completed": completed,
        "in_progress": in_progress,
        "next": data.get("next", []),
        "notes": data.get("notes", ""),
    }


def sync_progress(
    target_date: str,
    completed: list[str],
    in_progress: list[str],
    next_items: list[str],
    dry_run: bool,
) -> dict:
    """Obsidian Daily Note의 ## Todos에 진행 상황을 반영."""
    daily_file = DAILY_DIR / f"{target_date}.md"

    if not daily_file.exists():
        return {"applied": False, "error": "daily_note_not_found", "file": str(daily_file)}

    lines = daily_file.read_text(encoding="utf-8").splitlines(keepends=True)

    # ## Todos 섹션 찾기
    todos_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "## Todos":
            todos_idx = i
            break

    if todos_idx is None:
        return {"applied": False, "error": "todos_section_not_found", "file": str(daily_file)}

    _, insert_idx, existing_todos = parse_todos_section(lines, todos_idx)

    changes = {"marked_done": [], "added_new": [], "skipped": []}

    # 1) completed 항목 처리: 기존 todo 매칭 → done 표시, 매칭 없음 → 새로 추가
    new_lines_to_add = []
    for item in completed:
        matched = False
        for todo in existing_todos:
            if fuzzy_match(item, todo["name"]):
                if todo["done"]:
                    changes["skipped"].append(item)
                else:
                    lines[todo["line_idx"]] = mark_done(lines[todo["line_idx"]], target_date)
                    changes["marked_done"].append(item)
                matched = True
                break
        if not matched:
            new_lines_to_add.append(f"- [x] {item} ✅ {target_date}\n")
            changes["marked_done"].append(f"{item} (신규)")

    # 2) in_progress 항목 처리: 기존 매칭 → 스킵, 매칭 없음 → 새로 추가
    for item in in_progress:
        matched = False
        for todo in existing_todos:
            if fuzzy_match(item, todo["name"]):
                matched = True
                break
        if not matched:
            new_lines_to_add.append(f"- [ ] {item}\n")
            changes["added_new"].append(item)

    # 3) next 항목 처리: 동일 로직
    for item in next_items:
        matched = False
        for todo in existing_todos:
            if fuzzy_match(item, todo["name"]):
                matched = True
                break
        # in_progress에서 이미 추가된 항목과도 중복 체크
        for prev in in_progress:
            if fuzzy_match(item, prev):
                matched = True
                break
        if not matched:
            new_lines_to_add.append(f"- [ ] {item}\n")
            changes["added_new"].append(item)

    result = {
        "mode": "dry-run" if dry_run else "apply",
        "file": str(daily_file),
        "date": target_date,
        "existing_todos_count": len(existing_todos),
        "changes": changes,
    }

    if dry_run:
        result["new_lines_preview"] = [l.rstrip() for l in new_lines_to_add]
        print(json.dumps(result, ensure_ascii=False))
        return result

    # apply: 새 항목 삽입 + done 표시는 이미 lines에 반영됨
    for line_to_insert in reversed(new_lines_to_add):
        lines.insert(insert_idx, line_to_insert)

    daily_file.write_text("".join(lines), encoding="utf-8")
    result["applied"] = True
    print(json.dumps(result, ensure_ascii=False))
    return result


def query_session_work(target_date: str) -> dict:
    """claude-mem.db에서 특정 날짜의 세션 요약 데이터를 조회한다."""
    if not CLAUDE_MEM_DB.exists():
        return {"error": "db_not_found", "path": str(CLAUDE_MEM_DB)}

    try:
        uri = f"file:{CLAUDE_MEM_DB}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        cur = con.cursor()
        cur.execute(
            "SELECT request, completed, next_steps FROM session_summaries WHERE date(created_at) = ? AND (completed IS NOT NULL OR next_steps IS NOT NULL)",
            (target_date,),
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error as e:
        return {"error": str(e)}

    raw_completed = []
    raw_next_steps = []
    for request, completed, next_steps in rows:
        if completed:
            raw_completed.append(completed)
        if next_steps:
            raw_next_steps.append(next_steps)

    return {
        "sessions_count": len(rows),
        "raw_completed": raw_completed,
        "raw_next_steps": raw_next_steps,
    }


def _strip_ko_particles(token: str) -> str:
    """한국어 토큰에서 조사를 제거한다. 긴 조사 먼저 시도."""
    for p in sorted(KO_PARTICLES, key=len, reverse=True):
        if token.endswith(p) and len(token) > len(p):
            return token[: -len(p)]
    return token


def _extract_tokens(text: str) -> list[str]:
    """텍스트에서 의미 있는 토큰 추출 (2자 이상, 조사 제거)."""
    raw = re.split(r"[\s,./\-_\(\)\[\]「」『』【】]+", text.lower())
    tokens = []
    for t in raw:
        t = t.strip()
        if len(t) < 2:
            continue
        t = _strip_ko_particles(t)
        if len(t) >= 2:
            tokens.append(t)
    return tokens


def enhanced_fuzzy_match(session_text: str, todo_name: str) -> float:
    """세션 텍스트와 todo 이름 간의 유사도 점수를 반환한다 (0.0~1.0).

    todo_name에서 핵심 토큰을 추출하여 session_text에 몇 개나 포함되는지 비율로 계산.
    토큰 수가 2개 이하인 짧은 todo는 완전 포함(substring) 방식으로 보조 판별.
    """
    if not session_text or not todo_name:
        return 0.0

    tokens = _extract_tokens(todo_name)
    if not tokens:
        return 0.0

    session_lower = session_text.lower()
    matched = sum(1 for t in tokens if t in session_lower)
    score = matched / len(tokens)
    return round(score, 4)


def auto_progress(target_date: str, dry_run: bool, threshold: float) -> dict:
    """claude-mem.db 세션 데이터와 Daily Note todos를 fuzzy match하여 진행 상황을 추천한다."""
    # Step 1: 세션 데이터 수집
    session_data = query_session_work(target_date)
    if "error" in session_data:
        result = {"error": session_data["error"], "date": target_date}
        print(json.dumps(result, ensure_ascii=False))
        return result

    if session_data["sessions_count"] == 0:
        result = {
            "date": target_date,
            "sessions_analyzed": 0,
            "message": "기록된 세션 없음",
            "recommendations": {"mark_done": [], "likely_in_progress": [], "unmatched_completed": [], "no_match_todos": []},
        }
        print(json.dumps(result, ensure_ascii=False))
        return result

    # Step 2: Daily Note todos 파싱
    daily_file = DAILY_DIR / f"{target_date}.md"
    if not daily_file.exists():
        result = {"error": "daily_note_not_found", "file": str(daily_file), "date": target_date}
        print(json.dumps(result, ensure_ascii=False))
        return result

    lines = daily_file.read_text(encoding="utf-8").splitlines(keepends=True)
    todos_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "## Todos":
            todos_idx = i
            break

    if todos_idx is None:
        result = {"error": "todos_section_not_found", "file": str(daily_file), "date": target_date}
        print(json.dumps(result, ensure_ascii=False))
        return result

    _, insert_idx, existing_todos = parse_todos_section(lines, todos_idx)
    pending_todos = [t for t in existing_todos if not t["done"]]

    raw_completed = session_data["raw_completed"]
    raw_next_steps = session_data["raw_next_steps"]
    all_completed_text = "\n".join(raw_completed)
    all_next_text = "\n".join(raw_next_steps)

    mark_done_candidates = []
    likely_in_progress_candidates = []
    matched_todo_names = set()

    # Step 3: 각 미완료 todo × completed 텍스트 매칭
    for todo in pending_todos:
        todo_name = todo["name"]
        # 짧은 todo (토큰 ≤2)는 threshold 자동 상향
        tokens = _extract_tokens(todo_name)
        effective_threshold = max(threshold, 0.8) if len(tokens) <= 2 else threshold

        best_score = 0.0
        best_snippet = ""
        for text in raw_completed:
            score = enhanced_fuzzy_match(text, todo_name)
            if score > best_score:
                best_score = score
                best_snippet = text[:120] if len(text) > 120 else text

        if best_score >= effective_threshold:
            mark_done_candidates.append({"todo": todo_name, "matched_by": best_snippet, "score": best_score})
            matched_todo_names.add(todo_name)
            continue

        # Step 4: next_steps 텍스트 매칭
        best_next_score = 0.0
        best_next_snippet = ""
        for text in raw_next_steps:
            score = enhanced_fuzzy_match(text, todo_name)
            if score > best_next_score:
                best_next_score = score
                best_next_snippet = text[:120] if len(text) > 120 else text

        if best_next_score >= effective_threshold:
            likely_in_progress_candidates.append({"todo": todo_name, "matched_by": best_next_snippet, "score": best_next_score})
            matched_todo_names.add(todo_name)

    no_match_todos = [t["name"] for t in pending_todos if t["name"] not in matched_todo_names]

    # completed 텍스트 중 todo와 매칭 안 된 것 (세션에서만 완료된 작업)
    matched_completed_texts = set()
    for item in mark_done_candidates:
        matched_completed_texts.add(item["matched_by"])
    unmatched_completed = [text[:80] for text in raw_completed if not any(
        item["matched_by"] in text for item in mark_done_candidates
    )][:10]  # 최대 10개

    result = {
        "date": target_date,
        "sessions_analyzed": session_data["sessions_count"],
        "mode": "dry-run" if dry_run else "apply",
        "recommendations": {
            "mark_done": mark_done_candidates,
            "likely_in_progress": likely_in_progress_candidates,
            "unmatched_completed": unmatched_completed,
            "no_match_todos": no_match_todos,
        },
    }

    if not dry_run and mark_done_candidates:
        # apply: mark_done 항목만 Daily Note에 반영
        applied = []
        for item in mark_done_candidates:
            for todo in existing_todos:
                if todo["name"] == item["todo"] and not todo["done"]:
                    lines[todo["line_idx"]] = mark_done(lines[todo["line_idx"]], target_date)
                    applied.append(item["todo"])
                    break
        daily_file.write_text("".join(lines), encoding="utf-8")
        result["applied"] = applied

    print(json.dumps(result, ensure_ascii=False))
    return result


def build_todo_line(name: str, priority: str | None, due: str | None, start_date: str) -> str:
    """Todo 라인 생성. priority/due 없으면 심플 형식."""
    if not priority and not due:
        return f"- [ ] {name}"
    is_p1 = priority.startswith("P1") if priority else False
    priority_suffix = " ⏫" if is_p1 else ""
    parts = ["- [ ] "]
    parts.append(f"🛫 {start_date}  ")
    if due:
        parts.append(f"📅 {due}  ")
    parts.append(f"{name}{priority_suffix}")
    return "".join(parts)


def append_todo(name: str, priority: str | None, due: str | None, description: str | None, target_date: str):
    """Obsidian Daily Note의 ## Todos 섹션에 todo 항목을 추가한다."""
    daily_file = DAILY_DIR / f"{target_date}.md"

    if not daily_file.exists():
        result = {
            "appended": False,
            "error": "daily_note_not_found",
            "file": str(daily_file),
        }
        print(json.dumps(result, ensure_ascii=False))
        return

    lines = daily_file.read_text(encoding="utf-8").splitlines(keepends=True)

    # ## Todos 섹션 찾기
    todos_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == "## Todos":
            todos_idx = i
            break

    if todos_idx is None:
        result = {
            "appended": False,
            "error": "todos_section_not_found",
            "file": str(daily_file),
        }
        print(json.dumps(result, ensure_ascii=False))
        return

    # 다음 ## 헤딩 찾기 (삽입 경계)
    boundary_idx = len(lines)
    for i in range(todos_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            boundary_idx = i
            break

    # 경계 바로 앞의 빈 줄 위에 삽입
    insert_idx = boundary_idx
    while insert_idx > todos_idx + 1 and lines[insert_idx - 1].strip() == "":
        insert_idx -= 1

    todo_line = build_todo_line(name, priority, due, target_date)
    new_lines = [todo_line + "\n"]
    if description:
        new_lines.append(f"\t- {description}\n")

    for line_to_insert in reversed(new_lines):
        lines.insert(insert_idx, line_to_insert)

    daily_file.write_text("".join(lines), encoding="utf-8")

    result = {
        "appended": True,
        "file": str(daily_file),
        "todo_line": todo_line,
    }
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Obsidian Daily Note Todo CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ap = subparsers.add_parser("append", help="Append a todo to daily note")
    ap.add_argument("--name", required=True, help="Task name")
    ap.add_argument("--priority", default=None, help="P1 - Must Have | P2 - Nice to Have")
    ap.add_argument("--due", default=None, help="Due date (YYYY-MM-DD)")
    ap.add_argument("--description", default=None, help="Optional description")
    ap.add_argument("--date", default=None, help="Target date (default: today)")

    sp = subparsers.add_parser("sync-progress", help="Sync progress to daily note todos")
    sp.add_argument("--handoff", default=None, help="Path to handoff JSON file")
    sp.add_argument("--completed", default=None, help="Comma-separated completed items")
    sp.add_argument("--in-progress", default=None, help="Comma-separated in-progress items")
    sp.add_argument("--next", default=None, help="Comma-separated next items")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes")
    group.add_argument("--apply", action="store_true", help="Apply changes")
    sp.add_argument("--date", default=None, help="Target date (default: today)")

    ap2 = subparsers.add_parser("auto-progress", help="Auto-detect progress from claude-mem session summaries")
    ap2.add_argument("--date", default=None, help="Target date (default: today)")
    ap2.add_argument("--threshold", type=float, default=0.5, help="Fuzzy match threshold 0.0~1.0 (default: 0.5)")
    group2 = ap2.add_mutually_exclusive_group(required=True)
    group2.add_argument("--dry-run", action="store_true", help="Preview recommendations without applying")
    group2.add_argument("--apply", action="store_true", help="Apply mark_done recommendations to daily note")

    args = parser.parse_args()

    if args.command == "append":
        target_date = args.date or date.today().isoformat()
        append_todo(args.name, args.priority, args.due, args.description, target_date)

    elif args.command == "sync-progress":
        target_date = args.date or date.today().isoformat()

        if args.handoff:
            data = load_handoff(args.handoff)
            if "error" in data:
                print(json.dumps(data, ensure_ascii=False))
                sys.exit(1)
            completed = data["completed"]
            in_progress = data["in_progress"]
            next_items = data["next"]
        else:
            completed = [s.strip() for s in args.completed.split(",")] if args.completed else []
            in_prog = getattr(args, "in_progress", None)
            in_progress = [s.strip() for s in in_prog.split(",")] if in_prog else []
            next_items = [s.strip() for s in args.next.split(",")] if args.next else []

        sync_progress(target_date, completed, in_progress, next_items, dry_run=args.dry_run)

    elif args.command == "auto-progress":
        target_date = args.date or date.today().isoformat()
        auto_progress(target_date, dry_run=args.dry_run, threshold=args.threshold)


if __name__ == "__main__":
    main()
