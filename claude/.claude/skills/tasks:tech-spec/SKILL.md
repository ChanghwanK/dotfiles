---
name: tasks:tech-spec
description: |
  인프라/DevOps Tech Spec 스킬. research:deep으로 자료를 모아 1차 계획을 쓰고, codex와 Claude 서브에이전트가 자료·계획을
  교차 리뷰한 뒤, 고정 H2 포맷(Objective 콜아웃 + Background / Goals & KeyResult / 설계 및 계획 / 예상 질문 정리 / 마일스톤)으로
  Tech Spec을 작성한다. 결과는 HTML Artifact와 콘솔로 출력하고(Notion에는 직접 쓰지 않는다, Notion 작성은 작업자가 한다), codex·Claude 리뷰 → 반영을 수렴할 때까지 반복한다.
  사용자 결정이 필요한 항목은 `### 결정 필요` 표로 모으고 HTML 상단에 강조한다.
  사용 시점: (1) 인프라 변경 계획 수립, (2) 설계 의사결정 구조화, (3) 새 프로젝트 킥오프, (4) 대화 내용을 스펙으로 정리,
  (5) notion:add-engineering-note가 grill-me 인터뷰 뒤 호출(eng-note 모드).
  트리거 키워드: "tech spec", "테크 스펙", "기술 스펙", "스펙 문서", "tech-spec 작성", "/tasks:tech-spec".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/spec_tool.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/codex_review.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:tech-spec/scripts/codex_research.py *)
  - Bash(cp *)
  - Bash(python3 /Users/changhwan/.claude/skills/tasks:manage/scripts/notion-task.py read-page *)
  - Skill
  - Agent
  - Artifact
  - Read
  - Write
  - Edit
---

# tasks:tech-spec: Tech Spec 스킬

```
Step 0 범위·실행 폴더 → Step 1 자료 수집(research:deep ∥ codex 독립 수집 → 상호 검토·보완, + 사내 조사) → 1차 계획
→ Step 2 codex·Claude 자료/계획 리뷰 → 계획 보강
→ Step 3 Tech Spec 작성(고정 H2) → Step 4 HTML + 콘솔 출력
→ Step 5 codex·Claude 스펙 리뷰 → Step 6 판정·반영 후 Step 4로(수렴할 때까지) → Step 7 마무리
```

`S=/Users/changhwan/.claude/skills/tasks:tech-spec/scripts/spec_tool.py`
`C=/Users/changhwan/.claude/skills/tasks:tech-spec/scripts/codex_review.py`
`SK=/Users/changhwan/.claude/skills/tasks:tech-spec`

---

## 핵심 원칙

- **포맷 정본은 `assets/spec-format.md`다.** H2 다섯 개(Background, Goals & KeyResult, 설계 및 계획, 예상 질문 정리, 마일스톤)와
  Objective 콜아웃만 고정이고 H3 이하는 주제에 맞게 짓는다. `spec_tool.py lint`가 검사한다
- **두 리뷰어는 서로 다른 눈이다.** codex는 공개 문서·사실 정확성(웹 검색 가능, read-only), Claude 서브에이전트는 사내 맥락·논리 연결·Day-2.
  둘 다 블라인드로 부른다: 파일 경로만 주고 Claude의 결론·기대 판정을 주지 않는다
- **리뷰 지적은 하나도 흘리지 않는다.** 모든 issue id를 `adjudication.md`에 `수용 / 기각 / 보류`로 판정한다. 기각은 근거(파일:줄, claim id, 측정)가
  있을 때만 하고, 수렴을 위해 기각하지 않는다. 보류는 사용자 결정이 필요한 것이며 스펙에 `(미결정)`과 `### 결정 필요` 표 행으로 드러낸다
