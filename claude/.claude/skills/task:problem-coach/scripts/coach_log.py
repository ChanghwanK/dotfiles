#!/usr/bin/env python3
"""문제 정의 코치 기록을 append-only 이벤트로 남기고, 저장 순서와 형식을 강제한다.

이 스크립트가 강제하는 것은 순서·횟수·형식뿐이다. 판정 이유에 답이 섞이는 의미적 누출은 막지 못하므로
그 확인은 SKILL.md의 전달 전 점검이 맡는다.
- 초안과 자기평가는 start에서 함께 저장되고, 고치는 명령이 없다(append-only)
- 질문은 고정 질문 목록의 ID로만 기록되고, 사용자에게는 이 파일의 고정 문구만 나간다
- 연습(train)은 초안 판정 → 질문 1개 → 고쳐 쓰기 1회 → 재판정으로 끝난다. 두 번째 고쳐 쓰기는 거부한다
- 평가(eval)는 질문과 고쳐 쓰기가 없다. 실력 변화는 처음 쓰는 사례의 평가 기록으로만 본다

사용:
  coach_log.py questions
  coach_log.py start --mode train|eval --case "..." --self-assessment "..." [--new-case] [--task-url URL] < draft.txt
  coach_log.py coach-input --id ID --stage draft|revision
  coach_log.py verdict --id ID --stage draft|revision < verdict.json
  coach_log.py revise --id ID < revision.txt
  coach_log.py show --id ID
  coach_log.py report
"""
import argparse
import fcntl
import hashlib
import json
import os
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 환경 변수는 테스트에서 실제 기록을 건드리지 않기 위한 것이다
LOG_PATH = os.environ.get("PROBLEM_COACH_LOG_PATH") or os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/"
    "03. Resources/Problem Coach Log.jsonl"
)
LOCK_PATH = LOG_PATH + ".lock"
# 판정 기준이 바뀌면 같은 실력도 다른 판정을 받는다. 기준 파일 내용으로 버전을 자동 계산해 판정마다 남긴다.
RUBRIC_FILES = ("agents/agent-coach.md", "references/coach-examples.md")

MODE_TRAIN = "train"
MODE_EVAL = "eval"
STAGE_DRAFT = "draft"
STAGE_REVISION = "revision"

# 질문은 구조 후보를 담지 않는 사실 확인형만 둔다. 코치는 ID만 고르고 문구를 만들지 않는다.
QUESTION_BANK = {
    "Q1": "정리하거나 고친 뒤에도 같은 상태가 다시 생긴 적이 있습니까? 있다면 언제, 몇 번입니까?",
    "Q2": "이 상태를 만드는 대상(규칙, 설정, 리소스, 요청 등)은 어떤 경로로 새로 생깁니까?",
    "Q3": "더 이상 필요 없어진 대상은 어떤 경로로 사라집니까?",
    "Q4": "이 상태가 쌓이거나 커지는 동안 누가, 무엇으로 알 수 있었습니까?",
    "Q5": "이 상태를 막으려면 누군가가 기억하거나 주의해야 합니까?",
    "Q6": "관측 칸의 내용 중 수치나 기록으로 직접 확인한 것은 무엇이고, 출처는 어디입니까?",
    "Q7": "지금 설명이 틀렸다면 가장 유력한 다른 설명은 무엇이고, 둘을 가르는 관측은 무엇입니까?",
    "Q8": "이 문제는 누구에게 어떤 영향을 주고, 그 크기는 어떻게 압니까?",
}

RUBRIC_KEYS = ("observation", "connection", "scope", "impact")
RUBRIC_LABELS = {"observation": "관측", "connection": "연결", "scope": "범위", "impact": "영향"}
LEVELS = ("충족", "부분", "미충족", "판정 불가")
CONCLUSION_TYPES = ("구조", "구조 확대 불필요", "원인 미확인", "상태")
# 판정 이유가 길어지면 구조 후보나 고쳐 쓴 문장이 섞이기 쉽다. 길이 상한으로 흘릴 공간을 줄인다.
MAX_REASON_CHARS = 160
EVAL_INTERVAL_DAYS = 14
MIN_EVALS_FOR_TREND = 5


def fail(message):
    print(json.dumps({"success": False, "error": message}, ensure_ascii=False, indent=2))
    sys.exit(1)


def ok(**payload):
    print(json.dumps({"success": True, **payload}, ensure_ascii=False, indent=2))


def read_stdin_text(what):
    text = sys.stdin.read().strip()
    if not text:
        fail(f"{what}이 비어 있습니다. 표준 입력으로 넘겨 주세요")
    return text


