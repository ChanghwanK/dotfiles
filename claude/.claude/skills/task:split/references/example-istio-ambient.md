# 예시: Istio sidecar → ambient 모드 전환

2026-11-27 `/task:split`으로 만든 예시다(4단계, 11개 Task). 리포 기준 Istio는 6개 클러스터(dev, stg, prod 1.30.3 / global, idc, office 1.28.1)에 배포되어 있다.
ambient 동작(전환 순서, waypoint 우회)은 공식 문서로 확인하지 않은 내용이므로 실제 계획에서는 Task 01에서 대상 버전 문서로 다시 확인한다.

## 선행관계

```
Task 01 ─→ Task 02 ─→ Task 03 ─→ Task 04 ─┐
              └─────→ Task 05 ────────────┴─→ Task 07 ─→ Task 08 ─┬─→ Task 09 ─┬─→ Task 11
Task 01 ─────────────→ Task 06 ─────────────────────────────────────→ (Task 09) │
                                                                  └─→ Task 10 ─┘
```

- Task 05(모니터링), Task 06(서비스군 정의)은 Task 03, 04와 병렬로 진행한다.
- Task 09(prod)는 Task 06이 끝나야 시작한다.
- Task 10(global·idc·office)은 stg 통과 뒤 prod와 병렬로 진행한다.

## Task

**PoC**

- **Task 01. 전 클러스터 Istio 기능 사용 현황 조사**
  - 하위 항목
    - 6개 클러스터의 VirtualService, DestinationRule, ServiceEntry, AuthorizationPolicy, RequestAuthentication, EnvoyFilter, Sidecar, Telemetry 사용처 집계
    - Istio 1.30.3, 1.28.1 공식 ambient 문서와 기능별 지원 범위 대조
    - Argo Rollouts Istio trafficRouting의 waypoint 지원 여부 확인
    - idc·office 클러스터 CNI와 istio-cni 호환 조건 확인
  - 완료 조건
    - As-is: 우리가 쓰는 Istio 기능 중 무엇이 ambient 전환을 막는지 모름
    - To-be: 전환에 영향을 주는 기능과 사용처가 정리되어, PoC에서 시험할 범위와 클러스터별 제약을 말할 수 있음
  - 연결된 결정: PoC 검증 범위, 전환 대상 클러스터 범위
  - 판정 근거: 기능별 사용처 수와 공식 지원 여부를 대조한 표
  - 선행: 없음

- **Task 02. dev istio ambient 환경 구축**
  - 하위 항목
    - dev istio-system에 istio-cni, ztunnel 추가
    - 테스트 네임스페이스로 sidecar 서비스와 ambient 서비스 간 mTLS 통신 검증
    - 기존 sidecar 서비스의 오류율 무변화 확인
  - 완료 조건
    - As-is: dev 메시는 sidecar 방식뿐이라 ambient로 옮겨 볼 곳이 없음
    - To-be: dev에서 sidecar 서비스와 ambient 서비스가 서로 mTLS로 호출하며 함께 운영됨
  - 연결된 결정: 혼재 상태로 점진 전환할 수 있는지, 일괄 전환해야 하는지
  - 판정 근거: sidecar→ambient, ambient→sidecar, ingress→ambient 호출 성공과 mTLS 적용. 기존 서비스 5xx 비율이 설치 전과 같음
  - 선행: Task 01
  - 실행 체크리스트
    1. istio-cni, ztunnel 배포
    2. 테스트 네임스페이스에 ambient 라벨 적용
    3. injection 라벨 해제
    4. Pod 재시작

- **Task 03. 기존 트래픽 정책의 ambient 동작 검증**
  - 하위 항목
    - waypoint 배포 후 Argo Rollouts 카나리 트래픽 분배 검증
    - DestinationRule connectionPool, outlierDetection, locality LB 적용 검증
    - ServiceEntry 경유 외부 API 호출 검증
    - 혼재 상태에서 L7 AuthorizationPolicy, RequestAuthentication 집행 검증
    - 기능별 전환 가능 판정과 대체 방식 정리
  - 완료 조건
    - As-is: 카나리, 트래픽 정책, egress, 인가가 ambient에서 동작하는지 모름
    - To-be: 기능별로 "그대로 동작 / 바꿔야 동작 / 불가"가 판정되어, 어디까지 전환할 수 있는지 근거를 들어 말할 수 있음
  - 연결된 결정: 전환 범위(전체, 부분, 중단)와 기능별 대체 방식
  - 판정 근거: Task 01 목록의 기능별 dev 시험 결과. sidecar 출발 트래픽이 waypoint를 우회할 때도 정책이 집행되는지 포함
  - 선행: Task 01, 02

**전환 준비**

- **Task 04. 서비스 전환 표준과 Runbook 수립**
  - 하위 항목
    - webserver chart에 ambient 전환 옵션 추가 후 버전업
    - 전환·롤백 Runbook 수립
    - dev 서비스 1개로 Runbook만 보고 전환·롤백 검증
  - 완료 조건
    - As-is: 서비스를 ambient로 옮기려면 DevOps가 서비스마다 설정을 직접 판단해야 하고, 실패하면 되돌리는 절차가 없음
    - To-be: values 옵션과 Runbook만으로 누구나 서비스를 전환하고 정해진 시간 안에 되돌릴 수 있음
  - 연결된 결정: 전환 단위(서비스 또는 네임스페이스)와 롤백 방식
  - 판정 근거: Runbook만으로 전환·롤백 성공 여부, 롤백 소요 시간
  - 선행: Task 03
  - 실행 체크리스트 (Runbook에 담을 전환 순서)
    1. waypoint 배포
    2. L7 정책 이전
    3. ambient 라벨 적용
    4. injection 해제
    5. Pod 재시작

