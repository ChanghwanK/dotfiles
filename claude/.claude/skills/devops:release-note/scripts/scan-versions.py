#!/usr/bin/env python3
"""
scan-versions.py: infra/observability kustomization.yaml에서 Helm chart 버전을 추출한다.

서브커맨드:
  scan --component <name>   특정 컴포넌트의 환경별 버전 조회 (JSON)
  list                      전체 인프라 컴포넌트 버전 인벤토리 (JSON)
"""

import argparse
import glob
import json
import os
import sys

REPO_BASE = os.path.expanduser("~/workspace/riiid/kubernetes")

# 별칭 → circle 이름(들) 매핑
# 키: 사용자 입력 키워드 (소문자), 값: circle 디렉토리 이름 목록
ALIASES: dict[str, list[str]] = {
    # Istio 관련
    "istio": ["istio-system", "istio-ingressgateway", "istio-egressgateway"],
    "istiod": ["istio-system"],
    "istio-ingressgateway": ["istio-ingressgateway"],
    "istio-egressgateway": ["istio-egressgateway"],
    # cert-manager
    "cert-manager": ["cert-manager"],
    "certmanager": ["cert-manager"],
    # VictoriaMetrics
    "victoriametrics": ["victoriametrics"],
    "vm": ["victoriametrics"],
    "victoria-metrics": ["victoriametrics"],
    "victoria-metrics-k8s-stack": ["victoriametrics"],
    # Loki
    "loki": ["loki"],
    # Alloy
    "alloy": ["alloy"],
    # Grafana
    "grafana": ["grafana"],
    # Jaeger
    "jaeger": ["jaeger"],
    # Tempo
    "tempo": ["tempo"],
    # Pyroscope
    "pyroscope": ["pyroscope"],
    # OpenTelemetry
    "opentelemetry": ["opentelemetry"],
    "otel": ["opentelemetry"],
    # KEDA
    "keda": ["keda"],
    # Argo Rollouts
    "argo-rollouts": ["argo-rollouts"],
    "argo_rollouts": ["argo-rollouts"],
    "argorollouts": ["argo-rollouts"],
    # external-secrets
    "external-secrets": ["external-secrets"],
    "external_secrets": ["external-secrets"],
    "eso": ["external-secrets"],
    # sealed-secrets
    "sealed-secrets": ["sealed-secrets", "sealed-secrets-web"],
    "sealedsecrets": ["sealed-secrets"],
    # cert-manager (jetstack)
    "jetstack": ["cert-manager"],
    # CNPG
    "cnpg": ["cnpg-system"],
    "cloudnative-pg": ["cnpg-system"],
    "cloudnativepg": ["cnpg-system"],
    # GPU Operator
    "gpu-operator": ["gpu-operator"],
    "gpuoperator": ["gpu-operator"],
    # Kyverno
    "kyverno": ["kyverno"],
    # external-dns
    "external-dns": ["external-dns"],
    "externaldns": ["external-dns"],
    # AWS CSI drivers
    "ebs-csi": ["aws-ebs-csi-driver"],
    "aws-ebs-csi": ["aws-ebs-csi-driver"],
    "aws-ebs-csi-driver": ["aws-ebs-csi-driver"],
    "efs-csi": ["aws-efs-csi-driver"],
    "aws-efs-csi": ["aws-efs-csi-driver"],
    "s3-csi": ["aws-s3-csi-driver"],
    # Rook-Ceph
    "rook-ceph": ["rook-ceph"],
    "ceph": ["rook-ceph"],
    "rook": ["rook-ceph"],
    # Harbor
    "harbor": ["harbor"],
    # HAProxy
    "haproxy": ["haproxy"],
    # KEDA
    "metrics-server": ["metrics-server"],
    # goldilocks
    "goldilocks": ["goldilocks"],
    # velero
    "velero": ["velero"],
    # reloader
    "reloader": ["reloader"],
    # opencost
    "opencost": ["opencost"],
    # tetragon
    "tetragon": ["tetragon"],
    # volcano
    "volcano": ["volcano"],
    # atlantis
    "atlantis": ["atlantis"],
    # elastic
    "elastic": ["elastic-system"],
    "elasticsearch": ["elastic-system"],
    "elastic-system": ["elastic-system"],
    # kube-downscaler
    "kube-downscaler": ["kube-downscaler"],
    "downscaler": ["kube-downscaler"],
    # open-feature
    "open-feature-operator": ["open-feature-operator"],
    "openfeature": ["open-feature-operator"],
    # qdrant
    "qdrant": ["qdrant"],
    # ebpf-exporter
    "ebpf-exporter": ["ebpf-exporter"],
    # multus
    "multus": ["multus"],
}

