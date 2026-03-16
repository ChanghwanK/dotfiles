# Pod 상태별 에러 진단 맵

## CrashLoopBackOff

**증상:** 컨테이너가 반복적으로 시작 → 실패 → 재시작. backoff 시간이 점점 증가 (10s → 20s → 40s → ... → 5m).

**진단 단계:**
1. exit code 확인: `kubectl get pod <name> -o jsonpath='{.status.containerStatuses[*].lastState.terminated.exitCode}'`
2. 이전 로그: `kubectl logs <name> --previous --tail=200`
3. describe로 event 확인: `kubectl describe pod <name>`

**Exit Code 매핑:**

| Exit Code | 의미 | 일반적 원인 |
|-----------|------|------------|
| 0 | 정상 종료 | 앱이 의도적으로 종료. restartPolicy 확인 |
| 1 | 일반 에러 | 애플리케이션 에러 (설정 파일 누락, DB 연결 실패 등) |
| 2 | Shell misuse | 잘못된 명령어, 스크립트 문법 에러 |
| 126 | 실행 불가 | 바이너리 권한 문제, 파일 형식 불일치 |
| 127 | 명령어 없음 | 잘못된 entrypoint/command, 바이너리 미포함 |
| 128+N | 시그널 N으로 종료 | 137=SIGKILL(OOM), 143=SIGTERM(graceful) |
| 137 | OOMKilled | 메모리 limit 초과 또는 노드 메모리 부족 |
| 139 | SIGSEGV | 세그폴트, 메모리 접근 위반 |
| 143 | SIGTERM | graceful shutdown, preStop hook 타임아웃 |

## ImagePullBackOff / ErrImagePull

**증상:** 이미지를 다운로드하지 못하여 컨테이너 시작 불가.

**진단 단계:**
1. 이미지 URL 확인: `kubectl get pod <name> -o jsonpath='{.spec.containers[*].image}'`
2. event에서 에러 메시지 확인: `kubectl describe pod <name>`
3. 레지스트리 접근 가능 여부 확인

**주요 원인:**
- **잘못된 이미지 태그**: 존재하지 않는 태그 (typo, 빌드 실패)
- **인증 실패**: imagePullSecrets 누락 또는 만료
  - Harbor 레지스트리: `harbor.global.riiid.team` → imagePullSecrets 확인
  - ECR: IRSA 또는 ECR credential helper 확인
- **네트워크 문제**: NAT Gateway 한도, DNS 해석 실패, 프록시 설정
- **레지스트리 불가**: Harbor 장애, ECR 리전 문제
- **이미지 크기**: 대용량 이미지 pull timeout

**Harbor 특이사항 (SOCRAAI):**
- IDC 클러스터는 `harbor.idc.riiid.team` 로컬 레지스트리 사용
- Pull-through cache 구성으로 외부 이미지도 Harbor 경유

## OOMKilled (exit code 137)

**증상:** 컨테이너가 메모리 limit을 초과하여 커널 OOM Killer에 의해 종료.

**진단 단계:**
1. 메모리 limit 확인: `kubectl get pod <name> -o jsonpath='{.spec.containers[*].resources.limits.memory}'`
2. 실제 사용량 확인 (메트릭): `container_memory_working_set_bytes` PromQL 쿼리
3. 메모리 증가 패턴 분석: 점진적(leak) vs 급격한(spike)

**주요 원인:**
- **메모리 누수**: 시간에 따라 점진적 증가 → 앱 코드 프로파일링 필요
- **리소스 limit 부족**: 정상 부하에서도 limit 초과 → limit 증가 필요
- **JVM/Runtime 설정 불일치**: JVM -Xmx와 container limit 불일치
- **캐시 무한 증가**: 인메모리 캐시 크기 제한 미설정

**JVM 환경 주의사항:**
- Container limit = JVM heap(-Xmx) + non-heap(~250-500MB)
- 예: limit 2Gi → -Xmx=1536m 권장

## Pending

**증상:** Pod가 스케줄링되지 않고 Pending 상태로 대기.