- **수용도 검증한다.** 리뷰어의 `fix`는 제안이지 근거가 아니다. 사실·메커니즘을 바꾸는 blocker·major는 반영 전에 리서치 원문(`sources/*.txt`,
  `claims.jsonl`)이나 공식 문서를 직접 대조하고, 판정 근거 칸에 대조한 출처를 쓴다. 대조할 수 없으면 수용하지 말고 보류한다
  (2026-11-23 PgBouncer 실행: 73건 중 기각 0건이었고, r1에서 원문 대조 없이 수용한 SIGINT 종료 수정이 r2에서 틀린 것으로 드러났다)
- **근거가 없는 사실은 쓰지 않는다.** 외부 사실은 research:deep에서 검증된 주장(SUPPORTED, 조건 반영한 PARTIAL)만, 사내 사실은 조회한
  측정·파일만 근거로 쓴다. 원인을 측정하지 못했으면 `(원인 미확인)`
- **산출물은 실행 폴더에 남긴다.** `~/.claude/tech-spec-runs/<날짜>-<slug>/`: `plan.md`, `context/`, `research/`(링크), `spec.md`,
  `spec.html`, `history/spec-rN.md`, `reviews/*.json`, `adjudication.md`. 지우지 않는다(재검토·감사용)
- 채팅 응답은 한국어 격식체, 문서 본문은 `~/.claude/docs/notion-writing-style.md`. em dash 금지

---

## 모드

| 조건 | 모드 | 차이 |
|------|------|------|
| `/tasks:tech-spec`, "테크 스펙 써줘" (기본) | **Standard** | Step 0~7 전부 |
| "빠르게 스펙 정리", "대화 내용을 스펙으로" | **Quick** | Step 1의 research:deep과 Step 2를 건너뛰고 대화 맥락으로 plan.md를 쓴다. 스펙 리뷰 루프 최대 2라운드 |
| notion:add-engineering-note에서 호출 | **eng-note** | grill-me 결과를 Step 1 입력으로 쓰고(다시 묻지 않음), Step 7에서 Notion 매핑을 호출한 스킬로 돌려준다 |

Quick 모드도 lint, HTML + 콘솔 출력, codex·Claude 스펙 리뷰는 생략하지 않는다.

---

## Step 0: 범위와 실행 폴더

1. 대화에서 주제, 대상(sphere/circle/env, 서비스 목록), 산출물 종류(설계만 / 구현 / 적용), 이미 확정된 결정을 뽑는다
2. 범위가 모호해 **조사 방향이 갈리는 경우에만** AskUserQuestion으로 묻는다(예: "Python 백엔드 전체인가, socraai만인가"). 그 외에는 묻지 않는다
3. 제목(H1)과 slug를 정한다. 연결된 Task가 있으면 Task 제목과 대응되게 짓는다
4. 실행 폴더를 만든다
   ```bash
   python3 $S init <slug> --title "<제목>"            # 출력 경로가 {run_dir}
   ```
5. 채팅에 한 줄: 실행 폴더와 이제 자료 수집을 시작한다는 것

---

## Step 1: 자료 수집과 1차 계획

### 1-a. 사내 조사 (백그라운드, 먼저 띄운다)

필요한 Agent만 골라 **한 메시지에서 동시에** `run_in_background=true`로 띄운다. 각 agent 파일을 Read해 placeholder를 치환한다.

| Agent | 실행 조건 | 파일 |
|-------|----------|------|
| A: 클러스터 현재 상태 | sphere/circle이 특정되고 현재 Pod/Deployment 상태를 모를 때 | `$SK/agents/agent-cluster-status.md` |
| B: 메트릭 현황 | 에러율, 지연, 리소스, 커넥션 수, 비용 수치가 필요할 때 | `$SK/agents/agent-metrics-check.md` |
| C: 코드베이스 탐색 | values.yaml, 차트 버전, 앱 설정(드라이버·풀)을 확인해야 할 때 | `$SK/agents/agent-codebase-explore.md` |

