---
name: wiki:note
description: |
  대화 결과를 04. Wiki/ 또는 03. Resources/에 구조화된 노트로 저장하는 스킬.
  사용자 요청(명시적) 또는 Claude 자동 제안(인사이트 감지) 두 가지 방식으로 동작.
  지원 타입: learning-note(기술 개념) · troubleshooting(에러 해결) · runbook(운영 절차) ·
  cheatsheet · incident(장애 post-mortem).
  사용 시점: (1) 학습/개념 설명 대화 후 노트화, (2) 트러블슈팅 해결 패턴 기록,
  (3) 장애 분석 post-mortem 저장, (4) 대화 인사이트 즉시 filing.
  트리거 키워드: "wiki 노트", "노트로 저장", "wiki에 저장", "/wiki:note",
  "위키에 저장", "wiki에 남겨", "노트로 저장해".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py *)
  - Agent
---

# Obsidian Note Skill

## TL;DR

- 대화에서 학습/설명한 내용을 **요약 없이 전체 구조화**하여 Obsidian 마크다운으로 저장
- 태그로 주제 분류, aliases 자동 추출로 Quick Switcher 검색성 확보
- 타입별 저장 경로 분기: `learning-note` → `04. Wiki/engineering/`, `runbook`·`troubleshooting`·`cheatsheet` → `03. Resources/`
- 관련 노트 자동 탐색 및 wikilink 연결

현재 대화에서 학습/설명한 내용을 Obsidian `04. Wiki/` 하위 디렉토리에 마크다운 파일로 저장한다.

**타입별 저장 경로 매핑**:

| `--type` 값 | 저장 경로 |
|-------------|----------|
| `learning-note` (기본) | `04. Wiki/engineering/` |
| `troubleshooting` | `03. Resources/troubleshooting/` |
| `runbook` | `03. Resources/runbooks/` |
| `cheatsheet` | `03. Resources/cheatsheets/` |
| `incident` | `04. Wiki/incidents/` |

> Resource 타입(`runbook`, `troubleshooting`, `cheatsheet`) 지정 시 `--category` 옵션은 무시되며 타입이 경로를 결정합니다.

## 핵심 원칙

- **대화 내용 기반**: 현재 대화에서 설명된 내용을 구조화된 마크다운으로 정리한다.
- **파일명 규칙**: `slugified-title.md` 형식으로 자동 생성된다 (날짜 prefix 없음).
- **태그**: `kubernetes`, `aws`, `observability`, `networking`, `terraform`, `database`, `on-premise`, `security`, `ai` 중 선택.
- **aliases (Claude 결정)**: 노트 내용을 바탕으로 핵심 키워드 3개를 Claude가 직접 판단하여 `--aliases`로 전달한다. Quick Switcher(Cmd+O) 검색을 활성화한다.
- **날짜 자동화**: 오늘 날짜가 `date`, `last_reviewed` 두 필드에 모두 기록된다.
- **관련 노트 자동 링크**: 같은 태그를 가진 기존 노트를 탐색하여 "관련 노트" 섹션에 wikilink로 자동 추가.

## 태그 네임스페이스

| 태그 | 커버리지 |
|------|---------|
| `kubernetes` | K8s, Karpenter, KEDA, Helm, ArgoCD |
| `aws` | EC2, EKS, VPC, Aurora, Route53, CloudFront, NAT |
| `observability` | Prometheus, Grafana, Tempo, Loki, OTel, VictoriaMetrics |
| `networking` | Istio, Envoy, Service Mesh, VPC 네트워킹 |
| `terraform` | Terraform, IaC |
| `database` | PostgreSQL, Aurora, CNPG, Redis |
| `on-premise` | IDC, Proxmox, GPU, Ceph, Cluster API |
| `security` | TLS, PKI, 인증서, mTLS, IAM, RBAC |
| `ai` | LLM, ML, 모델 서빙, GPU 워크로드 |

**기존 태그 자동 변환**: Kubernetes → kubernetes, Istio → networking 등 자동 매핑.

## aliases 결정 기준

노트 저장 전에 Claude가 직접 **3개**를 선택하여 `--aliases`로 전달한다. 3개는 각기 다른 역할을 맡는다.

**3개 역할 구성 (모두 채울 것):**
1. **Role A — 기술 약어/공식 명칭**: 영어 약어 또는 제품명 (예: `IRSA`, `mTLS`, `KEDA`, `CloudFront`)
2. **Role B — 한국어 개념어**: 영어 이름이 생각 안 날 때 타이핑할 단어 (예: `파드 권한`, `분산 추적`, `노드 자동 확장`)
3. **Role C — 연관 개념 진입점**: 이 노트 내용을 떠올리지만 제목과 다른 각도의 키워드 (예: `AWS 권한 위임`, `사이드카 프록시`, `카나리 배포`)

**안티패턴 (사용 금지):**
- 제목의 단어 그대로 반복 (대소문자·띄어쓰기만 다른 것 포함)
- 범용어: `설정`, `가이드`, `방법`, `노트`, `개념`, `정리`, `사용법`
- 동사형·문장형: `어떻게 설정하는지`, `사용하는 방법`
- 구두점 포함: `/`, `(`, `)`, `:` (기술 명칭의 일부인 경우 제외)

