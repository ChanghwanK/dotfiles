#!/usr/bin/env python3
"""tech_blog 신규 포스트 디렉토리 및 템플릿 생성 스크립트."""
import argparse
import os
import re
import sys
from datetime import datetime


BLOG_POSTS_DIR = "/Users/changhwan/workspace/tech_blog/content/posts"


def slugify(text):
    """한글/영문 제목을 URL-safe slug로 변환."""
    # 소문자 변환
    slug = text.lower()
    # 한글 → 제거 (영문 slug만 허용; 사용자가 --slug로 지정하는 경우 사용)
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "new-post"


def main():
    parser = argparse.ArgumentParser(
        description="tech_blog 신규 포스트 템플릿 생성"
    )
    parser.add_argument("--title", required=True, help="포스트 제목 (한글/영문)")
    parser.add_argument(
        "--slug",
        help="URL slug (미지정 시 제목에서 자동 생성). 영문/숫자/하이픈만 허용.",
    )
    parser.add_argument(
        "--tags",
        nargs="+",
        default=["DevOps"],
        help="태그 목록 (공백 구분). 예: --tags Kubernetes DevOps",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="포스트 날짜 (YYYY-MM-DD, 기본: 오늘)",
    )
    parser.add_argument("--description", default="", help="포스트 설명 (SEO용)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 파일 생성 없이 생성 예정 내용만 출력",
    )
    args = parser.parse_args()

    # slug 결정
    slug = args.slug if args.slug else slugify(args.title)
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        print(
            f"ERROR: slug '{slug}'는 유효하지 않습니다. 영문 소문자/숫자/하이픈만 허용합니다.",
            file=sys.stderr,
        )
        print("  --slug 옵션으로 직접 지정하세요. 예: --slug my-post-title", file=sys.stderr)
        sys.exit(1)

    dir_name = f"{args.date}-{slug}"
    post_dir = os.path.join(BLOG_POSTS_DIR, dir_name)
    index_path = os.path.join(post_dir, "index.md")

    # frontmatter 생성
    tags_yaml = "\n".join(f"  - {tag}" for tag in args.tags)
    content = f"""---
title: "{args.title}"
description: "{args.description}"
date: {args.date}
thumbnail: ./thumbnail.png
tags:
{tags_yaml}
---

"""

    if args.dry_run:
        print(f"[dry-run] 생성 예정 디렉토리: {post_dir}")
        print(f"[dry-run] 생성 예정 파일: {index_path}")
        print("[dry-run] --- index.md 내용 ---")
        print(content)
        return

    # 실제 생성
    if os.path.exists(post_dir):
        print(f"ERROR: 이미 존재하는 디렉토리입니다: {post_dir}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(post_dir)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"생성 완료!")
    print(f"  디렉토리: {post_dir}")
    print(f"  파일:     {index_path}")
    print(f"")
    print(f"다음 단계:")
    print(f"  1. thumbnail.png를 {post_dir}/에 추가")
    print(f"  2. {index_path} 에서 글 작성 시작")
    print(f"  3. description 필드 업데이트 (SEO)")


if __name__ == "__main__":
    main()
