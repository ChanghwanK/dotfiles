---
name: work:tech-spec
description: |
  인프라/DevOps Tech Spec 문서를 Obsidian에 생성하는 스킬. 대화 맥락에서 주제를 파악하여 제목을 동적 생성하고 합의된 최소 템플릿으로 구조화된 문서를 작성한다.
  사용 시점: (1) 인프라 변경 계획 문서화, (2) 설계 의사결정 기록, (3) 대화에서 논의된 작업을 Tech Spec으로 정리.
  트리거 키워드: "tech spec", "기술 스펙", "스펙 문서", "tech-spec 작성", "/work:tech-spec".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/work:tech-spec/scripts/tech-spec.py *)
  - Write(/tmp/tech-spec-content.json)
---

# work:tech-spec Skill

대화에서 논의된 인프라/DevOps 작업을 구조화된 Tech Spec 문서로 Obsidian에 저장한다.

**저장 경로**: `/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Engineering/tech_spec`

## 핵심 원칙

- **대화 기반**: 현재 대화에서 논의된 내용을 분석하여 Tech Spec 섹션을 채운다.
- **파일명 규칙**: `slugified-title.md` 형식 (날짜 prefix 없음).
- **태그 분류**: 작업 주제에 맞는 태그를 복수 선택한다.
- **상태 관리**: frontmatter `status` 필드로 라이프사이클 추적 (`시작전` → `진행중` → `완료`).
- **유형 판단**: 대화 맥락을 분석하여 **운영 변경**(기존 시스템 수정)인지 **인프라 설계**(신규 설계)인지 판단한다.

## 지원 태그 목록

| 카테고리 | 태그 |
|----------|------|
| 인프라 | `Kubernetes`, `AWS`, `Terraform`, `Infra`, `Network` |
| 서비스 메시 | `Istio`, `Envoy`, `ServiceMesh` |
| 관측가능성 | `Observability`, `Grafana`, `Prometheus`, `Loki`, `Tracing` |
| AI/ML | `AI`, `Agent`, `GPU`, `LLM` |
| 개발 | `Engineering`, `Security`, `자동화`, `OS`, `Git` |
| 기타 | `Issue`, `Design`, `Architecture` |

새로운 태그가 필요한 경우 직접 추가해도 된다.

## Tech Spec 템플릿

두 가지 유형:
- **운영 변경**: ConfigMap 변경, 스케일링, 마이그레이션 등 기존 시스템 수정
- **인프라 설계**: 새 클러스터 구축, VPC 아키텍처, 신규 서비스 인프라 등 신규 설계

```markdown
# {제목}

## 왜 이걸 해야 하는가?
현재 문제/동기/배경

## 현재 상태와 목표
- 운영 변경: Before(현재) → After(변경 후)
- 인프라 설계: 요구사항 → 목표 아키텍처

## 설계
(인프라 설계 유형에서만 상세 작성. 운영 변경은 생략하거나 간략하게)
- 컴포넌트 구성, 네트워크 토폴로지, 리소스 스펙
- 제약조건 (비용, 성능, 보안, 의존성)

## 왜 이 방법인가?
선택한 접근법 근거 + 기각된 대안들

## 실행 계획
단계별 절차, 각 단계의 전제조건과 검증 방법
잘못되면? (영향범위, 롤백, Point of No Return)

## 임팩트 측정
성공 기준 (무엇을 측정할 것인가)
Before 수치 → After 목표치
측정 방법 (대시보드, 쿼리, 명령어)

## 실제 결과 (Outcome)
(완료 후 작성)
계획 vs 실제 차이, 측정 결과, 배운 점
```

**유형별 작성 가이드**:
- 운영 변경: "설계" 섹션 생략 가능. "실행 계획"과 "임팩트 측정"에 집중.
- 인프라 설계: "설계" 섹션 상세 작성. 다이어그램, 리소스 스펙, 제약조건 포함.
- "실제 결과" 섹션은 빈 placeholder로 남긴다: `> 완료 후 작성`

## 워크플로우

### Step 1 — 대화 맥락 분석

대화에서 다음을 파악한다:
- 작업 주제와 동기
- 운영 변경인지 인프라 설계인지
- 핵심 의사결정과 대안
- 실행 계획과 영향 범위

### Step 2 — 제목과 태그 결정

- **제목**: 작업을 간결하게 설명 (예: `VictoriaMetrics vmagent ConfigMap 최적화`)
- **태그**: 위 태그 목록에서 1개 이상 선택

### Step 3 — content.json 작성

마크다운 본문을 `/tmp/tech-spec-content.json`에 저장한다:

```json
{
  "blocks": "마크다운 전체 텍스트 (위 템플릿 구조)"
}
```

### Step 4 — 스크립트 실행

```bash
python3 /Users/changhwan/.claude/skills/work:tech-spec/scripts/tech-spec.py create \
  --title "제목" \
  --tags "Kubernetes,Infra" \
  --content-file /tmp/tech-spec-content.json
```

### Step 5 — 결과 출력

스크립트의 JSON 응답을 파싱 후 사용자에게 출력:

```
Tech Spec이 생성되었습니다.
- 제목: {title}
- 태그: {tags}
- 상태: {status}
- 날짜: {date}
- 파일: {filename}
- 관련 스펙: {related_count}개 링크됨
```

## 목록 조회

```bash
python3 /Users/changhwan/.claude/skills/work:tech-spec/scripts/tech-spec.py list --limit 10
python3 /Users/changhwan/.claude/skills/work:tech-spec/scripts/tech-spec.py list --status 진행중
```

## 상태 변경

```bash
python3 /Users/changhwan/.claude/skills/work:tech-spec/scripts/tech-spec.py update-status \
  --filename "파일명.md" \
  --status 진행중
```

유효한 상태값: `시작전`, `진행중`, `완료`

## 검증

- 스크립트 응답의 `success` 필드 확인
- `success: false`이면 에러 메시지를 사용자에게 전달
- 파일이 실제로 생성되었는지 `filepath`로 확인
