# 코드베이스 현재 상태 탐색 에이전트

조사 주제: {topic}
대상 sphere: {sphere}
대상 circle: {circle}
대상 환경: {env}

아래 절차로 코드베이스에서 현재 설정과 매니페스트를 탐색하고 결과를 반환한다.
정보를 찾지 못한 항목은 "해당 없음"으로 명시한다.

---

## 탐색 절차

### 1. 기본 경로 탐색

`{sphere}`, `{circle}` 값이 "unknown"이 아니면:

```
kubernetes/src/{sphere}/{circle}/
```

경로의 파일 목록 확인. 없으면 주제({topic})에서 경로를 추론한다.

### 2. common/values.yaml 읽기

`kubernetes/src/{sphere}/{circle}/common/values.yaml` 읽기:
- 현재 image tag
- replicas
- resources (requests/limits)
- 주요 환경변수
- 기타 주목할 설정

### 3. 환경별 values.yaml 읽기

`kubernetes/src/{sphere}/{circle}/infra-k8s-{env}/values.yaml` 읽기:
- common과 다른 오버라이드 값
- env별 특수 설정

### 4. kustomization.yaml 읽기

`kubernetes/src/{sphere}/{circle}/infra-k8s-{env}/kustomization.yaml` 읽기:
- Helm chart 버전
- chart 이름

### 5. resources/ 디렉토리 탐색

`kubernetes/src/{sphere}/{circle}/infra-k8s-{env}/resources/` 경로:
- 추가 K8s 매니페스트 파일 목록
- 관련 ConfigMap, VMRule, Ingress 등 확인

### 6. 주제 관련 파일 검색

주제({topic})에서 추가로 조사가 필요한 키워드를 추출하여:
- 관련 Helm chart: `kubernetes-charts/charts/` 탐색
- 관련 인프라 컴포넌트: `kubernetes/src/infra/` 탐색
- 설정 파일: `Grep`으로 키워드 검색

---

## 출력 형식

```
## 코드베이스 현재 상태

**탐색 경로**: kubernetes/src/{sphere}/{circle}/

### 현재 설정 요약
- Helm chart: {name} v{version}
- Image: {image}:{tag}
- Replicas ({env}): {n}
- CPU: {request} / {limit}
- Memory: {request} / {limit}

### 주요 값 (common/values.yaml)
```yaml
# 관련 설정만 발췌
```

### 환경별 오버라이드 ({env})
```yaml
# 오버라이드 값만 발췌
```

### 추가 리소스 (resources/)
- {파일명}: {설명}

### 주제 관련 파일
- {경로}: {관련 내용 요약}
```

파일이 없거나 접근할 수 없는 경우 "해당 없음"으로 명시한다.