**진단 단계:**
1. event 확인: `kubectl describe pod <name>` → Events 섹션
2. 노드 리소스 확인: `kubectl describe nodes | grep -A5 "Allocated resources"`

**주요 원인:**
- **Insufficient CPU/Memory**: 요청한 리소스를 제공할 노드 없음
  - Karpenter: NodePool 설정 확인 (`kubernetes/docs/karpenter-guide.md`)
  - 인스턴스 타입 제한, 최대 limit 도달
- **Node selector/Affinity 불일치**: 매칭되는 노드 없음
- **Taint/Toleration**: 노드 taint에 대한 toleration 미설정
- **PVC 바인딩 실패**: PVC가 Pending → StorageClass, 가용 볼륨 확인
- **Resource Quota 초과**: 네임스페이스 quota 한도 도달
- **Pod Topology Spread**: 제약 조건을 만족하는 배치 불가

**Karpenter 연관 확인:**
```bash
# Karpenter 노드 프로비저닝 상태
kubectl --context <ctx> get nodeclaims -A
kubectl --context <ctx> get nodepools
# Karpenter 로그에서 프로비저닝 실패 원인
kubectl --context <ctx> logs -n kube-system -l app.kubernetes.io/name=karpenter --tail=50
```

## ContainerConfigError / CreateContainerConfigError

**증상:** 컨테이너 설정 오류로 시작 불가.

**주요 원인:**
- **ConfigMap/Secret 참조 오류**: 존재하지 않는 ConfigMap/Secret 참조
- **Volume mount 에러**: 잘못된 mount path, subPath
- **환경변수 참조 오류**: `valueFrom.secretKeyRef` 키 불일치
- **SecurityContext 오류**: 잘못된 runAsUser, capabilities

**진단:**
```bash
kubectl describe pod <name> | grep -A20 "Events:"
kubectl get configmap <name> -n <ns>
kubectl get secret <name> -n <ns>
```

## CreateContainerError

**증상:** 컨테이너 런타임이 컨테이너를 생성하지 못함.

**주요 원인:**
- 볼륨 마운트 실패 (EBS CSI, Ceph)
- 디바이스 플러그인 문제 (GPU)
- 컨테이너 런타임 이슈 (containerd)

## Init:Error / Init:CrashLoopBackOff

**증상:** Init 컨테이너가 실패하여 메인 컨테이너 시작 불가.

**진단:**
```bash
# init 컨테이너 로그
kubectl logs <pod-name> -c <init-container-name>
# init 컨테이너 상태
kubectl get pod <name> -o jsonpath='{.status.initContainerStatuses}'
```

**주요 원인:**
- DB migration 스크립트 실패
- 의존 서비스 대기 timeout
- 설정 파일 생성 실패

## Evicted

**증상:** 노드 리소스 압박으로 kubelet이 Pod를 축출.

**진단:**
```bash
# 축출 사유 확인
kubectl get pod <name> -o jsonpath='{.status.reason}'
kubectl get pod <name> -o jsonpath='{.status.message}'

# 노드 pressure 상태
kubectl describe node <node-name> | grep -E "Conditions|Pressure"
```

**주요 원인:**
- **DiskPressure**: 노드 디스크 사용률 > 임계치
- **MemoryPressure**: 노드 가용 메모리 < 100Mi
- **ephemeral-storage 초과**: 컨테이너 ephemeral storage limit 초과

## Terminating (stuck)

**증상:** Pod 삭제 요청 후 Terminating 상태에서 멈춤.

**주요 원인:**
- **Finalizer**: 처리 안 된 finalizer 존재
- **preStop hook**: preStop 스크립트 hang
- **Volume unmount 대기**: 볼륨 분리 완료 대기
- **Process 종료 지연**: graceful shutdown 시간 초과

**확인:**
```bash
kubectl get pod <name> -o jsonpath='{.metadata.finalizers}'
kubectl get pod <name> -o jsonpath='{.metadata.deletionTimestamp}'
```
