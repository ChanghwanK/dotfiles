# PVC 트러블슈팅 (ceph-block)

## PVC Pending

### 진단 순서

1. **PVC events 확인**
```bash
kubectl --context k8s-idc describe pvc <name> -n <ns>
```

2. **CSI provisioner 로그 확인**
```bash
kubectl --context k8s-idc logs -n rook-ceph -l app=csi-rbdplugin-provisioner --tail=50
```

3. **Ceph 상태 확인**
```bash
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- ceph status
```

### 주요 원인

| PVC Event 메시지 | 원인 | 해결 |
|-----------------|------|------|
| `waiting for a volume to be created` | CSI provisioner 미작동 | provisioner Pod 확인 |
| `failed to provision volume` | Ceph pool 문제 | pool 상태 확인, Ceph health 확인 |
| `node does not have enough capacity` | 노드 ephemeral 부족 | (PVC와 무관, 스케줄링 문제) |
| `storageclass "ceph-block" not found` | StorageClass 미생성 | StorageClass 생성 확인 |

### StorageClass 확인

```bash
# ceph-block StorageClass 존재 확인
kubectl --context k8s-idc get sc ceph-block -o yaml
```

필수 설정:
- `provisioner: rook-ceph.rbd.csi.ceph.com`
- `parameters.pool`: Ceph pool 이름
- `parameters.clusterID`: rook-ceph 네임스페이스

## PVC 마운트 실패

### 진단

```bash
# Pod events에서 마운트 에러 확인
kubectl --context k8s-idc describe pod <pod-name> -n <ns> | grep -A5 "Events:"

# CSI node plugin 로그
kubectl --context k8s-idc logs -n rook-ceph -l app=csi-rbdplugin --tail=50 -c csi-rbdplugin
```

### 주요 원인

| 에러 | 원인 | 해결 |
|------|------|------|
| `FailedAttachVolume` | RBD 이미지 attach 실패 | 다른 노드에 이미 attach 확인 (RWO) |
| `FailedMount: rbd map failed` | RBD 커널 모듈 문제 | 노드 커널 모듈 확인 |
| `volume is already exclusively attached` | RWO 볼륨 중복 attach | 이전 Pod가 종료되지 않음, force unmount |
| `MountVolume.MountDevice failed` | 파일시스템 에러 | fsck, 볼륨 복구 |

### RWO 볼륨 중복 attach 해결

RWO(ReadWriteOnce) 볼륨이 다른 노드에서 사용 중인 경우:

```bash
# 해당 PV가 어떤 노드에 attach되어 있는지 확인
kubectl --context k8s-idc get volumeattachments | grep <pv-name>

# RBD 이미지 상태 확인
kubectl --context k8s-idc -n rook-ceph exec deploy/rook-ceph-tools -- rbd status <pool>/<image>
```

**해결 순서:**
1. 이전 Pod가 Terminating이면 완료 대기
2. 이전 Pod가 없는데 attach 남아있으면 VolumeAttachment 삭제
3. 최후 수단: `rbd unmap` (데이터 손실 주의)

## PV 용량 확장

### 온라인 확장 (ceph-block 지원)

```bash
# PVC spec.resources.requests.storage 수정
kubectl --context k8s-idc patch pvc <name> -n <ns> -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

**조건:**
- StorageClass에 `allowVolumeExpansion: true` 설정 필요
- 축소는 불가 (확장만 가능)
- 파일시스템 확장은 자동 (Pod 재시작 불필요, ext4/xfs 기준)

## 모니터링

```promql
# PVC 사용률
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes

# PVC 사용량
kubelet_volume_stats_used_bytes{namespace="<ns>", persistentvolumeclaim="<pvc>"}

# 마운트된 볼륨 수
kubelet_volume_stats_capacity_bytes
```
