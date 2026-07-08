---
name: git:pr
description: |
  Kubernetes GitOps 레포에서 PR을 생성하는 스킬. git diff 분석으로 sphere/circle/env를 파악하고
  PR 제목·본문을 자동 생성한다. PR은 기본 ready(non-draft)로 오픈하며 리뷰어를 자동 제안한다.
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
- **PR은 기본 ready(non-draft)로 오픈** — 실제 merged PR 이력상 prod/global 변경 포함 여부와 무관하게 전부 non-draft로 오픈되어 왔다. 사용자가 명시적으로 요청할 때만 draft로 전환한다
- **리뷰어 자동 지정**: `src/ai-santa/` → `@riiid/mlops`, 나머지 → `@riiid/infra`
- **PR title = squash 후 main의 유일한 history 줄** — `git:commit`의 subject 규칙과 동일 기준을 적용한다 (아래 Title 컨벤션 참조)
- **PR 본문에 "변경 의도/배경(Why)" 필수** — diff는 "무엇을 바꿨는지"만 보여준다. 리뷰어·미래의 변경자가 안전하게 리뷰·롤백하려면 "왜 이 변경이 필요했는지"(유발한 문제·요구·배경)가 본문에 있어야 한다. 스크립트가 `## 변경 의도 / 배경 (Why)` 섹션에 `<!-- FILL_ME ... -->` placeholder를 넣으므로, LLM이 대화 맥락에서 이를 반드시 채운 뒤 PR을 생성한다 (아래 Step 4/5 게이트 참조).

## Title 컨벤션 (= git:commit subject 규칙과 정렬)

이 레포는 PR squash merge다. main `git log`에 남는 건 **PR title 한 줄**이며, 사람과 LLM이 history·맥락을 파악하는 1차 소스다.
따라서 title은 `git:commit`의 subject 규칙을 그대로 따른다:

- 형식 `type(sphere/circle): subject` — `동작 + 대상 + (가능하면) 의도/효과`를 한 줄로 압축
- 단순 `update N circles` / `update kubernetes manifests` / `Update X` 금지 — "왜/효과"를 한 조각 넣는다
- 길이 ~72자 가이드
- 원인 분석·해결 과정·롤백·blast radius는 title이 아닌 **PR 본문(Summary/테스트 플랜)**에 적는다 (커밋과 동일한 역할 분담)

| generic (지양) | history-친화 (지향) |
|----------------|---------------------|
| `chore(santa): update 3 circles` | `chore(santa): bump auth/worker/gateway images to dev-4164f0a` |
| `chore: update 5 circles across 2 spheres` | `fix: raise memory limits for tempo, loki to stop prod OOMKill` |

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
- `suggested_body` — 두괄식 3문장 요약(문제/해결/영향, 기술문서체) + 환경 요약 표 + 변경 내용 + 테스트 플랜 (Rollback 섹션 없음)
- `has_prod`, `has_global` — prod/global 변경 포함 여부 (본문/리뷰어 판단용, draft 판단에는 미사용)
- `suggest_draft` — 항상 `false` (팀 컨벤션: PR은 기본 ready로 오픈)
- `has_infra` — infra/observability sphere 포함 여부
- `needs_mlops_reviewer` — ai-santa sphere 포함 여부
- `affected_circles` — `[{sphere, circle, envs}]`

### Step 3 — 리뷰어 결정

| 조건 | 리뷰어 |
|------|--------|
| `src/ai-santa/` 변경 포함 | `riiid/mlops` |
| 그 외 (기본) | `riiid/infra` |
| 양쪽 모두 포함 | `riiid/infra,riiid/mlops` |

### Step 4 — PR 확정 (제목/Why 채우기, 확인 없이 진행)

**기본 동작: 확인을 구하지 않고 바로 확정한다.** title/draft/리뷰어는 기본값(컨벤션 준수 시 그대로,
draft=아니요)을 그대로 적용하고 Step 5로 진행한다. "이대로 진행할까요?" 같은 승인 대기 프롬프트를 만들지 않는다.
사용자가 직접 다른 제목/draft를 명시적으로 요청한 경우에만 그 값을 반영한다.

먼저 `suggested_title`을 **Title 컨벤션** 기준으로 평가한다.
스크립트는 다중 circle/sphere일 때 `update N circles` 같은 deterministic fallback을 낸다 —
이런 generic title이면 diff와 커밋 내용을 근거로 `동작 + 대상 + 의도/효과`로 다듬는다.
(단일 커밋 케이스는 커밋 subject가 그대로 흐르므로 추가 가공 불필요.) 다듬은 제목은 그대로 확정 — 재확인 불필요.

