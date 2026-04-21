#!/usr/bin/env python3
"""
공유 태그 정규화 유틸리티.
tech-spec.py, obsidian-note.py 등에서 공통으로 사용한다.
"""

# 태그 키워드 → 정규화 태그 매핑
# key는 소문자 + 특수문자 제거 후 매칭 (normalize_tags 참조)
TAG_DOMAIN_MAP = {
    "kubernetes": "kubernetes",
    "aws": "aws",
    "terraform": "terraform",
    "infra": None,  # 단독 사용 시 무시
    "network": "networking",
    "networking": "networking",
    "istio": "networking",
    "envoy": "networking",
    "servicemesh": "networking",
    "observability": "observability",
    "grafana": "observability",
    "prometheus": "observability",
    "loki": "observability",
    "tracing": "observability",
    "database": "database",
    "onpremise": "on-premise",
    "on-premise": "on-premise",
    "gpu": "on-premise",
    "ai": "ai",
    "agent": "ai",
    "llm": "ai",
    "ml": "ai",
    "machinelearning": "ai",
    "security": "security",
    "tls": "security",
    "pki": "security",
}

# AWS 서비스명 집합 — normalize_tags에서 aws 매핑에 사용
AWS_SERVICES = {
    "cloudfront", "route53", "aurora", "rds", "alb", "elb",
    "ecs", "eks", "ec2", "s3", "cloudwatch", "iam", "vpc",
    "natgateway", "transitgateway", "lambda", "sqs", "sns",
    "dynamodb", "elasticache", "kinesisfirehose",
}


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """기존 태그를 정규화하여 정렬된 리스트로 반환한다."""
    result = set()
    for tag in raw_tags:
        # 기존 domain/ 프리픽스 제거 후 매핑
        bare = tag.split("/", 1)[1] if tag.startswith("domain/") else tag
        key = bare.lower().replace(" ", "").replace("_", "").replace("-", "")
        mapped = TAG_DOMAIN_MAP.get(key)
        if mapped:
            result.add(mapped)
        elif key in AWS_SERVICES:
            result.add("aws")
        elif bare and not bare.startswith("type/") and not bare.startswith("resource/"):
            result.add(bare)
    return sorted(result)
