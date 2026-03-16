---
name: devops:storage-ops
description: |
  IDC 클러스터(infra-k8s-idc) Rook-Ceph 기반 스토리지 운영 스킬.
  Ceph 클러스터 상태 진단, PVC 마운트 실패, OSD 관리, 용량 계획을 커버.
  사용 시점: (1) Ceph HEALTH_WARN/HEALTH_ERR 알림, (2) PVC Pending/마운트 실패,
  (3) OSD 교체/추가, (4) 스토리지 용량 계획, (5) ceph-block PVC 이슈.
  트리거 키워드: "Ceph", "PVC", "스토리지", "storage", "OSD", "HEALTH_WARN",
  "마운트 실패", "볼륨", "ceph-block", "Rook", "PV", "PersistentVolume".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(kubectl *)
  - mcp__grafana__query_prometheus
---

# IDC Storage Operations (Rook-Ceph)

infra-k8s-idc 클러스터의 Rook-Ceph 기반 스토리지 운영 및 문제 진단.

**대상 클러스터:** infra-k8s-idc (kubectl context: `k8s-idc`)
**EKS 클러스터는 AWS EBS/EFS CSI를 사용하므로 이 스킬 대상이 아닙니다.**

## IDC 스토리지 구성

### 물리 노드 매핑

| 노드 | 디스크 타입 | Ceph OSD | 비고 |
|------|-----------|----------|------|
| a6000-node01 | NVMe | O | OSD 노드 |
| a6000-node02 | NVMe | O | OSD 노드 |
| a6000-node03 | NVMe | O | OSD 노드 |
| a6000-node04~07 | SATA | X | OSD 없음 (컴퓨트 전용) |

### StorageClass

| StorageClass | Provisioner | 용도 |
|-------------|-------------|------|
| `ceph-block` | rook-ceph.rbd.csi.ceph.com | 기본 블록 스토리지 (RBD) |

### Rook-Ceph 네임스페이스

```
rook-ceph         # Rook operator, Ceph 클러스터
rook-ceph-system  # CSI 드라이버 (선택적)
```

---

## 진단 워크플로우

### Step 1: Ceph 클러스터 상태 확인

```bash
# Ceph 상태 요약
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph status

# 상태 상세
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph health detail

# OSD 상태
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd tree

# PG 상태
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph pg stat
```

**Ceph Health 상태:**
- `HEALTH_OK`: 정상
- `HEALTH_WARN`: 경고 (성능 저하 가능, 서비스 영향 없음)
- `HEALTH_ERR`: 에러 (데이터 손실 위험, 즉시 대응)

### Step 2: PVC 상태 확인

```bash
# Pending PVC 확인
kubectl --context k8s-idc get pvc -A | grep Pending

# PVC 상세 (events 포함)
kubectl --context k8s-idc describe pvc <name> -n <ns>

# PV 상태
kubectl --context k8s-idc get pv | grep <pvc-name>
```

### Step 3: CSI 드라이버 상태

```bash
# CSI provisioner/plugin Pod
kubectl --context k8s-idc get pods -n rook-ceph -l app=csi-rbdplugin
kubectl --context k8s-idc get pods -n rook-ceph -l app=csi-rbdplugin-provisioner

# CSI 드라이버 로그
kubectl --context k8s-idc logs -n rook-ceph -l app=csi-rbdplugin-provisioner --tail=30
```

**상세 진단:** `references/ceph-operations.md`, `references/pvc-troubleshooting.md` 참조

---

## 주요 운영 시나리오

### HEALTH_WARN 대응

| 경고 메시지 | 원인 | 조치 |
|------------|------|------|
| `too few PGs per OSD` | PG 수 부족 | PG autoscaler 확인 |
| `clock skew detected` | 노드 시간 불일치 | NTP 동기화 확인 |
| `OSD near full` | OSD 디스크 거의 가득 | 데이터 정리 또는 OSD 추가 |
| `degraded data redundancy` | 복제 미완료 PG | 자동 복구 대기, OSD 상태 확인 |

### OSD 교체/추가

OSD 추가는 node01~03 NVMe 디스크에서만 가능.

```bash
# OSD 상태 확인
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd tree
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd df
```

### 용량 확인

```bash
# 클러스터 용량
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph df

# OSD별 용량
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph osd df tree
```

---

## 출력 포맷

```markdown
# IDC Storage 진단 리포트

## Ceph 클러스터 상태
- Health: [HEALTH_OK/WARN/ERR]
- OSD: [X up, Y in]
- PG: [X active+clean]

## 문제 분석
[증상, 원인, 영향]

## 해결 방안
[구체적 조치]
```