- 각 Agent 프롬프트 끝에 "결과를 `{run_dir}/context/<A|B|C>-<주제>.md`에 Write하고, 모든 사실에 조회 명령·쿼리·파일 경로를 붙여라"를 덧붙인다
- kubernetes 레포에서 작업 중이면 `devops-wiki/INDEX.md`에서 관련 guardrail·issue 문서를 직접 찾아 읽고 요점을 `context/wiki.md`에 쓴다
- 대화에 이미 조회로 확보한 수치가 있으면 그 Agent는 생략하고 `context/conversation.md`에 출처와 함께 옮긴다.
  이번 세션에서 Claude가 쓴 요약 문장은 측정이 아니므로 생략 근거가 되지 않는다

### 1-b. 외부 자료: research:deep

`research:deep`을 Skill 도구로 호출한다(Standard 모드만). args에 원 질문을 넘긴다: 주제의 동작 원리, 버전별 기본값·한도, 장애 모드,
운영 사례, 대안 비교처럼 **설계 결정을 가르는 질문**으로 쓴다. 예:

```
PgBouncer를 Kubernetes에서 Python(SQLAlchemy/psycopg) 백엔드와 Aurora PostgreSQL 사이에 둘 때:
pool_mode별 트랜잭션·prepared statement 의미, HA 배치 패턴, 장애·failover 시 동작, RDS Proxy와의 비교, 운영 사례
```

- research:deep은 자기 절차(Claude Docs 보고서, codex 주장 검증)를 끝까지 진행한다. 끝나면 실행 폴더를 연결한다
  ```bash
  python3 $S link-research {run_dir} ~/.claude/research-runs/<날짜>-<slug>
  ```
- research:deep이 실패하거나 사용자가 생략을 원하면 `research` 스킬로 대신하고, 결과를 `context/research-lite.md`에 출처 URL과 함께 쓴다

### 1-b'. codex 교차 리서치 (research:deep 안에서, Step 3 수집 브리핑과 Step 4 주장 원장 사이)

Claude와 codex가 같은 서브질문을 각자 수집하고, 서로의 결과를 검토·보완한 뒤에 주장 원장을 만든다. research:deep을 진행하다
Step 3(수집 브리핑)이 끝나면 Step 4로 가기 전에 아래를 한다. `R=<research_run>`, `X=$SK/scripts/codex_research.py`

1. `$R/subquestions.md`를 쓴다: research:deep Step 0의 서브질문을 `## q1 <제목>` 헤더와 핵심 질문 불릿으로
2. codex 독립 수집(빈 작업 폴더에서 실행해 Claude 자료를 보지 않는다). Claude 리서처와 **동시에** 띄워도 된다
   ```bash
   python3 $X collect $R --version-anchor "<버전 앵커>"     # Bash run_in_background=true, 서브질문별 병렬
   ```
3. 상호 검토를 **한 메시지에서 동시에** 띄운다
   - codex가 Claude 수집을 검토: `python3 $X cross-review $R` (백그라운드) → `$R/codex/cross-review.json`(errors, gaps)
   - Claude가 codex 수집을 검토·흡수: `$SK/agents/agent-codex-findings-review.md`를 Read해 `{research_run}` 치환 후
     `Agent(subagent_type="general-purpose", model="sonnet", run_in_background=true)` → `notes/<qN>-codex.jsonl`, `codex/findings-review.md`
4. 보완
   - cross-review `gaps`: 해당 서브질문만 research:deep 리서처를 1회 더 띄운다(프롬프트에 gap 목록과 `where_to_look`을 넣는다)
   - cross-review `errors`: research:deep `adjudication.md`에 `claim_id | codex 교차 검토 | 결론 | 근거`로 남기고, 맞는 지적이면 해당 주장을 Step 4에서 지운다
5. 채팅에 한 줄: codex 수집 n건 중 흡수 a / 중복 d / 불일치 x, codex가 찾은 Claude 오류 e건·공백 g건과 처리 결과
6. research:deep Step 4(ledger)로 돌아가 이후 절차를 진행한다. 이후 프로세스(주장 검증, 계획, 스펙)는 Claude가 주도한다
   - 주장 검증 범위(아래 "codex 예산"): research:deep Step 5를 전체 원장에 돌리지 않는다. Step 6 초안과 plan.md를 먼저 쓰고,
     그 둘이 인용한 claim id만 `codex_verify.py claims --only <ids> --effort medium`으로 검증한 뒤 초안을 확정한다