**자가 검증:** 작성 후 "Quick Switcher(Cmd+O)에서 이 단어를 타이핑하면 이 노트가 나올까?" 질문.

**예시:**

| 노트 제목 | Role A | Role B | Role C |
|-----------|--------|--------|--------|
| `IRSA 설정 가이드` | `IRSA` | `파드 권한` | `IAM Roles for Service Accounts` |
| `Karpenter 노드 프로비저닝` | `Karpenter` | `노드 자동 확장` | `EC2NodeClass` |
| `Loki 로그 수집 아키텍처` | `Loki` | `로그 파이프라인` | `LogQL` |
| `Istio mTLS 설정` | `mTLS` | `서비스 메시 암호화` | `PeerAuthentication` |

## 워크플로우

### Step 1 — 대화 내용 분석 및 마크다운 정리

**핵심 원칙:**
- **요약이 아닌 정리** — 대화에서 설명된 모든 내용을 빠짐없이 포함. 핵심만 추리지 않는다.
- **대화 흐름 보존** — Q&A, What-if 시나리오, 비교 분석 등 대화에서 나온 맥락을 유지.
- **깊이 유지** — 원리 설명, 코드, 다이어그램, 테이블 등 대화에서 사용된 표현 수단을 그대로 활용.

**필수 섹션 (반드시 포함):**
1. `## Summary` — 노트 전체 내용을 5~7개 bullet point로 요약 (노트 최상단에 위치)
   - 대화에서 다룬 핵심 포인트를 빠짐없이 나열
   - 각 bullet은 한 문장으로, 독립적으로 읽혔을 때 의미가 통해야 함
   - 아래 형식으로 작성:
     ```
     ## Summary
     - aaa
     - bbb
     - ccc
     ```
2. `## 핵심 개념` — 주제의 정의와 Why (왜 필요한지)
3. 주제별 본문 섹션들 — 대화 흐름에 맞게 자유롭게 구성
4. `## 정리` — 핵심 takeaway 3-5개 bullet point

**선택 섹션 (대화에 해당 내용이 있으면 반드시 포함):**

| 대화에서 나온 내용 | 추가할 섹션 |
|-------------------|-----------|
| 아키텍처/흐름도 설명 | `## 아키텍처` 또는 `## 동작 흐름` (ASCII 다이어그램 포함) |
| 대안/비교 분석 | `## 비교 분석` (테이블 형식) |
| 코드/설정 예시 | `## 코드 예시` 또는 해당 섹션에 인라인 |
| 실무 적용 논의 | `## SOCRAAI 환경 적용` |
| What-if / 장애 시나리오 | `## 장애 시나리오` 또는 `## What-if` |
| Q&A (사용자 질문→답변) | 해당 주제 섹션에 통합, 또는 `## FAQ` |
| 명령어/CLI 참조 | `## 명령어 레퍼런스` |
| 주의사항/함정 | `## 주의사항` |

**콘텐츠 깊이 지침:**
- 한 줄 요약이 아니라, 대화에서 설명한 만큼의 깊이를 유지
- 코드 블록은 주석 포함하여 self-contained하게
- 비교는 반드시 테이블 형식 사용
- 흐름/순서가 있는 내용은 번호 리스트 또는 ASCII 다이어그램 사용

**문장 끊기 & 불릿 활용 지침:**
- **한 문장 = 한 사실/행동** — 복문(A이고 B이며 C인)은 각각 별도 불릿으로 분리
  - ❌ `NLB는 L4에서 동작하며 패킷을 그대로 전달하고 소스 IP를 보존한다.`
  - ✅ `- NLB는 L4(TCP/UDP)에서 동작한다.` / `- 패킷을 그대로 전달한다 (NAT 없음).` / `- 소스 IP가 백엔드까지 보존된다.`
- **3가지 이상 나열 → 불릿** — 문장 안에 쉼표로 열거하지 말고 각 항목을 별도 불릿으로
  - ❌ `관련 리소스로는 NodePool, EC2NodeClass, Disruption Policy가 있다.`
  - ✅ 불릿 3개로 분리하고 각각 한 줄 설명 추가
- **조건·예외는 중첩 불릿** — "단, ~의 경우", "단, ~를 제외하고" → 상위 불릿 + 하위 `  - 예외: ...`
- **산문(prose) 허용 범위** — 개념 정의 첫 문장, 섹션 도입부 1~2줄에 한해 허용. 그 이후는 불릿으로 전환
- **중첩은 2단계까지** — 불릿 > 하위 불릿. 3단계 중첩이 필요하면 섹션(`###`)으로 분리

