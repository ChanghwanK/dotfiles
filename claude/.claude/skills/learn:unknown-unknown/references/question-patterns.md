# Question Patterns

Five question types. A session that uses only type 1 and 3 will not surface unknown unknowns.
Types 2 (Boundary) and 4 (Diagnosis) carry the highest discovery yield.

---

## 1. Lifecycle Question

Trace one real event from start to finish. This is the primary instrument of the skill.

```
Pod에서 curl http://user-service 를 실행하면
HTTP Response가 돌아올 때까지 실제로 어떤 일이 발생하는가?

kubectl apply를 실행하면 Pod가 Running이 될 때까지 무엇이 일어나는가?

ArgoCD가 Git commit을 감지하고 Rollout이 promote되기까지의 전 과정은?
```

Reference trace to compare against (reveal only AFTER the user answers):

```
Application → libc resolver → /etc/resolv.conf → CoreDNS → Service DNS record
→ socket() → TCP → network namespace → veth → CNI → Service translation
→ routing → destination Pod → application listener
```

---

## 2. Boundary Question

Where does one subsystem's responsibility end and the next begin? Boundaries are where unknown
unknowns hide, because each side assumes the other handles it.

```
CoreDNS가 IP를 반환한 이후, 실제 packet 전송은 어느 subsystem으로 넘어가는가?
Scheduler의 역할은 어디까지이고 kubelet의 역할은 어디서부터인가?
Karpenter가 NodeClaim을 만든 뒤 Node Ready까지는 누가 책임지는가?
Istio sidecar가 처리하는 구간과 애플리케이션이 처리하는 구간의 경계는?
ArgoCD가 소유하는 리소스와 controller가 동적으로 만드는 리소스의 경계는?
```

---

## 3. Failure Question

Per-subsystem failure modes. Only meaningful AFTER the Map and Trace stages.

```
DNS가 실패하면? TCP handshake가 실패하면?
Service routing이 실패하면? Application listener가 실패하면?
Control plane은 살아있고 data plane만 죽으면 무엇이 계속 동작하는가?
이미 맺어진 connection과 새 connection의 운명이 갈리는 지점은 어디인가?
```

---

## 4. Diagnosis Question

One symptom, many causes. The core question is not "what broke" but:

> **어디까지 정상이라는 것을 증명할 수 있는가?**

```
curl timeout 하나로부터
DNS / Routing / NetworkPolicy / Security Group / TCP / Service / Application
중 무엇인지 어떻게 가르는가?

503 하나로부터 UC / UH / UT / NR / UO / UF 중 무엇인지 어떤 필드로 가르는가?

Pod Pending 하나로부터 리소스 부족 / taint / PVC AZ 고정 / NodePool limit
중 무엇인지 어떤 이벤트 한 줄로 가르는가?
```

Good troubleshooting is not running many commands. It is **removing the most hypotheses with the
fewest observations.**

---

## 5. Trade-off / Design Question

Escalate from "how it works" to "why this design, and what did it cost".

```
왜 Service가 필요한가? Pod IP를 직접 쓰면 왜 안 되는가?
왜 CoreDNS를 쓰는가? 애플리케이션이 직접 service discovery 하면 안 되는가?
왜 CNI라는 인터페이스가 필요한가? kubelet이 직접 하면 안 되는가?
kube-proxy iptables vs IPVS vs Cilium eBPF: 무엇을 얻고 무엇을 잃는가?
```

Evaluate each alternative on: 성능 / 비용 / 운영 부담 / 복잡도 / 위험도 / debugging 난이도 /
failure surface. Then answer conditionally: "X 상황이면 A, Y 상황이면 B" — never "A가 낫습니다".

Mark one-way-door decisions explicitly.

---

## Difficulty Ladder

Do not stop at the definition. Climb:

```
What → Why → How → Dependency → Lifecycle → Failure → Observation → Diagnosis → Trade-off → Design
```

Example on one topic:

| 단계 | 질문 |
|------|------|
| What | CoreDNS란 무엇인가 |
| Why | 왜 클러스터에 DNS가 별도로 필요한가 |
| How | Service 이름을 어떤 데이터로 IP에 매핑하는가 |
| Dependency | CoreDNS는 무엇에 의존하는가 (kube-apiserver watch, upstream resolver) |
| Lifecycle | Pod의 resolv.conf는 누가 언제 써 넣는가 |
| Failure | CoreDNS가 전부 죽으면 기존/신규 connection은 각각 어떻게 되는가 |
| Observation | 그 상태를 어떤 메트릭·로그로 증명하는가 |
| Diagnosis | DNS 실패와 routing 실패를 어떤 관측 하나로 가르는가 |
| Trade-off | NodeLocal DNSCache는 무엇을 얻고 무엇을 잃는가 |
| Design | 운영 중인 환경의 QPS·비용·인력 조건에서 도입할 가치가 있는가 |
