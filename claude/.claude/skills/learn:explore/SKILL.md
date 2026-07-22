---
name: learn:explore
description: |
  특정 주제(기술/개념)에 대한 "탐구 지도"를 생성한다. 기본→중급→심화 3단계로 (1) 이해하면 좋을 개념,
  (2) 파고들 Why / 꼬리물기 질문, (3) 딥다이브 블로그 글쓰기 주제(의문형)를 정리한다.
  가르치지 않고(=learn), 커리큘럼 문서를 만들지 않으며(=learn:roadmap), 수준 인터뷰를 하지 않는다(=learn:design).
  "이 주제로 뭘 궁금해하고, 어떤 Why를 고민하고, 어떤 글을 쓰면 좋을지"를 한 번에 뽑아주는 스킬.
  사용 시점: (1) 새 주제를 파기 전 "무엇을 궁금해하면 좋을지" 지도가 필요할 때,
  (2) Why/꼬리물기 질문 세트를 얻고 싶을 때, (3) 블로그/기술글 딥다이브 주제를 발굴할 때.
  트리거 키워드: "/learn:explore", "탐구 지도", "뭘 궁금해하면 좋을지", "Why 꼬리물기 정리",
  "딥다이브 주제", "블로그 주제 정리", "학습 관점 정리", "이 주제 파고들 포인트".
model: sonnet
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---

# learn:explore

Generate a tiered **exploration map** for a topic. This skill does NOT teach the content and does NOT run an assessment interview. It produces one structured artifact that answers three questions per difficulty tier:

1. What concepts are worth understanding? (기본 → 중급 → 심화)
2. What Why / tail-questions ("꼬리물기") reveal the mechanism behind each concept?
3. What deep-dive blog topics (phrased as questions) turn this curiosity into writing?

The output is Korean, formal (`~입니다`, `~합니다`), bullet-list heavy. The instructions below are English by skill-file convention; the produced artifact is Korean.

## Boundary vs learn family

| Skill | Role | Route here instead when |
|-------|------|-------------------------|
| `learn` | Teaches content in a Why→How→What-if→Apply session | User says "설명해줘", "가르쳐줘", "deep-dive 해줘" |
| `learn:design` | Defines "knowing X well", interviews current level, designs order | User wants capability conditions or a level assessment |
| `learn:roadmap` | Level 0~10 curriculum saved to Obsidian with progress tracking | User wants a trackable curriculum document |
| `learn:explore` | **This skill.** One-shot curiosity/Why/blog-topic map | User asks "뭘 궁금해하면 좋을지 / Why 꼬리물기 / 딥다이브·블로그 주제 정리" |

If the request mixes intents (e.g. "map + then teach"), produce the exploration map first, then suggest `/learn <topic>` to go deeper on a chosen item.

## Core principles

- **Curiosity map, not answers**: State what to be curious about and why it matters. Do not resolve the Why questions; leaving them open is the point.
- **Mechanism-first Why**: Every Why/tail-question should push toward internals (왜 이렇게 설계됐는가, 어떤 조건에서 깨지는가), not surface facts. Chain them (`A → B → so C`) so one question opens the next.
- **Tiered by cognitive depth**: 기본 = existence/necessity, 중급 = abstraction & interaction, 심화 = internals & failure/edge cases. Each tier's Why questions must be answerable only after grasping that tier's concepts.
- **Blog topics are questions**: Every deep-dive topic is phrased as the question the post would answer ("~하면 어떻게 될까?", "~한 이유는?"). The title IS the curiosity hook.
- **Infra grounding (`우리 인프라에서는`)**: When the topic touches the user's stack (EKS gp3/EBS, IDC Rook-Ceph, StatefulSet, CNPG, Karpenter, Istio, VictoriaMetrics/Loki/Tempo, ArgoCD), add a short connection line per tier tying the concept to a real component or past incident. Read `devops-wiki/` only if a concrete grounding is worth confirming; otherwise use known context. Skip this block for topics unrelated to the infra.
- **No em dash, no emoji** in the produced artifact (team hard rule). Use colon / comma / parentheses instead.

## Flow

### Step 1: Confirm topic and angle