def rubric_version():
    digest = hashlib.sha256()
    for rel in RUBRIC_FILES:
        with open(os.path.join(SKILL_DIR, rel), "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:8]


@contextmanager
def log_lock():
    """읽기부터 추가까지를 한 덩어리로 묶어, 동시 실행이 횟수 제한과 불변성을 깨지 못하게 한다."""
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def load_events():
    """손상된 줄을 조용히 버리지 않는다. 줄 번호와 함께 멈춰서 사용자가 확인하게 한다."""
    if not os.path.exists(LOG_PATH):
        return []
    events = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as e:
                fail(f"기록 파일 {LOG_PATH}의 {lineno}번째 줄이 손상됐습니다({e}). 그 줄을 확인하고 고치거나 별도 파일로 옮긴 뒤 다시 실행해 주세요")
    return events


def append_event(event):
    event["at"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_records(events):
    """이벤트를 사례 단위 상태로 접는다. 같은 종류의 이벤트는 처음 것만 유효하다."""
    records = {}
    for e in events:
        rid = e.get("id")
        if e.get("type") == "start":
            records.setdefault(rid, {**e, "verdicts": {}, "verdict_at": {}, "question_id": None, "revision": None})
            continue
        record = records.get(rid)
        if record is None:
            continue
        if e.get("type") == "verdict" and e.get("stage") not in record["verdicts"]:
            record["verdicts"][e["stage"]] = e["verdict"]
            record["verdict_at"][e["stage"]] = e["at"]
            if e["stage"] == STAGE_DRAFT:
                record["question_id"] = e["verdict"].get("question_id")
        elif e.get("type") == "revision" and record["revision"] is None:
            record["revision"] = e["text"]
    return records


def get_record(rid):
    record = build_records(load_events()).get(rid)
    if record is None:
        fail(f"사례 {rid}를 찾을 수 없습니다")
    return record


def validate_verdict(verdict, expects_question):
    if not isinstance(verdict, dict):
        fail("판정은 JSON 객체여야 합니다")
    rubric = verdict.get("rubric")
    if not isinstance(rubric, dict) or set(rubric) != set(RUBRIC_KEYS):
        fail(f"rubric은 {list(RUBRIC_KEYS)} 네 항목을 정확히 가져야 합니다")
    for key in RUBRIC_KEYS:
        item = rubric[key]
        if not isinstance(item, dict):
            fail(f"{key}는 level과 reason을 가진 객체여야 합니다")
        if item.get("level") not in LEVELS:
            fail(f"{key}.level은 {list(LEVELS)} 중 하나여야 합니다")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            fail(f"{key}.reason은 비어 있지 않은 문자열이어야 합니다")
        if len(reason.strip()) > MAX_REASON_CHARS:
            fail(f"{key}.reason이 {MAX_REASON_CHARS}자를 넘습니다. 사용자 문장에 있는 것과 없는 것만 쓰도록 줄여 주세요")
    if verdict.get("conclusion_type") not in CONCLUSION_TYPES:
        fail(f"conclusion_type은 {list(CONCLUSION_TYPES)} 중 하나여야 합니다")
    qid = verdict.get("question_id")
    if expects_question and qid not in QUESTION_BANK:
        fail(f"연습 초안 판정에는 question_id가 {list(QUESTION_BANK)} 중 하나여야 합니다")
    if not expects_question and qid is not None:
        fail("이 단계에서는 question_id가 null이어야 합니다(평가 모드 또는 재판정)")


def cmd_questions(_args):
    ok(questions=QUESTION_BANK)


def cmd_start(args):
    draft = read_stdin_text("초안")
    if not args.self_assessment.strip():
        fail("자기평가가 비어 있습니다. 코치 판정 전에 본인 판정을 먼저 받아야 합니다")
    rid = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    with log_lock():
        if rid in build_records(load_events()):
            fail("ID가 겹쳤습니다. 다시 실행해 주세요")
        append_event({
            "id": rid, "type": "start", "mode": args.mode, "case": args.case, "new_case": args.new_case,
            "draft": draft, "self_assessment": args.self_assessment.strip(), "task_url": args.task_url,
        })
    ok(id=rid, mode=args.mode, new_case=args.new_case, log_path=LOG_PATH)


def cmd_coach_input(args):
    """코치에게 줄 입력. 자기평가는 빼서 코치가 사용자 판정에 끌려가지 않게 한다."""
    record = get_record(args.id)
    payload = {"case": record["case"], "mode": record["mode"], "stage": args.stage, "draft": record["draft"]}
    if args.stage == STAGE_REVISION:
        if record["revision"] is None:
            fail("고쳐 쓴 문장이 아직 없습니다")
        payload["question"] = QUESTION_BANK.get(record["question_id"])
        payload["revision"] = record["revision"]
    ok(mode=record["mode"], coach_input=payload)


def cmd_verdict(args):
    try:
        verdict = json.loads(read_stdin_text("판정 JSON"))
    except json.JSONDecodeError as e:
        fail(f"판정 JSON을 해석할 수 없습니다: {e}")
    with log_lock():
        record = get_record(args.id)
        if args.stage in record["verdicts"]:
            fail(f"{args.stage} 판정은 이미 기록됐습니다. 판정은 고칠 수 없습니다")
        if args.stage == STAGE_REVISION:
            if record["mode"] != MODE_TRAIN:
                fail("평가 모드에는 재판정이 없습니다")
            if record["revision"] is None:
                fail("고쳐 쓴 문장이 없어 재판정할 수 없습니다")
        expects_question = record["mode"] == MODE_TRAIN and args.stage == STAGE_DRAFT
        validate_verdict(verdict, expects_question)
        version = rubric_version()
        append_event({"id": args.id, "type": "verdict", "stage": args.stage, "verdict": verdict,
                      "rubric_version": version})
    qid = verdict.get("question_id")
    ok(id=args.id, mode=record["mode"], stage=args.stage, verdict=verdict, rubric_version=version,
       question={"id": qid, "text": QUESTION_BANK[qid]} if qid else None,
       self_assessment=record["self_assessment"])


def cmd_revise(args):
    text = read_stdin_text("고쳐 쓴 문장")
    with log_lock():
        record = get_record(args.id)
        if record["mode"] != MODE_TRAIN:
            fail("평가 모드에는 고쳐 쓰기가 없습니다")
        if STAGE_DRAFT not in record["verdicts"]:
            fail("초안 판정 전에는 고쳐 쓸 수 없습니다")
        if record["revision"] is not None:
            fail("고쳐 쓰기는 사례당 한 번입니다. 더 하려면 새 사례로 시작해 주세요")
        append_event({"id": args.id, "type": "revision", "text": text})
    ok(id=args.id)


def cmd_show(args):
    ok(record=get_record(args.id))


def summarize_levels(verdict):
    return {RUBRIC_LABELS[k]: verdict["rubric"][k]["level"] for k in RUBRIC_KEYS}


def cmd_report(_args):
    events = load_events()
    versions = {(e["id"], e["stage"]): e.get("rubric_version") for e in events if e.get("type") == "verdict"}
    records = sorted(build_records(events).values(), key=lambda r: r["id"])
    train = [r for r in records if r["mode"] == MODE_TRAIN]
    evals = [r for r in records if r["mode"] == MODE_EVAL and STAGE_DRAFT in r["verdicts"]]
    # 실력 변화 비교에는 처음 쓰는 사례만 쓴다. 같은 사례를 다시 내면 배운 답을 낸 것과 구별할 수 없다.
    transfer = [r for r in evals if r.get("new_case")]
    undecidable = {RUBRIC_LABELS[k]: sum(1 for r in transfer if r["verdicts"][STAGE_DRAFT]["rubric"][k]["level"] == "판정 불가")
                   for k in RUBRIC_KEYS}
    current_version = rubric_version()
    last_eval_at = max((r["verdict_at"][STAGE_DRAFT] for r in evals), default=None)
    days_since_eval = (datetime.now() - datetime.fromisoformat(last_eval_at)).days if last_eval_at else None
    ok(
        counts={
            "train_started": len(train),
            "train_completed": sum(1 for r in train if STAGE_REVISION in r["verdicts"]),
            "eval_total": len(evals),
            "eval_new_case": len(transfer),
            "eval_new_case_current_rubric": sum(1 for r in transfer if versions.get((r["id"], STAGE_DRAFT)) == current_version),
            "eval_undecidable_by_criterion": undecidable,
        },
        current_rubric_version=current_version,
        trend_judgeable=len(transfer) >= MIN_EVALS_FOR_TREND,
        eval_timeline=[{"id": r["id"], "case": r["case"], "new_case": r.get("new_case", False),
                        "rubric_version": versions.get((r["id"], STAGE_DRAFT)),
                        "conclusion_type": r["verdicts"][STAGE_DRAFT]["conclusion_type"],
                        "levels": summarize_levels(r["verdicts"][STAGE_DRAFT]), "task_url": r.get("task_url")}
                       for r in evals],
        days_since_last_eval=days_since_eval,
        eval_due=days_since_eval is None or days_since_eval >= EVAL_INTERVAL_DAYS,
        log_path=LOG_PATH,
    )


def main():
    parser = argparse.ArgumentParser(description="문제 정의 코치 기록")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("questions")

    p = sub.add_parser("start")
    p.add_argument("--mode", choices=(MODE_TRAIN, MODE_EVAL), required=True)
    p.add_argument("--case", required=True, help="사례 한 줄 이름")
    p.add_argument("--self-assessment", required=True, help="코치 판정 전 사용자 본인 판정")
    p.add_argument("--new-case", action="store_true", help="이 사례를 처음 쓴다(이전에 연습하거나 코치를 받은 적 없음)")
    p.add_argument("--task-url", default=None, help="장기 결과를 추적할 기존 Task 링크")

    for name in ("coach-input", "verdict"):
        p = sub.add_parser(name)
        p.add_argument("--id", required=True)
        p.add_argument("--stage", choices=(STAGE_DRAFT, STAGE_REVISION), required=True)

    for name in ("revise", "show"):
        sub.add_parser(name).add_argument("--id", required=True)

    sub.add_parser("report")

    args = parser.parse_args()
    {
        "questions": cmd_questions, "start": cmd_start, "coach-input": cmd_coach_input,
        "verdict": cmd_verdict, "revise": cmd_revise, "show": cmd_show, "report": cmd_report,
    }[args.command](args)


if __name__ == "__main__":
    main()