- **Task 05. ambient 모니터링 구성**
  - 하위 항목
    - ztunnel, waypoint에 VMServiceScrape 추가
    - Istio 알럿·대시보드를 ztunnel, waypoint 메트릭 기준으로 전환
    - waypoint 경유 트레이스의 Tempo, Kiali 표시 확인
    - dev 장애 주입으로 알럿 발화 검증
  - 완료 조건
    - As-is: ambient로 옮기면 sidecar 메트릭이 사라져, 장애가 나도 알럿으로 잡지 못함
    - To-be: ambient 서비스의 장애도 sidecar 때와 같은 알럿과 대시보드로 탐지됨
  - 연결된 결정: 확산 시작 여부
  - 판정 근거: dev에서 낸 장애(Pod 종료, 5xx 주입)에 알럿 발화
  - 선행: Task 02

- **Task 06. prod 서비스군과 전환 순서 확정**
  - 하위 항목
    - prod 서비스 간 호출 관계와 공유 컴포넌트(gateway, 인증) 정리
    - 실패 영향 범위 기준 서비스군 묶기와 전환 순서 확정
  - 완료 조건
    - As-is: prod를 어떤 순서로 옮겨야 영향 범위가 좁은지 모름
    - To-be: 서비스군마다 실패 시 영향받는 서비스를 말할 수 있고, 전환 순서가 정해짐
  - 연결된 결정: prod 전환 순서
  - 판정 근거: 서비스군별 호출자·피호출자 목록과 공유 컴포넌트 표시
  - 선행: Task 01

**전환**

- **Task 07. dev 전체 ambient 전환**
  - 하위 항목
    - dev 전 네임스페이스 Runbook 기준 전환
    - 관찰 기간 지표 비교
  - 완료 조건
    - As-is: dev 전 서비스가 Pod마다 sidecar를 달고 운영됨
    - To-be: dev 전 서비스가 sidecar 없이 운영되고, 관찰 기간 동안 전환으로 인한 장애가 없음
  - 연결된 결정: stg 진행 여부
  - 판정 근거: 관찰 기간 5xx 비율과 p99 지연을 전환 전과 비교, 롤백 발생 건수
  - 선행: Task 04, 05

- **Task 08. stg 전체 ambient 전환**
  - 하위 항목
    - stg 전 네임스페이스 Runbook 기준 전환
    - 관찰 기간 지표 비교
  - 완료 조건
    - As-is: stg 전 서비스가 sidecar로 운영됨
    - To-be: stg 전 서비스가 ambient로 운영되고, 관찰 기간 동안 전환으로 인한 장애가 없음
  - 연결된 결정: prod와 global·idc·office 진행 여부
  - 판정 근거: Task 07과 같은 지표
  - 선행: Task 07

- **Task 09. prod 서비스군별 ambient 전환**
  - 하위 항목
    - 1차 서비스군(비즈니스 중요도 낮음) 전환
    - 나머지 서비스군 순차 전환
  - 완료 조건
    - As-is: prod 전 서비스가 sidecar로 운영됨
    - To-be: prod 전 서비스가 ambient로 운영되고, 관찰 기간 동안 오류율과 지연이 전환 전과 같음
  - 연결된 결정: 서비스군마다 다음 서비스군으로 확대할지
  - 판정 근거: 서비스군별 관찰 기간 5xx 비율과 p99 지연
  - 선행: Task 06, 08
  - 실행 체크리스트 (서비스군마다 반복)
    1. 전환
    2. 관찰
    3. 확대 판단

- **Task 10. global·idc·office ambient 전환**
  - 하위 항목
    - global 전 네임스페이스 전환
    - idc·office CNI 조건 반영 후 전환
  - 완료 조건
    - As-is: global·idc·office 서비스가 sidecar로 운영됨
    - To-be: 세 클러스터 서비스가 ambient로 운영되고, 관찰 기간 동안 전환으로 인한 장애가 없음
  - 연결된 결정: sidecar 정리 시작 여부
  - 판정 근거: 클러스터별 관찰 기간 5xx 비율과 p99 지연
  - 선행: Task 08

**정리**

- **Task 11. sidecar 정리**
  - 하위 항목
    - 전 클러스터에서 istio-injection 라벨과 sidecar 전제 설정 제거
    - webserver chart의 sidecar 전용 옵션 정리
    - DevOps Wiki에 adr-istio-sidecar와 Istio 관련 문서 업데이트
  - 완료 조건
    - As-is: 전환 후에도 sidecar 설정이 남아 새 서비스가 sidecar로 뜰 수 있고, 문서가 실제 구성과 다름
    - To-be: 새 서비스는 기본으로 ambient로 뜨고, ADR과 Wiki 문서가 실제 구성과 일치함
  - 연결된 결정: sidecar 경로 폐기 (되돌리기 어려움)
  - 판정 근거: 전 클러스터 관찰 기간 통과, istio-proxy 컨테이너 수 0
  - 선행: Task 09, 10

***분리***

- global·idc·office Istio 1.28.1을 1.30.x로 맞추는 버전 정렬. Task 01에서 1.28.1로도 ambient가 가능하다고 확인되면 이번 범위에서 뺀다.

## 작은 작업 예시 (단계 없이 Task 하나)

알려진 절차로 끝나는 작업은 하위 항목만으로 충분하다.

- **ArgoCD 개발자 권한 정리**
  - Okta Engineer Group에 ArgoCD Application 연동
  - Okta ArgoCD SAML 앱의 group attribute filter 확인
  - helm diff 확인 후 helm upgrade로 적용
  - 테스트 계정으로 권한 검증
  - Okta argocd-admin, argocd-readonly Group에서 개발자 제외
  - DevOps Wiki에 ArgoCD 권한 관련 문서 업데이트
