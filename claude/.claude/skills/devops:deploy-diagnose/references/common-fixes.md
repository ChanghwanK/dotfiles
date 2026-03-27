# 증상별 수정 가이드 (3-Tier)

진단 결과에 따라 아래 3단계 중 적합한 Tier의 수정 방법을 제시한다.

---

## Tier 1: Self-fix — 개발자가 직접 수정 가능

### T1-A: 잘못된 이미지 태그

**증상**: ImagePullBackOff, `ErrImagePull`, `Back-off pulling image`

**수정 파일**: `src/{sphere}/{circle}/infra-k8s-{env}/values.yaml`

```yaml
# 변경 전 (잘못된 태그)
image:
  tag: "abc123-broken"

# 변경 후 (올바른 태그 또는 이전 태그)
image:
  tag: "abc123-working"  # Harbor에서 확인한 유효한 태그
```

**확인 방법**: Harbor 레지스트리 `harbor.global.riiid.team` 또는 빌드 CI에서 유효한 태그 확인

---

### T1-B: OOMKilled (메모리 부족)

**증상**: Pod 상태 `OOMKilled`, 종료 코드 137

**수정 파일**: `src/{sphere}/{circle}/infra-k8s-{env}/values.yaml`

```yaml
# 변경 전
resources:
  requests:
    memory: "256Mi"
  limits:
    memory: "512Mi"

# 변경 후 (1.5~2배 증가)
resources:
  requests:
    memory: "512Mi"
  limits:
    memory: "1Gi"
```

**언어별 권장 배율** (limits/requests):
- JVM (Java/Kotlin): 1.5~2x (힙 외 메타스페이스 고려)
- Python: 2~3x (인터프리터 오버헤드)
- Node.js: 1.5~2x
- Go: 1.2~1.5x (효율적인 메모리 관리)

---

### T1-C: YAML 문법 에러

**증상**: Helm render 실패, `yaml: line X: ...` 에러

**수정 방법**:
1. 에러 메시지에서 파일/라인 번호 확인
2. 해당 파일 수정 후 로컬 검증:
   ```bash
   yamllint -c .yamllint.yml src/{sphere}/{circle}/infra-k8s-{env}/values.yaml
   ```

**자주 발생하는 YAML 실수**:
- 들여쓰기 혼용 (탭/스페이스)
- 따옴표 미닫힘
- `-` 리스트 아이템 들여쓰기 오류

---

### T1-D: 환경변수 누락

**증상**: 애플리케이션 시작 실패, `KeyError`, `Required env var ... not set`

**수정 파일**: `src/{sphere}/{circle}/infra-k8s-{env}/values.yaml`

```yaml
# 환경변수 추가
extraEnvs:
  - name: NEW_ENV_VAR
    value: "value"
  # 시크릿에서 가져올 경우
  - name: SECRET_VAR
    valueFrom:
      secretKeyRef:
        name: my-secret
        key: my-key
```

**주의**: 시크릿이 필요한 경우 `externalSecretsEnvs` 패턴 사용 (AWS Secrets Manager 연동)

---

### T1-E: Chart version 불일치

**증상**: `Error: chart ... not found`, OCI 레지스트리 404

**수정 파일**: `src/{sphere}/{circle}/infra-k8s-{env}/kustomization.yaml`

```yaml
helmCharts:
  - repo: oci://harbor.global.riiid.team/helm-charts
    name: webserver
    version: 0.3.42  # ← 이 버전이 Harbor에 존재하는지 확인
    namespace: {sphere}-{circle}
```

**확인 방법**: 다른 circle의 `kustomization.yaml` 에서 현재 사용 중인 버전 참조

---

## Tier 2: Guided fix — DevOps 안내 하에 개발자 수정

### T2-A: Canary ignoreDifferences 누락

**증상**: Argo Rollouts가 VirtualService weight를 수정하면 ArgoCD가 OutOfSync로 감지

**수정 파일**: `src/{sphere}/{circle}/applicationset.jsonnet`

추가할 내용:
```jsonnet
// applicationset.jsonnet의 app 설정에 추가
ignoreDifferences: [
  {
    group: 'networking.istio.io',
    kind: 'VirtualService',
    jqPathExpressions: ['.spec.http[].route[].weight'],
  },
  {
    group: 'networking.istio.io',
    kind: 'DestinationRule',
    jqPathExpressions: ['.spec.subsets[].labels["rollouts-pod-template-hash"]'],
  },
]
```

**참조**: `src/applicationset.libsonnet` 표준 패턴

---

### T2-B: Immutable Field 변경 시도

**증상**: `field is immutable`, `spec.selector` 수정 불가

**해결 과정**:
1. 해당 리소스를 `resources/` 디렉토리에서 삭제 커밋
2. ArgoCD Prune으로 클러스터에서 리소스 삭제
3. 변경된 리소스를 다시 추가 커밋

**주의**: prod 환경에서는 다운타임 검토 필요 → Tier 3으로 에스컬레이션 권장

---

### T2-C: Helm 필수 필드 누락

**증상**: `Error: ... required field`, `values don't meet the chart's requirements`

**수정 방법**:
1. `devops:helm-chart` 스킬로 chart의 required values 확인
2. 해당 필드를 `values.yaml`에 추가

---

## Tier 3: Escalation — DevOps 직접 처리

아래 상황은 DevOps가 직접 처리해야 한다. Slack 메시지 템플릿을 제공한다.

### T3-A: Rollout Promote / Abort

카나리 promote/abort는 `kubectl argo rollouts` 명령 필요 (write 권한)

```bash
# Promote (다음 단계로 진행)
kubectl argo rollouts promote {circle} -n {namespace} --context {ctx}

# Abort (이전 버전으로 롤백)
kubectl argo rollouts abort {circle} -n {namespace} --context {ctx}
```

---

### T3-B: ArgoCD Force Sync / Hard Refresh

```bash
# Hard refresh (캐시 무시하고 재계산)
argocd app get {app-name} --hard-refresh

# Force sync (오류 무시하고 강제 동기화)
argocd app sync {app-name} --force
```

---

### T3-C: 인프라 레이어 문제

- 노드 압박 (Node pressure)
- Pod 스케줄링 실패 (Unschedulable)
- PVC Pending
- ArgoCD / Istio 자체 장애

→ `devops:k8s-troubleshoot` 또는 `sre-agent` 사용

---

## 에스컬레이션 Slack 메시지 템플릿

```
*배포 문제 진단 결과 공유*

• 서비스: {sphere}/{circle} ({env})
• 증상: {증상 요약}
• 진단: {원인 분류}
• ArgoCD: {sync status} / {health status}
• Pod: {running}/{total}, 재시작 {restart}회
• 핵심 에러: `{key error message}`
• 최근 변경: {git commit summary}

*권장 조치*: {Tier 3 액션}
```
