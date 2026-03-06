---
name: commit
description: |
  Git 변경사항 분석 후 commit message convention에 따라 커밋 & 푸시.
  사용 시점: (1) 변경사항 커밋, (2) 커밋 + 푸시, (3) 커밋 메시지 자동 생성.
  트리거 키워드: "/commit", "커밋", "commit and push", "커밋 앤 푸시", "커밋해줘".
model: haiku
allowed-tools:
  - Bash(git *)
---

# Commit Skill: Git 커밋 & 푸시 워크플로우

변경사항을 분석하고 커밋 메시지 컨벤션에 맞게 커밋한 후 푸시합니다.

---

## 워크플로우

### Step 1 — 정보 수집 (병렬 실행)

다음 명령을 **동시에** 실행한다:

```bash
git status
git diff --cached
git diff
git log --oneline -5
git remote -v
git branch --show-current
```

### Step 2 — 레포 타입 감지

변경된 파일 경로를 분석해 레포 타입을 결정한다:

| 조건 | 레포 타입 |
|------|-----------|
| `src/{sphere}/{circle}/infra-k8s-{env}/` 패턴 존재 | kubernetes |
| `.tf` 파일 또는 `terraform/` 경로 존재 | terraform |
| 그 외 | general |

### Step 3 — 변경 대상 분석

**kubernetes 레포의 경우**, 변경된 파일 경로에서 sphere/circle/env를 추출한다:

- 단일 circle, 단일 env: `chore(santa/authentication): Update replica count in dev`
- 단일 circle, 다중 env: `chore(santa/authentication): Update image tag in dev, stg`
- 다중 circle, 단일 sphere: `chore(santa): Update APM config for authentication, worker in dev`
- 다중 sphere: scope 없이 변경 내용 기술

**terraform 레포의 경우**, 변경된 모듈/리소스 경로를 scope로 사용한다:
- `chore(modules/vpc): Add NAT gateway configuration`

### Step 4 — Commit Message 생성

**규칙:**
- Conventional Commits 형식: `type(scope): description`
- Type 선택:
  - `chore` — 설정/인프라 변경 (image tag, values, config)
  - `feat` — 새 리소스/기능 추가
  - `fix` — 버그 수정
  - `docs` — 문서만 변경
  - `refactor` — 기능 변경 없는 구조 개선
- 이모지 절대 금지
- 영어로 작성
- description은 명령형 현재형 (Update, Add, Fix, Remove...)

**예시:**
```
chore(santa/authentication): Update replica count in dev
```

```
feat(tech/ai-gateway): Add rate limiting configuration
```

### Step 5 — 민감 파일 체크

아래 패턴의 파일은 **커밋에서 제외**하고 사용자에게 경고한다:
- `.env`, `.env.*`
- `*credentials*`, `*secret*` (소문자)
- `*.pem`, `*.key` (단, `.yaml` 안의 sealed secrets는 허용)

### Step 6 — Staging & Commit

```bash
# 변경된 파일을 개별적으로 명시 (git add -A / git add . 금지)
git add <file1> <file2> ...

# HEREDOC으로 커밋
git commit -m "$(cat <<'EOF'
type(scope): description
EOF
)"
```

pre-commit hook 실패 시: 문제를 수정한 후 **새 커밋 생성** (amend 금지).

### Step 7 — Push 확인 & 실행

생성된 커밋 메시지와 push 대상을 사용자에게 보여주고 확인을 요청한다:

```
커밋: chore(santa/authentication): Update replica count in dev
브랜치: main → origin/main

푸시할까요? (y/n)
```

사용자가 확인하면:
```bash
# upstream이 있는 경우
git push

# upstream이 없는 경우
git push -u origin <branch>
```

### Step 8 — 결과 확인 및 커밋 메시지 출력

```bash
git log --oneline -1
git status
```

완료 후 실제 사용된 커밋 메시지를 아래 형식으로 출력한다:

```
커밋 메시지:
─────────────────────────────
chore(santa/authentication): Update replica count in dev
─────────────────────────────
```

---

## 규칙 요약

- 이모지를 커밋 메시지에 절대 사용하지 않는다
- Co-Authored-By 라인을 커밋 메시지에 추가하지 않는다
- `git add -A` 또는 `git add .` 사용하지 않는다
- 민감 파일 감지 시 경고 후 skip
- amend 금지 — 항상 새 커밋 생성
- push는 반드시 사용자 확인 후 실행
