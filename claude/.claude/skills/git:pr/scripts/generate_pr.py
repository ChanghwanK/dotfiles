#!/usr/bin/env python3
"""
generate_pr.py — Analyze git diff/log and generate PR metadata for kubernetes GitOps repo.

Usage:
    python3 generate_pr.py analyze <diff_file> <log_file>

Output: JSON to stdout
"""

import json
import re
import sys

# Path patterns for src/{sphere}/{circle}/infra-k8s-{env}/...
ENV_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/(?P<env>infra-k8s-[^/]+)/'
)
COMMON_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/common/'
)
APPSET_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/applicationset(?:\.onpremise|\.test)?\.jsonnet$'
)

SENSITIVE_ENVS = {'infra-k8s-prod', 'infra-k8s-global', 'infra-k8s-idc'}
INFRA_SPHERES = {'infra', 'observability'}
MLOPS_SPHERES = {'ai-santa'}

CONVENTIONAL_COMMIT_RE = re.compile(r'^(?P<type>\w+)(?:\([^)]+\))?: (?P<desc>.+)')

ENV_CONTEXT_MAP = {
    'infra-k8s-dev': ('k8s-dev', 'dev'),
    'infra-k8s-stg': ('k8s-stg', 'stg'),
    'infra-k8s-prod': ('k8s-prod', 'prod'),
    'infra-k8s-global': ('k8s-global', 'global'),
    'infra-k8s-idc': ('k8s-idc', 'idc'),
    'infra-k8s-office': ('k8s-office', 'office'),
}


