#!/usr/bin/env python3
"""Kubernetes GitOps push 영향도 분석 스크립트.

stdin으로 `git diff --name-status` 출력을 받아 배포 영향도를 분석한다.

서브커맨드:
  analyze     - 변경 circle/env/type 파악, 안전 게이트 판단 (JSON 출력)
  verify-plan - 배포 후 검증 체크리스트 생성 (Markdown 출력)
"""

import argparse
import json
import re
import sys

SENSITIVE_ENVS = {'infra-k8s-prod', 'infra-k8s-global'}

# src/{sphere}/{circle}/infra-k8s-{env}/...
ENV_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/(?P<env>infra-k8s-[^/]+)/(?P<rest>.+)$'
)

# src/{sphere}/{circle}/common/...
COMMON_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/common/(?P<rest>.+)$'
)

# src/{sphere}/{circle}/applicationset.jsonnet
APPSET_PATH_RE = re.compile(
    r'^src/(?P<sphere>[^/]+)/(?P<circle>[^/]+)/applicationset\.jsonnet$'
)


def classify_change(filepath, rest):
    """파일 경로에서 변경 유형을 분류한다."""
    if rest == 'kustomization.yaml':
        return 'chart_version'
    if rest.endswith('values.yaml'):
        return 'values_change'
    if rest.startswith('resources/'):
        return 'new_resource'
    return 'other'


def parse_diff_lines(lines):
    """git diff --name-status 출력을 파싱한다.

    Returns:
        changes: list of {status, filepath, sphere, circle, env, change_type}
        deletions: list of deleted filepaths
    """
    changes = []
    deletions = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split('\t')
        if len(parts) < 2:
            # 탭이 아닌 공백으로 구분된 경우 처리
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue

        status = parts[0][0]  # M, A, D, R 등 (R100 → R)
        filepath = parts[-1]  # rename의 경우 마지막이 새 경로

        if status == 'D':
            deletions.append(filepath)

        # env-specific 경로 매칭
        m = ENV_PATH_RE.match(filepath)
        if m:
            change_type = classify_change(filepath, m.group('rest'))
            if status == 'D':
                change_type = 'deletion'
            changes.append({
                'status': status,
                'filepath': filepath,
                'sphere': m.group('sphere'),
                'circle': m.group('circle'),
                'env': m.group('env'),
                'rest': m.group('rest'),
                'change_type': change_type,
            })
            continue

        # common 경로 매칭
        m = COMMON_PATH_RE.match(filepath)
        if m:
            changes.append({
                'status': status,
                'filepath': filepath,
                'sphere': m.group('sphere'),
                'circle': m.group('circle'),
                'env': 'common',
                'change_type': 'common_change',
            })
            continue

        # applicationset 매칭
        m = APPSET_PATH_RE.match(filepath)
        if m:
            changes.append({
                'status': status,
                'filepath': filepath,
                'sphere': m.group('sphere'),
                'circle': m.group('circle'),
                'env': 'all',
                'change_type': 'applicationset',
            })
            continue

        # src/ 외부 또는 매칭 안 되는 파일
        changes.append({
            'status': status,
            'filepath': filepath,
            'sphere': None,
            'circle': None,
            'env': None,
            'change_type': 'other',
        })

    return changes, deletions


def build_affected_circles(changes):
    """변경 목록에서 영향받는 circle 목록을 추출한다 (중복 제거)."""
    seen = set()
    affected = []

    for c in changes:
        if c['sphere'] is None:
            continue
        key = (c['sphere'], c['circle'], c['env'], c['change_type'])
        if key not in seen:
            seen.add(key)
            affected.append({
                'sphere': c['sphere'],
                'circle': c['circle'],
                'env': c['env'],
                'rest': c.get('rest', ''),
                'change_type': c['change_type'],
            })

    return affected


