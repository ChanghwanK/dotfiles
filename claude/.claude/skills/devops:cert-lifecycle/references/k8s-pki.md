# Kubernetes PKI 구조

## 인증서 파일 위치

kubeadm 기반 클러스터에서 인증서는 `/etc/kubernetes/pki/`에 저장:

```
/etc/kubernetes/pki/
├── ca.crt                    # 클러스터 CA 인증서 (10년)
├── ca.key                    # 클러스터 CA 키
├── apiserver.crt             # API server 인증서 (1년)
├── apiserver.key
├── apiserver-kubelet-client.crt  # API → kubelet 클라이언트 인증서
├── apiserver-kubelet-client.key
├── apiserver-etcd-client.crt    # API → etcd 클라이언트 인증서
├── apiserver-etcd-client.key
├── front-proxy-ca.crt        # 프록시 CA (10년)
├── front-proxy-ca.key
├── front-proxy-client.crt    # aggregation layer 인증서 (1년)
├── front-proxy-client.key
├── sa.key                    # ServiceAccount 서명 키
├── sa.pub                    # ServiceAccount 검증 키
└── etcd/
    ├── ca.crt                # etcd CA (10년)
    ├── ca.key
    ├── server.crt            # etcd 서버 인증서 (1년)
    ├── server.key
    ├── peer.crt              # etcd peer 인증서 (1년)
    ├── peer.key
    ├── healthcheck-client.crt  # etcd 헬스체크 인증서 (1년)
    └── healthcheck-client.key
```

## kubeconfig 파일

```
/etc/kubernetes/
├── admin.conf                # 클러스터 관리자 kubeconfig
├── controller-manager.conf   # controller-manager kubeconfig
├── scheduler.conf            # scheduler kubeconfig
└── kubelet.conf              # kubelet kubeconfig (자동 로테이션)
```

## 인증서 만료 확인 방법

### kubeadm

```bash
# 모든 인증서 만료 확인
sudo kubeadm certs check-expiration

# 특정 인증서 만료 확인 (OpenSSL)
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt -noout -enddate
```

### 메트릭 기반

```promql
# API server 클라이언트 인증서 만료 분포
apiserver_client_certificate_expiration_seconds_bucket

# kubelet 서버 인증서 TTL
kubelet_certificate_manager_server_ttl_seconds
```

## 인증서 갱신

### kubeadm certs renew

```bash
# 모든 인증서 갱신
sudo kubeadm certs renew all

# 특정 인증서만 갱신
sudo kubeadm certs renew apiserver
sudo kubeadm certs renew apiserver-kubelet-client
sudo kubeadm certs renew apiserver-etcd-client
sudo kubeadm certs renew front-proxy-client
sudo kubeadm certs renew etcd-server
sudo kubeadm certs renew etcd-peer
sudo kubeadm certs renew etcd-healthcheck-client
```

### 갱신 후 필수 작업

1. **kubeconfig 갱신**: `kubeadm certs renew` 후 kubeconfig도 자동 갱신됨
2. **컨트롤플레인 재시작**: static Pod들이 새 인증서를 로드하도록 재시작
   ```bash
   # kubelet 재시작 → static Pod 재생성
   sudo systemctl restart kubelet
   ```
3. **확인**: `kubeadm certs check-expiration`으로 새 만료일 확인
4. **kubeconfig 복사**: `~/.kube/config` 업데이트
   ```bash
   sudo cp /etc/kubernetes/admin.conf ~/.kube/config
   sudo chown $(id -u):$(id -g) ~/.kube/config
   ```

## kubelet 인증서 자동 로테이션

### 동작 방식

1. kubelet이 자체 인증서 만료 70~90% 시점에 CSR(Certificate Signing Request) 생성
2. kube-controller-manager의 `csrsigning` 컨트롤러가 자동 승인 및 서명
3. kubelet이 새 인증서를 로드하여 자동 교체

### 확인

```bash
# kubelet 인증서 로테이션 설정 확인
kubectl --context k8s-idc get cm kubelet-config -n kube-system -o yaml | grep rotateCertificates

# CSR 상태 확인
kubectl --context k8s-idc get csr
```

### kubelet 인증서 위치

```
/var/lib/kubelet/pki/
├── kubelet-client-current.pem    # 현재 클라이언트 인증서 (심링크)
├── kubelet-client-YYYY-MM-DD.pem # 날짜별 클라이언트 인증서
└── kubelet.crt                   # 서버 인증서
```

## CA 인증서 갱신 (10년 주기)

CA 인증서는 kubeadm이 자동 갱신하지 않음. 10년 만료 전 수동 갱신 필요.

**주의:** CA 갱신은 모든 하위 인증서 재발급이 필요한 대규모 작업.
- 새 CA로 모든 인증서 재서명
- 모든 노드의 CA trust 업데이트
- 모든 kubeconfig 업데이트

이 작업은 별도 계획이 필요하며, 일반적인 인증서 갱신과 분리하여 진행.

## IDC 노드 매핑

| 역할 | 호스트 | IP | 인증서 관리 |
|------|--------|-----|-----------|
| 관리 CP | a6000-node01 | 10.10.0.75 | kubeadm 수동 갱신 |
| 워크로드 CP 1 | proxmox VM | DHCP | CAPI 자동 (rolloutBefore 설정 시) |
| 워크로드 CP 2 | proxmox VM | DHCP | CAPI 자동 |
| 워크로드 CP 3 | proxmox VM | DHCP | CAPI 자동 |
| 워커 1~7 | proxmox VM | DHCP | kubelet 자동 로테이션 |