codex 사용량과 한도 처리는 아래 "codex 예산"을 따른다.

### 1-c. 문제 검증 게이트 (plan.md를 쓰기 전)

사내 조사 Agent가 모두 끝난 뒤, 문제 정의를 아래로 검사한다. 걸리면 사용자에게 묻기 전에 조회·측정으로 먼저 해소한다.
kubernetes 레포에서는 `devops-wiki/03-guardrails/rca-shared-criteria.md` §1이 정본이고 아래는 축약본이다.

| # | 자문 | 걸리면 할 일 |
|---|------|-------------|
| G1 | 알럿·에러 로그·대시보드 이상에서 출발했는가? | 신호가 아니라 신호를 만든 메커니즘을 문제로 쓴다 |
| G2 | 영향을 진단 도구 단위(알럿 횟수, 노드 수, 로그 라인)로 셌는가? | 영향받는 대상(요청, 파드, 서비스, 사용자) 단위로 다시 센다 |
| G3 | 근거가 이번 세션의 내 요약 문장인가? | 재측정한다. "영향 없음" 같은 부정 결론은 그 0을 만든 쿼리를 다시 돌린다 |
| G4 | 표본이 n=1인가? | 창을 7일 이상(30일 권장)으로 넓혀 다시 센다 |

### 1-d. 1차 계획 작성

`{run_dir}/plan.md`를 Write한다. 스펙이 아니라 리뷰받을 계획 초안이다.

```markdown
# 1차 계획: {제목}

## 문제와 근거          ← 번호 목록, 근거마다 context 파일·쿼리·claim id
## 가설                 ← 무엇을 하면 → 어떤 동작 때문에 → 어떤 결과
## 접근안 후보와 추천    ← 2~3개, 안정성·비용·운영 부담·되돌리기 비교, 추천과 이유
## 미결정과 판단 기준
## 검증 아이디어         ← Key Result 후보와 각각을 어떻게·언제 판정할지
## 문제 검증 게이트      ← G1~G4 결과 표(통과 / 해당 없음 / 걸림 → 해소 / 걸림 → 미해소)
## 자료 공백
```

쓴 직후 버전을 남긴다: `python3 $S snapshot {run_dir} --plan --round 1` (→ `history/plan-v1.md`). plan.md를 고칠 때마다
고치기 **전에** 다음 버전 번호로 다시 스냅샷한다. 덮어써서 이전 버전을 잃지 않는다(브리핑의 근거다).

계획을 쓰며 아래를 자문하고 해당하면 계획에 반영한다: 한 번에 끝내기 어려운 크기인가(쪼갤 단위), 안 하면 실제로 어떤 손해인가(ROI),
cross-AZ·NAT·다른 팀 서비스 영향, 더 적은 변경으로 같은 목표에 닿는 안, 되돌리기 어려운 결정.

---

## Step 2: 자료·계획 교차 리뷰

1. 두 리뷰어를 **한 메시지에서 동시에** 띄운다
   ```bash
   python3 $C plan {run_dir} --round 1                 # Bash run_in_background=true
   ```
   ```
   Agent(subagent_type="general-purpose", run_in_background=true, description="Plan review r1",
         prompt=<$SK/agents/agent-plan-review.md를 Read해 {run_dir}, {round}=1, {repo_path} 치환>)
   ```
   두 완료 알림을 기다린다. 폴링하지 않는다
2. 집계하고 id를 부여한다
   ```bash
   python3 $S reviews {run_dir} --stage plan --round 1
   ```
