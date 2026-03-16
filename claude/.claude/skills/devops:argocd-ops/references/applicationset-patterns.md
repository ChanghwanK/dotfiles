# SOCRAAI ApplicationSet 패턴

## 표준 구조

모든 ApplicationSet은 Jsonnet으로 정의되며, `src/applicationset.libsonnet`을 import한다.

### 기본 패턴

```jsonnet
local applicationset = import '../../applicationset.libsonnet';
local sphere = import '../sphere.libsonnet';

applicationset(
  sphere=sphere,
  circle='ai-gateway',
  // 옵션들
)
```

### sphere.libsonnet

각 sphere 디렉토리의 루트에 위치:
```jsonnet
{
  sphereName: 'tech',  // 네임스페이스 prefix
}
```

### 네이밍 규칙

- **Application 이름**: `{circle}.{env}` (예: `ai-gateway.infra-k8s-prod`)
- **Namespace**: `{sphere}-{circle}` (예: `tech-ai-gateway`)
- **Helm Release**: `{circle}` (예: `ai-gateway`)

## Git Directory Generator

ApplicationSet은 git directory generator를 사용하여 환경별 Application을 자동 생성:

```jsonnet
// directories 패턴
directories: [{
  path: 'src/tech/ai-gateway/*',
  exclude: ['src/tech/ai-gateway/common'],
}]
```

이 설정은 `src/tech/ai-gateway/` 아래의 각 `infra-k8s-*` 디렉토리마다 하나의 Application을 생성한다.

## 변형 패턴

### On-Premise 클러스터

IDC/Office 클러스터용:
```jsonnet
local applicationset = import '../../applicationset.onpremise.libsonnet';
```

### Canary 배포

Argo Rollouts를 사용하는 앱은 ignoreDifferences 필수:
```jsonnet
applicationset(
  sphere=sphere,
  circle='ai-gateway',
  ignoreDifferences=[
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
  ],
)
```

### 커스텀 Slack 알림

prod는 전용 채널, 나머지는 minor 채널:
```jsonnet
'notifications.argoproj.io/subscribe.on-deployed.slack':
  '{{if eq .path.basename "infra-k8s-prod"}}notification_tech{{else}}notification_tech_minor{{end}}'
```

## 환경 디렉토리 구조

```
src/tech/ai-gateway/
├── applicationset.jsonnet      # ApplicationSet 정의
├── common/
│   └── values.yaml             # 공통 Helm values (모든 환경 공유)
├── infra-k8s-dev/
│   ├── kustomization.yaml      # Helm chart + Kustomize 설정
│   ├── values.yaml             # dev 환경 overrides
│   └── resources/              # 추가 K8s 매니페스트 (optional)
├── infra-k8s-stg/
│   ├── kustomization.yaml
│   └── values.yaml
└── infra-k8s-prod/
    ├── kustomization.yaml
    ├── values.yaml
    └── resources/
```

### kustomization.yaml 표준

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: tech-ai-gateway

helmCharts:
  - repo: oci://harbor.global.riiid.team/helm-charts
    name: webserver
    version: 0.3.42
    namespace: tech-ai-gateway
    releaseName: ai-gateway
    valuesFile: ../common/values.yaml
    additionalValuesFiles:
      - values.yaml

# resources/ 디렉토리가 있으면 자동 포함
resources:
  - resources/
```

## 트러블슈팅 체크리스트

1. **ApplicationSet이 Application을 생성하지 않음**
   - `jsonnet` 렌더링 확인: `jsonnet src/<sphere>/<circle>/applicationset.jsonnet`
   - directory 경로 패턴 확인
   - `infra-k8s-*` 디렉토리 존재 확인 (common 제외)

2. **Application이 생성되었지만 sync 안 됨**
   - `argocd app get <name>` 으로 조건 확인
   - Helm chart 버전 존재 확인
   - values.yaml 문법 오류 확인

3. **sync 후에도 OutOfSync**
   - ignoreDifferences 필요 여부 확인
   - controller가 관리하는 필드 식별
   - `argocd app diff <name>` 으로 실제 차이 확인
