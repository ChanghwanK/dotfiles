---
name: devops:cert-lifecycle
description: |
  IDC 클러스터(infra-k8s-idc) Kubernetes PKI 인증서 생명주기 관리 스킬.
  kubeadm 기반 인증서 만료 확인/갱신, CAPI 자동 로테이션, kubelet 인증서 상태 확인.
  EKS는 AWS가 컨트롤플레인 인증서를 자동 관리하므로 이 스킬 대상이 아님.
  사용 시점: (1) K8s 인증서 만료 알림 발생, (2) 인증서 만료 사전 점검,
  (3) CAPI 자동 로테이션 설정 확인, (4) kubelet 인증서 상태 확인,
  (5) 관리 클러스터(a6000-node01) 인증서 갱신.
  트리거 키워드: "인증서", "certificate", "cert", "PKI", "만료", "expiry",
  "kubeadm certs", "인증서 갱신", "cert rotation", "CAPI 인증서".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(kubectl *)
  - Bash(ssh *)
  - mcp__grafana__query_prometheus
---

# IDC Certificate Lifecycle Management

infra-k8s-idc 클러스터의 Kubernetes PKI 인증서 생명주기를 관리한다.

**대상:** infra-k8s-idc (kubeadm + Cluster API)
**EKS 클러스터는 AWS가 자동 관리하므로 대상 외.**

## 참조 문서 (필요 시 Read)

- CAPI 클러스터 정의: `/Users/changhwan/workspace/riiid/k8s-on-premise/cluster-idc.yaml`
- kubeadm 설정: `/Users/changhwan/workspace/riiid/k8s-on-premise/kubeadm-config-idc.yaml`

---

## IDC 클러스터 구조

### 관리 클러스터 (Management Cluster)

- **노드:** a6000-node01 (10.10.0.75)
- **프로비저닝:** kubeadm으로 직접 부트스트랩
- **인증서 갱신:** 수동 (`kubeadm certs renew`)
- **CAPI 컴포넌트:** CAPMOX v0.7.0 (ionos-cloud)

### 워크로드 클러스터 (infra-k8s-idc)

- **컨트롤플레인:** 3개 VM (Proxmox 위)
- **프로비저닝:** Cluster API (KubeadmControlPlane)
- **인증서 갱신:** CAPI 자동 로테이션 가능 (`rolloutBefore.certificatesExpiryDays`)

---

## 인증서 상태 확인

### 워크로드 클러스터 인증서 확인

```bash
# 컨트롤플레인 노드에서 확인 (SSH 필요)
# 또는 메트릭으로 확인
```

```promql
# 인증서 만료까지 남은 시간 (초)
apiserver_client_certificate_expiration_seconds_bucket

# kubelet 인증서 만료
kubelet_certificate_manager_server_ttl_seconds
```

### 관리 클러스터 인증서 확인

```bash
# a6000-node01에 SSH 접속 후
ssh a6000-node01
sudo kubeadm certs check-expiration
```

**출력 예시:**
```
CERTIFICATE                EXPIRES                  RESIDUAL TIME
admin.conf                 Mar 15, 2027 05:00 UTC   364d
apiserver                  Mar 15, 2027 05:00 UTC   364d
apiserver-etcd-client      Mar 15, 2027 05:00 UTC   364d
apiserver-kubelet-client   Mar 15, 2027 05:00 UTC   364d
controller-manager.conf    Mar 15, 2027 05:00 UTC   364d
etcd-healthcheck-client    Mar 15, 2027 05:00 UTC   364d
etcd-peer                  Mar 15, 2027 05:00 UTC   364d
etcd-server                Mar 15, 2027 05:00 UTC   364d
front-proxy-client         Mar 15, 2027 05:00 UTC   364d
scheduler.conf             Mar 15, 2027 05:00 UTC   364d
```

---

## CAPI 자동 인증서 로테이션

### 현재 설정 확인

```bash
# KubeadmControlPlane 설정 확인
kubectl --context k8s-idc get kcp -A -o yaml | grep -A5 rolloutBefore
```

### rolloutBefore 설정

```yaml
# cluster-idc.yaml의 KubeadmControlPlane
spec:
  rolloutBefore:
    certificatesExpiryDays: 30  # 만료 30일 전 자동 롤링 업데이트
```

이 설정이 활성화되면:
1. CAPI가 인증서 만료 30일 전 감지
2. 컨트롤플레인 노드를 순차적으로 롤링 업데이트
3. 새 노드는 새 인증서로 생성됨
4. 서비스 중단 없이 자동 갱신

**상세:** `references/capi-cert-rotation.md` 참조

---

## 수동 인증서 갱신 (관리 클러스터)

관리 클러스터(a6000-node01)는 CAPI가 관리하지 않으므로 수동 갱신 필요.

### 갱신 절차

```bash
# 1. 현재 만료 확인
ssh a6000-node01
sudo kubeadm certs check-expiration

# 2. 모든 인증서 갱신
sudo kubeadm certs renew all

# 3. 컨트롤플레인 컴포넌트 재시작
sudo systemctl restart kubelet
# static Pod들은 자동 재시작됨 (manifest 변경 감지)

# 4. kubeconfig 갱신 (admin.conf 등)
sudo cp /etc/kubernetes/admin.conf ~/.kube/config

# 5. 갱신 확인
sudo kubeadm certs check-expiration
```

### 주의사항

- **etcd 인증서도 함께 갱신됨** (kubeadm certs renew all)
- **kubeconfig 파일도 갱신 필요** (admin.conf, controller-manager.conf, scheduler.conf)
- **갱신 후 kubectl 동작 확인** 필수
- **CA 인증서는 kubeadm이 갱신하지 않음** (10년 유효, 별도 관리)

---

## Kubernetes PKI 구조

### 인증서 종류

| 인증서 | 용도 | 기본 유효기간 |
|--------|------|-------------|
| CA (ca.crt) | 클러스터 CA | 10년 |
| apiserver | API server TLS | 1년 |
| apiserver-kubelet-client | API→kubelet 인증 | 1년 |
| apiserver-etcd-client | API→etcd 인증 | 1년 |
| front-proxy-ca | 프록시 CA | 10년 |
| front-proxy-client | aggregation layer | 1년 |
| etcd CA | etcd 전용 CA | 10년 |
| etcd-server | etcd TLS | 1년 |
| etcd-peer | etcd 클러스터 간 | 1년 |
| etcd-healthcheck-client | etcd 헬스체크 | 1년 |

### kubelet 인증서 자동 로테이션

kubelet은 기본적으로 인증서 자동 로테이션을 지원:
- `--rotate-certificates=true` (기본 활성)
- kubelet이 만료 전 자동으로 CSR 생성 및 갱신
- API server의 CSR 자동 승인 설정 필요

**상세:** `references/k8s-pki.md` 참조

---

## 모니터링 알림

### 인증서 만료 알림 설정

```yaml
# VMRule 예시
- alert: KubeCertExpiringSoon
  expr: |
    apiserver_client_certificate_expiration_seconds_count > 0
    and histogram_quantile(0.01, rate(apiserver_client_certificate_expiration_seconds_bucket[5m])) < 86400 * 30
  for: 0m
  labels:
    severity: warning
  annotations:
    summary: "Kubernetes 인증서 30일 내 만료 예정"
```

---

## 출력 포맷

```markdown
# 인증서 상태 리포트

## 클러스터: [관리/워크로드]
| 인증서 | 만료일 | 남은 기간 | 상태 |
|--------|--------|----------|------|

## 조치 필요 항목
[갱신 필요한 인증서와 절차]
```
