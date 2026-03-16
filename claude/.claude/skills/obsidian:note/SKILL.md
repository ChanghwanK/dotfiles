---
name: obsidian:note
description: |
  Claude와의 학습/개념 설명 대화 결과를 Obsidian 노트로 저장하는 스킬.
  domain/ 태그로 학습 주제를 분류하고 aliases를 자동 추출하여 검색성을 높인다.
  사용 시점: (1) 개념 설명 요청 후 노트 저장, (2) 학습 내용 정리,
  (3) 특정 주제에 대한 참고 문서 생성.
  트리거 키워드: "obsidian 노트", "노트로 저장", "obsidian에 저장", "/obsidian:note", "옵시디언 노트".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---

# Obsidian Note Skill

현재 대화에서 학습/설명한 내용을 Obsidian `02. Notes/engineering/` 또는 `02. Notes/others/` 디렉토리에 마크다운 파일로 저장한다.

**타입별 저장 경로 매핑**:

| `--type` 값 | 저장 경로 |
|-------------|----------|
| `learning-note` (기본) | `02. Notes/engineering/` (또는 `--category others`로 `02. Notes/others/`) |
| `troubleshooting` | `03. Resources/troubleshooting/` |
| `runbook` | `03. Resources/runbooks/` |
| `cheatsheet` | `03. Resources/cheatsheets/` |

> Resource 타입(`runbook`, `troubleshooting`, `cheatsheet`) 지정 시 `--category` 옵션은 무시되며 타입이 경로를 결정합니다.

## 핵심 원칙

- **대화 내용 기반**: 현재 대화에서 설명된 내용을 구조화된 마크다운으로 정리한다.
- **파일명 규칙**: `slugified-title.md` 형식으로 자동 생성된다 (날짜 prefix 없음).
- **domain/ 태그**: `domain/kubernetes`, `domain/aws`, `domain/observability`, `domain/networking`, `domain/terraform`, `domain/database`, `domain/on-premise` 중 선택.
- **aliases 자동 추출**: 노트 제목과 본문에서 핵심 키워드(약어, 기술 용어, 한국어 쌍)를 자동 추출하여 Quick Switcher(Cmd+O) 검색을 활성화한다.
- **날짜 자동화**: 오늘 날짜가 `date`, `last_reviewed` 두 필드에 모두 기록된다.
- **관련 노트 자동 링크**: 같은 domain/ 태그를 가진 기존 노트를 탐색하여 "관련 노트" 섹션에 wikilink로 자동 추가.

## 태그 네임스페이스

| domain/ 태그 | 커버리지 |
|-------------|---------|
| `domain/kubernetes` | K8s, Karpenter, KEDA, Helm, ArgoCD |
| `domain/aws` | EC2, EKS, VPC, Aurora, Route53, CloudFront, NAT |
| `domain/observability` | Prometheus, Grafana, Tempo, Loki, OTel, VictoriaMetrics |
| `domain/networking` | Istio, Envoy, Service Mesh, VPC 네트워킹 |
| `domain/terraform` | Terraform, IaC |
| `domain/database` | PostgreSQL, Aurora, CNPG, Redis |
| `domain/on-premise` | IDC, Proxmox, GPU, Ceph, Cluster API |
| `domain/security` | TLS, PKI, 인증서, mTLS, IAM, RBAC |
| `domain/ai` | LLM, ML, 모델 서빙, GPU 워크로드 |

**기존 태그 자동 변환**: Kubernetes → domain/kubernetes, Istio → domain/networking 등 자동 매핑.

## aliases 자동 추출 로직

스크립트가 다음을 자동 추출합니다:
- 대문자 약어: `NAT`, `TCAM`, `OTel`, `FPGA`
- 고유명사: `Karpenter`, `Istio`, `Hyperplane`
- 백틱 기술 용어: `` `NodePool` ``, `` `metrics_generator` ``
- 에러 코드: `503`, `p99`, `p50`
- 제목의 한국어 키워드: `카펜터`, `섀도우 배포`

## 워크플로우

### Step 1 — 대화 내용 분석 및 마크다운 정리

**핵심 원칙:**
- **요약이 아닌 정리** — 대화에서 설명된 모든 내용을 빠짐없이 포함. 핵심만 추리지 않는다.
- **대화 흐름 보존** — Q&A, What-if 시나리오, 비교 분석 등 대화에서 나온 맥락을 유지.
- **깊이 유지** — 원리 설명, 코드, 다이어그램, 테이블 등 대화에서 사용된 표현 수단을 그대로 활용.

**필수 섹션 (반드시 포함):**
1. `## 핵심 개념` — 주제의 정의와 Why (왜 필요한지)
2. 주제별 본문 섹션들 — 대화 흐름에 맞게 자유롭게 구성
3. `## 정리` — 핵심 takeaway 3-5개 bullet point

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
- 리스트에서 `—` (em dash)로 설명 연결 금지. 중첩 불릿으로 설명을 분리
  - ❌ `- **CDP** — 크롬 브라우저를 직접 제어하는 프로토콜`
  - ✅ `- **CDP**` + 하위 `  - 크롬 브라우저를 직접 제어하는 프로토콜`

### Step 2 — 제목과 태그 결정

- **제목**: 학습 주제를 간결하게, **하이픈(`-`) 사용 금지** — 단어 구분은 공백으로 (예: `Kubernetes Init Container 라이프사이클`)
- **태그**: 위 domain/ 네임스페이스에서 1개 이상 선택 (기존 태그명 입력 시 자동 변환)

### Step 3 — content.json 작성

마크다운 본문을 `/tmp/obsidian-content.json`에 저장한다:

```json
{
  "blocks": "마크다운 전체 텍스트"
}
```

### Step 4 — 노트 생성 스크립트 실행

```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "제목" \
  --tags "Kubernetes,Infra" \
  --type "learning-note" \
  --category "engineering" \
  --content-file /tmp/obsidian-content.json
```

`--type` 옵션: `learning-note` (기본값) | `troubleshooting` | `cheatsheet`

`--category` 옵션: `engineering` (기본값) | `others`
- `engineering`: DevOps/인프라/관측 기술 노트 → `02. Notes/engineering/`
- `others`: 방법론, 자기계발 등 비-엔지니어링 노트 → `02. Notes/others/`

### Step 5 — 결과 출력

스크립트의 JSON 응답을 파싱 후 사용자에게 출력:

```
Obsidian 노트가 생성되었습니다.
- 제목: {title}
- 태그: {tags}
- aliases: {aliases} (자동 추출)
- 날짜: {date}
- 파일: {filename}
- 관련 노트: {related_count}개 링크됨 (없으면 생략)
```

## 최근 노트 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py list --limit 10
```

## 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
- 파일이 실제로 생성되었는지 `filepath`로 확인
