---
name: learn:design
description: |
  학습 착수 전 "X를 잘 안다"의 기준을 역량 조건으로 정의하고, 현재 수준을 인터뷰로 측정해
  학습 방향을 설계하는 메타 학습 스킬. 역량 조건 정의 → 지식 레이어 맵 → 수준 인터뷰 →
  학습 순서 설계 → 질문 체크리스트 산출. 콘텐츠를 가르치지 않는다
  (세션 실행은 /learn, 모의면접은 /learn:interview, 커리큘럼 문서는 /learn:roadmap).
  사용 시점: (1) 새 주제 학습 전 "뭘 알아야 하는지" 지도가 필요할 때,
  (2) "X를 잘 안다는 게 뭘까"를 정의하고 싶을 때, (3) 현재 수준 대비 효율적 학습 순서를 설계할 때.
  트리거 키워드: "/learn:design", "학습 설계", "학습 방향", "뭘 알아야 해", "잘 안다는 게 뭐야", "학습 인터뷰".
model: sonnet
allowed-tools:
  - Read
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---

# learn:design

Meta-learning skill. It does NOT teach content. It answers three questions before any learning starts:

1. What does "knowing {topic} well" actually mean? (observable capability conditions)
2. Where is the user right now? (behavioral self-assessment interview)
3. In what order should they learn, and how will they know each gap is closed? (order design + question checklist)

## Boundary vs learn family

| Skill | Role | Routing signal |
|-------|------|----------------|
| `learn` | Deep-dive teaching session (Why → How → What-if → Apply) | "설명해줘", "가르쳐줘", "deep-dive" |
| `learn:interview` | Mock interview, one question at a time with model answers | "면접 연습", "모의 면접" |
| `learn:roadmap` | Level 0-10 curriculum document in Obsidian (living doc) | "커리큘럼", "101", "로드맵 문서" |
| `learn:recall` | Re-interview of saved ignorance notes | "재인터뷰", "무지 노트 복습" |
| `learn:design` (this) | Competency definition → diagnosis → direction | "뭘 알아야 해", "잘 안다는 게 뭐야", "학습 방향" |

If mid-session the user asks to actually learn a layer ("이거 설명해줘"), answer briefly and suggest `/learn {topic}` for a full session. Do not turn this skill into a teaching session.

## Hard Rules

1. **No one-by-one quizzing.** The Phase 5 checklist is delivered as one complete list for self-navigation. This skill exists because quiz-mode was explicitly rejected for direction-setting: the user scans the list themselves, and items they cannot answer ARE the learning targets.
2. **Self-assessment options must be behaviorally anchored.** Never offer abstract grades ("초급/중급/고급"). Each option describes a concrete behavior or experience. Bad: "중급". Good: "설정은 복붙해서 써봤지만 왜 이렇게 동작하는지는 설명 어려움" / "flag를 보고 문제 지점을 실제로 좁혀본 적 있음". Abstract grades invite flattering self-reports; behavioral anchors get honest ones.
3. **Capabilities before knowledge.** Phase 1 defines what one should be able to DO, then Phase 2 derives what to learn backwards from that. Never start from a table-of-contents-style knowledge list.
4. **Every condition states its absence cost.** Each capability condition includes "이게 없으면 무엇이 안 되는가" so the user can see why the condition matters and self-verify against it.
5. **Exactly one AskUserQuestion call** for the interview (max 4 questions). If the layer map has more than 4 layers, group adjacent layers into question groups.
6. **Ground in real context when available.** For infra topics, attach devops-wiki docs (via INDEX.md triggers) and actual past incidents to layers. A real failure case the team lived through is the most efficient material for failure-grounded judgment.

## Phase 1 — Competency Definition

Define "knowing {topic} well" as 3-5 observable capability conditions.

