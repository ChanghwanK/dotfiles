# Release Note Analysis 출력 템플릿

## Release Note Analysis

### 기본 정보
| 항목 | 값 |
|------|-----|
| 기술 | {technology} |
| 릴리스 버전 | {new_version} |
| 릴리스 날짜 | {release_date} |

### 현재 환경별 버전
| 환경 | Chart | 현재 버전 | 최신 버전 | 상태 |
|------|-------|-----------|-----------|------|
| infra-k8s-dev | {chart_name} | {current} | {new} | ✅ 최신 / ⚠️ 업데이트 필요 |
| infra-k8s-stg | ... | ... | ... | ... |
| infra-k8s-prod | ... | ... | ... | ... |

> ⚠️ **버전 불일치**: infra-k8s-global 이 1.28.0으로 다른 환경과 다릅니다.

### 주요 변경사항 요약

**Breaking Changes** (영향도: HIGH / MEDIUM / LOW / NONE)
- {breaking change 1} → 현재 설정 영향: {있음/없음}
- {breaking change 2} → 현재 설정 영향: {있음/없음}

**신규 기능**
- {feature 1} → 활용 가능성: {높음/낮음}

**Deprecation 경고**
- {deprecated item} → 제거 예정: {버전} / 대응 필요 시점: {timeline}

**보안 수정**
- {CVE-XXXX-YYYY}: {severity} → 긴급 업그레이드 권장 여부

### 업그레이드 권고

**권고: ✅ 업그레이드 권장 / ⚠️ 조건부 권장 / ❌ 보류 권장**

근거:
- {권고 이유 1}
- {권고 이유 2}

수정 필요 파일:
- `src/infra/{circle}/infra-k8s-dev/kustomization.yaml` — version: {new}
- `src/infra/{circle}/infra-k8s-stg/kustomization.yaml` — version: {new}
- `src/infra/{circle}/infra-k8s-prod/kustomization.yaml` — version: {new}

values.yaml 수정 필요:
- `{옵션명}`: {변경 내용} (Breaking Change 대응)

롤아웃 순서: dev → stg → prod (최소 24h 간격 권장)

주의사항:
- {주의사항 1}
- {주의사항 2}
