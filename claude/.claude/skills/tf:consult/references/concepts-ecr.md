# Amazon ECR — 개발자를 위한 개념 가이드

## 한줄 요약

Docker Hub의 private repository를 AWS 안에 둔 것.
EKS(K8s)가 컨테이너 이미지를 가져올 때 ECR에서 pull한다.

## 개발자에게 익숙한 비유

`docker pull` 할 때 Docker Hub 대신 AWS ECR에서 가져온다고 생각하면 된다.

```
# Docker Hub (공개)
docker pull nginx:latest

# ECR (비공개, AWS 인증 필요)
docker pull 992382516451.dkr.ecr.ap-northeast-1.amazonaws.com/socraai-domain:v1.0.0
```

우리 팀은 ECR 외에 **Harbor** (`harbor.global.riid.team`)도 사용한다.
- **ECR**: AWS 서비스 전용 이미지, IAM으로 접근 제어
- **Harbor**: 팀 내부 공통 이미지, 더 강력한 취약점 스캔

## 핵심 개념

| AWS 용어 | 쉽게 말하면 | 예시 |
|---------|-----------|------|
| **Repository** | 하나의 이미지 저장소 | `socraai-domain` |
| **Image Tag** | 버전 식별자 | `v1.0.0`, `latest`, `main-a1b2c3d` |
| **수명주기 정책** | 오래된 이미지 자동 삭제 규칙 | 최근 10개만 유지 |
| **이미지 스캔** | 보안 취약점 자동 탐지 | push 시 자동 실행 |
| **Cross-Region Replication** | 다른 리전에 이미지 복제 | 우리는 단일 리전 사용 |

## Riiid에서 어떻게 쓰는지

- **위치**: `src/{sphere}/{circle}/global/ecr/` (항상 `global` 환경)
- **이름 규칙**: `{sphere}-{circle}` → 예: `socraai-domain`, `socraai-util-core`
- **수명주기**: 일반적으로 최근 N개 태그만 유지 (구 이미지 자동 삭제)
- **환경은 항상 global**: 이미지는 dev/stg/prod 환경 구분 없이 하나의 레지스트리 공유
- **pull 권한**: EKS IRSA 또는 노드 인스턴스 역할로 자동 부여

## 결정해야 할 사항 체크리스트

- [ ] 몇 개의 Repository가 필요한가? (서비스당 1개가 일반적)
- [ ] 이미지 보관 정책: 최근 몇 개 버전을 유지할 건가요?
- [ ] 이미지 스캔 자동화 필요 여부
- [ ] cross-account 접근 필요 여부 (다른 AWS 계정에서 pull)

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/global에 ECR Repository 생성
- Repository 이름: {sphere}-{circle} (예: socraai-domain)
- 이미지 보관 정책: 최근 {N}개 유지
- 이미지 스캔: {활성화 / 비활성화}
```
