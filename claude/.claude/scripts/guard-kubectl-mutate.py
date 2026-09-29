#!/usr/bin/env python3
"""PreToolUse(Bash) 훅: kubectl edit/delete 직접 실행을 막는다 (GitOps 보호).

명령 문자열 전체를 grep하면 커밋 메시지·heredoc·echo 인자 속 단어까지 막는다
(2026-09-29 dotfiles 커밋이 막힌 사례). 그래서 셸 명령을 토큰으로 나눠
kubectl이 명령 위치(첫 단어)에 있고 서브커맨드가 edit/delete일 때만 막는다.

알려진 미탐지: 셸 alias(`k delete`), 스크립트 파일 안의 kubectl, ssh 원격 명령.
파싱에 실패하면 예전 grep 규칙으로 판정한다 (놓치는 쪽보다 막는 쪽으로 기운다).

stdin: 훅 JSON. 차단이면 exit 2 + stderr 메시지, 아니면 exit 0.
"""
import json
import os
import re
import shlex
import sys

BLOCKED_SUBCOMMANDS = {"edit", "delete"}
BLOCK_MESSAGE = (
    "BLOCKED: kubectl edit/delete bypasses GitOps and will be reverted by ArgoCD. "
    "Modify YAML files in Git instead.\n"
)
LEGACY_PATTERN = re.compile(r"kubectl\s+(edit|delete)")

COMMAND_SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}"}
# 뒤따르는 단어를 실제 명령으로 실행하는 래퍼. 래퍼 자신의 플래그는 건너뛴다.
COMMAND_WRAPPERS = {"sudo", "env", "time", "command", "exec", "nohup", "xargs", "watch", "timeout", "nice"}
SHELLS_WITH_C_FLAG = {"bash", "sh", "zsh"}
# kubectl 전역 플래그 중 값을 다음 토큰으로 받는 것. 서브커맨드 위치를 찾을 때 값까지 건너뛴다.
KUBECTL_FLAGS_WITH_VALUE = {
    "-n", "--namespace", "--context", "--cluster", "--kubeconfig", "--user",
    "-s", "--server", "--token", "--as", "--as-group", "--request-timeout", "-v", "--v",
}
HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
COMMAND_SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def strip_heredoc_bodies(command: str) -> str:
    """heredoc 본문은 명령이 아니라 데이터이므로 판정 대상에서 뺀다."""
    lines = command.split("\n")
    kept = []
    pending_delimiters = []
    for line in lines:
        if pending_delimiters:
            if line.strip() == pending_delimiters[0]:
                pending_delimiters.pop(0)
            continue
        kept.append(line)
        pending_delimiters.extend(m.group(2) for m in HEREDOC_START.finditer(line))
    return "\n".join(kept)


def split_simple_commands(command: str) -> list[list[str]]:
    # 줄바꿈도 명령 구분자다. 따옴표 안의 줄바꿈은 ';'로 바뀌어도 같은 토큰 안에 남는다.
    joined = command.replace("\\\n", " ").replace("\n", " ; ")
    lexer = shlex.shlex(joined, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    simple_commands: list[list[str]] = [[]]
    for token in lexer:
        if token in COMMAND_SEPARATORS:
            simple_commands.append([])
        else:
            simple_commands[-1].append(token)
    return [words for words in simple_commands if words]


def strip_wrappers(words: list[str]) -> list[str]:
    index = 0
    while index < len(words):
        word = words[index]
        if ENV_ASSIGNMENT.match(word):
            index += 1
        elif os.path.basename(word) in COMMAND_WRAPPERS:
            wrapper = os.path.basename(word)
            index += 1
            while index < len(words) and (words[index].startswith("-") or ENV_ASSIGNMENT.match(words[index])):
                index += 1
            if wrapper == "timeout" and index < len(words):
                index += 1  # 시간 인자
        else:
            break
    return words[index:]


def kubectl_subcommand(args: list[str]) -> str | None:
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in KUBECTL_FLAGS_WITH_VALUE:
            index += 2
        elif arg.startswith("-"):
            index += 1
        else:
            return arg
    return None


def is_blocked(command: str) -> bool:
    for match in COMMAND_SUBSTITUTION.finditer(command):
        if is_blocked(match.group(1) or match.group(2) or ""):
            return True
    for words in split_simple_commands(strip_heredoc_bodies(command)):
        words = strip_wrappers(words)
        if not words:
            continue
        program = os.path.basename(words[0])
        if program in SHELLS_WITH_C_FLAG and "-c" in words[1:-1]:
            if is_blocked(words[words.index("-c", 1) + 1]):
                return True
        elif program == "eval" and is_blocked(" ".join(words[1:])):
            return True
        elif program == "kubectl" and kubectl_subcommand(words[1:]) in BLOCKED_SUBCOMMANDS:
            return True
    return False


def main() -> int:
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, AttributeError):
        return 0
    try:
        blocked = is_blocked(command)
    except ValueError:  # 닫히지 않은 따옴표 등 shlex 파싱 실패
        blocked = bool(LEGACY_PATTERN.search(command))
    if blocked:
        sys.stderr.write(BLOCK_MESSAGE)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
