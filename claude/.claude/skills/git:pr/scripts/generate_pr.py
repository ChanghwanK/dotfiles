#!/usr/bin/env python3
"""
generate_pr.py: Analyze git diff/log and generate PR metadata for kubernetes GitOps repo.

Usage:
    python3 generate_pr.py analyze [--base origin/main] [--no-fetch]
    python3 generate_pr.py wiki-impact [--base origin/main]

git 호출은 이 스크립트가 직접 한다. SKILL.md 쪽에서 리다이렉트(> /tmp/...)나
명령 치환($(git diff ...))을 쓰지 않게 하려는 것이다: 그런 복합 명령은 worktree 격리
세션에서 거부되고, 고정 /tmp 경로는 동시에 도는 세션끼리 서로 덮어쓴다.

비교 기준은 원격 브랜치(origin/main)다. worktree는 origin/main에서 만들어지므로
로컬 main이 뒤처져 있으면 남의 커밋이 diff에 섞여 sphere/env 판정이 틀어진다.

Output: analyze는 JSON, wiki-impact는 verify-impact.py 출력(없으면 빈 출력)
"""

import argparse
import json
import os
import re
import subprocess
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

# Title env slot은 배포 파이프라인 순서로 고정한다: 리뷰어가 매번 같은 자리에서 prod를 찾게 하려는 것.
ENV_LABEL_ORDER = ['common', 'dev', 'stg', 'prod', 'global', 'idc', 'office']

# 이 개수를 넘으면 나열 대신 sphere로 축약한다 (title이 대상 나열에 잠식되는 것을 막는다).
MAX_LISTED_CIRCLES = 3
MAX_LISTED_SPHERES = 3

TITLE_SUBJECT_PLACEHOLDER = (
    '<!-- FILL_ME: 동작 + 대상 + (가능하면) 효과. '
    '커밋 subject 복사 금지, PR 전체 의도로 새로 쓴다 -->'
)


DEFAULT_BASE = 'origin/main'
WIKI_IMPACT_SCRIPT = os.path.join('devops-wiki', 'scripts', 'verify-impact.py')


class GitError(RuntimeError):
    pass


