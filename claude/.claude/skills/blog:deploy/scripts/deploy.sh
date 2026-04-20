#!/bin/bash
# tech_blog GitHub Pages 배포 스크립트
# gatsby build → gh-pages -d public -b deploy
set -euo pipefail

BLOG_DIR="/Users/changhwan/workspace/tech_blog"

if [ ! -d "$BLOG_DIR" ]; then
  echo "ERROR: 블로그 디렉토리를 찾을 수 없습니다: $BLOG_DIR" >&2
  exit 1
fi

cd "$BLOG_DIR"
echo "==> 작업 디렉토리: $(pwd)"
echo ""

# 미커밋 변경사항 확인
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNCOMMITTED" -gt "0" ]; then
  echo "WARNING: 미커밋 변경사항이 ${UNCOMMITTED}개 있습니다."
  echo "$(git status --short)"
  echo ""
  echo "계속 진행합니다..."
fi

echo "==> gatsby build 시작..."
npm run build

echo ""
echo "==> gh-pages 배포 시작 (deploy 브랜치)..."
npx gh-pages -d public -b deploy

echo ""
echo "==> 배포 완료!"
echo "URL: https://dev.k10n.me"
