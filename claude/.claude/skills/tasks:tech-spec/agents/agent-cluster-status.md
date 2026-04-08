# 클러스터 현재 상태 수집 에이전트

조사 주제: {topic}
대상 sphere: {sphere}
대상 circle: {circle}
대상 환경: {env}

아래 절차로 Kubernetes 클러스터의 현재 상태를 수집하고 결과를 반환한다.
정보를 찾지 못한 항목은 "해당 없음"으로 명시한다.

---

## 수집 절차

### 1. 네임스페이스 및 Pod 상태

`{sphere}-{circle}` 네임스페이스가 있으면:

```bash
kubectl get pods -n {sphere}-{circle} -o wide --context {env}
kubectl get events -n {sphere}-{circle} --sort-by='.lastTimestamp' --context {env} | tail -20
```

네임스페이스가 없거나 `{sphere}`, `{circle}`이 "unknown"이면:
- 주제({topic})에서 관련 네임스페이스를 추론하거나
- 건너뛰고 "해당 없음" 명시

### 2. Deployment / StatefulSet 현재 스펙

```bash
kubectl get deployment,statefulset -n {sphere}-{circle} -o yaml --context {env}
```

replica 수, resource requests/limits, image tag를 추출한다.

### 3. 관련 ConfigMap / Secret 목록

```bash
kubectl get configmap,secret -n {sphere}-{circle} --context {env}
```

### 4. 노드 상태 (필요한 경우)

주제가 노드/클러스터 인프라 관련이면:

```bash
kubectl get nodes -o wide --context {env}
kubectl top nodes --context {env}
```

---

## 출력 형식

아래 형식으로 결과를 반환한다:

```
## 클러스터 현재 상태

**네임스페이스**: {sphere}-{circle} / {env}

### Pod 상태
| Pod 이름 | 상태 | 재시작 수 | 노드 |
|----------|------|-----------|------|
| ...      | ...  | ...       | ...  |

### 현재 Deployment 스펙
- replicas: N
- image: {image}:{tag}
- CPU request/limit: Xm / Ym
- Memory request/limit: XMi / YMi

### 최근 Events (이상 있을 때만)
- ...

### 노드 상태 (해당 시)
- ...
```

정보를 찾지 못한 섹션은 "해당 없음"으로 명시하고 계속 진행한다.
