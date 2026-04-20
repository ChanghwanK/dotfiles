#!/usr/bin/env python3
"""
공유 태그 정규화 유틸리티.
tech-spec.py, obsidian-note.py 등에서 공통으로 사용한다.
"""

# 태그 키워드 → domain/ 네임스페이스 매핑
# key는 소문자 + 특수문자 제거 후 매칭 (normalize_tags 참조)
TAG_DOMAIN_MAP = {
    "kubernetes": "domain/kubernetes",
    "aws": "domain/aws",
    "terraform": "domain/terraform",
    "infra": None,  # 단독 사용 시 무시
    "network": "domain/networking",
    "networking": "domain/networking",
    "istio": "domain/networking",
    "envoy": "domain/networking",
    "servicemesh": "domain/networking",
    "observability": "domain/observability",
    "grafana": "domain/observability",
    "prometheus": "domain/observability",
    "loki": "domain/observability",
    "tracing": "domain/observability",
    "database": "domain/database",
    "onpremise": "domain/on-premise",   # tech-spec 등에서 사용
    "on-premise": "domain/on-premise",  # obsidian-note 등에서 사용
    "gpu": "domain/on-premise",
    "ai": "domain/ai",
    "agent": "domain/ai",
    "llm": "domain/ai",
    "ml": "domain/ai",
    "machinelearning": "domain/ai",
    "security": "domain/security",
    "tls": "domain/security",
    "pki": "domain/security",
}

# AWS 서비스명 집합 — normalize_tags에서 domain/aws 매핑에 사용
AWS_SERVICES = {
    "cloudfront", "route53", "aurora", "rds", "alb", "elb",
    "ecs", "eks", "ec2", "s3", "cloudwatch", "iam", "vpc",
    "natgateway", "transitgateway", "lambda", "sqs", "sns",
    "dynamodb", "elasticache", "kinesisfirehose",
}


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """기존 태그를 domain/ 네임스페이스로 정규화하여 정렬된 리스트로 반환한다."""
    domain_tags = set()
    for tag in raw_tags:
        key = tag.lower().replace(" ", "").replace("_", "").replace("-", "")
        mapped = TAG_DOMAIN_MAP.get(key)
        if mapped:
            domain_tags.add(mapped)
        elif tag.startswith("domain/") or tag.startswith("type/") or tag.startswith("resource/") or tag.startswith("topic/"):
            domain_tags.add(tag)
        elif key in AWS_SERVICES:
            domain_tags.add("domain/aws")
    return sorted(domain_tags)
