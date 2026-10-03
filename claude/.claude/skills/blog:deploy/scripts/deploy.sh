#!/bin/bash
# tech_blog GitHub Pages 배포 스크립트
# 순서: (main 커밋·push 확인) → dev 서버 확인 → npm run clean → gatsby build → gh-pages -d public -b deploy
set -euo pipefail

BLOG_DIR="/Users/changhwan/workspace/tech_blog"
DEPLOY_BRANCH="main"
DEV_SERVER_PORT=8000

if [ ! -d "$BLOG_DIR" ]; then
  echo "ERROR: 블로그 디렉토리를 찾을 수 없습니다: $BLOG_DIR" >&2
  exit 1
fi

cd "$BLOG_DIR"
echo "==> 작업 디렉토리: $(pwd)"
echo ""

# 배포는 로컬 파일로 빌드하므로, main에 없는 변경이 사이트에만 올라가는 일을 막는다.
# (예전에는 경고만 하고 진행해서 사이트와 main이 어긋날 수 있었다)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "$DEPLOY_BRANCH" ]; then
  echo "ERROR: 현재 브랜치가 ${CURRENT_BRANCH}입니다. ${DEPLOY_BRANCH}에서 배포하세요." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: 미커밋 변경사항이 있습니다. ${DEPLOY_BRANCH}에 커밋·push한 뒤 배포하세요." >&2
  git status --short >&2
  exit 1
fi

git fetch -q origin "$DEPLOY_BRANCH"
if [ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/${DEPLOY_BRANCH}")" ]; then
  echo "ERROR: 로컬 ${DEPLOY_BRANCH}와 origin/${DEPLOY_BRANCH}가 다릅니다. pull/push로 맞춘 뒤 배포하세요." >&2
  git status -sb | head -1 >&2
  exit 1
fi

# clean은 .cache를 지운다. 같은 디렉터리에서 gatsby develop이 돌고 있으면 둘이 .cache를 동시에 써서
# 배포가 실패하거나(ENOTEMPTY 등) dev 서버가 500을 낸다. 사용자 서버일 수 있으므로 죽이지 않고 멈춘다.
if lsof -nP -iTCP:"$DEV_SERVER_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: ${DEV_SERVER_PORT} 포트에 dev 서버가 떠 있습니다. 끈 뒤 다시 배포하세요." >&2
  lsof -nP -iTCP:"$DEV_SERVER_PORT" -sTCP:LISTEN >&2
  exit 1
fi

# CSS Modules 변경(.cache/webpack)과 로컬 remark 플러그인 변경(transformer-remark가 예전 변환 결과를 재사용)을
# 놓치지 않도록 매번 캐시를 비운다.
echo "==> gatsby 캐시 정리..."
npm run clean

echo "==> gatsby build 시작..."
npm run build

echo ""
echo "==> gh-pages 배포 시작 (deploy 브랜치)..."
npx gh-pages -d public -b deploy

echo ""
echo "==> 배포 완료! ($(git rev-parse --short HEAD) 기준)"
echo "URL: https://dev.k10n.me"
