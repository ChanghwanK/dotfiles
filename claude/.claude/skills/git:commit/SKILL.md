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

**형식:** `type(scope): description` (Conventional Commits)

**Type 선택:**
- `chore` — 설정/인프라 변경 (image tag, values, config)
- `feat` — 새 리소스/기능 추가
- `fix` — 버그 수정
- `docs` — 문서만 변경
- `refactor` — 기능 변경 없는 구조 개선

**kubernetes 레포 scope 규칙:**
- 단일 circle, 단일 env → `chore(santa/authentication): Update image tag in dev`
- 단일 circle, 다중 env → `chore(santa/authentication): Update image tag in dev, stg`
- 다중 circle, 단일 sphere → `chore(santa): Update config for authentication, worker in dev`
- 다중 sphere → scope 없이 기술

**공통 규칙:**
- 이모지 금지, Co-Authored-By 금지
- 영어, 명령형 현재형 (Update, Add, Fix, Remove...)

### Step 4 — 민감 파일 체크

아래 패턴 파일은 staged에 포함되어 있어도 커밋 전 경고 후 진행 여부를 확인한다:
- `.env`, `.env.*`, `*credentials*`, `*secret*`, `*.pem`, `*.key`

### Step 5 — Commit 실행

```bash
git commit -m "$(cat <<'EOF'
type(scope): description
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

- staged 파일이 없으면 `git status --short`로 변경 목록을 출력한 뒤 `git add .`로 자동 add 후 진행한다
- push는 실행하지 않는다
- 이모지를 커밋 메시지에 절대 사용하지 않는다
- Co-Authored-By 라인을 커밋 메시지에 추가하지 않는다
- amend 금지 — MUST 새 커밋 생성