3. 각 issue를 읽고 `adjudication.md`에 `issue_id | 수용 / 기각 / 보류 | 근거 또는 반영 위치`로 한 줄씩 쓴다. 다시 `reviews`를 돌려 `undecided_ids`가 비었는지 확인한다
4. 수용한 지적을 `plan.md`에 반영한다. `reviews` 출력의 `likely_duplicates` 쌍은 한 번에 판정한다(둘째 id 근거에 `중복: <첫 id>`)
   - "자료 공백" 지적: 사내 사실이면 해당 Agent를 1회 다시 띄우고, 외부 사실이면 research:deep 실행 폴더에서 `codex_verify.py claims --only`로
     추가 주장을 검증하거나 `research` 스킬로 보충한다. 추가 수집은 1라운드까지만 한다
   - `expected_questions`는 `plan.md` 끝에 모아 둔다(Step 3에서 예상 질문 정리로 옮긴다)
5. 채팅에 한 줄: 리뷰어별 심각도 건수, 수용·기각·보류 수

---

## Step 3: Tech Spec 작성

1. `$SK/assets/spec-format.md`를 Read한다(포맷 정본, 섹션별 작성 안내)
2. `{run_dir}/spec.md`를 Write한다
   - Background ← plan의 문제와 근거. Goals & KeyResult ← 가설과 검증 아이디어(Key Result 규칙은 `task:keyresult`)
   - 설계 및 계획 ← `### Todo`, 주제별 설계 H3, 고려해야할 것 및 검증 목록(토글), 검증, 마이그레이션·롤아웃 계획
   - 예상 질문 정리 ← plan의 expected_questions와 Step 2 리뷰 질문. 답이 없으면 `(미결정)`과 판단 기준
   - 마일스톤 ← Todo를 관측 가능한 완료 기준으로 묶은 표
   - 인프라·prod 변경이면 마이그레이션·롤아웃 H3에 Blast radius, 실패 시나리오, 롤백 방법과 걸리는 시간을 쓴다
   - 다른 시스템과 상호작용이 있으면 다이어그램을 1개 이상 넣는다(시퀀스, 데이터 흐름, ERD 등). `archify`/`diagram-design`으로 흰 배경 PNG를 만들어
     `![캡션](/절대경로.png)`로 넣고, `render`가 PNG를 HTML에 함께 싣는다. 로우 레벨 스펙이면 인터페이스 명세(응답 코드, 요청·응답 포맷, 에러 명세, 설정값)까지 쓴다
3. 포맷을 검사한다. `ok: false`면 고치고 다시 돌린다. warnings는 판단해서 반영한다
   ```bash
   python3 $S lint {run_dir}
   ```
4. 이 첫 버전이 **초안**이다. 리뷰 전에 따로 남기고 따로 게시한다(최종본과 섞지 않는다)
   ```bash
   python3 $S snapshot {run_dir} --round 1                                   # history/spec-r1.md = 초안
   python3 $S render {run_dir} --src history/spec-r1.md --out spec-draft.html --label 초안
   ```

---

## Step 4: 출력 (HTML + 콘솔)

**첫 출력은 초안이다.** Step 3-4의 `spec-draft.html`을 초안 전용 경로(`<scratchpad>/<slug>-tech-spec-draft.html`)로 따로 게시하고,
콘솔에 초안 전문을 붙인다. 초안 Artifact는 이후 다시 게시하지 않는다(리뷰 전 상태를 보존). 아래는 리뷰 반영본(작업본)의 출력이다.

1. 렌더한다. `--round`에는 마지막으로 반영한 스펙 리뷰 라운드를 넣는다(첫 출력은 0). HTML은 이 명령만 만든다(손으로 쓰거나 고치지 않는다).
   출력의 `structure.ok`가 false면 `structure.errors`대로 `spec.md`를 고쳐 다시 렌더한다. 구조 정본은 `assets/spec-format.md` "HTML 출력 구조"
   ```bash
   python3 $S render {run_dir} --round <N>
   ```
