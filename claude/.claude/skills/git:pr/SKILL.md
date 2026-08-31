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

변경된 sphere/circle/env를 자동 분석하여 `[env] sphere/circle: subject` 형식의 제목과
테스트 플랜이 포함된 PR 본문을 생성하고 `gh pr create`로 PR을 생성한다.

---

## 핵심 원칙

- **PR은 커밋·푸시 완료 후 생성**: uncommitted 변경은 경고 후 계속
- **main 브랜치 직접 PR 생성 불가**: 별도 feature 브랜치 필요
- **PR은 기본 ready(non-draft)로 오픈**: 실제 merged PR 이력상 prod/global 변경 포함 여부와 무관하게 전부 non-draft로 오픈되어 왔다. 사용자가 명시적으로 요청할 때만 draft로 전환한다
- **리뷰어 자동 지정**: `src/ai-santa/` → `@riiid/mlops`, 나머지 → `@riiid/infra`
- **PR title은 커밋에서 파생하지 않는다**: 커밋 subject를 복사하거나 커밋 type을 물려받지 않는다. PR은 커밋 하나가 아니라 변경 전체이므로 title도 PR 전체 의도로 새로 쓴다 (아래 Title 컨벤션 참조)
- **PR 본문에 "변경 의도/배경(Why)" 필수**: diff는 "무엇을 바꿨는지"만 보여준다. 리뷰어·미래의 변경자가 안전하게 리뷰·롤백하려면 "왜 이 변경이 필요했는지"(유발한 문제·요구·배경)가 본문에 있어야 한다. 스크립트가 `## 변경 의도 / 배경 (Why)` 섹션에 `<!-- FILL_ME ... -->` placeholder를 넣으므로, LLM이 대화 맥락에서 이를 반드시 채운 뒤 PR을 생성한다 (아래 Step 4/5 게이트 참조).

## Title 컨벤션 (PR 전용 형식)

**형식: `[env] sphere/circle: 동작 + 대상 + (가능하면) 효과`**

이 레포는 PR squash merge다. main `git log`에 남는 건 **PR title 한 줄**이며, 동시에 리뷰어가
PR 목록에서 blast radius를 판단하는 1차 신호다. 그래서 title은 커밋 규칙을 물려받는 대신
**환경 → 대상 → 내용** 순서를 고정 슬롯으로 갖는다. 리뷰어가 매번 같은 자리에서 prod 여부를 찾게 하려는 것이다.

### 슬롯 1: `[env]` (스크립트가 diff에서 결정, 임의 수정 금지)

- 표기 순서 고정: `common` → `dev` → `stg` → `prod` → `global` → `idc` → `office`
- `common/`·`applicationset.jsonnet` 변경은 그 circle의 전 환경에 반영되므로 `common`을 포함한다 (예: `[common,prod]`)
- 클러스터에 배포되지 않는 변경(`devops-wiki/`, 스크립트, `.github/`)은 `[repo]`
- 커밋 type(`chore`/`feat`/`fix`)은 이 슬롯에 들어가지 않는다: 유형 판단은 본문 Summary가 담당한다

### 슬롯 2: `sphere/circle` (스크립트가 결정)

| 변경 범위 | 표기 |
|-----------|------|
| circle 1개 | `observability/alloy` |
| 같은 sphere, circle 3개 이하 | `santa/authentication,gateway,worker` |
| 같은 sphere, circle 4개 이상 | `santa` (sphere만, 개수는 쓰지 않는다) |
| 여러 sphere | `infra,observability` |
| src 밖 변경만 | 슬롯 생략 (`[repo]: ...`) |

### 슬롯 3: subject (LLM이 작성)

- `동작 + 대상 + (가능하면) 효과`를 한 줄로 압축한다. 길이 가이드는 슬롯 포함 ~72자
- **커밋 subject 복사 금지**: 커밋은 작업 단위, PR은 변경 전체다. 커밋 3개짜리 PR의 title이 첫 커밋만 설명하면 squash 후 history가 나머지 2개를 잃는다
- `update N circles` / `여러 서비스 설정 변경` 같은 개수·범주 서술 금지: 개수는 이미 슬롯 2에 있으므로 subject에는 **공통 의도**를 적는다
- 환경명을 subject에 중복해 쓰지 않는다: `[prod] observability/alloy: prod Alloy에 카운터 추가` (X)

| 지양 | 지향 |
|------|------|
| `[dev] santa: update 3 circles` | `[dev] santa/authentication,gateway,worker: 이미지를 dev-4164f0a로 일괄 승격` |
| `[prod] observability/tempo,loki: 메모리 limit 수정` | `[prod] observability/loki,tempo: 메모리 limit 상향으로 OOMKill 차단` |
| `[stg] infra/argo-rollouts: oauth2-proxy 변경` | `[stg] infra/argo-rollouts: oauth2-proxy OIDC를 okta.socra.ai로 전환 (2/3)` |

