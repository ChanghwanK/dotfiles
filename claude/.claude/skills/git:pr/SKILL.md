---
name: git:pr
description: |
  Kubernetes GitOps 레포에서 PR을 생성하는 스킬. git diff 분석으로 sphere/circle/env를 파악하고
  PR 제목·본문을 자동 생성한다. prod/global 변경 시 Draft PR을 권고하고 리뷰어를 자동 제안한다.
  사용 시점: (1) 커밋·푸시 후 PR 생성, (2) 변경 영향도 포함한 PR 작성, (3) git:commit → git:push 이후 최종 단계.
  트리거 키워드: "PR 만들어줘", "PR 생성", "pull request", "git:pr", "/git:pr".
model: sonnet
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(python3 /Users/changhwan/.claude/skills/git:pr/scripts/generate_pr.py *)
  - Read
---

# git:pr

변경된 sphere/circle/env를 자동 분석하여 Conventional Commits 제목과
테스트 플랜이 포함된 PR 본문을 생성하고 `gh pr create`로 PR을 생성한다.

---

## 핵심 원칙

- **PR은 커밋·푸시 완료 후 생성** — uncommitted 변경은 경고 후 계속
- **main 브랜치 직접 PR 생성 불가** — 별도 feature 브랜치 필요
- **prod/global 변경 시 Draft 권고** — 사용자 최종 확인 후 결정
- **리뷰어 자동 지정**: `src/ai-santa/` → `@riiid/mlops`, 나머지 → `@riiid/infra`

---

## 워크플로우

### Step 1 — Pre-flight 확인

병렬 실행:

```bash
git branch --show-current
git status --porcelain
git log main...HEAD --oneline
```

**중단 조건:**
- 브랜치 = `main` → "main 브랜치에서는 PR을 생성할 수 없습니다. feature 브랜치를 사용하세요"
- `git log` 비어있음 → "main 대비 커밋이 없습니다. 먼저 `git:commit`으로 커밋하세요"

**경고 후 계속:**
- uncommitted 파일 존재 → "⚠️ 미커밋 변경사항이 있습니다 (PR에 포함되지 않음)"

### Step 2 — 변경 분석

```bash
git diff main...HEAD --name-status > /tmp/git_pr_diff.txt
git log main...HEAD --format="%H %s" > /tmp/git_pr_log.txt
python3 /Users/changhwan/.claude/skills/git:pr/scripts/generate_pr.py \
  analyze /tmp/git_pr_diff.txt /tmp/git_pr_log.txt
```

JSON 출력 필드:
- `suggested_title` — `type(sphere/circle): message` 형식
- `suggested_body` — Summary 테이블 + 변경 내용 + 테스트 플랜
- `has_prod`, `has_global`, `suggest_draft` — Draft 여부
- `has_infra` — infra/observability sphere 포함 여부
- `needs_mlops_reviewer` — ai-santa sphere 포함 여부
- `affected_circles` — `[{sphere, circle, envs}]`

### Step 3 — 리뷰어 결정

| 조건 | 리뷰어 |
|------|--------|
| `src/ai-santa/` 변경 포함 | `riiid/mlops` |
| 그 외 (기본) | `riiid/infra` |
| 양쪽 모두 포함 | `riiid/infra,riiid/mlops` |

### Step 4 — PR 미리보기 및 사용자 확인

아래 형식으로 예정 PR을 출력한다:

```
────────────────────────────────────────────
 📋 PR 미리보기
────────────────────────────────────────────
 제목  : feat(tech/ai-gateway): update image to v1.2.3
 Draft : 아니요  ← prod/global 변경 포함 시 "예 (권고)"
 리뷰어: riiid/infra
────────────────────────────────────────────
 ## Summary
 | 항목 | 내용 |
 ...
────────────────────────────────────────────
```

사용자 확인 항목:
1. 제목 수정 여부 (엔터 = 그대로 사용)
2. Draft 여부 (`suggest_draft=true`이면 기본 Yes, 사용자가 변경 가능)

### Step 5 — PR 생성

upstream 없으면 먼저 push:

```bash
git push -u origin HEAD
```

이미 PR 존재 여부 확인:

```bash
gh pr view --json url 2>/dev/null
```

PR 이미 존재 시 URL 출력 후 중단.

PR 생성:

```bash
gh pr create \
  --title "<confirmed_title>" \
  --body "<generated_body>" \
  [--draft] \
  --reviewer "riiid/infra"
```

### Step 6 — 결과 검증 및 출력

```
✅ PR 생성 완료
URL: https://github.com/riiid/kubernetes/pull/NNNN

─── 다음 단계 ──────────────────────────────
1. 리뷰어(@riiid/infra) 승인 후 머지
2. 머지 후: /devops:deploy-check 으로 ArgoCD sync/Pod 상태 확인
────────────────────────────────────────────
```

`gh pr view` 로 PR URL이 실제로 존재하는지 MUST 확인한다.

---

## 오류 처리

| 상황 | 대응 |
|------|------|
| `gh` CLI 미설치 | "gh CLI가 필요합니다: `brew install gh && gh auth login`" |
| GitHub 인증 없음 | "`gh auth status` 확인 후 `gh auth login` 실행" |
| PR 이미 존재 | "이미 PR이 열려 있습니다: {url}" 출력 후 중단 |
| push 실패 | 에러 메시지 그대로 출력 후 중단 |
| 변경 파일 없음 | "kubernetes 표준 경로(`src/sphere/circle/`) 외 변경만 감지됨 — 제목/본문 직접 입력" 후 계속 |