def run_git(*args: str) -> str:
    proc = subprocess.run(['git', *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError(f'git {" ".join(args)} failed: {proc.stderr.strip()}')
    return proc.stdout


def fetch_base(base: str) -> bool:
    """base가 'origin/main' 꼴이면 그 브랜치만 fetch한다. 실패해도 분석은 계속한다(오프라인 등)."""
    remote, _, branch = base.partition('/')
    if not branch:
        return False
    try:
        run_git('fetch', '--quiet', remote, branch)
        return True
    except GitError:
        return False


def parse_diff(diff_text: str) -> list:
    entries = []
    for line in diff_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t', 1)
        if len(parts) == 2:
            entries.append({'status': parts[0], 'path': parts[1]})
    return entries


def parse_log(log_text: str) -> list:
    commits = []
    for line in log_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(' ', 1)
        if len(parts) == 2:
            commits.append({'hash': parts[0][:7], 'subject': parts[1]})
    return commits


def read_branch_changes(base: str) -> tuple:
    # diff는 '...'(merge-base 기준: 이 브랜치가 바꾼 것만), log는 '..'(이 브랜치에만 있는 커밋).
    # log에 '...'를 쓰면 대칭차라서 base에 새로 들어온 남의 커밋까지 섞인다.
    diff_text = run_git('diff', f'{base}...HEAD', '--name-status')
    log_text = run_git('log', f'{base}..HEAD', '--format=%H %s')
    return parse_diff(diff_text), parse_log(log_text)


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


def strip_commit_prefix(subject: str) -> str:
    """Drop a Conventional Commits prefix so the subject can seed a PR title hint."""
    m = CONVENTIONAL_COMMIT_RE.match(subject)
    return m.group('desc') if m else subject


def collect_subject_hints(commits: list) -> list:
    """Commit subjects are hints for the author, never the PR title itself."""
    hints = []
    for c in commits:
        desc = strip_commit_prefix(c['subject']).strip()
        if desc and desc not in hints:
            hints.append(desc)
    return hints


def build_env_slot(circles: dict) -> str:
    """Env slot = blast radius, the first thing a GitOps reviewer needs."""
    labels = set()
    for envs in circles.values():
        for env in envs:
            if env in ('common', 'applicationset'):
                # common/applicationset 레이어는 그 circle의 모든 환경에 반영된다.
                labels.add('common')
            elif env.startswith('infra-k8s-'):
                labels.add(ENV_CONTEXT_MAP.get(env, (env, env))[1])

    if not labels:
        # 클러스터에 배포되지 않는 변경(문서, 스킬, 스크립트).
        return 'repo'

    ordered = [label for label in ENV_LABEL_ORDER if label in labels]
    ordered += sorted(labels - set(ENV_LABEL_ORDER))
    return ','.join(ordered)


def build_scope(circles: dict) -> str:
    """Scope 표기: circle을 최대 3개까지만 나열하고 넘으면 sphere로 축약한다."""
    if not circles:
        return ''

    spheres = sorted({sphere for sphere, _ in circles})

    if len(spheres) == 1:
        circle_names = sorted(circle for _, circle in circles)
        if len(circle_names) <= MAX_LISTED_CIRCLES:
            return f'{spheres[0]}/{",".join(circle_names)}'
        return spheres[0]

    if len(spheres) <= MAX_LISTED_SPHERES:
        return ','.join(spheres)
    listed = ','.join(spheres[:MAX_LISTED_SPHERES])
    return f'{listed},+{len(spheres) - MAX_LISTED_SPHERES}'


def generate_title(circles: dict, commits: list) -> str:
    """Deterministic prefix only. Subject는 LLM이 PR 전체 의도로 새로 쓴다.

    커밋 subject를 그대로 흘려보내던 이전 동작을 제거했다: PR title은 squash 후
    main history 한 줄이자 리뷰 진입점이므로, 첫 커밋이 아니라 PR 전체를 설명해야 한다.
    """
    scope = build_scope(circles)
    prefix = f'[{build_env_slot(circles)}]'
    if scope:
        prefix = f'{prefix} {scope}'
    return f'{prefix}: {TITLE_SUBJECT_PLACEHOLDER}'


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

    # 두괄식 topline 요약: 짧은 선언문 3개(문제/해결/영향)를 불릿 리스트로, 절 연결 없이 문장 단위로 끊는다.
    # diff/title만으로 부족하면 git:pr 스킬(LLM)이 대화 맥락으로 채운다 (SKILL.md Step 4).
    lines.append('- <!-- FILL_ME: 문제 상황을 짧은 한 문장으로, 높임말(~습니다/합니다) 종결, 쉼표로 이어붙이지 않음 -->')
    lines.append('- <!-- FILL_ME: 해결 방법을 짧은 한 문장으로, 높임말 종결 -->')
    lines.append('- <!-- FILL_ME: 영향 범위/주의사항을 짧은 한 문장으로, 높임말 종결 -->')
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

    # 의도/배경은 diff만으로 유추 불가하며, git:pr 스킬(LLM)이 대화 맥락에서 채운다.
    # placeholder가 남아 있으면 SKILL.md Step 4/5에서 PR 생성을 막는다.
    lines.append('## 변경 의도 / 배경 (Why)')
    lines.append('')
    lines.append('<!-- FILL_ME: 이 변경을 유발한 문제·요구·배경을 대화 맥락에서 서술, 높임말(~습니다/합니다) 종결 (무엇을 바꿨는지가 아니라 왜 바꾸는지) -->')
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


def cmd_analyze(base: str, fetch: bool) -> None:
    fetched = fetch_base(base) if fetch else False
    entries, commits = read_branch_changes(base)
    circles = analyze_changes(entries)
    sensitivity = check_sensitivity(circles)

    result = {
        'base': base,
        'fetched': fetched,
        'suggested_title': generate_title(circles, commits),
        'title_prefix': (
            f'[{build_env_slot(circles)}] {build_scope(circles)}'.strip()
        ),
        'subject_hints': collect_subject_hints(commits),
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


def cmd_wiki_impact(base: str) -> None:
    """kubernetes 레포에만 있는 verify-impact.py를 돌린다. 스크립트가 없거나 매치가 없으면 아무것도 출력하지 않는다."""
    repo_root = run_git('rev-parse', '--show-toplevel').strip()
    script = os.path.join(repo_root, WIKI_IMPACT_SCRIPT)
    if not os.path.isfile(script):
        return
    changed = run_git('diff', f'{base}...HEAD', '--name-only').strip()
    if not changed:
        return
    proc = subprocess.run(
        [sys.executable, script, '--changed-files', changed],
        cwd=repo_root, capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description='PR metadata generator for kubernetes GitOps repo')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_analyze = sub.add_parser('analyze', help='브랜치 변경을 분석해 PR 제목·본문 JSON을 출력한다')
    p_analyze.add_argument('--base', default=DEFAULT_BASE)
    p_analyze.add_argument('--no-fetch', action='store_true', help='base fetch를 건너뛴다')

    p_wiki = sub.add_parser('wiki-impact', help='DevOps Infra Wiki recompile 후보를 출력한다')
    p_wiki.add_argument('--base', default=DEFAULT_BASE)

    args = parser.parse_args()
    try:
        if args.cmd == 'analyze':
            cmd_analyze(args.base, fetch=not args.no_fetch)
        else:
            cmd_wiki_impact(args.base)
    except GitError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
