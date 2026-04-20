---
name: blog:new-post
description: |
  tech_blog 신규 포스트 템플릿 생성 스킬. 제목/태그/날짜를 입력받아
  content/posts/<date>-<slug>/index.md와 디렉토리 구조를 자동 생성한다.
  사용 시점: (1) 새 블로그 포스트 작성 시작, (2) frontmatter 템플릿 자동 생성.
  트리거 키워드: "포스트 생성", "new post", "글 쓰기", "blog:new-post", "/blog:new-post".
model: haiku
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/blog:new-post/scripts/new_post.py *)
  - Read
  - Write
---
# blog:new-post

tech_blog에 새 포스트 디렉토리와 `index.md` 템플릿을 생성한다.

---

## 포스트 생성 워크플로우

### Step 1 — 정보 수집

사용자 메시지에서 다음을 파악한다. 누락된 필수 항목은 1회 질문한다.

| 항목 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `--title` | 필수 | — | 포스트 제목 (한글/영문) |
| `--slug` | 선택 | 제목에서 자동 생성 | URL slug (영문/숫자/하이픈) |
| `--tags` | 선택 | `DevOps` | 태그 목록 |
| `--date` | 선택 | 오늘 날짜 | `YYYY-MM-DD` 형식 |
| `--description` | 선택 | 빈 문자열 | SEO용 설명 (나중에 작성 가능) |

> **한글 제목 주의**: 한글 제목은 slug 자동 생성 시 결과가 `new-post`가 될 수 있다.
> 한글 제목 사용 시 `--slug`를 반드시 영문으로 지정하도록 안내한다.

### Step 2 — dry-run 확인

먼저 dry-run으로 생성 예정 내용을 보여준다:

```bash
python3 /Users/changhwan/.claude/skills/blog:new-post/scripts/new_post.py \
  --title "제목" \
  --slug "my-post-slug" \
  --tags Kubernetes DevOps \
  --date 2026-04-12 \
  --description "설명" \
  --dry-run
```

### Step 3 — 실제 생성

사용자 확인 후 (또는 확인 없이 바로 진행하라고 한 경우) `--dry-run` 없이 실행:

```bash
python3 /Users/changhwan/.claude/skills/blog:new-post/scripts/new_post.py \
  --title "제목" \
  --slug "my-post-slug" \
  --tags Kubernetes DevOps \
  --date 2026-04-12 \
  --description "설명"
```

### Step 4 — 완료 안내

생성 완료 후 사용자에게 다음 작업을 안내한다:

1. `thumbnail.png`를 포스트 디렉토리에 추가
2. `description` 필드 작성 (SEO 중요)
3. 본문 작성 시작

---

## 포스트 디렉토리 구조

```
content/posts/<date>-<slug>/
├── index.md          ← 생성됨 (frontmatter + 빈 본문)
└── thumbnail.png     ← 수동으로 추가 필요
```

## 생성되는 index.md 예시

```markdown
---
title: "Kubernetes 네트워킹 깊게 이해하기"
description: ""
date: 2026-04-12
thumbnail: ./thumbnail.png
tags:
  - Kubernetes
  - DevOps
---

# Kubernetes 네트워킹 깊게 이해하기
```

---

## 주의사항

- 같은 slug/날짜 조합의 디렉토리가 이미 존재하면 에러로 중단됨 (덮어쓰기 방지)
- thumbnail 없이 빌드하면 gatsby-source-filesystem이 이미지 없다는 에러를 낼 수 있음 — 임시 이미지를 먼저 넣거나 frontmatter의 thumbnail 필드를 제거하고 진행