2. HTML Artifact로 게시한다
   - 세션에서 처음 게시하기 전에 `artifact-design` 스킬을 한 번 로드한다(Artifact 도구 계약). 템플릿 `assets/spec.html.tmpl`이 이미
     사용자 전역 Artifact 규칙(흰 배경 단일 라이트 테마, 1px 테두리, `#f1f4f7` 구분)을 따르므로 디자인을 새로 하지 않는다
   - 스크래치패드에 고정 이름으로 복사해 게시한다. 라운드마다 **같은 경로**로 다시 게시해야 같은 URL이 유지된다
     ```bash
     cp {run_dir}/spec.html <scratchpad>/<slug>-tech-spec.html
     ```
     첫 게시: `Artifact(file_path=<위 경로>, icon="document", description="<Objective 한 문장>")`. 이후: 같은 `file_path`, icon 생략
   - 받은 URL을 `{run_dir}/run.json`의 `artifact_url`에 Edit로 기록한다
3. 콘솔(채팅)에 출력한다
   - 첫 출력과 최종 출력(Step 7): `spec.md` 전문을 그대로 붙이고 맨 위에 Artifact 링크 한 줄
   - 중간 라운드: `python3 $S diff {run_dir} --round <N+1>`로 바뀐 섹션만 붙이고, 맨 위에 링크와 "라운드 N 반영: 수용 a / 기각 r / 보류 h" 한 줄

---

## Step 5: 스펙 리뷰 (라운드 N, 1부터)

1. 리뷰할 버전을 고정한다
   ```bash
   python3 $S snapshot {run_dir} --round <N>
   ```
2. 두 리뷰어를 **한 메시지에서 동시에** 띄우고 완료 알림을 기다린다
   ```bash
   python3 $C spec {run_dir} --round <N>               # Bash run_in_background=true
   ```
   ```
   Agent(subagent_type="general-purpose", run_in_background=true, description="Spec review r<N>",
         prompt=<$SK/agents/agent-spec-review.md를 Read해 {run_dir}, {round}=N, {prev}=N-1, {spec_type}, {repo_path} 치환. N=1이면 1.5절을 지운다>)
   ```
   `spec_type`은 아래 "스펙 유형" 표에서 고른다
3. 집계한다
   ```bash
   python3 $S reviews {run_dir} --stage spec --round <N>
   ```
   한 리뷰어가 실패하면(codex usage limit, 타임아웃) 1회 재시도하고, 그래도 실패하면 남은 리뷰어 결과로 진행하되 Step 7 출력에 명시한다

## Step 6: 판정·반영 루프

1. 모든 issue id를 `adjudication.md`에 판정한다(핵심 원칙의 기준). `reviews`를 다시 돌려 `undecided_ids`가 빈 것을 확인한다
2. **종료 판정** (`reviews` 출력 기준)
   - `converged: true`(기각·보류를 뺀 blocker+major가 0)이면: 수용한 minor만 반영하고 Step 7로 간다
   - N이 최대 라운드(Standard 3, Quick 2)면: 수용한 지적을 반영하고 Step 7로 간다. 남은 blocker·major를 Step 7에 명시한다
   - 이번 라운드에 수용한 지적이 0건이면(같은 지적만 반복됨): Step 7로 간다
   - 그 외: 계속
3. 수용한 지적을 `spec.md`에 반영한다. `likely_duplicates` 쌍은 한 번에 판정한다. 보류는 해당 위치에 `(미결정)`과 선택지·판단 기준으로 쓰고,
   `### 결정 필요` 표에 행(필수 / 필수 아님)과 상세 설명(`<details><summary>N. ...`)을 더한다. `expected_questions`는 예상 질문 정리에 합친다(중복 제거)
4. `lint` → `render --round <N>`(`structure.ok` 확인) → 같은 경로로 재게시 → 콘솔에 diff 출력(Step 4의 중간 라운드 형식)
   - 최대 라운드에서 끝나 마지막 수정이 다시 리뷰되지 않았으면, 마지막 라운드에서 수용한 blocker·major 수정만 Claude 서브에이전트(sonnet)로
     "직전 수정 검증"(agent-spec-review.md 1.5)을 한 번 더 돌린다. codex는 부르지 않는다