- Conditions are capabilities, not knowledge items. Example shape: "증상을 보고 어느 메커니즘 레이어의 실패인지 특정할 수 있다", "설정 변경의 blast radius를 적용 전에 예측할 수 있다", "값 선택에 '왜 이 값인가'를 답할 수 있다", "실제 실패 사례 기반의 판단 근거를 갖고 있다".
- Order conditions by dependency: mechanism understanding usually enables prediction, which enables trade-off judgment.

Output format (Korean):

```
| 조건 | 의미 | 이게 없으면 |
|------|------|-------------|
| A. {capability} | {what it looks like in practice} | {what stays broken without it} |
...

이 조건들은 순서대로 쌓입니다. {dependency explanation in 1-2 sentences}
```

## Phase 2 — Knowledge Layer Map

Decompose the knowledge required to reach the conditions into dependency-ordered layers.

For each layer state:
- What it contains (specific concepts, not chapter titles)
- Which condition(s) it serves
- Why skipping it blocks later layers ("이걸 모르면 다음 레이어에서 무엇이 이해 안 되는지")

For infra topics, add a "우리 인프라에서는" mapping: which internal doc / ADR / postmortem covers each layer, and which layers are best filled by real incident material.

## Phase 3 — Level Interview

Single AskUserQuestion call, max 4 questions. Group layers if needed.

- Each question covers one layer group and asks "이해도는 어느 정도인가요?"
- 3-4 options per question, spanning "전혀 모름" → "실전 경험 있음", every option a concrete behavioral descriptor (Hard Rule 2)
- This is self-report, not a quiz. The goal is a fast, honest position fix, not verification. (Verification happens later via the checklist.)

## Phase 4 — Learning Order Design

Design the session order from the interview result using two principles:

- **Prerequisite chain**: among unknown layers, foundations first.
- **Anchor-first**: layers where the user reported partial knowledge ("용어만 들어봄", "역할만 앎") go early. Extending a known fragment is faster than building from zero, and the anchor layer usually IS the vocabulary the remaining layers are written in.

Output format (Korean):

```
| 세션 | 레이어 | 왜 이 순서인가 |
|------|--------|----------------|
| 1 | {layers} | {anchor/prerequisite rationale} |
...

조건 매핑: 세션 {n}~{m}이 조건 {X}를 채우고, ... 조건 {D}는 각 세션 안에서 실제 사례로 채워갑니다.
```

Propose the order and ask for confirmation or reordering in one sentence. Do not start teaching Session 1.

## Phase 5 — Question Checklist

For each layer, list the questions one should be able to answer to claim that layer. Deliver the entire list at once, grouped by layer (Hard Rule 1).

- Frame at the top: "지금 답이 안 나오는 항목이 곧 학습해야 할 지점입니다."
- Prefer mechanism/why questions over term-definition questions: "X가 실패하면 어떤 순서로 장애가 이어지는가", "왜 A와 B는 분리되어 있는가"
- Include our-infra questions where real cases exist: "{incident}에서 근본 원인은 무엇이었는가?"
- Close with: 답이 바로 나오는 항목은 스킵하고 막히는 항목만 골라 학습하면 된다는 안내

## Wrap-up

1. **Save proposal (do not auto-save).** Offer once:

```
이 설계(역량 조건 + 레이어 맵 + 학습 순서 + 질문 체크리스트)를 Obsidian에 저장할까요?
```

On explicit approval, write the full artifact to `/tmp/obsidian-content.json` as `{"blocks": "..."}` and run:

```bash
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py create \
  --title "{topic} 학습 설계" \
  --tags "{topic}" \
  --aliases "{topic},학습 설계,{topic} 체크리스트" \
  --content-file /tmp/obsidian-content.json \
  --type learning-design
```

2. **Handoff guidance (loose coupling).** Learning itself happens outside this skill, by any method the user prefers (`/learn` sessions, docs, hands-on). Do not embed `/learn` commands into checklist items. Close with one line: 학습 후 이 체크리스트로 돌아와 답할 수 있게 된 항목을 직접 확인하면 진척이 측정됩니다.