Get from the user (ask only if missing):
- Topic (e.g. "파드와 볼륨", "Istio sidecar", "Kafka consumer group")
- Optional angle: 운영 / 트러블슈팅 / 설계 / 인터뷰 / 블로그 중심 (default: balanced, all tiers)

If the topic is already clear from the conversation, skip the question and generate directly.

### Step 2: Generate the exploration map

Produce the artifact using the template below. Rules:
- Each tier has 3 blocks: **이해할 개념** (4~7 bullets), **Why / 꼬리물기 질문** (4~6 bullets, each chained toward mechanism), and (tier-level) an optional **우리 인프라에서는** line.
- 딥다이브 블로그 주제 is a separate final section, grouped by difficulty (입문 / 중급 / 심화), every title in question form.
- End with a **추천 시작점**: which tier to start learning from, and which 1~2 blog topics have the highest reuse value (flag ones that connect to team postmortem/guardrail as worth saving to `devops-wiki`).
- Close with the standard 이해 점검 3-question block (초급/중급/고급) derived directly from this topic.

### Step 3 (optional, on request): Save to Obsidian

Only if the user asks to save ("저장해줘", "노트로 남겨줘"). Write the artifact body to `/tmp/obsidian-content.json` and run:

```bash
python3 /Users/changhwan/.claude/skills/wiki:note/scripts/obsidian-note.py create \
  --title "{topic} 탐구 지도" \
  --tags "{topic}" \
  --content-file /tmp/obsidian-content.json \
  --type resource
```

Otherwise, do not save. End the response with the soft suggestion line: `💡 /wiki:note 로 이 탐구 지도를 개인 wiki에 저장할 수 있습니다.`

## Output template

```markdown
{topic}은(는) "{한 문장짜리 핵심 질문}"에서 출발해 {영역}으로 뻗어나가는 주제입니다.
기본 → 중급 → 심화 로드맵에 이어, 딥다이브 블로그 주제를 의문 해결형 질문으로 정리했습니다.

## 1단계: 기본 ({이 단계의 한 줄 주제})

### 이해할 개념
- ...

### Why / 꼬리물기 질문
- **{질문}?** → {꼬리물기 힌트, 다음 질문으로 연결}
- ...

### 우리 인프라에서는   ← 인프라 무관 주제면 생략
- ...

## 2단계: 중급 ({주제})

### 이해할 개념
- ...

### Why / 꼬리물기 질문
- ...

### 우리 인프라에서는
- ...

## 3단계: 심화 ({주제})

### 이해할 개념
- ...

### Why / 꼬리물기 질문
- ...

### 우리 인프라에서는
- ...

## 딥다이브 주제 (블로그 글쓰기, 의문 해결형)

각 제목이 곧 글이 답할 질문입니다.

### 입문 난이도 (개념 정립형)
- **"{~하면 어떻게 될까? / ~한 이유는?}"** → {한 줄 각도}
- ...

### 중급 난이도 (메커니즘 해부형)
- **"{질문형 제목}"** → {각도}
- ...

### 심화 난이도 (내부 원리 + 장애 분석형)
- **"{질문형 제목}"** → {각도, 가능하면 팀 사례 연결}
- ...

### 추천 시작점
{어느 단계부터, 어떤 블로그 주제가 재사용 가치 높은지 1~2개}

---
**이해 점검** (스킵하려면 다음 질문으로 넘어가세요)
- **초급**: {정의형 질문}
- **중급**: {메커니즘형 질문}
- **고급**: {실무 연계형/트레이드오프형 질문}
```

## Notes

- Keep the Why questions genuinely open. If a bullet answers itself, it belongs in 이해할 개념, not in Why.
- Blog topics must be questions, never noun phrases. "CSI Attach/Mount 해부" is wrong; "볼륨이 stuck됐을 때 CSI 3단계 중 어디서 막힌 걸까?" is right.
- Do not pad tiers with generic filler. If the topic is narrow, fewer high-quality bullets beat many shallow ones.
- This skill runs in the main conversation; apply the user's proactive-suggestion rules at the end (이해 점검 + wiki save suggestion), not both a gate and a wiki suggestion at once.
