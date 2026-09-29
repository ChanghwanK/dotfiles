#!/usr/bin/env python3
"""guard-kubectl-mutate.py 회귀 테스트.

명령 위치의 kubectl edit/delete는 막고, 텍스트 속 단어(커밋 메시지·heredoc·echo)는 통과시키는지 보호한다.
실행: python3 test_guard_kubectl_mutate.py   (성공 시 exit 0)
"""
import importlib.util
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "guard-kubectl-mutate.py")
_SPEC = importlib.util.spec_from_file_location("guard", _SCRIPT)
m = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m)

MUST_BLOCK = [
    "kubectl delete pod x",
    "kubectl edit deploy/api",
    "kubectl --context k8s-prod -n santa delete pod x",
    "kubectl --context=k8s-dev delete pod x",
    "/usr/local/bin/kubectl delete pod x",
    "cd /tmp && kubectl delete pod x",
    "echo start; kubectl delete pod x",
    "echo start\nkubectl delete pod x",
    "kubectl get pods -o name | xargs kubectl delete",
    "KUBECONFIG=/tmp/k sudo kubectl delete pod x",
    "timeout 10 kubectl delete pod x",
    "bash -c 'kubectl delete pod x'",
    "eval kubectl delete pod x",
    "echo $(kubectl delete pod x)",
    "(kubectl edit cm foo)",
]

MUST_ALLOW = [
    "kubectl get pods -n santa",
    "kubectl -n delete get pods",  # 네임스페이스 이름이 delete
    "kubectl describe pod delete-me",
    "git commit -m '하드 가드레일에서 kubectl edit/delete 금지 줄을 뺀다'",
    "git commit -q -F - <<'EOF'\n- kubectl edit/delete 금지 줄을 뺀다\nkubectl delete pod x\nEOF\ngit log -1",
    "echo 'kubectl delete pod x'",
    "grep -n 'kubectl delete' README.md",
    'printf "%s" "kubectl edit deploy"',
    "",
]


def run_hook(command: str) -> int:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run([sys.executable, _SCRIPT], input=payload, text=True, capture_output=True).returncode


def main() -> int:
    failures = []
    for command in MUST_BLOCK:
        if not m.is_blocked(command):
            failures.append(f"차단돼야 하는데 통과: {command!r}")
    for command in MUST_ALLOW:
        if m.is_blocked(command):
            failures.append(f"통과돼야 하는데 차단: {command!r}")
    # 훅 경계: exit 2가 차단, exit 0이 통과다. 파싱 실패(닫히지 않은 따옴표)는 예전 grep 규칙으로 막는다.
    if run_hook("kubectl delete pod x") != 2:
        failures.append("훅 exit code: 차단 명령이 2가 아님")
    if run_hook("echo 'kubectl delete pod x'") != 0:
        failures.append("훅 exit code: 텍스트 속 단어가 0이 아님")
    if run_hook("echo 'unterminated && kubectl delete pod x") != 2:
        failures.append("훅 exit code: 파싱 실패 시 예전 규칙으로 막지 않음")
    for failure in failures:
        print("FAIL", failure)
    print(f"{len(MUST_BLOCK) + len(MUST_ALLOW) + 3 - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
