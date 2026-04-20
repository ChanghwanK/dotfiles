# Engineering Review Checklist

Phase 1 엔지니어링 검증에서 참고할 도메인별 체크리스트.

---

## Kubernetes

### API 오브젝트 명칭
- `ConfigMap` (단어 붙임, C/M 대문자)
- `Secret`, `Pod`, `Deployment`, `Service`, `Ingress`
- `ServiceAccount` (단어 붙임)
- `PersistentVolumeClaim` (PVC)
- 필드명은 camelCase: `volumeMounts`, `envFrom`, `configMapKeyRef`

### 자주 틀리는 경로
- kubelet 볼륨 마운트 경로: `/var/lib/kubelet/pods/<pod-uid>/volumes/kubernetes.io~configmap/<volume-name>`
- Secret의 경우: `kubernetes.io~secret`
- `kubernetes.io` — 오타 주의 (kubertes, k8s.io 등)

### 사실 체크 포인트
- ConfigMap 데이터 크기 제한: **1MiB**
- Secret은 기본적으로 etcd에 **평문(base64 인코딩, 암호화 X)** 저장
- `..data` 심볼릭 링크를 통한 원자적 업데이트 — Hot Reload 원리
- 환경 변수는 `execve()` 시점에 고정 → Pod 재시작 없이는 변경 불가
- Secret type 목록: `Opaque`, `kubernetes.io/service-account-token`, `kubernetes.io/dockerconfigjson`, `kubernetes.io/basic-auth`, `kubernetes.io/ssh-auth`, `kubernetes.io/tls`
- `stringData`는 쓰기 전용 — 조회 시 `data` 필드에만 표시

### YAML 예시 검증
- `apiVersion`, `kind`, `metadata`, `spec` 필드 순서 (권장)
- `configMapKeyRef` / `secretKeyRef` 사용 시 `name` + `key` 필드 필수
- `envFrom` 사용 시 `configMapRef` 또는 `secretRef`

---

## Linux/OS 개념

### 시스템 콜
- `fork()` — 부모 프로세스 복제
- `execve()` — 새 프로세스 이미지로 교체 (환경 변수를 인자로 전달)
- `mmap()` — 파일을 메모리에 매핑

### 프로세스 메모리 레이아웃 (x86-64)
높은 주소 → 낮은 주소 순:
```
Kernel Space
Environment Variables + Arguments   ← 높은 주소
Stack (↓ 감소)
(Unmapped)
Heap (↑ 증가)
BSS Segment
Data Segment
Text Segment (Code)                 ← 낮은 주소
```
- 환경 변수는 Stack 세그먼트 **위**(높은 주소)에 위치
- `_end` / `__bss_end__` 심볼: BSS 끝 주소, libc malloc 초기화 기준점

### 자주 틀리는 표현
- `Encryption at Rest` (O) — `Encryption at Reset` (X)
- `execve` (소문자, e 붙음) — `exec`, `execv` 와 구분
- `RSP 레지스터` (x86-64 스택 포인터)

---

## 일반 개념

### 12-Factor App
- Config 원칙: "설정은 환경변수로 저장하거나, 코드에 포함되지 않는 파일에 저장한다"

### Base64
- 바이너리 → ASCII 변환 인코딩, **암호화 아님**
- 목적: YAML/JSON 파싱 시 바이너리 데이터 호환성 확보

### Immutable Infrastructure
- "설정이 바뀌면 Pod를 새로 배포한다"는 철학
- 환경 변수 방식이 이 철학을 자연스럽게 강제함
