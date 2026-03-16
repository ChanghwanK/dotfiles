---
name: devops:release-note
description: |
  릴리스 노트 URL을 분석하여 현재 인프라 버전과 비교하는 스킬.
  URL에서 기술/버전을 추출 후, kustomization.yaml에서 현재 버전을 조회하고
  Breaking Changes/개선사항/Deprecation을 분석하여 업그레이드 권고를 생성한다.
  사용 시점: (1) 새 릴리스 확인 시 영향도 분석, (2) 업그레이드 계획 수립,
  (3) 환경별 버전 불일치 확인, (4) 인프라 컴포넌트 버전 인벤토리 조회.
  트리거 키워드: "릴리스 노트", "release note", "버전 비교", "업그레이드 분석",
  "버전 인벤토리", "어떤 버전", "/devops:release-note".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/devops:release-note/scripts/scan-versions.py *)
  - WebFetch
  - Read
  - Glob
  - Grep
---

# devops:release-note 스킬

릴리스 노트를 분석하여 현재 인프라 버전과 비교하고, 업그레이드 권고를 생성한다.

---

## 핵심 원칙

- **단일 소스**: `src/infra/`, `src/observability/` 아래 `kustomization.yaml`에서 버전을 추출한다.
- **특수 컴포넌트 예외**: ArgoCD(raw manifests), Karpenter(Terraform), arc-systems(수동 Helm CLI)는 별도 안내.
- **URL 없이 컴포넌트명만 제공 시** → 인벤토리 모드로 자동 분기.
- 버전 분석은 Claude 자연어 이해를 우선 활용한다.

---

## 워크플로우

### Step 1 — 입력 파싱 및 모드 결정

사용자 입력을 분석하여 두 가지 모드 중 하나로 진행한다:

**모드 A — 릴리스 노트 분석** (URL 제공 시):
- URL이 포함된 경우 → Step 2로 진행
- 예: "cert-manager 1.17 릴리스 노트 분석해줘: https://..."

**모드 B — 인벤토리 조회** (URL 없이 컴포넌트명 또는 "버전 목록" 요청 시):
- 컴포넌트명 제공 → `scan` 서브커맨드로 단일 컴포넌트 조회
- "전체", "인벤토리", "버전 목록" 키워드 → `list` 서브커맨드 → **B-1 심플 모드**로 출력
- "스큐", "불일치", "리포트", "분석" 키워드 포함 → `list` 서브커맨드 → **B-2 리포트 모드**로 출력

**B-1 심플 모드 (기본)**: JSON 결과를 그대로 테이블로 변환. 판정 없음.
```
| Circle | Chart | dev | stg | prod | global |
|--------|-------|-----|-----|------|--------|
| ⚠️ cert-manager | cert-manager | 1.18.2 | 1.18.2 | 1.18.2 | 1.18.2 |
```
불일치 행에만 ⚠️ 표시. 판정 컬럼 없음.

**B-2 리포트 모드 (명시 요청 시)**: `assets/inventory-template.md` 형식으로 스큐 판정 포함 전체 리포트 출력.

```bash
# 단일 컴포넌트 조회
python3 /Users/changhwan/.claude/skills/devops:release-note/scripts/scan-versions.py \
  scan --component <name>

# 전체 인벤토리
python3 /Users/changhwan/.claude/skills/devops:release-note/scripts/scan-versions.py list
```

---

### Step 2 — 릴리스 노트 수집

`WebFetch`로 URL 콘텐츠를 수집한다.

- **GitHub Releases 페이지**: 버전, 변경사항, Breaking Changes 섹션 자동 파싱
- **공식 문서/블로그**: Claude 자연어 이해로 주요 변경사항 추출
- **GitHub API** (여러 버전 비교 시): releases 목록 조회로 중간 버전 Breaking Changes 누적 분석

---

### Step 3 — 기술/버전 식별

릴리스 노트에서 다음 정보를 추출한다:

| 항목 | 내용 |
|------|------|
| 기술명 | 컴포넌트 이름 (예: cert-manager, Istio, KEDA) |
| 신규 버전 | 릴리스된 버전 번호 |
| Breaking Changes | API 변경, deprecated 옵션 제거, 동작 변경 |
| 신규 기능 | 추가된 기능, 성능 개선 |
| Bug Fixes | 수정된 버그 목록 |
| Deprecation | 향후 제거 예정 기능 경고 |
| Security Fixes | CVE 수정, 보안 패치 |
| 업그레이드 전제조건 | 최소 K8s 버전, 의존성 컴포넌트 버전 요구사항 |

---

### Step 4 — 현재 버전 조회

```bash
python3 /Users/changhwan/.claude/skills/devops:release-note/scripts/scan-versions.py \
  scan --component <기술명>
```

**결과 해석:**

