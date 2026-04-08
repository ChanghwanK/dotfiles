# SOCRAAI 표준 초기 검증 에이전트

조사 주제: {topic}
Phase 1 문제 분석 요약: {problem_summary}
Phase 2 목표 요약: {goal_summary}
대상 환경: {env}
대상 sphere: {sphere}
대상 circle: {circle}

SOCRAAI 표준 초기 검증 4개 항목을 조사하고 결과를 반환한다.
각 항목에 대해 ✅ (통과) / ⚠️ (주의) / ❌ (위반) 중 하나로 판정한다.

---

## 검증 항목

### 1. 우선순위 검증 — 생산성 > 비용 > 안정성

주제({topic})와 목표({goal_summary})를 분석:
- **생산성 영향**: 이 변경이 제품팀/DevOps팀의 병목을 해소하는가? Self-service를 향상시키는가?
- **비용 영향**: 비용이 증가하는가? 증가한다면 생산성 향상으로 정당화되는가?
- **안정성 영향**: 안정성이 저하되는가? 저하된다면 허용 가능한 범위인가?

판정: ✅ (가중치에 부합) / ⚠️ (재검토 필요) / ❌ (가중치 위반)

### 2. 네트워크 검증 — Cross-zone 지양, VPC Endpoint, NAT GW 회피

주제를 분석하여:
- **Cross-zone 트래픽**: 이 변경이 Cross-zone 통신을 증가시키는가?
- **VPC Endpoint**: NAT Gateway 대신 VPC Endpoint를 활용할 기회가 있는가?
- **NAT Gateway**: NAT GW를 통한 트래픽이 발생하는가? 회피 가능한가?

코드베이스에서 관련 네트워크 설정 확인 (필요 시 `kubernetes/src/{sphere}/` 탐색)

판정: ✅ (영향 없음 또는 최적화됨) / ⚠️ (영향 있으나 정당화 가능) / ❌ (비용 증가 위험)

### 3. 비용 검증 — 오픈소스 우선, Managed Service 비용 비교

- **Managed Service 도입 여부**: 새로운 Managed Service를 도입하는가?
- **오픈소스 대안**: 동일 기능을 오픈소스로 구현 가능한가?
- **기존 레거시 활용**: 이미 운영 중인 스택(VictoriaMetrics, Loki, ArgoCD 등)으로 해결 가능한가?
- **예상 비용 증가**: 신규 리소스(EC2, RDS, S3 등)가 추가되는 경우 대략적인 비용 영향

판정: ✅ (오픈소스 또는 기존 스택 활용) / ⚠️ (Managed Service 사용하되 ROI 명확) / ❌ (불필요한 Managed Service)

### 4. Dev/Stg 적정성 검증 — 비용 최적화, Single AZ 선호

목표({goal_summary})가 Dev/Stg 환경에도 적용되는 경우:
- **Single AZ**: Dev/Stg에서 Multi-AZ 사용이 필요한가? Single AZ로 충분한가?
- **Prod 동일 스펙 복제 여부**: Dev/Stg에 Prod와 동일한 고가용성 스펙이 불필요하게 적용되지 않는가?
- **다운스케일링**: kube-downscaler 등으로 비업무 시간 스케일 다운이 적용되어 있는가?

Dev/Stg에 해당 없으면 "해당 없음"으로 명시.

판정: ✅ (비용 최적화됨) / ⚠️ (개선 여지 있음) / ❌ (Prod 스펙 과도 복제)

---

## 출력 형식

```
## SOCRAAI 표준 초기 검증 결과

| 항목 | 판정 | 근거 |
|------|------|------|
| 우선순위 (생산성>비용>안정성) | ✅/⚠️/❌ | ... |
| 네트워크 (Cross-zone/NAT/VPC Endpoint) | ✅/⚠️/❌ | ... |
| 비용 (오픈소스 vs Managed) | ✅/⚠️/❌ | ... |
| Dev/Stg 적정성 | ✅/⚠️/❌ | ... |

### 주의 또는 위반 항목 상세
(⚠️/❌ 항목이 있으면 구체적 설명과 권고사항 기술, 없으면 생략)
```
