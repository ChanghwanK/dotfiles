#!/usr/bin/env python3
"""PreToolUse(Bash) 훅: AWS CLI로 리소스를 삭제하는 명령을 막는다.

Bash를 settings.json allow로 전부 허용했으므로(플랜 모드 포함), AWS 리소스 삭제만
이 훅이 마지막으로 막는다. 삭제는 되돌릴 수 없기 때문에 사용자가 직접 실행한다.

차단 대상 (aws가 명령 위치에 있을 때):
- `aws <service> delete-*` / `terminate-*`  (예: ec2 terminate-instances, rds delete-db-instance)
- `aws s3 rm`, `aws s3 rb`
- `aws s3 sync ... --delete`  (대상 쪽 객체를 지운다)

명령 문자열 전체를 grep하면 커밋 메시지·heredoc·echo 인자 속 단어까지 막는다
(2026-09-29 kubectl 가드에서 dotfiles 커밋이 막힌 사례). 그래서 셸 명령을 토큰으로
나눠 aws가 명령 위치(첫 단어)에 있을 때만 서비스·오퍼레이션을 본다.

알려진 미탐지: 셸 alias, 스크립트 파일 안의 aws, ssh 원격 명령, terraform/eksctl 같은
다른 도구를 통한 삭제, boto3 등 SDK 호출.
파싱에 실패하면 정규식으로 판정한다 (놓치는 쪽보다 막는 쪽으로 기운다).

stdin: 훅 JSON. 차단이면 exit 2 + stderr 메시지, 아니면 exit 0.
"""
import json
import os
import re
import shlex
import sys

DELETE_OPERATION_PREFIXES = ("delete-", "terminate-")
S3_DELETE_COMMANDS = {"rm", "rb"}
S3_SYNC_DELETE_FLAG = "--delete"
BLOCK_MESSAGE = (
    "BLOCKED: AWS resource deletion (delete-*/terminate-*/s3 rm/s3 rb/s3 sync --delete) "
    "is not allowed from Claude. Show the command to the user and let them run it.\n"
)
FALLBACK_PATTERN = re.compile(
    r"\baws\b[^\n;|&]*?\s(delete-[a-z0-9-]+|terminate-[a-z0-9-]+|s3\s+(rm|rb)\b|s3\s+sync\b[^\n;|&]*\s--delete\b)"
)

COMMAND_SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "{", "}"}
# 뒤따르는 단어를 실제 명령으로 실행하는 래퍼. 래퍼 자신의 플래그는 건너뛴다.
COMMAND_WRAPPERS = {"sudo", "env", "time", "command", "exec", "nohup", "xargs", "watch", "timeout", "nice", "aws-vault"}
SHELLS_WITH_C_FLAG = {"bash", "sh", "zsh"}
# aws 전역 플래그 중 값을 다음 토큰으로 받는 것. 서비스·오퍼레이션 위치를 찾을 때 값까지 건너뛴다.
AWS_FLAGS_WITH_VALUE = {
    "--profile", "--region", "--output", "--endpoint-url", "--query", "--ca-bundle",
    "--cli-read-timeout", "--cli-connect-timeout", "--color", "--cli-binary-format",
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
            if wrapper == "aws-vault":
                # aws-vault exec <profile> [flags] -- <command>
                if "--" in words[index:]:
                    index = words.index("--", index) + 1
                    continue
                index += 2  # exec <profile>
            while index < len(words) and (words[index].startswith("-") or ENV_ASSIGNMENT.match(words[index])):
                index += 1
            if wrapper == "timeout" and index < len(words):
                index += 1  # 시간 인자
        else:
            break
    return words[index:]


def aws_positional_args(args: list[str]) -> list[str]:
    """전역 플래그와 그 값을 빼고 서비스·오퍼레이션 같은 위치 인자만 남긴다."""
    positional = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in AWS_FLAGS_WITH_VALUE:
            index += 2
        elif arg.startswith("-"):
            index += 1
        else:
            positional.append(arg)
            index += 1
    return positional


def is_aws_delete(args: list[str]) -> bool:
    positional = aws_positional_args(args)
    if len(positional) < 2:
        return False
    service, operation = positional[0], positional[1]
    if operation.startswith(DELETE_OPERATION_PREFIXES):
        return True
    if service == "s3" and operation in S3_DELETE_COMMANDS:
        return True
    return service == "s3" and operation == "sync" and S3_SYNC_DELETE_FLAG in args


def is_blocked(command: str) -> bool:
    # heredoc 본문을 먼저 빼야 본문 속 `$(...)`를 명령 치환으로 오인하지 않는다.
    command = strip_heredoc_bodies(command)
    for match in COMMAND_SUBSTITUTION.finditer(command):
        if is_blocked(match.group(1) or match.group(2) or ""):
            return True
    for words in split_simple_commands(command):
        words = strip_wrappers(words)
        if not words:
            continue
        program = os.path.basename(words[0])
        if program in SHELLS_WITH_C_FLAG and "-c" in words[1:-1]:
            if is_blocked(words[words.index("-c", 1) + 1]):
                return True
        elif program == "eval" and is_blocked(" ".join(words[1:])):
            return True
        elif program == "aws" and is_aws_delete(words[1:]):
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
        blocked = bool(FALLBACK_PATTERN.search(strip_heredoc_bodies(command)))
    if blocked:
        sys.stderr.write(BLOCK_MESSAGE)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
