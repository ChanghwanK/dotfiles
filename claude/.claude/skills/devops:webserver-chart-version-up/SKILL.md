---
name: devops:webserver-chart-version-up
description: |
  Helm chart 버전업 워크플로우. Chart.yaml 버전 범프 → CHANGELOG 생성 → diff 정리.
  사용 시점: (1) webserver 등 chart 변경 후 버전업, (2) CHANGELOG 자동 작성, (3) 변경사항 diff 정리.
  트리거 키워드: "chart versionup", "버전업", "version up", "/devops:webserver-chart-version-up".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/devops:webserver-chart-version-up/scripts/versionup.py *)
  - Bash(helm template *)
  - Bash(helm lint *)
  - Bash(git diff *)
  - Bash(git log *)
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---
# devops:webserver-chart-version-up

Chart.yaml 버전 범프 → 변경사항 분석 → CHANGELOG 엔트리 작성 → diff 정리 출력.

---

## 핵심 원칙

- 리포지토리 루트: `~/workspace/riiid/kubernetes-charts`
- 대상 chart: 기본 `webserver` (다른 chart도 `--chart` 인자로 지정 가능)
- CHANGELOG는 `charts/<chart>/CHANGELOG.md`에 누적 관리
- 버전 컨벤션: 정식 `X.Y.Z`, 프리릴리스 `X.Y.Z-suffix`

---

## 워크플로우

### Step 1 — 현재 상태 수집

```bash
python3 /Users/changhwan/.claude/skills/devops:webserver-chart-version-up/scripts/versionup.py \
  --repo-root ~/workspace/riiid/kubernetes-charts \
  info --chart webserver
```

출력에서 확인:
- `current_version`: 현재 버전
- `git_log`: 마지막 버전 변경 이후 커밋 목록
- `changed_files`: 현재 미커밋 변경 파일
- `next_patch` / `next_minor`: 다음 버전 후보

### Step 2 — 변경사항 분석

1. `git_log`의 커밋 메시지를 분류:
   - `feat:` → **Added**
   - `fix:` → **Fixed**
   - `refactor:` → **Changed**
   - `chore:` → **Changed** (버전 범프 커밋은 제외)
   - `docs:` → **Changed**

2. 미커밋 변경이 있다면 `git diff`로 상세 내용 확인:

```bash
git diff HEAD -- charts/webserver/
```

3. 변경 규모에 따라 버전 범프 타입 결정:
   - 새 기능 추가 → minor
   - 버그 수정/설정 변경 → patch
   - 사용자가 명시적으로 지정한 경우 해당 버전 사용

### Step 3 — 버전 범프

사용자에게 새 버전을 확인한 후 실행:

```bash
python3 /Users/changhwan/.claude/skills/devops:webserver-chart-version-up/scripts/versionup.py \
  --repo-root ~/workspace/riiid/kubernetes-charts \
  bump --chart webserver --version <NEW_VERSION>
```

### Step 4 — CHANGELOG 자동 생성 및 검토

1. `versionup.py changelog` 서브커맨드로 초안 생성:

```bash
python3 /Users/changhwan/.claude/skills/devops:webserver-chart-version-up/scripts/versionup.py \
  --repo-root ~/workspace/riiid/kubernetes-charts \
  changelog --chart webserver --version <NEW_VERSION>
```

2. 출력된 초안을 검토하여 커밋 메시지를 사람이 읽기 좋은 **한국어**로 다듬기:
   - 기술적 커밋 메시지 → 사용자 관점 설명으로 변환
   - 중복/유사 항목 통합
   - 빈 카테고리(Added/Fixed/Changed) 생략

3. 다듬은 내용을 `charts/<chart>/CHANGELOG.md` 상단(`# Changelog` 바로 아래)에 삽입:

```markdown
# Changelog

## [X.Y.Z] - YYYY-MM-DD

### Added
- 새로 추가된 기능 설명

### Fixed
- 수정된 버그 설명

### Changed
- 변경된 동작/설정 설명

## [이전 버전] ...
```

4. 사용자에게 최종 CHANGELOG 내용 확인 요청

규칙:
- 최신 버전이 파일 상단에 위치
- 각 항목은 사용자가 이해할 수 있는 한국어로 작성
- 커밋 해시나 기술적 세부사항은 포함하지 않음
- 자동 분류가 어려운 경우 초안에 `_변경사항 없음 또는 자동 분류 불가_`가 출력되면 git log를 직접 확인하여 수동 작성

### Step 5 — diff 정리 출력

사용자에게 다음을 출력:

```
## Version Up Summary

- **Chart**: webserver
- **Version**: 0.3.51 → 0.3.52
- **Bump type**: patch

### 변경 내역
- (CHANGELOG 내용 요약)

### 변경 파일
- templates/deploy.yaml (수정)
- values.yaml (수정)
```

### Step 6 — 검증

```bash
helm lint charts/webserver -f charts/webserver/values.yaml
```

실패 시:
- `error: Chart.yaml` → 버전 형식 확인 후 재실행
- `error: template` → 템플릿 문법 확인

---

## 주의사항

- `.helmignore`에 `CHANGELOG.md`가 없는지 확인. 포함되어 있다면 helm package에서 제외됨 (CHANGELOG는 git 기록용이므로 .helmignore에 추가해도 무방)
- 프리릴리스 버전(`X.Y.Z-beta.1` 등)은 Harbor에만 푸시되고 자동 PR이 생성되지 않음
- 정식 버전(`X.Y.Z`)으로 올리면 `autopush.yaml` CI가 자동으로 kubernetes 리포에 PR 생성
