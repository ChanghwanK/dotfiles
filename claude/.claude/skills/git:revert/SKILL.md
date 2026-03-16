---
name: git:revert
description: |
  kubernetes GitOps 레포에서 이미 배포된 커밋을 찾아 git revert로 되돌린다.
  sphere/circle/env/이미지 태그/chart 버전으로 커밋을 검색하고 영향도를 분석한다.
  사용 시점: (1) 잘못 배포된 이미지 태그 롤백, (2) chart 업그레이드 롤백, (3) 배포된 설정 변경 취소.
  트리거 키워드: "롤백", "rollback", "배포 되돌려", "배포 취소", "/git:revert".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py *)
  - Bash(git revert *)
  - Bash(git status *)
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(yamllint *)
  - Read
  - Glob
  - Grep
---
# git:revert — kubernetes GitOps 배포 롤백 워크플로우

배포된 커밋을 찾아 `git revert`로 안전하게 되돌린다. 히스토리를 보존하는 비파괴적 롤백.

---

## 핵심 원칙

- **`git reset --hard` 절대 금지** — 반드시 `git revert`로 히스토리 보존
- **본인 커밋만 롤백** — 다른 사람의 커밋은 절대 revert하지 않는다. 검색 시 `--author` 필터 기본 사용
- merge commit은 `git revert -m 1` 사용
- 복수 커밋 revert 시 **최신 → 과거 역순**으로 처리
- **prod 포함 시 명시적 확인 필수** — 자동 진행 금지
- conflict 발생 시 `git revert --abort` 후 수동 안내
- 스크립트만 호출한다. 직접 `git log` 파싱 금지.

---

## 워크플로우

### Step 1 — 요청 분석 & 검색

사용자 요청에서 sphere, circle, env, tag, chart version 등을 추출하여 검색 실행.

```bash
# 기본 검색 (sphere + circle 기준)
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --sphere <sphere> --circle <circle> --limit 10

# 환경 필터 추가
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --sphere <sphere> --circle <circle> --env infra-k8s-dev --limit 10

# 작성자 필터 (본인 커밋만 검색)
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --sphere <sphere> --author changhwan --limit 10

# 이미지 태그로 검색
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --sphere <sphere> --tag <image-tag> --limit 10

# 차트 버전으로 검색
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --sphere <sphere> --chart-version 0.3.51 --limit 10

# 커밋 해시 직접 조회
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --hash <commit-hash>

# 커스텀 grep
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py search \
  --grep "rollback\|revert" --since "1 week ago" --limit 20
```

**중요:** 기본적으로 `--author` 필터를 사용하여 본인 커밋만 검색한다. 다른 사람의 커밋을 revert하면 안 된다.

검색 결과를 테이블로 표시:

```
| # | Hash | Date | Message | Spheres | Circles | Envs | Merge |
|---|------|------|---------|---------|---------|------|-------|
```

### Step 2 — 사용자 확인

- 검색 결과에서 롤백 대상 커밋 선택을 사용자에게 확인
- 관련 커밋이 여러 개면 모두 포함할지 확인
- 하나도 찾지 못했으면 검색 조건 조정 제안

### Step 3 — 영향도 분석

선택된 커밋들의 영향도를 분석:

```bash
python3 /Users/changhwan/.claude/skills/git:revert/scripts/rollback.py analyze \
  --commits <hash1>,<hash2>
```

분석 결과 표시:
- **영향 파일**: 변경될 파일 목록
- **영향 환경**: dev, stg, prod 등
- **⚠️ Prod 경고**: prod 환경 포함 시 빨간 경고
- **⚠️ Merge commit**: merge commit 포함 시 `-m 1` 안내
- **⚠️ Conflict 위험**: 이후 같은 파일 수정한 커밋 존재 시 경고
- **Reverse diff**: `--stat` 요약

prod가 포함되면 반드시 "prod 환경이 포함되어 있습니다. 진행하시겠습니까?" 확인.

### Step 4 — Revert 실행

```bash
# 단일 커밋 revert (일반)
git revert --no-commit <hash>

# 단일 커밋 revert (merge commit)
git revert --no-commit -m 1 <hash>

# 복수 커밋: 최신 → 과거 역순으로 각각 --no-commit
git revert --no-commit <newest-hash>
git revert --no-commit <older-hash>
# ... (역순 반복)
```

모든 revert를 `--no-commit`으로 스테이징한 뒤, 단일 커밋으로 생성.

**커밋 메시지 형식:**

단일 circle:
```
revert(<sphere>/<circle>): Rollback <변경 내용> in <env>
```

다중 circle 또는 다중 env:
```
revert(<sphere>): Rollback <변경 내용> in <env1>, <env2>
```

예시:
```
revert(santa/gateway-server): Rollback image tag 0.0.20 in dev
revert(santa): Rollback webserver chart 0.3.51 upgrade in dev, stg
revert(tech): Rollback ai-gateway, core-api config change in prod
```

**Conflict 발생 시:**
```bash
git revert --abort
```
그리고 사용자에게 수동 해결 안내:
- conflict 파일 목록 표시
- 원인이 된 후속 커밋 정보 표시
- 수동 수정 방법 제안

### Step 5 — 검증

```bash
# YAML 린트 검증
yamllint -c .yamllint.yml src/

# 변경 요약 확인
git diff HEAD --stat
```

린트 에러가 있으면 수정 후 재검증.

### Step 6 — 결과 & Push

최종 요약 출력:

```
## 롤백 완료

- **Reverted commits**: <hash1>, <hash2>
- **영향 환경**: infra-k8s-dev, infra-k8s-stg
- **변경 파일**: N개
- **커밋**: <revert commit hash> — <message>

Push하시겠습니까? (y/n)
```

push 승인 시:
```bash
git push origin main
```

---

## 주의사항

- `git reset --hard` 절대 사용 금지
- push 전 반드시 사용자 확인
- prod 환경 롤백은 이중 확인 (Step 3 + Step 6)
- revert 후 ArgoCD가 자동 sync하므로 클러스터 반영은 별도 확인 불필요 (필요 시 deploy-verify-agent 사용)
