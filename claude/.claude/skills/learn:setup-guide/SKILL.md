---
name: learn:setup-guide
description: |
  특정 기술의 상세 적용 가이드를 생성하는 스킬. Generic(범용) / Applied(SOCRA AI 인프라 맞춤) 2모드 지원.
  사용 시점: (1) 새 기술 도입 전 구현 가이드 필요 시, (2) 우리 인프라에 맞춘 적용 방법 문서화,
  (3) 팀원 온보딩을 위한 단계별 설정 가이드 생성, (4) 공식 문서를 SOCRA AI 환경에 맞게 번역/적용.
  트리거 키워드: "setup guide", "적용 가이드", "설정 가이드", "구현 가이드", "how to", "/learn:setup-guide".
model: sonnet
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Write(/tmp/setup-guide-content.json)
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
---
# Setup Guide Generator

공식 문서와 베스트 프랙티스를 리서치하여 실행 가능한 단계별 구현 가이드를 생성하는 워크플로우 스킬.

---

## 핵심 원칙

- **리서치 우선**: 추측이 아닌 공식 문서와 검증된 레퍼런스를 근거로 작성
- **실행 가능성**: 모든 단계에는 실제 실행 가능한 명령어/코드 포함
- **모드 충실**: Generic은 범용성 유지, Applied는 SOCRA AI 컨텍스트 완전 반영
- **검증 포함**: 각 구현 단계 후 정상 동작 확인 방법 반드시 포함

---

## 모드 분기

요청 내용을 분석하여 아래 중 하나를 선택한다:

```
요청 분석
    │
    ├─ "우리", "우리 인프라", "우리 클러스터", SOCRA, sphere명,
    │   클러스터명(prod/stg/dev/global/idc), ArgoCD, Karpenter  → Applied 모드
    │
    ├─ 일반 기술명, 범용 사용법, 특정 인프라 언급 없음           → Generic 모드
    │
    └─ 판별 불가                                                 → 사용자에게 질문:
       "범용 가이드(어느 환경에서나 적용 가능)와
        SOCRA AI 맞춤 가이드(우리 클러스터/GitOps 기반) 중
        어떤 형태가 필요한가요?"
```

### Applied 모드 전용 컨텍스트

Applied 모드 가이드 작성 시 아래 인프라 컨텍스트를 매핑한다:

| 컨텍스트 | 값 |
|---------|-----|
| 클러스터 | infra-k8s-{prod,stg,dev,global,idc} |
| GitOps 경로 | `kubernetes/src/<sphere>/<app>/` |
| 배포 방식 | ArgoCD (kubectl edit/delete 금지) |
| Service Mesh | Istio |
| Node Provisioning | Karpenter |
| Registry | `harbor.global.riid.team` |
| Tokyo VPC | 10.0.0.0/16 |
| Seoul VPC | 10.100.0.0/16 |

---

## 워크플로우

### Step 1 — 주제 분석 및 모드 결정

1. 요청에서 기술명과 적용 맥락을 추출
2. 위 모드 분기 기준으로 Generic / Applied 결정
3. 모드 선택 이유를 한 줄로 출력 후 계속

```
분석: {기술명} — {Generic | Applied} 모드로 진행합니다.
사유: {모드 선택 이유 한 줄}
```

### Step 2 — 리서치

WebSearch와 WebFetch로 아래 정보를 수집한다:

- 공식 문서 (설치/설정/베스트 프랙티스)
- GitHub 공식 예제 및 README
- 알려진 트러블슈팅 사례

**Applied 모드 추가 리서치:**
- SOCRA AI 환경 관련 통합 사례 (예: "EKS + {기술}")
- 우리 스택과의 호환성 이슈 (Istio, Karpenter, ArgoCD)

### Step 3 — 가이드 작성

`assets/guide-template.md` 구조를 그대로 따르되, 각 섹션을 리서치 결과로 채운다.

**Applied 모드:** "SOCRA AI 환경 매핑" 섹션을 반드시 포함하고,
모든 예시 코드에 우리 환경 값(클러스터명, 네임스페이스, GitOps 경로 등)을 반영한다.

### Step 4 — 검증

가이드 작성 완료 후 아래 항목을 체크한다:

- [ ] 개요: 기술의 목적과 필요성 기술
- [ ] 사전 조건: 필요 도구/권한 명시
- [ ] 아키텍처 / 동작 원리: 흐름 설명 포함
- [ ] 핵심 개념: 구성 요소 정리
- [ ] 구현 단계: 각 단계에 실행 가능한 명령어 포함
- [ ] 검증 방법: 정상 동작 확인 방법 포함
- [ ] 트러블슈팅: 주요 오류 패턴 최소 2개
- [ ] Applied 모드 전용: SOCRA AI 환경 매핑 섹션 포함

### Step 5 — Obsidian 저장

가이드 생성 완료 후 저장 여부를 묻는다:

```
가이드 생성이 완료되었습니다.
→ Obsidian에 저장할까요? (Y/n)
```

"Y" 또는 Enter 시:
1. `/tmp/setup-guide-content.json` 작성 (title, content, tags, aliases)
2. `python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create --input /tmp/setup-guide-content.json` 실행
3. 저장된 파일 경로 출력

**저장 메타데이터:**
- title: `{기술명} 적용 가이드` (Applied) 또는 `{기술명} 구현 가이드` (Generic)
- tags: `["domain/devops", "setup-guide", "{기술 카테고리}"]`
- aliases: `["{기술명}", "{기술명} 설정", "{기술명} 설치"]`

---

## 주의사항

- WebSearch 결과가 공식 문서가 아닌 경우, 출처를 명시하고 검증 필요 표시
- Applied 모드에서 `kubectl edit` / `kubectl delete` 사용 금지 — ArgoCD GitOps 워크플로우 보호
- 비밀값(토큰, 패스워드)이 포함된 예시는 반드시 placeholder로 처리 (`${SECRET_NAME}`, `<YOUR_TOKEN>`)
- 환경별(prod/stg/dev) 차이가 있으면 별도 섹션 또는 표로 분리