def parse_diff(diff_file: str) -> list:
    entries = []
    try:
        with open(diff_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    entries.append({'status': parts[0], 'path': parts[1]})
    except (OSError, IOError):
        pass
    return entries


def parse_log(log_file: str) -> list:
    commits = []
    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    commits.append({'hash': parts[0][:7], 'subject': parts[1]})
    except (OSError, IOError):
        pass
    return commits


def analyze_changes(entries: list) -> dict:
    """Map (sphere, circle) -> set of envs/tags."""
    circles = {}

    for entry in entries:
        path = entry['path']

        m = ENV_PATH_RE.match(path)
        if m:
            key = (m.group('sphere'), m.group('circle'))
            circles.setdefault(key, set()).add(m.group('env'))
            continue

        m = COMMON_PATH_RE.match(path)
        if m:
            key = (m.group('sphere'), m.group('circle'))
            circles.setdefault(key, set()).add('common')
            continue

        m = APPSET_PATH_RE.match(path)
        if m:
            key = (m.group('sphere'), m.group('circle'))
            circles.setdefault(key, set()).add('applicationset')

    return circles


def infer_commit_type(commits: list) -> str:
    if not commits:
        return 'chore'
    m = CONVENTIONAL_COMMIT_RE.match(commits[0]['subject'])
    return m.group('type') if m else 'feat'


def generate_title(circles: dict, commits: list) -> str:
    if not commits:
        return 'chore: update kubernetes manifests'

    # Single commit → use subject directly
    if len(commits) == 1:
        return commits[0]['subject']

    sphere_circle_list = sorted(circles.keys())

    if len(sphere_circle_list) == 0:
        return commits[0]['subject']

    if len(sphere_circle_list) == 1:
        sphere, circle = sphere_circle_list[0]
        commit_type = infer_commit_type(commits)
        m = CONVENTIONAL_COMMIT_RE.match(commits[0]['subject'])
        desc = m.group('desc') if m else commits[0]['subject']
        return f'{commit_type}({sphere}/{circle}): {desc}'

    spheres = sorted({s for s, _ in sphere_circle_list})
    commit_type = infer_commit_type(commits)

    if len(spheres) == 1:
        n = len(sphere_circle_list)
        return f'{commit_type}({spheres[0]}): update {n} circles'

    return f'{commit_type}: update {len(sphere_circle_list)} circles across {len(spheres)} spheres'


def generate_body(circles: dict, commits: list) -> str:
    all_envs = set()
    for envs in circles.values():
        all_envs.update(envs)

    real_envs = sorted(
        e for e in all_envs if e.startswith('infra-k8s-')
    )
    env_display = ', '.join(
        ENV_CONTEXT_MAP.get(e, (e, e))[1] for e in real_envs
    ) or '-'

    sphere_list = sorted({s for s, _ in circles.keys()})
    lines = ['## Summary', '']

    # 두괄식 topline 요약: 짧은 선언문 3개(문제/해결/영향), 절 연결 없이 문장 단위로 끊는다.
    # diff/title만으로 부족하면 git:pr 스킬(LLM)이 대화 맥락으로 채운다 (SKILL.md Step 4).
    lines.append('<!-- FILL_ME: 문제 상황을 짧은 한 문장으로 (기술문서체, 쉼표로 이어붙이지 않음) -->')
    lines.append('')
    lines.append('<!-- FILL_ME: 해결 방법을 짧은 한 문장으로 -->')
    lines.append('')
    lines.append('<!-- FILL_ME: 영향 범위/주의사항을 짧은 한 문장으로 -->')
    lines.append('')

    lines.append('### 환경 요약')
    lines.append('')
    lines.append('| 항목 | 내용 |')
    lines.append('|------|------|')
    lines.append(f'| 변경 Sphere | {", ".join(sphere_list)} |')
    lines.append(f'| 변경 Circle 수 | {len(circles)} |')
    lines.append(f'| 영향 환경 | {env_display} |')
    lines.append(f'| 커밋 수 | {len(commits)} |')
    lines.append('')

    # 의도/배경은 diff만으로 유추 불가 — git:pr 스킬(LLM)이 대화 맥락에서 채운다.
    # placeholder가 남아 있으면 SKILL.md Step 4/5에서 PR 생성을 막는다.
    lines.append('## 변경 의도 / 배경 (Why)')
    lines.append('')
    lines.append('<!-- FILL_ME: 이 변경을 유발한 문제·요구·배경을 대화 맥락에서 서술 (무엇을 바꿨는지가 아니라 왜 바꾸는지) -->')
    lines.append('')

    lines.append('## 변경 내용')
    lines.append('')
    for (sphere, circle), envs in sorted(circles.items()):
        lines.append(f'### `{sphere}/{circle}`')
        for env in sorted(envs):
            display = ENV_CONTEXT_MAP.get(env, (env, env))[1] if env.startswith('infra-k8s-') else env
            lines.append(f'- {display}')
        lines.append('')

    if commits:
        lines.append('## 커밋 이력')
        lines.append('')
        for c in commits:
            lines.append(f'- `{c["hash"]}` {c["subject"]}')
        lines.append('')

    lines.append('## 테스트 플랜')
    lines.append('')

    env_order = [
        ('infra-k8s-dev', 'Dev', 'k8s-dev'),
        ('infra-k8s-stg', 'Staging', 'k8s-stg'),
        ('infra-k8s-prod', 'Production', 'k8s-prod'),
        ('infra-k8s-global', 'Global', 'k8s-global'),
        ('infra-k8s-idc', 'IDC', 'k8s-idc'),
    ]

    for env_key, label, ctx in env_order:
        affected = [(s, c) for (s, c), envs in circles.items() if env_key in envs]
        if not affected:
            continue
        lines.append(f'**{label}**')
        for s, c in sorted(affected):
            ns = f'{s}-{c}'
            if env_key == 'infra-k8s-prod':
                lines.append(f'- [ ] ArgoCD sync 확인: `{s}.{c}.{env_key}`')
            lines.append(f'- [ ] `kubectl get pods -n {ns} --context {ctx}`')
        lines.append('')

    lines.append('🤖 Generated with [Claude Code](https://claude.com/claude-code) (`git:pr` skill)')
    return '\n'.join(lines)


def check_sensitivity(circles: dict) -> dict:
    has_prod = any('infra-k8s-prod' in envs for envs in circles.values())
    has_global = any('infra-k8s-global' in envs for envs in circles.values())
    has_idc = any('infra-k8s-idc' in envs for envs in circles.values())
    has_infra = any(sphere in INFRA_SPHERES for sphere, _ in circles.keys())
    needs_mlops = any(sphere in MLOPS_SPHERES for sphere, _ in circles.keys())

    return {
        'has_prod': has_prod,
        'has_global': has_global,
        'has_idc': has_idc,
        'has_infra': has_infra,
        'needs_mlops_reviewer': needs_mlops,
        # 팀 컨벤션: PR은 기본 ready(non-draft)로 오픈한다 (merged PR 이력상
        # prod/global 변경 포함 여부와 무관하게 전부 non-draft). 사용자가
        # Step 4에서 명시적으로 요청할 때만 draft로 전환한다.
        'suggest_draft': False,
    }


def cmd_analyze(diff_file: str, log_file: str) -> None:
    entries = parse_diff(diff_file)
    commits = parse_log(log_file)
    circles = analyze_changes(entries)
    sensitivity = check_sensitivity(circles)

    result = {
        'suggested_title': generate_title(circles, commits),
        'suggested_body': generate_body(circles, commits),
        'affected_circles': [
            {'sphere': s, 'circle': c, 'envs': sorted(envs)}
            for (s, c), envs in sorted(circles.items())
        ],
        **sensitivity,
        'commit_count': len(commits),
        'has_changes': bool(circles),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: generate_pr.py analyze <diff_file> <log_file>', file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'analyze':
        if len(sys.argv) < 4:
            print('Usage: generate_pr.py analyze <diff_file> <log_file>', file=sys.stderr)
            sys.exit(1)
        cmd_analyze(sys.argv[2], sys.argv[3])
    else:
        print(f'Unknown command: {cmd}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
