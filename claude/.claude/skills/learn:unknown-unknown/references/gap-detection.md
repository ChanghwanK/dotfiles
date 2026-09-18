# Gap Detection & Evaluation

When the user explains a system, do NOT reveal the reference answer first. Run these five checks,
then name each missing piece explicitly.

---

## 5 Detection Rules

### 1. Missing Component

A major subsystem is absent from the flow.

User says:

```
Pod → Service → Pod
```

Check for these candidates:

```
DNS resolution / network namespace / veth pair / CNI
Service translation (kube-proxy or eBPF) / node networking / cloud networking
Istio sidecar (mesh 사용 시) / conntrack
```

How to point it out:

> 여기에는 DNS Resolution 단계가 빠져 있습니다.
> `user-service`라는 문자열이 IP로 변환되지 않으면 TCP connection 자체를 시작할 수 없습니다.
> 따라서 다음 영역이 추가되어야 합니다: Application resolver → /etc/resolv.conf → CoreDNS → Service DNS record.

Name it, state why the flow cannot complete, list the area to add. Never just say "빠진 게 있습니다".

---

### 2. Missing Layer

The explanation lives in one abstraction layer only.

If the user explains only at the Kubernetes layer, expand:

```
Application → Linux (libc, syscall) → Kernel (netfilter, conntrack, cgroup, scheduler)
→ Network (L2/L3/L4/L7) → Kubernetes → Cloud (VPC, ENI, NLB, route table)
```

Common single-layer traps: "Kubernetes 레이어만", "AWS 콘솔 레이어만", "애플리케이션 로그 레이어만".

---

### 3. Missing Lifecycle

The user knows the static architecture but cannot connect it into a runtime sequence.

Knowing `API Server` / `Scheduler` / `kubelet` individually does not mean they can narrate
`kubectl apply → Pod Running`. Convert any static list answer into a lifecycle question immediately.

---

### 4. Missing Failure Surface

Only the happy path is described. Add:

```
Component failure / dependency failure / resource exhaustion / network partition
timeout / retry storm / concurrency / race condition / partial failure
control-plane failure vs data-plane failure / cascading failure
```

Key discriminator to push on: **control plane이 죽어도 계속 도는 것은 무엇이고, 즉시 멈추는 것은 무엇인가.**

---

### 5. Missing Scale Dimension

Scale is treated as traffic only. Expand:

```
Traffic scale / data scale / concurrency scale / connection scale
Node scale / Pod scale / deployment frequency scale
Failure scale (동시 장애 수) / organizational scale (사람·팀 수)
```

Many designs survive traffic growth but die on connection count, object count in etcd, or the number
of humans who must understand them.

---

## Evaluation Axes

Assess the user's explanation on eight axes. Report plainly, no praise padding.

| 축 | 질문 |
|----|------|
| Coverage | 전체 Problem Space를 얼마나 포함했는가 |
| Depth | 각 component의 메커니즘을 얼마나 이해했는가 |
| Connectivity | component 사이 dependency를 설명할 수 있는가 |
| Causality | 왜 그 결과가 나오는지 인과로 설명하는가 |
| Failure Awareness | 어떻게 깨지는지 아는가 |
| Observability | 깨졌을 때 어떻게 증명하는가 |
| Trade-off | alternative와 비교할 수 있는가 |
| Decision | 특정 환경에서 판단을 내릴 수 있는가 |

Reporting format:

```
Coverage        3/5   DNS·CNI 누락
Connectivity    2/5   Service와 EndpointSlice의 관계 미설명
Failure         1/5   happy path만
Observability   0/5   미언급
```

Low scores are the session's agenda, not a verdict. Convert each low axis directly into the next
question.
