#!/usr/bin/env python3
"""SessionStart 훅: 인프라 레포에서 시작한 세션에만 DevOps 작업 규칙을 주입한다.

전역 CLAUDE.md에는 DevOps 전용 규칙을 두지 않는다(docs/rules-map.md 층 경계).
대신 이 훅이 cwd를 보고 docs/devops-work.md와 docs/kubectl-contexts.md를 additionalContext로 넣는다.
"""
import json
import pathlib
import sys

HOME = pathlib.Path.home()
INFRA_REPOS = [HOME / "workspace/riiid" / name for name in ("kubernetes", "k8s-on-premise", "terraform", "kubernetes-charts")]
DOCS = [HOME / ".claude/docs/devops-work.md", HOME / ".claude/docs/kubectl-contexts.md"]


def in_infra_repo(cwd):
    path = pathlib.Path(cwd).resolve()
    return any(path == repo or repo in path.parents for repo in INFRA_REPOS)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    cwd = payload.get("cwd") or ""
    if not cwd or not in_infra_repo(cwd):
        return
    parts, missing = [], []
    for doc in DOCS:
        try:
            parts.append(doc.read_text())
        except OSError:
            missing.append(doc.name)
    # 주입 여부를 첫 줄에 남겨, 규칙이 조용히 빠지는 실패를 알아챌 수 있게 한다
    header = "[devops-work 주입] 인프라 레포 세션이라 DevOps 작업 규칙을 적용합니다."
    if missing:
        header += f" 읽지 못한 문서: {', '.join(missing)} (`make dotfiles`로 링크를 확인하세요)."
    context = header + "\n\n" + "\n\n".join(parts)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # 훅 실패가 세션 시작을 막지 않게 한다
        print(f"[inject-devops-rules] 오류: {exc}", file=sys.stderr)
