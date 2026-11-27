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

diff에서 sphere/circle/env를 분석해 `[env] sphere/circle: subject` 제목과 본문을 만들고 `gh pr create`로 PR을 연다.

## 핵심 원칙

- 커밋·푸시 완료 후 생성한다. uncommitted 변경은 경고 후 계속
- PR은 ready(non-draft)로 연다. draft는 사용자가 명시적으로 요청할 때만
- PR title은 커밋 subject를 복사하거나 커밋 type을 물려받지 않고, PR 전체 의도로 새로 쓴다
- 본문의 `## 변경 의도 / 배경 (Why)` 필수: diff는 무엇만 보여 주므로, 왜 바꿨는지를 대화 맥락에서 채운다(Step 4 게이트)

## Title 컨벤션

**형식: `[env] sphere/circle: 동작 + 대상 + (가능하면) 효과`**

squash merge라 main `git log`에는 PR title 한 줄만 남고, 리뷰어는 이 자리에서 prod 여부(blast radius)를 본다. 그래서 환경 → 대상 → 내용 순서를 고정한다.

### 슬롯 1: `[env]` (스크립트가 diff에서 결정, 임의 수정 금지)

- 표기 순서 고정: `common` → `dev` → `stg` → `prod` → `global` → `idc` → `office`
- `common/`·`applicationset.jsonnet` 변경은 그 circle 전 환경에 반영되므로 `common` 포함 (예: `[common,prod]`)
- 클러스터에 배포되지 않는 변경(`devops-wiki/`, 스크립트, `.github/`)은 `[repo]`
- 커밋 type(`chore`/`feat`/`fix`)은 넣지 않는다

### 슬롯 2: `sphere/circle` (스크립트가 결정)

| 변경 범위 | 표기 |
|-----------|------|
| circle 1개 | `observability/alloy` |
| 같은 sphere, circle 3개 이하 | `santa/authentication,gateway,worker` |
| 같은 sphere, circle 4개 이상 | `santa` (sphere만, 개수는 쓰지 않는다) |
| 여러 sphere | `infra,observability` |
| src 밖 변경만 | 슬롯 생략 (`[repo]: ...`) |

### 슬롯 3: subject (LLM이 작성)

- `동작 + 대상 + (가능하면) 효과` 한 줄, 슬롯 포함 ~72자
- 커밋 subject 복사 금지: 커밋 3개짜리 PR의 title이 첫 커밋만 설명하면 squash 후 나머지 2개가 history에서 사라진다
- `update N circles` / `여러 서비스 설정 변경` 같은 개수·범주 서술 금지: 공통 의도를 쓴다
- 환경명을 subject에 중복하지 않는다: `[prod] observability/alloy: prod Alloy에 카운터 추가` (X)
- 원인 분석·해결 과정·blast radius는 title이 아닌 본문에 쓴다

| 지양 | 지향 |
|------|------|
| `[dev] santa: update 3 circles` | `[dev] santa/authentication,gateway,worker: 이미지를 dev-4164f0a로 일괄 승격` |
| `[prod] observability/tempo,loki: 메모리 limit 수정` | `[prod] observability/loki,tempo: 메모리 limit 상향으로 OOMKill 차단` |
| `[stg] infra/argo-rollouts: oauth2-proxy 변경` | `[stg] infra/argo-rollouts: oauth2-proxy OIDC를 okta.socra.ai로 전환 (2/3)` |

## 워크플로우

### Step 1: Pre-flight 확인

각각 별도 명령으로 실행한다(`&&`·`;`로 묶지 않는다. worktree 격리 세션은 복합 git 명령을 거부한다):

```bash
git branch --show-current
git status --porcelain
```

**중단 조건:**
- 브랜치 = `main` → "main 브랜치에서는 PR을 생성할 수 없습니다. feature 브랜치를 사용하세요"
- Step 2 결과의 `commit_count`가 0 → "origin/main 대비 커밋이 없습니다. 먼저 `git:commit`으로 커밋하세요"

**경고 후 계속:** uncommitted 파일 존재 → "미커밋 변경사항이 있습니다 (PR에 포함되지 않음)"

### Step 2: 변경 분석

```bash
python3 /Users/changhwan/.claude/skills/git:pr/scripts/generate_pr.py analyze
```

스크립트가 `origin/main`을 fetch하고 diff(`origin/main...HEAD`)와 커밋(`origin/main..HEAD`)을 직접 읽는다. diff를 파일로 리다이렉트하거나 git 명령을 따로 조합하지 않는다.
- 기준은 로컬 `main`이 아니라 `origin/main`이다(worktree의 로컬 main은 뒤처져 남의 커밋이 섞인다)
- base가 다른 레포는 `--base origin/<branch>`, 오프라인이면 `--no-fetch`
- exit 1이면 stderr의 git 오류를 그대로 보여 주고 중단
- kubernetes 표준 경로(`src/sphere/circle/`) 밖 변경만 감지되면 제목/본문을 직접 작성하고 계속

JSON 출력 필드:
- `base`, `fetched`: `fetched: false`면 FYI 블록에 "origin/main fetch 실패: 원격 최신 상태가 아닐 수 있음" 한 줄 추가
- `commit_count`: Step 1 중단 조건에 쓴다
- `title_prefix`: `[env] sphere/circle` 고정 슬롯
- `suggested_title`: `title_prefix` + `: ` + subject `<!-- FILL_ME ... -->` placeholder
- `subject_hints`: 커밋 subject에서 `type(scope):`를 벗긴 목록. title 후보가 아니라 참고 재료다
- `suggested_body`: 3불릿 Summary + 환경 요약 표 + 변경 내용 + 테스트 플랜 (Rollback 섹션 없음)
- `needs_mlops_reviewer`: ai-santa sphere 포함 여부(Step 3)

