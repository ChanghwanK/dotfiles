---
name: git:commit
description: |
  Staged 변경사항을 분석하고 커밋 컨벤션에 맞게 커밋한다. push는 하지 않는다.
  사용 시점: (1) 변경사항 커밋, (2) 커밋 메시지 자동 생성.
  트리거 키워드: "/git:commit", "커밋", "커밋해줘".
model: sonnet
allowed-tools:
  - Bash(git *)
---

# git:commit

## Step 1: Staged 변경사항 수집

```bash
git diff --cached --name-only
```

staged 파일이 없으면 `git status --short`로 전체 변경을 본다.
- 변경이 없으면 "커밋할 변경사항이 없습니다." 출력 후 종료
- 이번 작업에서 변경한 파일만 경로를 지정해 스테이징한다(`git add .` 금지):

```bash
git add <path1> <path2> ...
```

- 이번 작업과 무관해 보이는 변경(다른 수정 파일, untracked)은 스테이징하지 않고, 스테이징한 목록과 함께 보여 주며 포함 여부를 묻는다

스테이징 후 `git diff --cached`로 staged diff를 수집한다.

## Step 2: Commit Message 생성

**형식:** `type(scope): subject` + 빈 줄 + body 1~3 bullet (Conventional Commits)

커밋은 "무엇을 / 왜" 요약만 담고, 원인 분석·해결 과정·롤백·blast radius는 PR 본문에 쓴다. PR squash merge라 main에는 subject 한 줄(PR title)만 남으므로 정보는 subject에 먼저 압축한다.

**Type:** `chore`(설정/인프라: image tag, values, config), `feat`(새 리소스/기능), `fix`(버그), `docs`(문서만), `refactor`(기능 변경 없는 구조 개선)

**Subject 규칙 (가장 중요):**
- `동작 + 대상 + (가능하면) 의도/효과` 한 줄, ~72자. 넘으면 body로 빼지 말고 subject에서 압축
- 단순 `Update X` / `Change Y` 금지: "왜/효과"를 한 조각 넣는다

| generic (지양) | history-친화 (지향) |
|----------------|---------------------|
| `chore(santa/authentication): Update image tag in dev` | `chore(santa/authentication): bump image to dev-4164f0a for OTel trace fix` |
| `chore(observability/alloy): update config` | `fix(observability/alloy): set GOMEMLIMIT to prevent OOMKill in prod` |
| `chore(data-platform): exclude columns` | `chore(data-platform): exclude large JSON columns from k6 essay CDC` |

**kubernetes 레포 scope 규칙** (staged 경로가 `src/{sphere}/{circle}/infra-k8s-{env}/` 패턴일 때):
- 단일 circle, 단일 env → `chore(santa/authentication): ... in dev`
- 단일 circle, 다중 env → `chore(santa/authentication): ... in dev, stg`
- 다중 circle, 단일 sphere → `chore(santa): ... for authentication, worker in dev`
- 다중 sphere → scope 없이 기술

**Body 규칙:**
- bullet마다 "무엇을 왜" 한 줄. diff가 자명하게 말하는 내용을 반복하지 않는다
- 불확실한 의도는 단정하지 않는다(틀린 body는 안 적느니만 못하다)

**공통:** subject·body 모두 영어, 명령형 현재형. 이모지 금지, Co-Authored-By 라인 금지.

## Step 3: 민감 파일 체크

staged에 `.env`, `.env.*`, `*credentials*`, `*secret*`, `*.pem`, `*.key`가 있으면 커밋 전 경고하고 진행 여부를 확인한다.

## Step 4: Commit 실행

```bash
git commit -m "$(cat <<'EOF'
type(scope): subject

- body 요약 bullet 1
- body 요약 bullet 2
EOF
)"
```

- pre-commit hook 실패 시 문제를 고친 뒤 새 커밋을 만든다(amend 금지)
- push는 하지 않는다

## Step 5: 결과 출력

`git commit` 출력의 커밋 해시와 subject를 보여 준다.
