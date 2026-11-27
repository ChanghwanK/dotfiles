# 예시: Istio sidecar → ambient 모드 전환

2026-11-27 대화에서 기준을 잡으며 만든 형식 예시다. ambient 동작(전환 순서, waypoint 역할)은 공식 문서로 확인하지 않은 내용이므로 실제 계획에서는 Task 01에서 대상 버전 문서로 다시 확인한다.

## 선행관계

```
Task 01 ─→ Task 02 ─→ Task 03 ─→ Task 04 ─┐
              └─────→ Task 05 ────────────┴─→ Task 06 ─→ Task 07 ─→ Task 08 ─→ Task 09
```

- Task 05는 Task 02 뒤에 Task 03, 04와 병렬로 진행한다.
- Task 06은 Task 04와 05가 모두 끝나야 시작한다.

## Task

**PoC**

- **Task 01. 사용 중인 Istio 기능 조사**
  - 완료 조건
    - As-is: 우리가 쓰는 Istio 기능 중 무엇이 ambient 전환에 걸리는지 모름
    - To-be: 전환에 영향을 주는 기능과 사용처가 정리되어, PoC에서 시험할 범위가 정해짐
  - 연결된 결정: PoC 검증 범위
  - 판정 근거: 전 env의 VirtualService, DestinationRule, ServiceEntry, AuthorizationPolicy, EnvoyFilter, Sidecar, Telemetry 사용처를 공식 ambient 지원 범위와 대조한 표
  - 선행: 없음
- **Task 02. dev istio ambient 환경 구축**
  - 완료 조건
    - As-is: dev 메시는 sidecar 방식뿐이라 ambient로 옮겨 볼 수 있는 곳이 없음
    - To-be: dev에서 sidecar 서비스와 ambient 서비스가 서로 mTLS로 호출하며 함께 운영됨
  - 연결된 결정: 혼재 상태로 점진 전환할 수 있는지, 일괄 전환해야 하는지
  - 판정 근거: sidecar→ambient, ambient→sidecar, ingress→ambient 호출 성공과 mTLS 적용, 기존 sidecar 서비스 오류율 무변화
  - 선행: Task 01
  - 실행 체크리스트
    1. istio-system에 istio-cni, ztunnel 추가
    2. 테스트 네임스페이스에 ambient 라벨 적용
    3. injection 라벨 해제
    4. Pod 재시작
- **Task 03. 기존 트래픽 정책 호환성 검증**
  - 완료 조건
    - As-is: 카나리, 트래픽 정책, egress, 인가가 ambient에서 동작하는지 모름
    - To-be: 기능별로 "그대로 동작 / 바꿔야 동작 / 불가"가 판정되어, 어디까지 전환할 수 있는지 근거를 들어 말할 수 있음
  - 연결된 결정: 전환 범위(전체, 부분, 중단)와 기능별 대체 방식
  - 판정 근거: Task 01 목록의 기능별 dev 시험 결과. 혼재 상태의 L7 정책 집행 여부 포함
  - 선행: Task 01, 02

**전환 준비**

- **Task 04. 서비스 전환 표준 수립**
  - 완료 조건
    - As-is: 서비스를 ambient로 옮기려면 DevOps가 서비스마다 설정을 직접 판단해야 함
    - To-be: values 옵션과 문서화된 절차만으로 누구나 서비스를 전환하고 되돌릴 수 있음
  - 연결된 결정: 전환 단위(서비스 또는 네임스페이스)와 롤백 방식
  - 판정 근거: 절차 문서만으로 dev 서비스 1개를 전환·롤백 성공, 롤백 소요 시간
  - 선행: Task 03
  - 실행 체크리스트
    1. waypoint 배포
    2. L7 정책 이전
    3. ambient 라벨 적용
    4. injection 해제
    5. Pod 재시작
- **Task 05. ambient 모니터링 구성**
  - 완료 조건
    - As-is: ambient로 옮기면 sidecar 메트릭이 사라져, 장애가 나도 알럿으로 잡지 못함
    - To-be: ambient 서비스의 장애도 sidecar 때와 같은 알럿과 대시보드로 탐지됨
  - 연결된 결정: 확산 시작 여부
  - 판정 근거: dev에서 일부러 낸 장애(Pod 종료, 5xx 주입)에 알럿 발화
  - 선행: Task 02

**전환**

- **Task 06. dev 전체 ambient 전환**
  - 완료 조건
    - As-is: dev 전 서비스가 Pod마다 sidecar를 달고 운영됨
    - To-be: dev 전 서비스가 sidecar 없이 운영되고, 관찰 기간 동안 전환으로 인한 장애가 없음
  - 연결된 결정: stg 진행 여부
  - 판정 근거: 관찰 기간 5xx 비율과 p99 지연을 전환 전과 비교, 롤백 발생 건수
  - 선행: Task 04, 05
- **Task 07. stg 전체 ambient 전환**
  - 완료 조건
    - As-is: stg 전 서비스가 sidecar로 운영됨
    - To-be: stg 전 서비스가 ambient로 운영되고, 관찰 기간 동안 전환으로 인한 장애가 없음
  - 연결된 결정: prod 진행 여부
  - 판정 근거: Task 06과 같은 지표
  - 선행: Task 06
- **Task 08. prod ambient 전환**
  - 완료 조건
    - As-is: prod 전 서비스가 sidecar로 운영됨
    - To-be: prod 전 서비스가 ambient로 운영되고, 관찰 기간 동안 오류율과 지연이 전환 전과 같음
  - 연결된 결정: 서비스군마다 다음 서비스군으로 확대할지
  - 판정 근거: 서비스군별 관찰 기간 5xx 비율과 p99 지연
  - 선행: Task 07
  - 실행 체크리스트
    1. 호출 관계와 공유 컴포넌트 기준으로 서비스군 묶기
    2. 비즈니스 중요도 낮은 서비스군부터 전환
    3. 관찰
    4. 확대 판단

**정리**

- **Task 09. sidecar 정리**
  - 완료 조건
    - As-is: injection 라벨과 sidecar 전제 설정이 남아 새 서비스가 sidecar로 뜰 수 있고, 문서가 실제 구성과 다름
    - To-be: 새 서비스는 기본으로 ambient로 뜨고, ADR과 Wiki 문서가 실제 구성과 일치함
  - 연결된 결정: sidecar 경로 폐기 (되돌리기 어려움)
  - 판정 근거: prod 전 서비스 관찰 기간 통과, istio-proxy 컨테이너 수 0
  - 선행: Task 08

## 작은 작업 예시 (단계 없이 Task 하나)

알려진 절차로 끝나는 작업은 하위 항목만으로 충분하다.

- **ArgoCD 개발자 권한 정리**
  - Okta Engineer Group에 ArgoCD Application 연동
  - Okta ArgoCD SAML 앱의 group attribute filter 확인
  - helm diff 확인 후 helm upgrade로 적용
  - 테스트 계정으로 권한 검증
  - Okta argocd-admin, argocd-readonly Group에서 개발자 제외
  - DevOps Wiki에 ArgoCD 권한 관련 문서 업데이트