### Step 2.5: Wiki 영향 감지 (자동, 조용함)

```bash
python3 /Users/changhwan/.claude/skills/git:pr/scripts/generate_pr.py wiki-impact
```

- 출력이 비어 있으면(매치 없음, 또는 `devops-wiki/scripts/verify-impact.py`가 없는 레포) 아무 말도 하지 않는다
- 출력이 있으면 Step 4의 FYI 블록 직전에 채팅으로 그대로 보여 준다. PR 본문(`suggested_body`)에는 넣지 않고, 문서도 직접 고치지 않는다. 후속은 `/devops:wiki:recompile` 또는 `wiki-audit.py --fact-check`

### Step 3: 리뷰어 결정

| 조건 | 리뷰어 |
|------|--------|
| `src/ai-santa/` 변경 포함 | `riiid/mlops` |
| 그 외 (기본) | `riiid/infra` |
| 양쪽 모두 포함 | `riiid/infra,riiid/mlops` |

### Step 4: PR 확정 (제목/Why 채우기, 확인 없이 진행)

승인을 구하지 않고 확정한다. title/리뷰어는 기본값, draft=아니요로 Step 5로 간다. "이대로 진행할까요?" 프롬프트를 만들지 않는다. 사용자가 다른 제목/draft를 명시한 경우에만 반영한다.

**Title:** `title_prefix`는 그대로 쓴다(환경·대상을 줄이거나 바꾸지 않는다). subject placeholder만 diff·커밋 전체·대화 맥락으로 채운다. 커밋이 하나여도 그 subject를 옮기지 않고 PR 전체를 설명하는지 확인한다.

**Placeholder 게이트 (유일한 예외):** `suggested_body`의 `<!-- FILL_ME ... -->` 네 개를 채운다.
1. `## Summary` 첫 불릿: 문제 상황
2. `## Summary` 둘째 불릿: 해결 방법
3. `## Summary` 셋째 불릿: 영향 범위/주의사항
4. `## 변경 의도 / 배경 (Why)`: 1~2번의 배경을 풀어 쓴 문제·요구·배경(무엇이 아니라 왜)

- 대화 맥락(diff·커밋·앞서 언급된 알럿/장애/요구)으로 바로 채운다
- 맥락이 부족해 문제/해결/Why를 채울 수 없을 때만 멈추고 묻는다. 이 스킬에서 사용자 응답을 기다리는 유일한 지점이다
- 제목 또는 본문에 `<!-- FILL_ME -->`가 하나라도 남으면 Step 5로 가지 않는다

**Summary 3불릿 스타일 (필수):**
- 문단이 아닌 불릿 리스트
- 높임말 종결(`~합니다`, `~했습니다`, `~입니다`). 평서체(`~한다`) 금지
- 한 불릿에 한 사실. 쉼표·연결어(~해서, ~하며, ~고)로 절을 잇지 않는다
- 두괄식: 무엇이 문제고 무엇을 했는지 먼저, 배경·수식어를 앞세우지 않는다
- 값·설정키·리소스명은 inline code
- 예시:
  ```
  - `amd64-mem-optimized` NodePool에 taint가 없습니다.
  - 일반 워크로드가 유입되어 RI headroom을 소진합니다.
  - `limits.cpu`를 0으로 낮춰 신규 프로비저닝을 막습니다.
  ```
- `## 변경 의도 / 배경 (Why)`는 연결된 서술을 허용하되 종결은 높임말

**Rollback 섹션은 만들지 않는다:** GitOps에서 되돌리는 방법은 "이 PR을 revert" 하나라 정보가 없다. 원복이 사소하지 않으면(순서 의존 마이그레이션, 되돌릴 수 없는 데이터 변경) Why 안에 한 문장으로 쓴다.

확정 내용은 Step 5 직전에 FYI로 출력한다(승인 대기 아님):

```
PR 생성
제목  : [dev,stg] tech/ai-gateway: 이미지를 v1.2.3으로 올려 토큰 만료 버그 수정
Draft : 아니요
리뷰어: riiid/infra
(본문)
```

### Step 5: PR 생성

`--title`·`--body`에 `FILL_ME`가 남아 있으면 중단하고 Step 4 게이트로 돌아간다.

upstream 없으면 먼저 push:

```bash
git push -u origin HEAD
```

PR이 이미 있으면 URL 출력 후 중단:

```bash
gh pr view --json url 2>/dev/null
```

PR 생성:

```bash
gh pr create \
  --title "<confirmed_title>" \
  --body "<generated_body>" \
  [--draft] \
  --reviewer "riiid/infra"  # GIT_PR_SKILL=1
```

> `# GIT_PR_SKILL=1` 트레일링 주석은 필수다. kubernetes 레포의 PreToolUse 훅(`.claude/settings.local.json`)이 이 sentinel 없는 `gh pr create`를 차단한다. 지우지 말 것.

### Step 6: 결과 검증 및 출력

`gh pr view`로 PR URL이 실제로 존재하는지 MUST 확인한 뒤 출력한다:

```
PR 생성 완료: https://github.com/riiid/kubernetes/pull/NNNN
다음: 리뷰어 승인 후 머지, 머지 후 /devops:deploy-check로 ArgoCD sync/Pod 상태 확인
```