원인 분석·해결 과정·blast radius 서술은 title이 아닌 **PR 본문(Summary / 변경 의도)**에 적는다.

---

## 워크플로우

### Step 1: Pre-flight 확인

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

### Step 2: 변경 분석

```bash
git diff main...HEAD --name-status > /tmp/git_pr_diff.txt
git log main...HEAD --format="%H %s" > /tmp/git_pr_log.txt
python3 /Users/changhwan/.claude/skills/git:pr/scripts/generate_pr.py \
  analyze /tmp/git_pr_diff.txt /tmp/git_pr_log.txt
```

JSON 출력 필드:
- `title_prefix`: `[env] sphere/circle` (diff에서 결정된 고정 슬롯, 그대로 사용한다)
- `suggested_title`: `title_prefix` + `: ` + subject `<!-- FILL_ME ... -->` placeholder
- `subject_hints`: 커밋 subject에서 `type(scope):`를 벗겨낸 목록. **title 후보가 아니라 참고 재료다** (그대로 복사하지 않는다)
- `suggested_body`: 두괄식 3불릿 요약(문제/해결/영향, 높임말 기술문서체) + 환경 요약 표 + 변경 내용 + 테스트 플랜 (Rollback 섹션 없음)
- `has_prod`, `has_global`: prod/global 변경 포함 여부 (본문/리뷰어 판단용, draft 판단에는 미사용)
- `suggest_draft`: 항상 `false` (팀 컨벤션: PR은 기본 ready로 오픈)
- `has_infra`: infra/observability sphere 포함 여부
- `needs_mlops_reviewer`: ai-santa sphere 포함 여부
- `affected_circles`: `[{sphere, circle, envs}]`

### Step 2.5: Wiki 영향 감지 (자동, 조용함)

이 PR의 diff가 DevOps Infra Wiki 문서의 `verify:` REPO 대상(`file`/`component`/`exists`)과
겹치는지 확인한다. 매치가 없으면 완전히 침묵한다 — 매 PR마다 뜨는 잡음을 만들지 않는 것이
최우선 설계 기준이다.

```bash
python3 devops-wiki/scripts/verify-impact.py --changed-files "$(git diff main...HEAD --name-only)"
```

출력이 있으면(비어있지 않으면) Step 4의 FYI 블록 직전에 그대로 보여준다:

```
⚠️  recompile 후보 문서:
  📄 02-context/observability-stack.md
     - Loki chart (prod)  (changed: src/observability/loki/infra-k8s-prod/kustomization.yaml)
```

**PR 본문에는 넣지 않는다.** `## 변경 의도 / 배경 (Why)`나 Summary 3불릿 규칙과는 무관한
별개 관심사이므로, 채팅 메시지로만 보여주고 `suggested_body`에 섞지 않는다. 문서 프로즈를
직접 고치는 것도 이 스킬의 역할이 아니다 — 필요하면 `/devops:wiki:recompile` 또는
`wiki-audit.py --fact-check`로 이어서 확인한다. (`kubernetes` 레포 전용 스텝 — 이 스크립트는
그 레포의 `devops-wiki/`에만 존재한다.)

### Step 3: 리뷰어 결정

| 조건 | 리뷰어 |
|------|--------|
| `src/ai-santa/` 변경 포함 | `riiid/mlops` |
| 그 외 (기본) | `riiid/infra` |
| 양쪽 모두 포함 | `riiid/infra,riiid/mlops` |

### Step 4: PR 확정 (제목/Why 채우기, 확인 없이 진행)

**기본 동작: 확인을 구하지 않고 바로 확정한다.** title/draft/리뷰어는 기본값(컨벤션 준수 시 그대로,
draft=아니요)을 그대로 적용하고 Step 5로 진행한다. "이대로 진행할까요?" 같은 승인 대기 프롬프트를 만들지 않는다.
사용자가 직접 다른 제목/draft를 명시적으로 요청한 경우에만 그 값을 반영한다.

**Title 확정 (슬롯 3만 작성):**
- `title_prefix`(`[env] sphere/circle`)는 diff에서 결정된 값이므로 **그대로 쓴다.** 환경·대상을 임의로 줄이거나 바꾸지 않는다.
- subject placeholder만 채운다. 재료는 diff·커밋 전체·대화 맥락이며, `subject_hints`는 참고용이다.
  커밋이 하나뿐이어도 그 subject를 그대로 옮기지 않고, PR 전체를 설명하는 문장인지 확인한 뒤 쓴다.
- 채운 제목은 그대로 확정한다 (재확인 불필요).

