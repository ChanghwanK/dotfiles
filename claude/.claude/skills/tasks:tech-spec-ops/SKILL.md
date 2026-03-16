---
name: tasks:tech-spec-ops
description: |
  Tech Spec 운영 스킬. 동적 분석/검토, Phase 4 실행 추적, Phase 5 측정/완료 처리, validate, list, migrate.
  사용 시점: (1) Tech Spec 검토/분석 요청, (2) 실행 시작/진행 기록, (3) 완료 후 결과 측정, (4) 스펙 검증, (5) 목록 조회.
  트리거 키워드: "스펙 검토", "스펙 분석", "스펙 업데이트해줘", "진행 상황 반영",
  "스펙 진행", "스펙 완료", "스펙 검증", "tech spec ops", "/tasks:tech-spec-ops".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/tech-spec.py *)
  - Write(/tmp/tech-spec-*.*)
  - Read
  - Edit
  - Agent
---

# tasks:tech-spec-ops — 운영 스킬 (Phase 4-5 + 유틸리티)

`tasks:tech-spec`에서 생성된 Tech Spec의 실행 추적, 완료 측정, 검증, 목록 조회를 담당한다.

**스크립트**: `~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py` (계획 스킬과 공유)
**Tech Spec 경로**: `03. Resources/tech-specs/`

---

## 동적 분석 및 수정 — "읽고, 탐지하고, 제안한다"

트리거: "스펙 검토", "스펙 분석", "진행 상황 반영", "스펙 업데이트해줘", "이 스펙 봐줘"

사용자가 **"무엇을 바꿔라"**를 명시하지 않아도 Claude가 자율적으로 문서를 분석하여 불일치와 개선점을 탐지한다.

### 파이프라인

#### 1. 수집 (Collect)

- 대상 스펙 특정 (파일명 모르면 `search --query "키워드"`)
- 문서 전체 읽기 (`read-section --section "전체"` 또는 Read 도구)
- 외부 컨텍스트 수집:
  - `git log --oneline -10 -- <파일경로>` (최근 커밋)
  - `python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py validate --filename "파일명.md"` (검증 결과)
  - `## 실행 기록` 섹션 읽기 (완료된 Phase 파악)

#### 2. 탐지 (Detect)

아래 22개 규칙을 순회하며 해당하는 항목을 findings로 수집한다:

**카테고리 A — 진행 상황 불일치**

| ID | 탐지 규칙 | 예시 |
|----|-----------|------|
| A-1 | `## 실행 계획`의 체크박스 `- [ ]`와 strikethrough `~~텍스트~~` 불일치 | 실행 기록엔 Step 1 완료 기록이 있는데 체크박스가 `[ ]`인 경우 |
| A-2 | `## 실행 기록`의 완료 항목이 `## 실행 계획` 체크박스에 미반영 | 실행 기록: "Step 2 완료" 기록 있음 → 체크박스: `[ ]` |
| A-3 | git 커밋 메시지에 스펙 관련 작업이 있는데 실행 기록에 기록 없음 | 커밋: "feat: add alert rules" → 실행 기록에 언급 없음 |
| A-4 | 스펙 아티팩트 파일 경로가 Git에 존재하는데 `## 실행 계획`에 미완료 표시 | spec_artifact가 Git에 있음 → 해당 스텝이 `[ ]` |
| A-5 | overview 체크박스(`## 개요` 또는 서두의 Phase 목록)가 실행 기록 완료 항목과 불일치 | 실행 기록에 Phase 1 완료 → overview Phase 1 체크 없음 |

**카테고리 B — 구조 개선**

| ID | 탐지 규칙 | 예시 |
|----|-----------|------|
| B-1 | Phase 목록(overview)이 없고 `## 실행 계획`에 Phase가 여러 개 존재 | 스펙에 Phase 1~4가 있지만 진행 상황 한눈에 보기 불가 |
| B-2 | 체크박스(`- [ ]`)와 strikethrough(`~~`)가 혼용되어 완료 표시 방식이 불통일 | `- [x] 완료`, `~~Step 2~~` 혼용 |
| B-3 | `## 실행 기록` 섹션이 없음 (스펙 status가 `진행중` 또는 `완료`) | status: 진행중인데 실행 기록 없음 |
| B-4 | `## 실제 결과 (Outcome)` 섹션이 비어 있고 status가 `완료` | 완료 처리됐지만 결과 미기록 |
| B-5 | `## 실행 계획` 스텝에 책임자/예상 소요시간 없음 (스펙 규모가 크거나 multi-person) | Phase 3 스텝에 담당자 언급 없음 |

**카테고리 C — 상태 불일치**

| ID | 탐지 규칙 | 예시 |
|----|-----------|------|
| C-1 | frontmatter `status: 시작전`인데 `## 실행 기록`에 내용이 있음 | status 전환 누락 |
| C-2 | frontmatter `status: 진행중`인데 모든 실행 계획 스텝이 완료 표시 | 완료 전환 누락 |
| C-3 | frontmatter `status: 완료`인데 `## 실제 결과 (Outcome)` 섹션이 비어 있음 | 완료 처리 후 결과 미기록 |
| C-4 | frontmatter `last_reviewed` 날짜가 6개월 이상 지남 | 오래된 스펙의 신선도 경고 |
| C-5 | `## 실행 계획` 스텝에 strikethrough가 있는데 frontmatter가 `시작전` | status가 시작전인데 이미 일부 작업 완료 흔적 |