# Helm 외 방식으로 관리되는 특수 컴포넌트
SPECIAL_COMPONENTS: dict[str, str] = {
    "argocd": (
        "raw manifests로 관리됩니다. "
        "버전 확인: src/infra/argocd/infra-k8s-global/resources/ 의 install.yaml 참조\n"
        "업그레이드: https://github.com/argoproj/argo-cd/releases 에서 install.yaml 다운로드 후 교체"
    ),
    "karpenter": (
        "Terraform으로 관리됩니다. "
        "버전 확인/변경: ~/workspace/riiid/terraform 리포에서 karpenter 모듈 참조\n"
        "terraform plan/apply로 업그레이드"
    ),
    "arc-systems": (
        "수동 Helm CLI로 관리됩니다. "
        "현재 버전 및 업그레이드 방법: src/infra/arc-systems/README.md 참조\n"
        "업그레이드: helm upgrade --install 명령어로 수동 실행"
    ),
    "arc": (
        "수동 Helm CLI로 관리됩니다. "
        "현재 버전 및 업그레이드 방법: src/infra/arc-systems/README.md 참조"
    ),
}

ENV_ORDER = [
    "infra-k8s-dev",
    "infra-k8s-stg",
    "infra-k8s-prod",
    "infra-k8s-global",
    "infra-k8s-idc",
    "infra-k8s-office",
]


def find_kustomization_files(circles: list[str]) -> list[str]:
    """지정된 circle들의 kustomization.yaml 파일 경로 목록 반환."""
    files = []
    for circle in circles:
        pattern = os.path.join(
            REPO_BASE, "src", "*", circle, "infra-k8s-*", "kustomization.yaml"
        )
        matched = glob.glob(pattern)
        files.extend(sorted(matched))
    return files


def find_all_infra_kustomization_files() -> list[str]:
    """infra/ 와 observability/ 전체 kustomization.yaml 파일 반환."""
    files = []
    for sphere in ["infra", "observability"]:
        pattern = os.path.join(
            REPO_BASE, "src", sphere, "*", "infra-k8s-*", "kustomization.yaml"
        )
        files.extend(sorted(glob.glob(pattern)))
    return files


def parse_kustomization(filepath: str) -> list[dict]:
    """
    kustomization.yaml을 line-by-line 파싱하여 helmCharts 블록 추출.
    주석 처리된 줄은 스킵한다.
    반환: [{'name': str, 'version': str, 'repo': str}, ...]
    """
    charts = []
    current: dict = {}
    in_helm_charts = False
    in_entry = False

    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        # 주석 줄 스킵
        stripped = line.rstrip()
        if stripped.lstrip().startswith("#"):
            continue

        # helmCharts 블록 진입
        if stripped.strip() == "helmCharts:":
            in_helm_charts = True
            continue

        if not in_helm_charts:
            continue

        # helmCharts 블록 종료 감지 (최상위 key가 등장)
        if stripped and not stripped.startswith(" ") and not stripped.startswith("-"):
            in_helm_charts = False
            if current:
                charts.append(current)
                current = {}
            continue

        # 새 chart entry 시작
        if stripped.strip().startswith("- repo:") or stripped.strip().startswith("- name:"):
            if current:
                charts.append(current)
                current = {}
            in_entry = True

        if in_entry:
            s = stripped.strip().lstrip("- ")
            if s.startswith("repo:"):
                current["repo"] = s[len("repo:"):].strip()
            elif s.startswith("name:"):
                current["name"] = s[len("name:"):].strip()
            elif s.startswith("version:"):
                current["version"] = s[len("version:"):].strip()

    if current:
        charts.append(current)

    return charts


def extract_path_info(filepath: str) -> tuple[str, str, str]:
    """
    파일 경로에서 (sphere, circle, env) 추출.
    예: .../src/infra/cert-manager/infra-k8s-prod/kustomization.yaml
        → ('infra', 'cert-manager', 'infra-k8s-prod')
    """
    parts = filepath.split(os.sep)
    try:
        src_idx = parts.index("src")
        sphere = parts[src_idx + 1]
        circle = parts[src_idx + 2]
        env = parts[src_idx + 3]
        return sphere, circle, env
    except (ValueError, IndexError):
        return "unknown", "unknown", "unknown"


