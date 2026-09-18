# External Reference Models

A self-built mental model cannot reveal its own holes. Every session compares the user's model
against at least one external source.

```
My Mental Model → Reference Model → Difference → Unknown Unknown 발견
```

The goal is the **difference**, not memorizing the reference.

---

## Source Priority

| 소스 | 무엇을 얻는가 |
|------|---------------|
| Official documentation | 설계 의도, 설정 표면 전체 |
| Reference architecture | 실제 배치와 경계 |
| Source code | 관측한 동작이 만들어지는 decision point |
| RFC / design proposal (KEP 등) | 왜 이렇게 설계했고 무엇을 기각했는가 |
| Postmortem (타사) | 내가 몰랐던 dependency |
| GitHub issue | 문서에 없는 실제 실패 모드 |
| Engineering blog | 운영 규모에서의 트레이드오프 |

Prefer sources that state rejected alternatives: those name the trade-off directly.

---

## Source Code

Never say "소스를 읽어보세요". Read against one question:

> 내가 관측한 현상이 코드의 어느 **decision point**에서 만들어지는가?

```
Pending Pod
 → Scheduler Queue → Filter → Score → Bind

Pending Pod (Karpenter)
 → Reconcile → Scheduling Simulation → NodeClaim → Cloud Provider
```

Specify the decision point to look for, not the repository. The goal is connecting runtime behavior
to implementation, not code mastery.

---

## Postmortem

Read in this order. Reading the root cause first destroys the exercise.

```
Symptom 확인
 ↓
읽기 중단
 ↓
내 Hypothesis 작성
 ↓
Dependency Graph 작성
 ↓
실제 RCA 확인
 ↓
내 Mental Model과 비교 → 내가 세우지 못한 가설이 곧 unknown unknown
```

Sources, in order of preference:

| 소스 | 왜 |
|------|-----|
| 사용자 조직의 자체 장애 기록 | 같은 스택·같은 제약이라 전이 가능성이 가장 높다 |
| 공개 postmortem (Cloudflare, GitHub, AWS post-event summary 등) | 규모가 커서 드러난 dependency를 볼 수 있다 |
| 해당 프로젝트의 GitHub issue | 문서에 없는 실제 실패 모드 |

If the user's org keeps an internal incident archive, ask for its location once and use it; do not
assume a path.

---

## Environment Anchoring

Design-stage answers must be conditional on the user's environment. Elicit the axes below rather
than assuming values, and state which axis drives the recommendation.

| 축 | 묻는 것 |
|----|---------|
| Traffic / Scale | 요청량, 객체 수, connection 수 |
| Cost sensitivity | 무엇이 지배적 비용 항목인가 |
| Availability requirement | 실제로 요구되는 수준 (선언된 수준이 아니라) |
| Operation capacity | 이걸 6개월 뒤 유지할 사람이 몇 명인가 |
| Platform dependency | 특정 클라우드/온프렘 종속을 받아들일 수 있는가 |
| Developer productivity | 복잡도가 사용자(개발팀)에게 노출되는가 |

Rules:

- 조건부로 답한다. "A가 낫습니다"가 아니라 "X면 A, Y면 B".
- 되돌리기 어려운 결정(one-way door)은 명시한다.
- Managed Service가 기본 정답이라고 가정하지 않는다. 자체 운영이 사는 것(비용·역량·성능)과
  치르는 대가(학습 곡선·유지보수)를 양쪽 다 진술한다.
- 사용자가 축의 값을 모르면 그것 자체가 발견이다: "이 결정은 {축}에 달려 있는데 지금 그 값을
  모르고 계십니다"로 짚는다.
