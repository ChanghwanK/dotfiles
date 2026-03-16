# Cluster API 인증서 자동 로테이션

## 개요

Cluster API(CAPI)의 KubeadmControlPlane은 `rolloutBefore.certificatesExpiryDays` 설정을 통해
컨트롤플레인 인증서를 자동으로 갱신할 수 있다.

## 동작 원리

1. CAPI controller가 주기적으로 컨트롤플레인 노드의 인증서 만료일 확인
2. 만료까지 남은 일수가 `certificatesExpiryDays` 이하이면 롤링 업데이트 시작
3. 새 컨트롤플레인 VM 생성 (새 인증서 포함)
4. 이전 VM에서 워크로드 drain
5. 이전 VM 삭제
6. 다음 컨트롤플레인 노드로 반복 (순차적)

## KubeadmControlPlane 설정

### cluster-idc.yaml 설정 위치

```yaml
apiVersion: controlplane.cluster.x-k8s.io/v1beta1
kind: KubeadmControlPlane
metadata:
  name: infra-k8s-idc
  namespace: default
spec:
  replicas: 3
  version: v1.32.0

  # 인증서 자동 갱신 설정
  rolloutBefore:
    certificatesExpiryDays: 30  # 만료 30일 전 롤링 업데이트

  rolloutStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1  # 동시에 추가할 수 있는 노드 수

  kubeadmConfigSpec:
    clusterConfiguration:
      # ...
    initConfiguration:
      # ...
    joinConfiguration:
      # ...
```

### 핵심 파라미터

| 파라미터 | 설명 | 권장값 |
|---------|------|--------|
| `rolloutBefore.certificatesExpiryDays` | 만료 N일 전 갱신 시작 | 30 |
| `rolloutStrategy.rollingUpdate.maxSurge` | 동시 추가 노드 수 | 1 |

## 갱신 프로세스 상세

### 순서

```
CP-1 갱신:
  1. 새 CP 노드 VM 생성 (Proxmox)
  2. 새 CP 노드에 kubeadm join (새 인증서)
  3. etcd 멤버 추가
  4. 이전 CP-1 drain
  5. etcd 멤버 제거
  6. 이전 CP-1 VM 삭제

→ CP-2, CP-3 순차 반복
```

### 소요 시간

- 노드당 약 5~15분 (VM 생성 + join + drain)
- 컨트롤플레인 3개 기준: 약 15~45분
- 서비스 중단 없음 (하나씩 순차적으로 교체)

## 현재 상태 확인

```bash
# KubeadmControlPlane 상태 확인
kubectl --context k8s-idc get kcp -A

# 롤아웃 상태 확인
kubectl --context k8s-idc describe kcp <name>

# Machine 상태 (각 CP 노드)
kubectl --context k8s-idc get machines -A
```

### 롤링 업데이트 진행 중 확인

```bash
# Machine 상태에서 Provisioning/Running 확인
kubectl --context k8s-idc get machines -A -o wide

# KubeadmControlPlane conditions
kubectl --context k8s-idc get kcp -A -o jsonpath='{.items[*].status.conditions}' | jq
```

## 주의사항

### CAPMOX (Proxmox) 특이사항

- VM 생성 시 Proxmox API 호출
- Proxmox 호스트의 리소스 여유 필요 (maxSurge=1이면 임시로 4번째 CP 노드 생성)
- Proxmox 네트워크 설정이 새 VM에도 올바르게 적용되는지 확인

### etcd 안전성

- 3노드 etcd에서 1노드씩 교체하므로 quorum 유지 (2/3)
- 교체 중 추가 장애 발생 시 quorum 상실 위험
- 갱신 중에는 다른 클러스터 변경 작업 자제

### 설정 변경 방법

```bash
# cluster-idc.yaml 수정 후 kubectl apply
# /Users/changhwan/workspace/riiid/k8s-on-premise/cluster-idc.yaml

# rolloutBefore 추가/수정
kubectl --context k8s-idc edit kcp <name>
# 또는 Git에서 cluster-idc.yaml 수정 후 apply
```

## 관리 클러스터 (a6000-node01) 주의

관리 클러스터는 CAPI가 관리하지 않으므로:
- `rolloutBefore` 설정 불가
- `kubeadm certs renew all` 수동 실행 필요
- 캘린더 알림 설정 권장 (만료 30일 전)
- 별도 모니터링 알림 설정 권장
