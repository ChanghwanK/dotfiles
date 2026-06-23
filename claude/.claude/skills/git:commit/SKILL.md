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

# Commit Skill: Git 커밋 워크플로우

Staged 파일을 분석하고 커밋 컨벤션에 맞게 커밋한다.

---

## 워크플로우

### Step 1 — Staged 변경사항 수집

```bash
git diff --cached --name-only   # staged 파일 목록 확인
```

**staged 파일이 없으면 → 자동 스테이징 절차:**

```bash
git status --short   # 전체 변경사항 파악
```

- 변경 파일이 없으면 → "커밋할 변경사항이 없습니다." 출력 후 종료.
- 변경 파일이 있으면 → 파일 목록을 다음 형식으로 출력 후 `git add .` 실행:

```
스테이징할 파일:
  M  src/tech/ai-gateway/infra-k8s-dev/values.yaml
  M  src/tech/ai-gateway/infra-k8s-stg/values.yaml
  ?? src/tech/new-service/common/values.yaml
→ git add . 실행
```

`git add .` 실행 후 `git diff --cached` 로 staged diff를 수집하고 Step 2로 진행한다.

### Step 2 — 레포 타입 감지

staged 파일 경로를 분석해 레포 타입을 결정한다:

| 조건 | 레포 타입 |
|------|-----------|
| `src/{sphere}/{circle}/infra-k8s-{env}/` 패턴 존재 | kubernetes |
| `.tf` 파일 또는 `terraform/` 경로 존재 | terraform |
| 그 외 | general |

### Step 3 — Commit Message 생성

**형식:** `type(scope): subject` + 빈 줄 + body 요약 (Conventional Commits)

커밋 메시지는 사람과 LLM이 나중에 `git log`로 작업 history와 맥락을 파악하는 1차 소스다.
**역할 분담:** 커밋은 "무엇을 / 왜" 요약만, 원인 분석·해결 과정·롤백·blast radius는 PR 본문에 적는다.

> **squash 인지:** 이 레포는 PR squash merge다. main에 남는 건 subject 한 줄(= PR title)뿐이며 body는 휘발한다.
> 따라서 정보 밀도는 subject에 우선 압축하고, body 요약은 feature 브랜치·PR 리뷰·로컬 history 용도다.

**Type 선택:**
- `chore` — 설정/인프라 변경 (image tag, values, config)
- `feat` — 새 리소스/기능 추가
- `fix` — 버그 수정
- `docs` — 문서만 변경
- `refactor` — 기능 변경 없는 구조 개선

**Subject 규칙 (가장 중요):**
- `동작 + 대상 + (가능하면) 의도/효과`를 한 줄로 압축한다.
- 단순 `Update X` / `Change Y` 금지 — diff만 봐도 아는 "무엇"만 적지 말고 "왜/효과"를 한 조각 넣는다.
- 길이 ~72자 가이드. 넘으면 body로 빼지 말고 subject에서 의도를 압축한다.

| generic (지양) | history-친화 (지향) |
|----------------|---------------------|
| `chore(santa/authentication): Update image tag in dev` | `chore(santa/authentication): bump image to dev-4164f0a for OTel trace fix` |
| `chore(observability/alloy): update config` | `fix(observability/alloy): set GOMEMLIMIT to prevent OOMKill in prod` |
| `chore(data-platform): exclude columns` | `chore(data-platform): exclude large JSON columns from k6 essay CDC` |

**kubernetes 레포 scope 규칙:**
- 단일 circle, 단일 env → `chore(santa/authentication): ... in dev`
- 단일 circle, 다중 env → `chore(santa/authentication): ... in dev, stg`
- 다중 circle, 단일 sphere → `chore(santa): ... for authentication, worker in dev`
- 다중 sphere → scope 없이 기술

**Body 요약 규칙:**
- subject 다음 빈 줄 뒤에 **1~3개 bullet**로 변경 요약을 적는다.
- 각 bullet은 "무엇을 왜" 한 줄. diff가 자명하게 말하는 내용을 산문으로 반복하지 않는다.
- 추론이 불확실한 의도는 단정하지 않는다 (틀린 body는 안 적느니만 못함).
- 원인 분석·재현 절차·롤백 방법·영향 범위는 body에 넣지 않고 PR로 미룬다.

```
fix(observability/alloy): set GOMEMLIMIT to prevent OOMKill in prod

- Alloy pod가 limit 미만에서도 Go heap 누적으로 OOMKill되던 문제 완화
- GOMEMLIMIT을 limit의 ~90%로 설정해 GC를 조기 유발
```

**공통 규칙:**
- 이모지 금지, Co-Authored-By 금지
- subject·body 모두 영어, 명령형 현재형 (Update, Add, Fix, Remove...)

### Step 4 — 민감 파일 체크

아래 패턴 파일은 staged에 포함되어 있어도 커밋 전 경고 후 진행 여부를 확인한다:
- `.env`, `.env.*`, `*credentials*`, `*secret*`, `*.pem`, `*.key`

### Step 5 — Commit 실행

```bash
git commit -m "$(cat <<'EOF'
type(scope): subject

- body 요약 bullet 1
- body 요약 bullet 2
EOF
)"
```

pre-commit hook 실패 시: 문제를 수정한 후 **새 커밋 생성** (amend 금지).

### Step 6 — 결과 출력

`git commit` 출력에서 커밋 해시와 메시지를 직접 표시한다.

```
커밋 완료:
─────────────────────────────
chore(santa/authentication): Update image tag in dev
─────────────────────────────
```

---

## 규칙 요약

- subject는 `동작 + 대상 + 의도/효과` 한 줄(~72자). generic한 `Update X` 금지
- subject 다음 빈 줄 + body 1~3 bullet로 "무엇을 왜" 요약. diff 자명한 내용 반복 금지
- 원인·해결·롤백·blast radius는 커밋이 아닌 PR 본문에 적는다 (squash로 body는 main에서 휘발)
- staged 파일이 없으면 `git status --short`로 변경 목록을 출력한 뒤 `git add .`로 자동 add 후 진행한다
- push는 실행하지 않는다
- 이모지를 커밋 메시지에 절대 사용하지 않는다
- Co-Authored-By 라인을 커밋 메시지에 추가하지 않는다
- amend 금지 — MUST 새 커밋 생성
