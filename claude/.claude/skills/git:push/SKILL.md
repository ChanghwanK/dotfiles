---
name: git:push
description: |
  Kubernetes GitOps 저장소의 안전한 git push 워크플로우 (반드시 pull 받고 push).
  사용 시점: (1) 커밋 완료 후 원격에 push, (2) 배포 영향도 확인 후 push.
  트리거 키워드: "push", "푸시", "푸시해줘", "/git:push".
model: sonnet
allowed-tools:
  - Bash(git *)
  - Bash(yamllint *)
  - Bash(python3 /Users/changhwan/.claude/skills/git:push/scripts/analyze_push_impact.py *)
  - Read
  - Grep
  - Glob
---

# Push Skill: 안전한 GitOps Push 워크플로우

커밋된 변경사항을 린팅 검증, 배포 영향도 분석, 안전 게이트를 거쳐 원격에 push한다.

---

## 워크플로우

### Step 1 — Pre-flight 확인

다음 명령을 **동시에** 실행한다:

```bash
git branch --show-current
git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "NO_UPSTREAM"
git status --porcelain
git log --oneline @{upstream}..HEAD 2>/dev/null || git log --oneline -5
```

**중단 조건:**
- 미커밋 변경사항이 있으면 → "커밋되지 않은 변경사항이 있습니다. `/commit`을 먼저 실행하세요." 출력 후 중단
- unpushed 커밋이 없으면 → "push할 커밋이 없습니다." 출력 후 중단

### Step 2 — yamllint 검증

```bash
yamllint -c .yamllint.yml src/ --no-warnings
```

- **error** 발생 시 → 에러 내용을 출력하고 중단. 수정 후 재실행 안내
- warning은 `--no-warnings` 플래그로 억제하여 표시하지 않음 (CI와 동일)

### Step 3 — 배포 영향도 분석

비교 기준을 결정하고 분석 스크립트를 실행한다:

```bash
# 비교 기준 결정 로직:
# 1. main 브랜치가 아닌 경우 → origin/main...HEAD
# 2. main 브랜치이고 upstream이 있는 경우 → @{upstream}..HEAD (unpushed commits만)

# main 브랜치에서 직접 push하는 경우
git diff --name-status @{upstream}..HEAD | python3 /Users/changhwan/.claude/skills/git:push/scripts/analyze_push_impact.py analyze

# feature 브랜치인 경우
git diff --name-status origin/main...HEAD | python3 /Users/changhwan/.claude/skills/git:push/scripts/analyze_push_impact.py analyze
```

스크립트가 JSON을 반환한다. 이를 파싱하여 다음 Step에서 사용한다.

### Step 4 — 배포 요약 출력

Step 3의 JSON 결과를 기반으로 영향 범위를 테이블로 출력한다:

```
### 배포 영향도 분석

| Sphere | Circle | Environment | Change Type |
|--------|--------|-------------|-------------|
| tech | ai-gateway | infra-k8s-prod | chart_version |
| santa | authentication | infra-k8s-dev | values_change |
```

변경사항이 `src/` 외부 파일만 포함하는 경우 → "K8s 배포에 영향 없는 변경입니다." 출력 후 Step 6으로 건너뛴다.

### Step 5 — 안전 게이트

JSON 결과의 `requires_confirmation`이 `true`이면 사용자 확인을 반드시 받는다.

확인이 필요한 조건:
- `infra-k8s-prod` 환경 포함
- `infra-k8s-global` 환경 포함
- `infra-k8s-idc` 환경에서 `prod` 서브 env 또는 서브 env 없는 클러스터 레벨 변경
- 파일 삭제(D status) 포함
- `common/values.yaml` 변경 (전 환경 영향)

출력 형식:
```
### 안전 게이트

다음 사유로 확인이 필요합니다:
- [PROD] tech/ai-gateway: chart_version
- [DELETE] src/tech/ai-gateway/infra-k8s-dev/resources/old.yaml

계속 진행할까요? (yes/no)
```

사용자가 "yes"를 입력하지 않으면 중단한다.

`requires_confirmation`이 `false`이면 이 Step을 건너뛴다.

### Step 6 — Pull --rebase

```bash
git pull --rebase
```

- 충돌 발생 시 → `git rebase --abort` 안내 후 중단
- 성공 시 → 계속 진행

### Step 7 — Push

```bash
# upstream이 있는 경우
git push

# upstream이 없는 경우
git push -u origin <current-branch>
```

### Step 8 — 검증 계획

push 성공 후, 영향도 분석 결과를 기반으로 검증 체크리스트를 생성한다:

```bash
git diff --name-status @{upstream}~{pushed_count}..@{upstream} | python3 /Users/changhwan/.claude/skills/git:push/scripts/analyze_push_impact.py verify-plan
```

출력된 체크리스트를 사용자에게 보여준다. `deploy-verify-agent`를 사용한 검증을 제안한다.

실패 시:
- yamllint 에러 → 에러 파일/라인 수정 후 커밋, `/push` 재실행
- rebase 충돌 → `git rebase --abort` 후 수동 해결, 재커밋, `/push` 재실행
- push 거부 → `git pull --rebase` 후 `/push` 재실행

---

## 규칙 요약

- yamllint 에러가 있으면 반드시 중단 (warning은 허용)
- PROD/Global/IDC 환경 변경 시 반드시 사용자 확인
- `git push --force` 절대 금지
- push 전 반드시 `git pull --rebase` 실행
- 검증 계획은 반드시 출력