def cmd_scan(component: str) -> dict:
    """특정 컴포넌트의 환경별 버전을 조회한다."""
    comp_lower = component.lower()

    # 특수 컴포넌트 확인
    if comp_lower in SPECIAL_COMPONENTS:
        return {
            "component": component,
            "special": True,
            "special_note": SPECIAL_COMPONENTS[comp_lower],
            "circles": [],
            "files": [],
        }

    # 별칭 → circles 매핑
    circles = ALIASES.get(comp_lower)
    if not circles:
        # 별칭에 없으면 circle 이름 직접 사용
        circles = [comp_lower]

    files = find_kustomization_files(circles)

    if not files:
        return {
            "component": component,
            "found": False,
            "message": f"'{component}' 컴포넌트를 infra/ 또는 observability/ 에서 찾을 수 없습니다.",
            "circles": [],
            "files": [],
        }

    # circle별로 chart 버전 집계
    # 구조: {circle: {chart_name: {env: version}}}
    data: dict[str, dict[str, dict[str, str]]] = {}

    for filepath in files:
        sphere, circle, env = extract_path_info(filepath)
        charts = parse_kustomization(filepath)

        if circle not in data:
            data[circle] = {}

        for chart in charts:
            chart_name = chart.get("name", "unknown")
            version = chart.get("version", "unknown")

            if chart_name not in data[circle]:
                data[circle][chart_name] = {}
            data[circle][chart_name][env] = version

    # 결과 포맷팅
    circles_result = []
    for circle, charts_map in data.items():
        charts_list = []
        for chart_name, env_versions in charts_map.items():
            # 환경 순서 정렬
            sorted_versions = {
                env: env_versions[env]
                for env in ENV_ORDER
                if env in env_versions
            }
            # ENV_ORDER에 없는 환경 추가
            for env in env_versions:
                if env not in sorted_versions:
                    sorted_versions[env] = env_versions[env]

            # 버전 일치 여부 확인
            unique_versions = list(set(env_versions.values()))
            charts_list.append({
                "name": chart_name,
                "version": sorted_versions,
                "version_consistent": len(unique_versions) == 1,
                "unique_versions": unique_versions,
            })

        circles_result.append({
            "circle": circle,
            "charts": charts_list,
        })

    return {
        "component": component,
        "found": True,
        "special": False,
        "special_note": None,
        "circles": circles_result,
        "files": files,
    }


def cmd_list() -> dict:
    """전체 infra/observability 컴포넌트 버전 인벤토리를 반환한다."""
    files = find_all_infra_kustomization_files()

    # 구조: {sphere: {circle: {chart_name: {env: version}}}}
    inventory: dict[str, dict[str, dict[str, dict[str, str]]]] = {}
    # 버전 불일치 컴포넌트 추적
    inconsistent: list[dict] = []

    for filepath in files:
        sphere, circle, env = extract_path_info(filepath)
        charts = parse_kustomization(filepath)

        if sphere not in inventory:
            inventory[sphere] = {}
        if circle not in inventory[sphere]:
            inventory[sphere][circle] = {}

        for chart in charts:
            chart_name = chart.get("name", "unknown")
            version = chart.get("version", "unknown")

            if chart_name not in inventory[sphere][circle]:
                inventory[sphere][circle][chart_name] = {}
            inventory[sphere][circle][chart_name][env] = version

    # 결과 포맷팅 + 버전 불일치 감지
    result_spheres = []
    for sphere, circles_map in sorted(inventory.items()):
        circles_list = []
        for circle, charts_map in sorted(circles_map.items()):
            charts_list = []
            for chart_name, env_versions in sorted(charts_map.items()):
                sorted_versions = {
                    env: env_versions[env]
                    for env in ENV_ORDER
                    if env in env_versions
                }
                for env in env_versions:
                    if env not in sorted_versions:
                        sorted_versions[env] = env_versions[env]

                unique_versions = list(set(env_versions.values()))
                is_consistent = len(unique_versions) == 1

                chart_entry = {
                    "name": chart_name,
                    "version": sorted_versions,
                    "version_consistent": is_consistent,
                    "unique_versions": unique_versions,
                }
                charts_list.append(chart_entry)

                if not is_consistent:
                    inconsistent.append({
                        "sphere": sphere,
                        "circle": circle,
                        "chart": chart_name,
                        "versions": sorted_versions,
                    })

            circles_list.append({
                "circle": circle,
                "charts": charts_list,
            })

        result_spheres.append({
            "sphere": sphere,
            "circles": circles_list,
        })

    # 특수 컴포넌트 안내
    special_info = [
        {"name": k, "note": v} for k, v in SPECIAL_COMPONENTS.items()
        if k not in ["arc"]  # 중복 제거
    ]

    return {
        "inventory": result_spheres,
        "inconsistent_versions": inconsistent,
        "total_files_scanned": len(files),
        "special_components": special_info,
    }


def main():
    parser = argparse.ArgumentParser(
        description="인프라 컴포넌트 버전 스캐너"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan 서브커맨드
    scan_parser = subparsers.add_parser("scan", help="특정 컴포넌트 버전 조회")
    scan_parser.add_argument("--component", required=True, help="컴포넌트 이름 또는 별칭")

    # list 서브커맨드
    subparsers.add_parser("list", help="전체 컴포넌트 버전 인벤토리")

    args = parser.parse_args()

    if args.command == "scan":
        result = cmd_scan(args.component)
    elif args.command == "list":
        result = cmd_list()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