5. N+1로 Step 5를 다시 한다

---

## Step 7: 마무리 (보고는 세 부분으로 나눠 이 순서로)

사용자 보고는 **① 초안 → ② 리뷰 흐름 브리핑 → ③ 최종 보고서**를 섞지 않고 따로 보인다. 각 부분은 HTML Artifact(별도 URL)와 콘솔 출력을 함께 갖는다.

**① 초안**
- 초안 Artifact 링크(Step 4에서 게시한 `*-tech-spec-draft.html`)와 `history/spec-r1.md` 전문
- 1차 계획 v1(`history/plan-v1.md`)은 브리핑 흐름에서 링크한다

**② 리뷰 흐름 브리핑**
1. 표·변경 섹션 골격을 만든다
   ```bash
   python3 $S briefing {run_dir}
   ```
   흐름(자료 수집 → 계획 v1 → 계획 리뷰 → 계획 v2 → 초안 → 스펙 리뷰 r1 → ... → 최종), 라운드별 리뷰어 집계, 지적별 판정·반영 근거,
   버전 간 바뀐 섹션(신설·수정·삭제, 줄 수)이 들어간다
2. `briefing.md`의 `## 흐름` 앞에 `## 요약`을 Claude가 직접 쓴다. 바뀐 결정마다 한 불릿: **무엇이 어떻게 바뀌었나(전 → 후), 어느 리뷰의
   어떤 지적 때문인가(issue id), 왜 수용했나(근거)**. 기각한 주요 지적과 그 이유, 사용자 결정으로 넘긴 보류 항목도 쓴다
3. 골격을 다시 만들 때는 `--keep-narrative`로 요약을 보존한다. 렌더·게시:
   ```bash
   python3 $S render {run_dir} --src briefing.md --out briefing.html --label 브리핑
   cp {run_dir}/briefing.html <scratchpad>/<slug>-review-briefing.html     # 별도 Artifact로 게시
   ```
4. 콘솔에는 `## 요약`과 라운드별 집계 표를 붙이고, 지적별 상세는 Artifact 링크로 안내한다

**③ 최종 보고서**
0. **Notion에는 쓰지 않는다.** PE Working Note DB(`[PE - Tech Spec Template]`)에 다시 적는 것은 작업자가 하는 일이다(규칙).
   이 스킬은 Notion 페이지를 만들거나 고치지 않고, Notion MCP 쓰기 도구를 부르지 않는다. 스펙의 H2 구성은 그 템플릿과 같게 유지해 옮겨 적기 쉽게 한다
1. 최종본 Artifact 링크(Step 4의 작업본 경로를 마지막으로 재게시한 것)와 `spec.md` 전문
2. 사용자 결정이 필요한 항목: 스펙의 `### 결정 필요` 표(보류, 남은 blocker·major)를 콘솔에도 붙인다. HTML은 상단 배너와 본문의 `미결정` 표시로 강조된다. 없으면 생략
3. 다음 행동 제안 최대 1줄

**eng-note 모드의 매핑**: 이 스킬은 저장하지 않는다. `notion:add-engineering-note`가 호출했을 때만 아래 sections 키로 옮긴 결과를 돌려주고, 저장은 호출한 스킬이 한다.

| Tech Spec | sections 키 |
|-----------|-------------|
| Background(문제) | `problem` |
| Background의 원인·근거, `(원인 미확인)` 후보 | `root_cause` |
| Key Result + 해결 가설 | `value` (`가설:` / `Key Result:` 라벨) |
| Goal / Non-Goal | `goals` / `non_goals` |
| 설계 및 계획의 주제별 H3, 고려해야할 것, 검증, 예상 질문 정리 | `design` (H3는 `###` 유지, 예상 질문은 `### 예상 질문`) |
| Todo + 마일스톤 | `plan` |

eng-note 모드에서는 이 매핑 결과를 호출한 스킬로 돌려주고, 호출한 스킬이 저장·출력한다(중복 출력 방지).

