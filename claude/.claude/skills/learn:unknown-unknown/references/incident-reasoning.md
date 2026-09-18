# Incident Reasoning Drill

When the user brings an incident instead of a topic, do NOT lead with commands. Commands come after
the hypothesis set exists, because a command you cannot interpret produces no scope reduction.

---

## Chain

```
Symptom
   ↓
Scope            (누가 영향받고 누가 멀쩡한가: 1 Pod / 1 Node / 1 AZ / 1 namespace / 전체)
   ↓
System Boundary  (이 증상이 나올 수 있는 경계는 어디까지인가)
   ↓
Dependency Graph (그 경계 안의 의존성)
   ↓
Hypothesis       (복수로 세운다. 단일 가설은 확증 편향)
   ↓
Discriminating Evidence
   ↓
Test
   ↓
Scope Reduction
   ↓
Root Cause
```

---

## Discriminating Evidence

The central skill. For any two hypotheses, ask:

> 어떤 **하나의** 관측으로 두 hypothesis 중 하나를 제거할 수 있는가?

```
Hypothesis A: destination Pod 문제
Hypothesis B: source node network 문제

변별 관측: 같은 노드의 다른 Pod에서 같은 목적지로 호출
  → 성공하면 A, 실패하면 B
```

Good troubleshooting is **removing the most hypotheses with the fewest observations**, not running
the most commands. Explicitly reject "일단 로그부터 다 봅시다".

---

## Scope Questions

These narrow faster than any log query:

```
언제부터인가? 그 시각에 무엇이 배포/변경되었는가?
전부인가 일부인가? 일부라면 그 일부의 공통점은? (노드/AZ/버전/replica/이미지 태그)
재현되는가, 산발적인가?
새 connection만 실패인가, 기존 connection도 끊기는가?
읽기만 실패인가, 쓰기도 실패인가?
```

---

## Anti-patterns

| 안티패턴 | 왜 문제인가 |
|----------|-------------|
| 단일 가설로 직행 | 확증 편향. 반증 증거를 안 찾게 됨 |
| 명령어 나열부터 시작 | 해석 기준 없이 출력만 쌓임 |
| 상관관계를 인과로 승격 | "X 증가할 때 Y도 증가" ≠ "X가 Y를 일으킨다" |
| 증상 제거로 종료 | 재발. 메커니즘 수준까지 내려가지 않음 |
| 재시작으로 확인 종료 | 증거 소멸. 재시작 전 상태 캡처가 먼저 |

---

## Causal Chain Requirement

The root cause must connect to the user-visible symptom without a gap:

```
CoreDNS CPU throttling
        ↓ 왜?
DNS query 처리 지연
        ↓ 왜?
애플리케이션 name resolution 지연
        ↓ 왜?
신규 outbound connection 수립 지연
        ↓ 왜?
애플리케이션 P99 latency 상승
```

If any arrow requires "그리고 어쩌다 보니", the chain is incomplete: that arrow is the next
investigation target.