**Placeholder 채우기 (유일한 예외 게이트):**
- `suggested_body`에는 네 종류의 `<!-- FILL_ME ... -->` placeholder가 들어 있다.
  1. `## Summary` 첫 문장 — **문제 상황**을 짧은 한 문장으로.
  2. `## Summary` 둘째 문장 — **해결 방법**을 짧은 한 문장으로.
  3. `## Summary` 셋째 문장 — **영향 범위/주의사항**을 짧은 한 문장으로.
  4. `## 변경 의도 / 배경 (Why)` — 문제·요구·배경의 상세 서술 (위 1~2번 문장의 배경을 더 풀어쓴 버전; 무엇을 바꿨는지가 아니라 왜 바꾸는지).

**Summary 3문장 스타일 (필수 — 간결한 기술문서체 + 두괄식):**
- 각 문장은 **짧고 독립적인 선언문**이다. 쉼표·연결어(~해서, ~하며, ~고)로 여러 절을 이어 붙이지 않는다 — 한 문장 = 한 사실.
- 결론(무엇이 문제고 무엇을 했는지)이 먼저 오는 두괄식. 배경 설명이나 수식어를 앞세우지 않는다.
- 값·설정키·리소스명은 inline code로: `` `limits.cpu` ``, `` `amd64-mem-optimized` ``.
- 예시 (참고 문서체 그대로):
  ```
  amd64-mem-optimized NodePool에 taint가 없다.
  일반 워크로드가 유입되어 RI headroom을 소진한다.
  `limits.cpu`를 0으로 낮춰 신규 프로비저닝을 막는다.
  ```
- 나쁜 예 (긴 복문, 두괄식 아님): "prod `amd64-mem-optimized` NodePool이 taint 없이 일반 워크로드를 흡수해 RI headroom을 갉아먹는 문제를, 신규 프로비저닝 차단으로 임시 봉쇄한다."
- 네 placeholder 모두 **대화 맥락**(diff·커밋 메시지·이전 대화에서 언급된 알럿/장애/요구사항 등)으로 채운다. 대부분의 경우 diff/제목/커밋만으로 채울 수 있으므로 확인 없이 바로 채운다.
- **맥락이 불충분해 문제/해결 문장이나 Why를 채울 수 없는 경우에만** 진행을 멈추고 사용자에게 물어본다 — 이것이 이 스킬에서 유일하게 사용자 응답을 기다리는 지점이다.
- `<!-- FILL_ME -->` placeholder가 하나라도 남아 있는 본문으로는 **Step 5(PR 생성)로 진행하지 않는다.**

**Rollback 섹션은 만들지 않는다:**
- PR 본문에 별도 `## Rollback` 헤딩을 추가하지 않는다. GitOps 레포는 PR 자체가 단일 revert 대상이라 "이 PR을 되돌리는 방법"이 항상 "이 PR을 revert한다"로 동일하며, 별도 서술이 정보값을 더하지 않는다.
- 원복 조건이 사소하지 않은 경우(예: 순서 의존적 마이그레이션, 되돌릴 수 없는 데이터 변경)에는 `## 변경 의도 / 배경 (Why)` 안에 한 문장으로 녹여 서술한다 — 별도 섹션을 만들지 않는다.

확정된 내용은 Step 5 실행 직전에 FYI로 출력한다 (승인 대기가 아닌 통지):

```
────────────────────────────────────────────
 📋 PR 생성
────────────────────────────────────────────
 제목  : feat(tech/ai-gateway): update image to v1.2.3
 Draft : 아니요
 리뷰어: riiid/infra
────────────────────────────────────────────
 ## Summary
 (문제 상황 한 문장)
 (해결 방법 한 문장)
 (영향 범위/주의 한 문장)

 ### 환경 요약
 | 항목 | 내용 |
 ...
────────────────────────────────────────────
```

### Step 5 — PR 생성

**진행 전 확인**: `--body`로 넘길 본문에 `FILL_ME` placeholder가 남아 있으면 중단하고 Step 4의 placeholder 게이트로 돌아간다.

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
  --reviewer "riiid/infra"  # GIT_PR_SKILL=1
```

> `# GIT_PR_SKILL=1` 트레일링 주석은 필수다. kubernetes 레포의 PreToolUse 훅(`.claude/settings.local.json`)이 이 sentinel 없는 `gh pr create`를 차단해 "PR은 git:pr 스킬로만 생성" 정책을 강제한다. 이 줄을 지우지 말 것.

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