---

## 스펙 유형 (Claude 리뷰 강도 결정용)

| spec_type | Spec Layer | 대표 경로 |
|-----------|------------|----------|
| `terraform` | 인프라 | `terraform/modules/...` |
| `k8s-manifest` | 워크로드 | `kubernetes/src/<sphere>/...` |
| `k8s-crd` | 워크로드 | CRD 정의 |
| `helm-chart` | 워크로드 | `kubernetes-charts/charts/...` |
| `jsonnet` | 워크로드 | `kubernetes/src/<sphere>/*.jsonnet` |
| `kyverno-policy` | 정책 | `kubernetes/src/infra/kyverno/...` |
| `alert-rule` | 관측 | VMRule/PrometheusRule YAML |
| `api-spec` | 인터페이스 | OpenAPI, Protobuf |
| `ops-change` | 운영 변경 | 스펙 아티팩트 해당 없음 |

---

## codex 예산

codex는 ChatGPT 플랜의 5시간 단위 한도와 주간 한도를 함께 쓴다(Codex, Work 등과 공유). 둘 다 남아야 호출된다.

- 실측 기준(2026-11-23, ChatGPT Plus): 주장 15건 검증 1회(effort high, 웹 검색 약 7회)가 약 5만~11만 토큰, 평균 약 6만.
  호출 12회(약 71만 토큰, 4개 병렬 약 5분)에 5시간 한도가 소진됐다
- **codex 단계를 시작하기 전에** 예상 사용량을 채팅에 한 줄로 보인다: `codex 예정: <단계> <호출 수>회 × 약 6만 = 약 <N>만 토큰`.
  이번 5시간 창 누적 예상이 약 60만을 넘으면 진행 전에 사용자에게 묻는다(사용량 화면: https://chatgpt.com/settings/usage)
- 기본 effort: codex 독립 수집은 medium(검색·인용 수집 위주라 추론 부담이 작다. 2026-11-23 PgBouncer 실행에서 수집이 codex 사용량의 59%, 약 118만 토큰),
  주장 검증은 계획·스펙이 인용한 주장만 medium, 수집 상호 검토와 리뷰(계획·스펙)는 high(판단이 필요한 단계)
- 더 줄여야 하면: codex 수집 `--parallel 2` → 수집 대상 서브질문을 `--only`로 좁힌다
- 한도에 걸리면(`codex_usage_limit (try again at HH:MM)`) 완료된 결과는 지우지 않고, 해제 시각을 알린 뒤 사용자가 고르게 한다:
  해제 후 재개 / Claude 서브에이전트로 대체 / codex는 스펙 리뷰만

## 주의사항

- codex 모델은 모든 호출에서 `gpt-6.1-sol`이 기본값이다. reasoning effort 기본값은 리뷰(`codex_review.py`)와 수집 상호 검토(`codex_research.py cross-review`)가 `high`,
  독립 수집(`codex_research.py collect`)이 `medium`이다. 주장 검증(research:deep `codex_verify.py`)은 위 절차대로 `--effort medium`을 넘긴다
- codex 호출은 Bash 포그라운드 한도(600초)를 넘기 쉬우므로 반드시 `run_in_background=true`로 실행한다. `codex` 셸 alias를 직접 쓰지 않는다(스크립트가 `-s read-only`로 실행)
- 비용: Standard 1회에 research:deep(리서처 3~5개 + codex 검증), 사내 조사 Agent 0~3개, 리뷰 라운드마다 codex 1회 + Claude Agent 1개가 든다.
  단순 운영 변경이면 Quick 모드를 권한다
- 기존 Obsidian 스펙은 `tasks:tech-spec-ops`와 `scripts/tech-spec.py`가 다룬다(과거 문서용). 이 스킬은 Obsidian에 저장하지 않는다
- 2026-11-23 개편 전 버전은 `~/.claude/skills-backup-tasks-tech-spec-20261123/`에 있다
