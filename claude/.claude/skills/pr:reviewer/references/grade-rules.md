# 등급 규칙과 판정 원리

`scripts/grade_rules.json`의 정본 설명이다. 규칙을 고칠 때 이 문서도 함께 고친다.

---

## 왜 등급인가

AI가 산출물을 만드는 속도가 사람이 이해하는 속도를 앞지르면 병목은 생산이 아니라 이해로 옮겨간다.
그렇다고 모든 PR을 같은 깊이로 이해할 필요는 없다. 이해 비용은 균등 배분이 아니라
**다시 만질 확률 × blast radius**에 비례해 배분한다. 여기에 두 가지 보정이 붙는다.

- **조용한 실패**: 틀려도 에러가 나지 않고 데이터·권한·알럿만 사라지는 변경은 blast radius가 작아 보여도 가장 비싸다. 발견 장치 자체가 고장나기 때문이다.
- **검증 장치 유무**: 테스트·CI·파이프라인이 변경을 대신 검증할 수 있으면 사람의 이해가 장치를 대신할 필요가 없다. 장치가 없는 곳에서는 이해가 장치를 대신해야 한다.

---

## 등급

| 등급 | 뜻 | 모드 | 예 |
|------|----|------|----|
| **A** | 이해 필수. 소유자가 이론을 머리에 들고 있어야 한다 | 리뷰어 질문 → 판정 | GitOps 매니페스트, Terraform, 관측 파이프라인, 마이그레이션, CI, ADR/PRD, 권한, API 계약, 런타임 설정 |
| **B** | 검증 장치가 대신한다. 장치의 존재와 범위만 확인 | 요약 | TS/JVM/파이썬 소스, 테스트, 빌드 설정, 비프로드 이미지 태그 승격 |
| **C** | 기계적. 이해할 것이 없다 | 요약 | lockfile, 포맷 설정, vendored 산출물, 스냅샷, 일반 문서 |

PR 등급 = 파일 등급의 최댓값. 파일 등급 = 매칭된 규칙의 최댓값.

---

## 규칙의 두 종류

**path_rules**: 파일 경로에 정규식. 등급과 사유, 선택적으로 플래그를 준다.
**content_rules**: 그 파일의 **추가된 라인**에 정규식. `applies_to`가 경로 조건이다. `grade: null`이면 등급은 안 바꾸고 플래그만 붙인다(예: TODO 표식).

플래그는 리뷰어 질문의 축을 고른다.

| 플래그 | 붙이는 규칙 | 추가되는 축 |
|--------|------------|------------|
| `silent_failure` | 관측 파이프라인 경로, drop/keep 규칙 | 실패 양상 |
| `prod` | 경로 토큰 `prod`/`production`/`live`/`global`, Terraform | 영향 범위, 롤백 |
| `runtime` | replicas/image/limits 같은 노브 | 영향 범위 |
| `one_way_door` | 파괴적 DDL, `rm -rf`, force push, kubectl의 delete·edit 호출 | 롤백 |
| `contract` | openapi/proto, `src/types`, `src/data`, 백엔드 web 모듈 | 호환성 |
| `security` | 권한·시크릿 경로, 리터럴 자격증명, permitAll 류 | 노출 |
| `decision` | ADR, PRD, context 문서 | 기각 대안, 의도적 제외 |

축은 항상 `의도`, `메커니즘`, `검증` 3개에 플래그 축을 더해 최대 5개다. 우선순위는 `axis_selection.priority`.

---

## 스크립트가 스스로 조정하는 두 경우

- **관례 배포 하향 (A → B)**: 모든 파일의 추가 라인이 이미지 태그 한 줄뿐이고 `prod`가 없으면 B. 파이프라인이 검증 장치다. prod가 하나라도 있으면 A 유지.
- **검증 장치 부재 상향 (B → A)**: B인데 리포에 `.github/workflows`가 없으면 A. 존재하지 않는 장치는 이해를 대신할 수 없다.

조정 내역은 `adjustment` 필드에 남고 출력에 인용한다.

---

## Claude가 보정하는 것

스크립트는 경로와 정규식만 본다. 다음은 Claude가 `context.diff`를 읽고 판단한다.

- 문서(C)이지만 runbook·온콜 절차·롤백 절차를 바꿈 → A로 올린다.
- 소스(B)이지만 테스트가 바뀐 경로를 덮지 않음 → A로 올린다.
- A 규칙에 걸렸지만 실제 변경이 주석·문자열뿐 → 사유를 적고 내린다.
- 경로에 환경 토큰이 없는 리포 → `prod` 플래그를 손으로 보정한다.

---

## 예시: Alloy 파이프라인 변경

`src/observability/alloy/infra-k8s-global/values.yaml`에 `action = "drop"` 규칙 추가.

- path: `gitops-manifest`(A), `observability-pipeline`(A, silent_failure), 경로 토큰 `global` → prod
- content: `relabel-drop-keep`(A, silent_failure)
- 축: 의도, 메커니즘, 검증, 실패 양상, 영향 범위

리뷰어가 묻는 것은 Alloy 내부가 아니다. 이 블록에 무엇이 들어오고 나가는지, 규칙이 넓게 매칭되면 무엇이 사라지는지, 그것을 `loki_process_dropped_lines_total` 같은 어떤 지표로 10분 안에 확인하는지다. 세 가지에 답하면 충분한 이해이고 소스를 열 필요는 없다.

---

## 규칙 고치기

```bash
python3 /Users/changhwan/.claude/skills/pr:reviewer/scripts/triage_pr.py rules
python3 /Users/changhwan/.claude/skills/pr:reviewer/scripts/triage_pr.py classify --path src/santa/gateway/prod.jsonnet --path README.md
```

- 새 경로 유형이 `default`(B)로 떨어지면 규칙을 추가한다. 사유는 "왜 이 등급인가"를 한 문장으로.
- 규칙이 너무 넓어 관례 작업이 A로 올라오면 규칙을 좁히지 말고 `routine`에 관례 패턴을 추가한다. 규칙의 사유는 여전히 참이기 때문이다.
- 정규식은 리포 상대 경로에 적용된다. 리포 이름은 경로에 없다.
