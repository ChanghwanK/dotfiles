#!/usr/bin/env python3
"""질문형 사용자 메시지에 대한 응답을 두 지표로 잰다.

1. 덧붙임 섹션 수: 요청하지 않은 이해 점검, 2줄 이상 제안, 위험 3종
2. 되묻기 비율: 응답 직후 사용자가 "핵심이 뭐야", "왜 자꾸 X를" 처럼 질문을 다시 겨누는 비율

전역 지침 재설계(2026-10-22, 플랜 starry-frolicking-wirth)의 "응답 기본값" 결과 검증용.
덧붙임 수는 기준선이 이미 낮아(10개 중 1) 반증력이 약하므로, 판정은 되묻기 비율로 한다.
휴리스틱이다: 질문·되묻기·덧붙임 판별 모두 문자열 패턴이라, 판정 전에 되묻기 표본을 눈으로 확인한다.

사용 예:
  measure_response_addons.py --after 2026-10-08 --before 2026-10-22 --n 0   # 기준선 (n=0 이면 전부)
  measure_response_addons.py --after 2026-10-22 --n 0                       # 재설계 이후
"""
import argparse
import json
import pathlib
import re

TRANSCRIPTS = pathlib.Path.home() / ".claude/projects/-Users-changhwan-workspace-riiid-kubernetes"

QUESTION = re.compile(r"\?|？|왜|뭐|무엇|어떤|어떻게|인가|인지|일까|는가")
# 응답이 질문을 비껴갔을 때 사용자가 다시 겨누는 표현
REASK = re.compile(r"핵심 답|내 질문|물어본 건|묻는 건|그게 아니라|왜 자꾸|질문에 답|말고|요점")
# 덧붙임 섹션: 사용자가 요청하지 않았는데 응답 끝에 붙는 블록
ADDONS = {
    "understanding_check": re.compile(r"이해 점검"),
    "suggestion_line": re.compile(r"(?m)^💡"),
    "risk_triad": re.compile(r"Blast radius|실패 시나리오"),
}


def user_text(entry):
    """사람이 입력한 텍스트만 꺼낸다. 도구 결과와 시스템 주입 메시지는 None."""
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(c.get("type") == "tool_result" for c in content if isinstance(c, dict)):
            return None
        text = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    else:
        return None
    text = text.strip()
    if not text or text.startswith("<") or text.startswith("/"):
        return None
    return text


def assistant_texts(entry):
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]


def samples(after, before):
    for path in sorted(TRANSCRIPTS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        entries = []
        for line in path.read_text(errors="ignore").splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        pending = None  # (timestamp, question, [assistant texts])
        for e in entries:
            if e.get("type") == "user":
                text = user_text(e)
                if text is None:
                    continue
                if pending and pending[2]:
                    # 바로 다음 사람 메시지가 되묻기인지 함께 넘긴다
                    yield pending[0], pending[1], pending[2][-1], bool(REASK.search(text))
                ts = e.get("timestamp", "")[:10]
                is_question = len(text) <= 300 and QUESTION.search(text)
                in_window = (not after or ts >= after) and (not before or ts < before)
                pending = (ts, text, []) if is_question and in_window else None
            elif e.get("type") == "assistant" and pending is not None:
                pending[2].extend(t for t in assistant_texts(e) if t.strip())
        if pending and pending[2]:
            yield pending[0], pending[1], pending[2][-1], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after")
    ap.add_argument("--before")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    total = n = reasks = 0
    for ts, q, answer, reasked in samples(args.after, args.before):
        if args.n and n >= args.n:
            break
        n += 1
        hits = {k: len(p.findall(answer)) for k, p in ADDONS.items()}
        # 제안 줄은 1줄까지 허용하므로 2줄 이상일 때만 덧붙임 1개로 센다
        count = int(hits["understanding_check"] > 0) + int(hits["suggestion_line"] >= 2) + int(hits["risk_triad"] > 0)
        total += count
        reasks += reasked
        if count or reasked:
            print(f"{ts} addons={count} reasked={reasked} | Q: {q[:60]!r}")
    rate = reasks / n if n else 0
    print(f"questions={n} addon_sections={total} reasked={reasks} reask_rate={rate:.1%}")


if __name__ == "__main__":
    main()