**카테고리 D — 누락 정보**

| ID | 탐지 규칙 | 예시 |
|----|-----------|------|
| D-1 | 필수 H2 섹션 4개(`배경 및 목표`, `현재 상태와 목표`, `실행 계획`, `실제 결과 (Outcome)`) 중 누락 | validate 결과로 확인 |
| D-2 | `### 성공 기준`이 없거나 측정 불가능한 기술 (숫자/Before-After 없음) | "성능이 개선된다" → 측정 불가 |
| D-3 | `### 롤백 계획`이 없음 | 실행 계획에 롤백 언급 없음 |
| D-4 | `domain/` 태그가 없음 | tags: ["Observability"] → domain/ 없음 |
| D-5 | `Non-Goals` 섹션이 없음 | 범위 불명확 스펙 |
| D-6 | `spec_type`이 ops-change가 아닌데 `## 스펙 아티팩트` 섹션 없음 | infra-change 스펙에 아티팩트 미기록 |
| D-7 | `## 실행 계획` 스텝에 검증 방법 언급 없음 (스텝 완료 후 어떻게 확인하는지) | "ConfigMap 적용" → 적용 확인 방법 없음 |

#### 3. 제안 (Propose)

findings를 테이블로 출력:

```
## 분석 결과: {스펙명}

| ID | 카테고리 | 발견 내용 | 자동 적용 |
|----|----------|-----------|-----------|
| A-1 | 진행 불일치 | Step 2 체크박스 미반영 (실행 기록 2026-03-15 완료) | 가능 |
| B-1 | 구조 개선 | Phase overview 없음 (Phase 1~4 존재) | 가능 |
| C-1 | 상태 불일치 | status 시작전인데 실행 기록 존재 | 확인 필요 |
| D-3 | 누락 정보 | 롤백 계획 없음 | 내용 판단 필요 |
```

자동 적용 분류:
- **가능**: 기계적으로 확정 가능 (체크박스 동기화, overview 생성, status 전환이 명확한 경우)
- **확인 필요**: 내용 판단이 필요한 변경 (status 전환, 새 섹션 내용 작성)
- **내용 판단 필요**: 사용자가 직접 작성해야 할 내용 (롤백 계획, 성공 기준 보강)

"자동 적용 가능" 항목은 한꺼번에 적용 제안:
```
위 항목 중 자동 적용 가능한 [A-1, B-1] 을 지금 적용할까요?
```

#### 4. 적용 (Apply)

승인 후 Edit 도구 또는 스크립트로 변경:

- **체크박스 동기화 (A-1, A-2)**: Edit 도구로 `- [ ]` → `- [x]` 또는 strikethrough 추가
- **overview 생성 (B-1, A-5)**: Edit 도구로 실행 계획 앞에 Phase 체크리스트 삽입
- **status 전환 (C-1, C-2)**: `update-status` 커맨드
- **실행 기록 섹션 추가 (B-3)**: `append-content` 커맨드
- **validate 재실행**: 적용 후 `validate --filename` 으로 잔여 이슈 확인

실행/측정이 수반되는 findings는 **Phase 4/5 워크플로우로 handoff**:
```
D-7 (검증 방법 누락)은 실행 시 직접 채워야 합니다.
지금 Phase 4 실행을 시작할까요?
```

---

## Phase 4: 실행 및 수정 — "진행하며 기록한다"

트리거: "스펙 진행", "tech spec 진행", "실행 시작", "스펙 업데이트"

### 워크플로우

1. **대상 스펙 선택**
   ```bash
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list --status 시작전
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list --status 진행중
   ```
   사용자에게 목록을 보여주고 대상 선택.

2. **상태 전환** (`시작전` → `진행중`)
   ```bash
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py update-status \
     --filename "파일명.md" --status 진행중
   ```

3. **필요시 Agent spawn → 실행 작업 수행**
   - Tech Spec의 `## 실행 계획` 섹션을 읽어 Agent에게 전달
   - **스펙 아티팩트가 있으면 해당 스펙 파일부터 생성/수정** (Spec First)
   - Agent가 kubectl, Terraform, 코드 수정 등 실제 작업 수행
   - 스펙 파일 변경 후 실행 기록에 커밋 해시/PR 링크 기록
   - 결과를 수집하여 실행 기록에 반영

4. **실행 기록 추가**
   진행 상황, 이슈, 변경사항을 `## 실행 기록` 섹션에 타임스탬프로 append:

   ```bash
   # /tmp/tech-spec-append.md에 추가할 내용 작성 후:
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py append-content \
     --filename "파일명.md" \
     --section "실행 기록" \
     --content-file /tmp/tech-spec-append.md
   ```

   실행 기록 형식:
   ```markdown
   ### YYYY-MM-DD
   - Step 1 완료: ConfigMap 적용
   - 예상치 못한 이슈: OOM → 리소스 limit 상향
   - Step 2 수정: rolling update → recreate (이유: ...)
   ```