1. `"special": true` → 특수 컴포넌트 안내 출력 후 수동 확인 가이드 제공
2. `"found": false` → "현재 인프라에서 사용하지 않는 기술입니다" 안내 후 종료
3. `"found": true` → 환경별 버전 테이블 작성

**컴포넌트 이름 매핑 실패 시:**
- 스크립트에서 `found: false` 반환
- circle 이름을 직접 시도하거나 사용자에게 정확한 컴포넌트명 확인

---

### Step 5 — 비교 분석

현재 버전(Step 4)과 신규 버전(Step 3)을 비교한다:

**분석 항목:**
1. **버전 거리**: major.minor.patch 거리 계산 (major 차이는 HIGH 위험)
2. **Skip Version 위험**: 현재와 신규 사이 중간 릴리스의 Breaking Changes 누적
3. **Breaking Changes 영향도**: 현재 `values.yaml`/설정에 미치는 실제 영향
4. **환경별 불일치**: `version_consistent: false`인 경우 불일치 환경 강조
5. **의존성 체인**: Istio처럼 여러 circle을 동시 업그레이드해야 하는 경우

**영향도 분류:**
- `HIGH`: Breaking Changes가 현재 설정에 직접 영향 / major 버전 변경
- `MEDIUM`: Breaking Changes 있지만 현재 설정 미사용 / minor 버전 변경 다수
- `LOW`: Bug fix / security patch 위주, Breaking Changes 없음
- `NONE`: Patch 수정만

---

### Step 6 — 업그레이드 권고 생성

아래 형식으로 최종 리포트를 출력한다. 상세 템플릿: `assets/report-template.md` 참조.

**섹션 구성:**
- 기본 정보 테이블 (기술명, 릴리스 버전, 날짜)
- 현재 환경별 버전 테이블 (dev/stg/prod/global/idc/office × chart, 버전 불일치 강조)
- 주요 변경사항 (Breaking Changes 영향도, 신규 기능, Deprecation, 보안 수정)
- 업그레이드 권고 (✅/⚠️/❌, 수정 필요 파일 목록, 롤아웃 순서, 주의사항)

---

### Step 7 — 검증

1. scan-versions.py JSON 버전과 리포트 버전 일치 확인
2. "수정 필요 파일" 목록이 실제 존재하는지 Glob으로 확인
3. Breaking Changes 분석이 누락 없이 포함되었는지 확인
4. 의존성 체인 컴포넌트가 있으면 함께 언급

---

## 인벤토리 모드 출력 형식

### B-1 심플 모드 (기본)

`list` JSON → Circle × 환경 테이블 직접 출력. 판정 로직 없음.

- 불일치 행에만 ⚠️ 접두어
- infra/ 테이블, observability/ 테이블 두 개로 분리
- 특수 컴포넌트(ArgoCD, Karpenter, arc-systems) 한 줄씩 별도 안내

### B-2 리포트 모드 (명시 요청 시)

상세 템플릿: `assets/inventory-template.md` 참조.

**목표**: "지금 뭘 쓰고 있고, 어디가 어긋나 있는지 30초 내 파악"

**섹션 구성:**
1. **환경 간 버전 불일치** — 스큐 판정 포함 테이블 (⚠️ 강조)
2. **버전 일관** — 일치하는 chart 목록
3. **비 GitOps 관리 컴포넌트** — ArgoCD, Karpenter, arc-systems 별도 표시

**스큐 판정 로직:**

| 조건 | 판정 |
|------|------|
| dev 버전 > stg/prod 버전 | "dev-first 정상" (의도적 프로모션 대기) |
| prod만 뒤처짐 (dev=stg≠prod) | "prod 뒤처짐" |
| global 또는 idc만 다름 | "{env} 미업데이트" |
| major 버전 차이 (X.y.z → X+1.y.z) | "⚠️ MAJOR gap" |

**버전 비교 기준:**
- semver 비교: `>` 판정은 major.minor.patch 순위 기반
- 배포된 환경이 없는 경우 `-` 표시 (판정에서 제외)
- 2개 이상 환경이 다를 때는 가장 낮은 환경 버전 기준으로 판정

---

## 에지 케이스 처리

| 상황 | 대응 |
|------|------|
| GitHub 외 URL (블로그, changelog 사이트) | WebFetch 후 Claude 자연어로 주요 변경사항 추출 |
| 인프라에 없는 기술 | "현재 미사용 기술입니다" 안내 후 종료 |
| ArgoCD/Karpenter/arc-systems 요청 | special_note로 수동 확인 가이드 제공 |
| 여러 버전 건너뜀 (skip upgrade) | 각 중간 릴리스 Breaking Changes 누적 분석 안내 |
| 같은 circle에 여러 chart (Istio) | 모든 chart 개별 표시 및 동시 업그레이드 권고 |
| WebFetch 실패 | 사용자에게 접근 가능한 다른 URL 요청 또는 수동 내용 붙여넣기 요청 |
