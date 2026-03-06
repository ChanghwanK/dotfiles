---
name: devops:gpu-analysis
description: >
  IDC GPU 클러스터 사용 현황 분석 스킬. kubectl + Grafana DCGM 메트릭을 통해 GPU 노드 상태,
  VRAM/Power/온도 현황, 워크로드 매핑, 모델 배포 가능성을 분석한다.
  사용 시점: (1) GPU 전체 현황 파악, (2) 모델 배포 가능 여부 확인 (VRAM 여유 분석),
  (3) GPU 고부하/이상 노드 탐지, (4) 워크로드별 GPU 리소스 사용 분석.
  트리거 키워드: "GPU 현황", "GPU 분석", "VRAM", "GPU 남아있어?", "모델 올릴 수 있어?",
  "GPU 사용률", "DCGM", "GPU 배포 가능", "GPU 노드".
---

# GPU 사용 분석

## 클러스터 정보

- **컨텍스트**: `k8s-idc`
- **GPU 노드**: `proxmox-workers-node01~07` (control-plane 3개 제외)
- **Grafana Datasource UID**: `bemfeemok4ge8c` (VictoriaMetrics/Prometheus)
- **GPU Operator 네임스페이스**: `gpu-operator`

## 분석 워크플로우

### 1단계: 노드 GPU 인벤토리 조회

```bash
# 노드별 GPU 수량 확인
kubectl --context k8s-idc get nodes \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.conditions[-1].type,GPU:.status.capacity.nvidia\.com/gpu'

# 노드별 GPU 모델 + 메모리 레이블 확인
kubectl --context k8s-idc get node <node-name> \
  -o jsonpath='{.metadata.labels}' | tr ',' '\n' \
  | grep -E 'nvidia.com/gpu.product|nvidia.com/gpu.count|nvidia.com/gpu.memory'
```

**주요 레이블:**
- `nvidia.com/gpu.product`: GPU 모델명 (e.g. `NVIDIA-RTX-A6000`)
- `nvidia.com/gpu.count`: 물리 GPU 수
- `nvidia.com/gpu.memory`: VRAM MB 단위 (49140 ≈ 48GB)

### 2단계: GPU Operator 상태 확인

```bash
kubectl --context k8s-idc get pods -n gpu-operator
```

정상 상태 컴포넌트: `nvidia-driver-daemonset`, `nvidia-device-plugin-daemonset`,
`nvidia-dcgm-exporter`, `gpu-feature-discovery`, `nvidia-operator-validator`

### 3단계: Grafana DCGM 메트릭 쿼리

Grafana MCP 또는 `mcp__grafana__query_prometheus`로 아래 PromQL 쿼리 사용:

| 분석 목적 | PromQL |
|-----------|--------|
| VRAM 사용률 (%) | `DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE) * 100` |
| VRAM 사용량 (MiB) | `DCGM_FI_DEV_FB_USED` |
| GPU 연산 사용률 (%) | `DCGM_FI_DEV_GPU_UTIL` |
| 전력 소비 (W) | `DCGM_FI_DEV_POWER_USAGE` |
| 온도 (°C) | `DCGM_FI_DEV_GPU_TEMP` |
| Tensor Core 활용률 | `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` |

**주요 레이블:**
- `Hostname`: 노드명
- `gpu`: GPU 인덱스 (0~3)
- `modelName`: GPU 모델
- `exported_pod` / `exported_namespace`: 해당 GPU를 사용 중인 Pod

> GPU Util은 순간 샘플링이라 0%로 찍혀도 VRAM 점유 + Power 소비를 함께 봐야 실제 부하 판단 가능

### 4단계: 결과 정리 포맷

노드별로 아래 표 형식으로 정리:

```
| GPU | VRAM 사용률 | Power | 온도 | 서비스 (namespace) |
```

- VRAM 사용률 80% 이상: 주의
- 온도 70°C 이상: 경고
- `exported_pod` 없음: idle 상태

### 5단계: 모델 배포 가능성 분석 (옵션)

모델 VRAM 요구량 기준 여유 GPU 판별:

| 정밀도 | 17B | 70B | 8B |
|--------|-----|-----|----|
| FP16 | ~38GB | ~140GB | ~16GB |
| INT8 | ~19GB | ~70GB | ~8GB |
| INT4 | ~10GB | ~35GB | ~5GB |

GPU 1장 VRAM = **48GB** 기준. 멀티 GPU 필요 시 tensor parallel 고려.

자세한 모델 크기별 VRAM 계산은 `references/model-vram.md` 참조.

---

## 현재 인프라 현황 (참고)

| 노드 | GPU 모델 | 장 수 | 비고 |
|------|----------|-------|------|
| node01~03 | RTX 6000 Ada Generation | 4장/노드 | - |
| node04~05 | RTX A6000 | 4장/노드 | - |
| node06~07 | RTX A6000 | 4장/노드 | MPS 활성화 (GPU 공유) |

- **총 28장, 1,344GB VRAM**
- MPS 노드(06,07): 물리 4장을 가상 분할해 다수 Pod 동시 서빙
