# Domain Doc Map: 도메인별 공식 문서 seed + 조사 축

Step 1(서브질문 분해)과 Step 2(doc-researcher `{official_domains}` 치환)에서 참조한다.
아래에 없는 도메인은 같은 패턴(공식 docs + 벤더 공식 blog)으로 seed를 구성한다.

---

## AWS 네트워크 설계 (VPC, TGW, Peering, DNS)

- **Seed**: `docs.aws.amazon.com`, `aws.amazon.com/blogs/networking-and-content-delivery`, `aws.amazon.com/architecture` (Well-Architected)
- **조사 축**: CIDR/서브넷 설계 원칙, 라우팅 토폴로지(TGW vs Peering), quota(VPC당 라우트 수 등), 데이터 전송 비용 모델, cross-AZ/cross-region 비용, DNS 해석 경로(Route 53 Resolver)
- **우리 인프라 접점**: Tokyo VPC `10.0.0.0/16`, Seoul VPC `10.100.0.0/16`, IDC 연동

## AWS PrivateLink / VPC Endpoint

- **Seed**: `docs.aws.amazon.com/vpc/latest/privatelink/`, `aws.amazon.com/blogs/networking-and-content-delivery`
- **조사 축**: Endpoint Service(NLB 필수) vs Gateway/Interface Endpoint 구분, cross-region 지원 여부, 시간당+데이터 처리 비용, DNS private hosted zone 연동, quota(endpoint당 대역폭)

## K8s 컨트롤 플레인 / 클러스터 토폴로지

- **Seed**: `kubernetes.io/docs`, `docs.aws.amazon.com/eks/`, `github.com/kubernetes` (KEP), `cluster-api.sigs.k8s.io`
- **조사 축**: CP HA 구성(etcd quorum, stacked vs external), 관리형(EKS) vs 자체 구축 경계, 버전 skew 정책, 클러스터 분리 기준(env별 vs 통합+멀티테넌시), upgrade 전략
- **우리 인프라 접점**: EKS(prod/stg/dev/global) + IDC(Proxmox + Cluster API)

## ClickHouse 설계

- **Seed**: `clickhouse.com/docs`, `clickhouse.com/blog` (이해관계 하향 적용)
- **조사 축**: shard/replica 토폴로지, ReplicatedMergeTree + Keeper(ZooKeeper 대체) 구성, 스토리지(로컬 vs S3-backed), 삽입 패턴(batch 권장), 리소스 사이징 원칙, ClickHouse Operator(Altinity) vs ClickHouse Cloud
- **우리 인프라 접점**: observability sphere(VictoriaMetrics·Loki와 역할 경계), data-platform sphere

## Strimzi Kafka 클러스터

- **Seed**: `strimzi.io/docs`, `kafka.apache.org/documentation`, `www.confluent.io/blog` (이해관계 하향)
- **조사 축**: KRaft vs ZooKeeper(버전별 지원), broker/controller 노드 풀 분리, 스토리지(JBOD, PV 클래스), rack awareness(topology spread), listener 구성(내부/외부 노출), Cruise Control 리밸런싱, MSK 대안 비교
- **우리 인프라 접점**: KEDA(consumer lag 스케일링), Istio 통과 여부, CNPG처럼 Operator 기반 운영 패턴

## Observability 스택 확장

- **Seed**: `docs.victoriametrics.com`, `grafana.com/docs`(Loki/Tempo/Alloy), `opentelemetry.io/docs`
- **조사 축**: 카디널리티/리텐션 설계, 스토리지 백엔드, 샘플링 전략, HA 구성
- **우리 인프라 접점**: observability sphere 기존 스택과의 역할 중복 여부

## 데이터베이스 (PostgreSQL 계열)

- **Seed**: `www.postgresql.org/docs`, `cloudnative-pg.io/documentation`, `docs.aws.amazon.com/AmazonRDS/` (Aurora)
- **조사 축**: Aurora vs CNPG 경계(관리형 vs K8s 네이티브), replica 토폴로지, 백업/PITR, connection pooling
- **우리 인프라 접점**: Aurora PostgreSQL(관리형) + CNPG(클러스터 내) 이원 운영 중

---

## 우리 인프라 컨텍스트 소스 (context-collector가 사용)

### Wiki 소스 선택 (설계 주제 기반)

devops-wiki는 리포마다 별도로 존재한다. 설계 주제에 따라 읽을 wiki를 선택한다 (복수 선택 가능):

| Wiki 경로 | 담당 영역 | 포함 조건 |
|-----------|----------|-----------|
| `~/workspace/riiid/kubernetes/devops-wiki` | EKS 클러스터·GitOps·워크로드 (istio, victoriametrics, cnpg 등 ADR) | 기본 포함 (모든 설계) |
| `~/workspace/riiid/k8s-on-premise/devops-wiki` | IDC/Office 온프레미스 (Proxmox, Cluster API, GPU/MPS, Ceph, Cilium, kube-vip ADR) | IDC·GPU·온프레미스·하이브리드 연동 설계 시 |
| `~/workspace/riiid/terraform/devops-wiki` | AWS IaC (계정·네트워크 결정) | AWS 네트워크·계정·리소스 프로비저닝 설계 시 |

주제가 어느 wiki에 걸치는지 애매하면 후보 wiki의 `INDEX.md`만 먼저 읽어 관련성을 판단한 뒤 본문을 읽는다.

### Wiki 내부 구조 (세 wiki 공통)

| 디렉터리 | 내용 |
|----------|------|
| `INDEX.md` | wiki 전체 목차 (진입점) |
| `01-decisions/` | ADR (기존 기술 선정 이유, 설계와 충돌 가능한 결정) |
| `02-context/` | 인프라 현황 컨텍스트 |
| `03-guardrails/` | 팀 가드레일 (설계가 위반하면 안 되는 규칙, 없는 wiki도 있음) |
| `memory/` | 계정·노드 구성·알려진 이슈 |
| `04-issues/`, `04-postmortems/` | 장애·이슈 이력 |

### 실제 배포 구성

| 소스 | 내용 |
|------|------|
| `~/workspace/riiid/kubernetes/src/<sphere>/` | EKS 배포 구성 (Jsonnet/YAML) |
| `~/workspace/riiid/k8s-on-premise/` | IDC/Office 클러스터 부트스트랩 (cluster-*.yaml, kubeadm-config, cilium) |
