# 모델 크기별 VRAM 요구량

## 계산 공식

```
가중치 메모리 = 파라미터 수 × 바이트/파라미터
총 VRAM ≈ 가중치 메모리 × 1.2  (KV cache + activation 오버헤드 20%)
```

| 정밀도 | 바이트/파라미터 |
|--------|----------------|
| FP32   | 4 bytes        |
| FP16 / BF16 | 2 bytes  |
| INT8   | 1 byte         |
| INT4   | 0.5 bytes      |

## 모델별 VRAM 요구량 (단일 GPU 기준)

| 모델 크기 | FP16 | INT8 | INT4 | 비고 |
|-----------|------|------|------|------|
| 7B / 8B   | ~16GB | ~9GB | ~5GB | 단일 GPU (48GB) 여유 |
| 13B       | ~28GB | ~15GB | ~8GB | 단일 GPU 가능 |
| 17B       | ~38GB | ~20GB | ~11GB | FP16 단일 GPU 가능 (48GB) |
| 30B / 34B | ~68GB | ~35GB | ~18GB | FP16: 2장 필요 |
| 70B       | ~140GB | ~72GB | ~38GB | FP16: 3장 필요 |
| 72B       | ~144GB | ~74GB | ~39GB | FP16: 3~4장 필요 |

## 48GB GPU 1장 배포 가능 모델

- FP16: **최대 ~20B** (여유 포함 38~42GB → 48GB 이내)
- INT8: **최대 ~40B**
- INT4: **최대 ~80B**

## 멀티 GPU (Tensor Parallel) 계산

GPU N장 사용 시 가용 VRAM = N × 48GB

| GPU 수 | 가용 VRAM | FP16 최대 모델 크기 |
|--------|-----------|---------------------|
| 1장    | 48GB      | ~20B                |
| 2장    | 96GB      | ~45B                |
| 4장    | 192GB     | ~90B                |
| 8장    | 384GB     | ~180B               |

## 참고: vLLM / Triton 배포 시 추가 고려사항

- **KV cache**: context length가 길수록 증가. 4096 token이면 ~2~4GB 추가
- **batch size**: 동시 요청 수에 비례해 KV cache 증가
- **quantization 효과**: AWQ/GPTQ INT4는 품질 손실 최소화하며 메모리 절반
- **LoRA**: base model + adapter, 추가 메모리 ~수백MB~수GB