---

## Phase 5: 측정 — "목표를 달성했는가?"

트리거: "스펙 완료", "tech spec 완료", "측정"

### 워크플로우

1. **대상 스펙 선택** (Phase 4와 동일, `진행중` 필터)

2. **Tech Spec 읽기** — `## 현재 상태와 목표` > `### 성공 기준` 확인

3. **필요시 Agent spawn → 측정 수행**
   - Grafana 쿼리, kubectl 확인, 비용 대시보드 조회 등
   - 성공 기준별 실제 결과 수집
   - 스펙 아티팩트에 명시된 파일이 Git 리포에 존재하는지 확인
   - Drift 여부 확인 (ArgoCD Synced, `terraform plan` 결과)

4. **결과 작성** — `## 실제 결과 (Outcome)` 섹션 교체:
   ```bash
   # /tmp/tech-spec-outcome.md에 결과 작성 후:
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py update-content \
     --filename "파일명.md" \
     --section "실제 결과 (Outcome)" \
     --content-file /tmp/tech-spec-outcome.md
   ```

   결과 형식:
   ```markdown
   ### 성공 기준 검증
   | 기준 | 목표 | 실제 | 결과 |
   |------|------|------|------|
   | API latency | -30% | -35% | Pass |
   | 비용 | $100 절감 | $80 절감 | Partial |

   ### 계획 vs 실제 차이
   - ...

   ### 배운 점
   - ...
   ```

5. **상태 전환** → `완료`
   ```bash
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py update-status \
     --filename "파일명.md" --status 완료
   ```

---

## 유틸리티 커맨드

### 목록 조회

```bash
# 전체 목록
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list

# 상태별 필터
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list --status 시작전
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list --status 진행중
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py list --status 완료
```

### 품질 검증

```bash
# 단일 파일 검증
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py validate --filename "파일명.md"

# 전체 검증
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py validate --all
```

6개 검증 항목:
1. 필수 H2 섹션 4개 존재
2. 임팩트에 숫자 또는 Before/After 패턴
3. 실행 계획에 롤백 언급
4. domain/ 태그 1개 이상
5. Non-Goals 섹션 존재
6. 스펙 아티팩트 참조 (spec_type ≠ ops-change)

결과를 표 형태로 사용자에게 출력:
```
| 항목 | 결과 | 상세 |
|------|------|------|
| 필수 섹션 | Pass | 4개 필수 섹션 존재 |
| 임팩트 측정 | Fail | 숫자 또는 Before/After 패턴 없음 |
| ... | ... | ... |
```

### 마이그레이션

기존 Tech Spec 문서를 새 표준으로 일괄 전환:

```bash
# 미리보기 (변경 없음)
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py migrate --dry-run

# 실제 적용
python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py migrate --apply
```

마이그레이션 항목:
- 태그 → `domain/` 형식 정규화
- aliases 자동 추출 (비어있으면)
- `last_reviewed` 필드 추가
- `type: tech-spec` 필드 추가
- `## 실행 기록` 섹션 추가

---

## 정밀 업데이트 — "특정 내용만 수정한다"

트리거: "성공 기준 수정", "태그 추가", "스텝 추가/삽입" 등 **부분 수정** 요청

### 워크플로우

1. **대상 스펙 찾기** (파일명 모르면)
   ```bash
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py search --query "키워드"
   ```

2. **수정 대상 섹션 읽기** (`filepath`도 함께 반환됨)
   ```bash
   # H2 섹션 읽기
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py \
     read-section --filename "파일명.md" --section "현재 상태와 목표"

   # H3 섹션 읽기
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py \
     read-section --filename "파일명.md" --section "성공 기준" --level 3

   # frontmatter 읽기 (태그, aliases, status 수정 시)
   python3 ~/.claude/skills/tasks:tech-spec/scripts/tech-spec.py \
     read-section --filename "파일명.md" --section "frontmatter"
   ```

3. **Edit 도구로 정밀 수정**
   - `read-section` 결과의 `filepath`를 Edit 도구에 전달
   - `content`에서 정확한 old_string을 선택하여 new_string으로 교체
   - 최소한의 범위만 수정 (H2 전체 재작성 불필요)

4. **`update-content`는 H2 전체 교체가 필요할 때만 사용**

### 시나리오 예시

| 요청 | 사용 커맨드 |
|------|------------|
| latency 목표 300ms → 250ms | `read-section --level 3 --section "성공 기준"` → Edit |
| 실행 계획에 Step 3 삽입 | `read-section --section "실행 계획"` → Edit |
| 태그에 Observability 추가 | `read-section --section "frontmatter"` → Edit |
| "Istio 관련 스펙 찾아줘" | `search --query "Istio"` |
| 스펙 아티팩트 테이블에 행 추가 | `read-section --level 3 --section "스펙 아티팩트"` → Edit |

---

## 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