지원 마크다운 요소:
- 헤딩 (`#`, `##`, `###`)
- 불릿/숫자 리스트
- 코드 블록 (``` 구문)
- 테이블 (`| col1 | col2 |`)
- 인용 (`>`)
- 인라인 서식 (`**bold**`, `*italic*`, `` `code` ``)

**금지 요소:**
- `---` 수평선(horizontal rule) — 섹션 구분에 절대 사용 금지. 섹션은 반드시 `##` 헤딩으로 구분
- 헤딩에 `—` (em dash) 사용 금지. 부제나 보충 설명이 필요하면 별도 `###` 하위 헤딩으로 분리
  - ❌ `## CDP로 Gmail 자동화 — 기술적 가능 vs 현실적 장벽`
  - ✅ `## CDP로 Gmail 자동화` + `### 기술적 가능 vs 현실적 장벽`
- 번호/레이블 헤딩은 `레이블: 제목` 형식 사용 — em dash(`—`) 사용 금지
  - ❌ `### 1단계 — 인증서 발급` / `### Step 1 — 앱 생성` / `### 규칙 1 — Deny 우선` / `### Case 1 — EKS Pod` / `## Level 0 — 왜 React인가`
  - ✅ `### 1단계: 인증서 발급` / `### Step 1: 앱 생성` / `### 규칙 1: Deny 우선` / `### Case 1: EKS Pod` / `## Level 0: 왜 React인가`
- 리스트에서 `—` (em dash)로 설명/예시/부연 연결 금지. 반드시 중첩 불릿으로 분리
  - 패턴 1: bold 용어 + 설명
    - ❌ `- **CDP** — 크롬 브라우저를 직접 제어하는 프로토콜`
    - ✅ `- **CDP**` → `  - 크롬 브라우저를 직접 제어하는 프로토콜`
  - 패턴 2: 사실/현상 + 구체적 예시/근거
    - ❌ `- AlertManager inhibition 미존재 — OOMKill 발생 시 이중 호출`
    - ✅ `- AlertManager inhibition 미존재` → `  - OOMKill 발생 시 이중 호출`
  - 패턴 3: 코드/설정 + 부연
    - ❌ `` - `oncall: true` 가 커스텀 OOM rule에만 존재 — 긴급 상황에 oncall 없음 ``
    - ✅ `` - `oncall: true` 가 커스텀 OOM rule에만 존재 `` → `  - 긴급 상황에 oncall 없음`

### Step 2 — 제목과 태그 결정

- **제목**: 학습 주제를 간결하게, **하이픈(`-`) 사용 금지** — 단어 구분은 공백으로 (예: `Kubernetes Init Container 라이프사이클`)
- **태그**: 위 태그 목록에서 1개 이상 선택 (기존 태그명 입력 시 자동 변환)

### Step 3 — 노트 생성 스크립트 실행

마크다운 본문을 stdin으로 직접 파이프하여 스크립트를 실행한다.
`<< 'OBSIDIAN_CONTENT_EOF'` 방식으로 heredoc을 사용하여 특수문자(`$`, `` ` ``, 따옴표 등)가 shell에 의해 해석되지 않게 한다.

스크립트 호출 전에 Claude가 핵심 키워드 3개를 결정한다 (`## aliases 결정 기준` 참고).

```bash
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py create \
  --title "제목" \
  --tags "Kubernetes,Infra" \
  --aliases "키워드1,키워드2,키워드3" \
  --type "learning-note" \
  --category "engineering" \
  --content-file - << 'OBSIDIAN_CONTENT_EOF'
마크다운 전체 텍스트
OBSIDIAN_CONTENT_EOF
```

`--type` 옵션: `learning-note` (기본값) | `troubleshooting` | `cheatsheet`

`--category` 옵션: `engineering` (기본값) | `career`
- `engineering`: 기술 노트 전체 (개념, 장애 분석, 인사이트 포함) → `04. Wiki/engineering/`
- `career`: 엔지니어링 철학/성장/팀 운영 노트 → `04. Wiki/career/`

### Step 4 — 노트 품질 리뷰 (Agent)

노트 생성 성공 후, Review Agent를 실행하여 aliases·구조·지식 연결을 자동 점검한다.

`agents/agent-note-reviewer.md`를 Read한 후 아래 변수를 치환하여 Agent tool로 호출한다:

- `{filepath}` → 스크립트 응답의 `filepath` 값
- `{title}` → 노트 제목
- `{aliases}` → `--aliases`로 전달한 값
- `{tags}` → 정규화된 태그 목록
- `{related_slugs}` → 스크립트 응답의 `related` 목록 (없으면 빈 배열)

Agent 결과가 반환되면:
- `overall_score ≥ 85`: "리뷰 통과" 메시지와 함께 `top_actions`만 표시
- `overall_score < 85`: 개선 항목을 사용자에게 구조화하여 표시
- 수정 적용: 사용자가 확인하면 Edit tool로 파일 직접 수정 (자동 적용 금지)

### Step 5 — 결과 출력

스크립트의 JSON 응답을 파싱 후 사용자에게 출력:

```
Obsidian 노트가 생성되었습니다.
- 제목: {title}
- 태그: {tags}
- aliases: {aliases}
- 날짜: {date}
- 파일: {filename}
- 관련 노트: {related_count}개 링크됨 (없으면 생략)
- Daily Note: {daily_linked가 true이면 "📝 Daily Note에 연결됨", false이면 생략}
```

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py list --limit 10
```

## 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
- 파일이 실제로 생성되었는지 `filepath`로 확인
