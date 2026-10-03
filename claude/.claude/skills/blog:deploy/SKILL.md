---
name: blog:deploy
description: |
  tech_blog GitHub Pages 배포 스킬. 변경을 main에 커밋·push한 뒤 npm run clean → gatsby build →
  gh-pages deploy 브랜치 배포를 실행하고 결과를 확인한다.
  사용 시점: (1) 블로그 변경사항을 dev.k10n.me에 배포, (2) 빌드/배포 오류 진단.
  트리거 키워드: "배포", "deploy", "publish", "blog:deploy", "/blog:deploy".
model: haiku
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/blog:deploy/scripts/deploy.sh)
  - Bash(git -C /Users/changhwan/workspace/tech_blog *)
  - Bash(lsof *)
  - Read
---
# blog:deploy

tech_blog를 GitHub Pages(`dev.k10n.me`)에 배포한다.

배포 순서는 항상 **main 커밋·push → `npm run clean` → `npm run deploy`(build + gh-pages)** 다.
배포는 로컬 파일로 빌드되므로, main에 없는 변경이 사이트에만 올라가지 않게 main을 먼저 맞춘다.

---

## 배포 워크플로우

### Step 1: main에 커밋·push

1. `git -C /Users/changhwan/workspace/tech_blog status --short`로 변경을 확인한다.
2. 변경이 있으면 성격별로 나눠 커밋한다 (메시지는 기존 컨벤션 `type(scope): 요약`을 따른다).
   사용자가 만들지 않은 변경이 섞여 있으면 커밋 전에 사용자에게 확인한다.
3. `git pull --rebase origin main` 후 `git push origin main`.

### Step 2: dev 서버 확인

`lsof -nP -iTCP:8000 -sTCP:LISTEN`으로 확인한다. 떠 있으면 배포가 `.cache`를 두고 충돌한다.
- Claude가 띄운 서버면 자기가 띄운 태스크/PID로만 끈다 (`pkill -f "gatsby develop"` 금지).
- 사용자 서버면 끄지 말고 사용자에게 알린다.

### Step 3: 배포 실행

```bash
bash /Users/changhwan/.claude/skills/blog:deploy/scripts/deploy.sh
```

스크립트가 차례로:
- main 브랜치인지, 미커밋 변경이 없는지, 로컬 main과 origin/main이 같은지 확인하고 아니면 중단
- 8000 포트에 dev 서버가 있으면 중단
- `npm run clean` (CSS Modules·로컬 remark 플러그인 변경이 캐시에 가려지는 것 방지)
- `npm run build` 후 `gh-pages`로 deploy 브랜치에 push

### Step 4: 결과 보고

배포 성공 시 deploy 브랜치 커밋과 실제 페이지를 확인한다:
```bash
git -C /Users/changhwan/workspace/tech_blog fetch -q origin deploy
git -C /Users/changhwan/workspace/tech_blog log -1 --format='%h %ci' origin/deploy
```
바뀐 글이 있으면 해당 URL이 200을 반환하는지, 바뀐 문자열이 들어갔는지 확인한다.

실패 시 오류 메시지를 분석해서 원인을 사용자에게 알린다:
- **사전 확인 실패**: 미커밋 변경, main 불일치, dev 서버 실행 중 (메시지에 해결 방법이 있다)
- **빌드 오류**: GraphQL 쿼리 오류, 누락된 frontmatter 필드, 잘못된 이미지 경로, mermaid 문법 오류(`index.md:줄번호` 포함)
- **gh-pages 오류**: 인증 문제, 네트워크 오류

---

## 주의사항

- `status: writing` 글은 프로덕션 빌드에서 제외된다. 사이트에 안 보이면 frontmatter부터 확인한다.
- mermaid 블록은 빌드 때 로컬 Chrome으로 SVG를 만들고, 글자 폭은 jsDelivr에서 받은 Pretendard로 잰다(`plugins/gatsby-remark-mermaid-svg/themes.js`의 `FONT_CSS_URL`).
  - 로컬 Chrome이 없으면 빌드가 실패한다.
  - jsDelivr에서 폰트를 받지 못하면 다른 폰트로 박스 크기를 재서, 사이트에서 라벨 끝이 잘릴 수 있다. 다이어그램 라벨이 잘려 보이면 이것부터 의심한다.
  - 방문자용 폰트는 npm `pretendard` 패키지에서 서빙한다. 패키지 버전을 올리면 `FONT_CSS_URL`의 버전도 함께 맞춘다.
- 배포 후 반영까지 GitHub Pages CDN 전파에 수 분이 소요될 수 있음