def check_confirmation(affected_circles, deletions):
    """안전 게이트 확인이 필요한지 판단한다."""
    reasons = []

    for ac in affected_circles:
        env = ac['env']
        label = f"{ac['sphere']}/{ac['circle']}"

        if env in SENSITIVE_ENVS:
            env_label = {
                'infra-k8s-prod': 'PROD',
                'infra-k8s-global': 'GLOBAL',
            }.get(env, env.upper())
            reasons.append(f"[{env_label}] {label}: {ac['change_type']}")

        # IDC 환경: dev/stg 서브 env는 Pass, prod 또는 서브 env 없는 경우만 확인 필요
        if env == 'infra-k8s-idc':
            rest = ac.get('rest', '')
            is_safe_sub_env = rest.startswith('dev/') or rest.startswith('stg/')
            if not is_safe_sub_env:
                sub_env_hint = rest.split('/')[0] if rest else '(클러스터 레벨)'
                reasons.append(f"[IDC/{sub_env_hint.upper()}] {label}: {ac['change_type']}")

        if ac['change_type'] == 'common_change':
            reasons.append(f"[COMMON] {label}: common/values.yaml 변경 (전 환경 영향)")

    for fp in deletions:
        reasons.append(f"[DELETE] {fp}")

    return bool(reasons), reasons


def cmd_analyze(args):
    """배포 영향도를 분석하여 JSON으로 출력한다."""
    lines = sys.stdin.read().splitlines()
    changes, deletions = parse_diff_lines(lines)
    affected_circles = build_affected_circles(changes)
    requires_confirmation, confirmation_reasons = check_confirmation(
        affected_circles, deletions
    )

    result = {
        'total_files_changed': len(changes),
        'affected_circles': affected_circles,
        'requires_confirmation': requires_confirmation,
        'confirmation_reasons': confirmation_reasons,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_verify_plan(args):
    """배포 후 검증 체크리스트를 Markdown으로 출력한다."""
    lines = sys.stdin.read().splitlines()
    changes, _ = parse_diff_lines(lines)
    affected_circles = build_affected_circles(changes)

    # env가 실제 배포 대상인 circle만 필터링 (common, all, None 제외)
    deploy_targets = [
        ac for ac in affected_circles
        if ac['env'] and ac['env'].startswith('infra-k8s-')
    ]

    if not deploy_targets:
        print("변경사항에 K8s 배포 대상이 없습니다.")
        return

    # 중복 제거: (sphere, circle, env) 단위
    seen = set()
    unique_targets = []
    for t in deploy_targets:
        key = (t['sphere'], t['circle'], t['env'])
        if key not in seen:
            seen.add(key)
            unique_targets.append(t)

    print("### 배포 후 검증 체크리스트\n")

    print("**ArgoCD Sync 확인:**")
    for t in unique_targets:
        app_name = f"{t['sphere']}.{t['circle']}.{t['env']}"
        print(f"- [ ] `{app_name}` sync 상태 확인")

    print()
    print("**Pod 상태 확인:**")
    seen_ns = set()
    for t in unique_targets:
        ns = f"{t['sphere']}-{t['circle']}"
        env_ctx = {
            'infra-k8s-prod': 'k8s-prod',
            'infra-k8s-stg': 'k8s-stg',
            'infra-k8s-dev': 'k8s-dev',
            'infra-k8s-global': 'k8s-global',
            'infra-k8s-idc': 'k8s-idc',
        }.get(t['env'], t['env'])
        key = (ns, env_ctx)
        if key not in seen_ns:
            seen_ns.add(key)
            print(f"- [ ] `{ns}` namespace pod Running/Ready 확인 (context: {env_ctx})")

    # common 변경이 있으면 추가 경고
    common_circles = [
        ac for ac in affected_circles
        if ac['change_type'] == 'common_change'
    ]
    if common_circles:
        print()
        print("**common 변경 주의:**")
        for c in common_circles:
            print(f"- [ ] `{c['sphere']}/{c['circle']}` 전 환경 배포 상태 확인 필요")


def main():
    parser = argparse.ArgumentParser(
        description='Kubernetes GitOps push 영향도 분석'
    )
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser(
        'analyze',
        help='배포 영향도 분석 (JSON 출력)'
    )
    sub.add_parser(
        'verify-plan',
        help='배포 후 검증 체크리스트 생성 (Markdown 출력)'
    )

    args = parser.parse_args()
    {
        'analyze': cmd_analyze,
        'verify-plan': cmd_verify_plan,
    }[args.command](args)


if __name__ == '__main__':
    main()