**Placeholder 채우기 (유일한 예외 게이트):**
- title에 subject placeholder 1개, `suggested_body`에 네 종류의 `<!-- FILL_ME ... -->` placeholder가 들어 있다.
  1. `## Summary` 첫 불릿: **문제 상황**을 짧은 한 문장으로.
  2. `## Summary` 둘째 불릿: **해결 방법**을 짧은 한 문장으로.
  3. `## Summary` 셋째 불릿: **영향 범위/주의사항**을 짧은 한 문장으로.
  4. `## 변경 의도 / 배경 (Why)`: 문제·요구·배경의 상세 서술 (위 1~2번 불릿의 배경을 더 풀어쓴 버전이며, 무엇을 바꿨는지가 아니라 왜 바꾸는지를 담는다).

**Summary 3불릿 스타일 (필수: 불릿 리스트 + 높임말 + 두괄식):**
- 문단 나열이 아닌 **불릿 리스트**로 작성한다. 세 문장을 이어붙인 문단으로 만들지 않는다.
- 종결어미는 **높임말**(`~합니다`, `~했습니다`, `~입니다`)을 사용한다. 평서체(`~한다`, `~했다`, `~이다`)로 끝내지 않는다.
- 각 불릿은 **짧고 독립적인 선언문**이다. 쉼표·연결어(~해서, ~하며, ~고)로 여러 절을 이어 붙이지 않는다: 한 불릿은 한 사실만 담는다.
- 결론(무엇이 문제고 무엇을 했는지)이 먼저 오는 두괄식. 배경 설명이나 수식어를 앞세우지 않는다.
- 값·설정키·리소스명은 inline code로: `` `limits.cpu` ``, `` `amd64-mem-optimized` ``.
- 예시 (참고 문서체 그대로):
  ```
  - `amd64-mem-optimized` NodePool에 taint가 없습니다.
  - 일반 워크로드가 유입되어 RI headroom을 소진합니다.
  - `limits.cpu`를 0으로 낮춰 신규 프로비저닝을 막습니다.
  ```
- 나쁜 예 (문단 나열, 평서체, 긴 복문, 두괄식 아님): "prod `amd64-mem-optimized` NodePool이 taint 없이 일반 워크로드를 흡수해 RI headroom을 갉아먹는 문제를, 신규 프로비저닝 차단으로 임시 봉쇄한다."
- `## 변경 의도 / 배경 (Why)`는 원인 분석·논증이 목적인 문단이라 연결된 서술을 허용하지만, 종결어미는 동일하게 높임말을 사용한다.
- 네 placeholder 모두 **대화 맥락**(diff·커밋 메시지·이전 대화에서 언급된 알럿/장애/요구사항 등)으로 채운다. 대부분의 경우 diff/제목/커밋만으로 채울 수 있으므로 확인 없이 바로 채운다.
- **맥락이 불충분해 문제/해결 문장이나 Why를 채울 수 없는 경우에만** 진행을 멈추고 사용자에게 물어본다. 이것이 이 스킬에서 유일하게 사용자 응답을 기다리는 지점이다.
- `<!-- FILL_ME -->` placeholder가 **제목 또는 본문**에 하나라도 남아 있으면 **Step 5(PR 생성)로 진행하지 않는다.**

**Rollback 섹션은 만들지 않는다:**
- PR 본문에 별도 `## Rollback` 헤딩을 추가하지 않는다. GitOps 레포는 PR 자체가 단일 revert 대상이라 "이 PR을 되돌리는 방법"이 항상 "이 PR을 revert한다"로 동일하며, 별도 서술이 정보값을 더하지 않는다.
- 원복 조건이 사소하지 않은 경우(예: 순서 의존적 마이그레이션, 되돌릴 수 없는 데이터 변경)에는 `## 변경 의도 / 배경 (Why)` 안에 한 문장으로 녹여 서술하며, 별도 섹션은 만들지 않는다.

확정된 내용은 Step 5 실행 직전에 FYI로 출력한다 (승인 대기가 아닌 통지):

```
────────────────────────────────────────────
 📋 PR 생성
────────────────────────────────────────────
 제목  : [dev,stg] tech/ai-gateway: 이미지를 v1.2.3으로 올려 토큰 만료 버그 수정
 Draft : 아니요
 리뷰어: riiid/infra
────────────────────────────────────────────
 ## Summary
 - (문제 상황 한 문장, 높임말)
 - (해결 방법 한 문장, 높임말)
 - (영향 범위/주의 한 문장, 높임말)

 ### 환경 요약
 | 항목 | 내용 |
 ...
────────────────────────────────────────────
```

### Step 5: PR 생성

**진행 전 확인**: `--title`·`--body`로 넘길 제목과 본문에 `FILL_ME` placeholder가 남아 있으면 중단하고 Step 4의 placeholder 게이트로 돌아간다.

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

### Step 6: 결과 검증 및 출력

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
| 변경 파일 없음 | "kubernetes 표준 경로(`src/sphere/circle/`) 외 변경만 감지됨: 제목/본문 직접 입력" 후 계속 |
