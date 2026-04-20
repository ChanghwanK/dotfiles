---
name: blog:deploy
description: |
  tech_blog GitHub Pages 배포 스킬. gatsby build → gh-pages deploy 브랜치 배포를 실행하고
  배포 결과를 확인한다. 미커밋 변경사항이 있으면 경고 후 계속 진행한다.
  사용 시점: (1) 블로그 변경사항을 dev.k10n.me에 배포, (2) 빌드/배포 오류 진단.
  트리거 키워드: "배포", "deploy", "publish", "blog:deploy", "/blog:deploy".
model: haiku
allowed-tools:
  - Bash(bash /Users/changhwan/.claude/skills/blog:deploy/scripts/deploy.sh)
  - Read
---
# blog:deploy

tech_blog를 GitHub Pages(`dev.k10n.me`)에 배포한다.

---

## 배포 워크플로우

### Step 1 — 사전 확인

배포 전 현재 상태를 확인한다:

1. 작업 디렉토리: `/Users/changhwan/workspace/tech_blog`
2. 배포 명령: `gatsby build && gh-pages -d public -b deploy`
3. 대상: GitHub Pages `deploy` 브랜치 → `dev.k10n.me`

### Step 2 — 배포 실행

```bash
bash /Users/changhwan/.claude/skills/blog:deploy/scripts/deploy.sh
```

스크립트가 자동으로:
- 미커밋 변경사항 경고 출력
- `gatsby build` 실행 (public/ 생성)
- `gh-pages` 로 deploy 브랜치에 push

### Step 3 — 결과 보고

배포 성공 시:
```
==> 배포 완료!
URL: https://dev.k10n.me
```

실패 시 오류 메시지를 분석해서 원인을 사용자에게 알린다:
- **빌드 오류**: GraphQL 쿼리 오류, 누락된 frontmatter 필드, 잘못된 이미지 경로
- **gh-pages 오류**: 인증 문제, 네트워크 오류

---

## 주의사항

- 배포는 `main` 브랜치 코드 기준이 아닌 **현재 로컬 파일 기준**으로 빌드됨
- gatsby-config.js의 `siteMetadata`가 빌드 시 번들에 포함됨
- 배포 후 반영까지 GitHub Pages CDN 전파에 수 분이 소요될 수 있음
