---
name: task:understand-quiz
description: |
  Runs an iterative understanding-check loop for a unit of work: closed-book gates and questions first, grading against model answers after the owner replies, then follow-up questions that drill into every gap until the owner passes. Purpose is to clear the comprehension bottleneck, not to render a one-shot quiz. Default scope is the whole task; it narrows to a phase, a step, or a PR only when explicitly asked. Sources: Notion Task, plan file, PR, or the current session.
  사용 시점: (1) Task 착수 전 목적과 방향을 스스로 점검, (2) 특정 Phase/Step 진입 전 준비 확인, (3) PR 리뷰 대비, (4) 남의 작업 인수인계.
  트리거 키워드: "이해 점검", "이해 점검 질문", "Task 점검 질문", "PR 점검 질문", "설명할 수 있나", "퀴즈", "리뷰 대비", "task:understand-quiz", "/task:understand-quiz".
model: opus
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/task:understand-quiz/scripts/collect_work_context.py *)
  - Read
  - mcp__notion-personal__API-retrieve-page-markdown
  - mcp__notion-personal__API-retrieve-a-page
---
# task:understand-quiz Skill

Turns a unit of work into an iterative understanding-check loop, so the owner ends up able to explain and defend it without re-reading the artifact. Output alone is not the deliverable; the owner's verified understanding is.

---

## 핵심 원칙

- **Ground every answer in collected context.** Each model answer MUST point at something real: a file path, a config key, a value, a step title, a commit, a number. No answer may rest on general knowledge alone.
- **Never invent a rationale.** When the artifact does not state why the work exists, report that gap instead of writing a plausible purpose. A fabricated why is worse than a missing one, because the owner will repeat it.
- **Default to the whole task.** Narrow to a phase, a step, or a PR only when the user names one. Do not volunteer a narrower scope.
- **Axes follow granularity.** A task and a step do not ask the same three questions. Use the axis table in Step 3.
- **Closed-book gates come before the quiz.** AI-parallel work produces output faster than understanding accumulates (comprehension debt), and "feels understood" is not a reliable signal. So round 1 opens with two gates the owner must answer without re-reading the artifact: restate the work in their own words, and recall its three load-bearing claims.
- **The quiz is a loop, not a one-shot.** Grade the owner's answers, then chase every partial or wrong answer with follow-up questions aimed at the exact gap. Continue by default; the owner stops the loop, not the skill. The loop ends when every axis passes or the owner says stop.
- **Model answers are withheld until grading.** The question round shows questions only. Model answers, 한 문장 요약, and 게이트 기준답 surface in the grading round for the items being graded. Revealing them upfront would reduce the loop to reading comprehension.
- **스크립트만 호출한다.** Direct `gh` or `git` invocation is not allowed. Notion pages come from the MCP read tool, everything else from the script.

---

## 워크플로우

### Step 1: Resolve target and granularity

Read the user's request for two independent things.

**Target** (what work), in priority order:

| Signal | Target |
|--------|--------|
| Notion URL or "Task" + a name | Notion Task page |
| PR number, `#N`, PR URL, or "PR" | PR |
| Plan name, "플랜", "이 플랜" | Plan file |
| Nothing named | Whatever this session has been working on. Ask only if genuinely ambiguous. |

**Granularity** (how much of it):

| Signal | Granularity |
|--------|-------------|
| **Nothing said** | **`task`, the default** |
| "Phase 2", "2단계", a phase name | `phase` |
| "Step 3", "3번", a step title | `step` |
| "PR 기준", or the target is a PR | `pr` |

Granularity is not inferred from target size. A ten-step plan still defaults to `task`.

### Step 2: Collect context

```bash
# PR (current branch's PR by default)
python3 /Users/changhwan/.claude/skills/task:understand-quiz/scripts/collect_work_context.py pr
python3 /Users/changhwan/.claude/skills/task:understand-quiz/scripts/collect_work_context.py pr --ref 8665

# Plan file
python3 /Users/changhwan/.claude/skills/task:understand-quiz/scripts/collect_work_context.py list-plans
python3 /Users/changhwan/.claude/skills/task:understand-quiz/scripts/collect_work_context.py plan --name scalable-wishing-floyd
```

For a **Notion Task**, read the page with `API-retrieve-page-markdown`. The 6-field body maps as follows:

| Body section | Use it for |
|--------------|------------|
| `00. Summary` | one-line framing |
| `01. 문제 정의` (As-Is / To-Be) | 목적 axis |
| `02. 문제 분석` | evidence for every answer |
| `03. 해결 이유` | 목적 axis, urgency |
| `04. 기대효과` 측정 기준 | completion criteria |
| `05. Goals/Non Goals` | **방향성 axis. Non-Goals is the richest source.** |
| `06. 세부 계획` checkboxes | the `units` for phase/step granularity |

For **session context** (no artifact), use the conversation itself and say so in the scope line.

The script's normalized fields, whatever the source:

| Field | Meaning |
|-------|---------|
| `kind` | `pr` or `plan` |
| `purpose` / `purpose_present` | the stated why. `false` triggers the gap rule. |
| `units[]` | addressable sub-units: `{id, label, title, status, body}` |
| `diff` / `diff_truncated` | PR only. Do not write an answer depending on a cut hunk. |

### Step 3: Pick axes by granularity

| 단위 | Q1 | Q2 | Q3 |
|------|----|----|----|
| **task** (기본) | **목적** 어떤 문제 때문에 존재하며, 없으면 무엇이 불가능한가 | **방향성** 일부러 하지 않기로 한 것과 그 이유 | **해결 방법** 무엇을 어떻게 바꿔 목적을 달성하는가 |
| **phase** | **선행 조건** 이 phase가 시작되려면 무엇이 이미 참이어야 하는가 | **완료 판정** 무엇을 보고 이 phase가 끝났다고 하는가 | **다음 의존** 이게 없으면 다음 phase의 무엇이 막히는가 |
| **step** | **변경 내용** 이 step이 구체적으로 무엇을 바꾸는가 | **순서 근거** 왜 앞이나 뒤가 아니라 여기인가 | **실패 인지** 실패하면 어떻게 알아차리며 어떻게 되돌리는가 |
| **pr** | **목적** 어떤 문제 때문에 만들어졌는가 | **방향성** 일부러 하지 않은 것과 그 이유 | **해결 방법** 무엇을 고쳐 그 목적을 달성하는가 |

Fill the three cells from the context before drafting a single question. A cell you cannot fill is a `GAP`; carry it to 근거를 찾지 못한 항목.

**Gap rule**: still ask the question, but write the answer as "이 {단위}는 {축}을 명시하지 않았습니다" plus the strongest inference, clearly labeled as inference.

**Phase and step answers MUST place the unit in sequence.** Use `units[]` status to say what is already done and what waits. This is what the 이 단위의 위치 block in the template is for.

### Step 4: Write at the requested difficulty

Default is 3 questions, one per axis, at 초급. Honor explicit requests such as "중급으로", "5문항", "고급만".

| 난이도 | Shape | Answerable by |
|--------|-------|---------------|
| **초급** | Definitional. "What is X and what does it do here?" | Reading the artifact surface |
| **중급** | Mechanism. "How does this produce that effect?" | Tracing the change through the system |
| **고급** | Trade-off, blast radius, failure mode. "What breaks this, and how would you notice?" | Reasoning about conditions the artifact does not state |

Rules at every level:

- No yes/no questions. Every question demands an explanation.
- One question per axis by default. For more, add depth within an axis rather than inventing a fourth.
- The 고급 question should surface a **silent failure mode** when one exists: something that degrades quietly rather than erroring. Those catch real gaps.
- Model answers are 3 to 8 sentences.

### Step 4.5: Build the closed-book gate (always)

Extract from the collected context the **three load-bearing claims** of the unit: the decisions, mechanisms, or numbers that, if the owner cannot recall them, mean the work is not defensible. Rules:

- Each claim is one sentence, concrete, and grounded in the context like any model answer (a decision plus its reason, a config key plus its value, a trade-off plus what it bought).
- The three claims must be independent of each other; do not split one decision into three phrasings.
- Fewer than three real claims in the context is a `GAP`: render the ones that exist, lower the pass threshold accordingly, and carry the shortfall to 근거를 찾지 못한 항목.

Only the two prompts (재구성, 복기) render in round 1. The reference claims (게이트 기준답) and the 한 문장 요약 that grades gate 1 are prepared here but revealed only in the grading round.

### Step 5: Render

```
Read /Users/changhwan/.claude/skills/task:understand-quiz/assets/output-template.md
```

Render the **question round** template only: gates (round 1) plus the axis questions, with no model answers, no 한 문장 요약, no 게이트 기준답. Substitute the axis names for the resolved granularity. Include `## 이 단위의 위치` only for `phase` and `step`. Include `## 근거를 찾지 못한 항목` only when Step 3 or Step 4.5 produced a `GAP`.

The scope line MUST state what was quizzed, for example `Task 전체 기준입니다` or `Step 3만 다룹니다 (전체 6단계 중 1개 완료)`.

Then stop and wait for the owner's answers. Do not answer the questions in the same message.

### Step 6: Verify before returning a question round (MUST)

- [ ] Every model answer (held for grading) cites a concrete artifact from the context.
- [ ] No answer asserts a rationale absent from the source, unless labeled as inference.
- [ ] No question can be answered "yes" or "no".
- [ ] Axis names match the resolved granularity in the Step 3 table.
- [ ] Phase and step quizzes include 이 단위의 위치.
- [ ] If `diff_truncated` is `true`, no answer depends on a cut hunk.
- [ ] The question round reveals no model answer, no 한 문장 요약, no 게이트 기준답, and none of the three claims.
- [ ] Each 게이트 기준답 claim is grounded in the context, and a shortfall below three is reported as a `GAP` with the threshold adjusted.
- [ ] Output has no em dash and no emoji.

### Step 7: Grade and deepen (the loop)

When the owner replies, grade and continue. This step repeats until exit.

**Grading** (use the grading round template):

- Verdict per item: `통과` / `부분` / `미달`. Grade the substance, not the wording; the owner's phrasing may differ freely from the model answer.
- For every graded item, now reveal the held reference: the model answer, and for round 1 the 한 문장 요약 (grades gate 1) and 게이트 기준답 (grades gate 2, pass at {pass_threshold} of {claim_count}).
- 교정 must name what exactly was missing or wrong, grounded in the context. "아쉽습니다" without the missed artifact is not a grade.

**Deepening**:

- Every `부분`/`미달` item spawns 1 to 2 follow-up questions aimed at the exact gap: the mechanism behind the miss, or a re-explanation in the owner's own words. Never repeat the original question verbatim.
- When all items at the current difficulty pass, escalate the weakest axes one level (초급 → 중급 → 고급) and continue with up to 3 new questions. Escalation is the default, not an offer.
- Keep every round at 3 questions or fewer. Depth over breadth.

**Exit** (only these):

- All axes pass at 고급, or
- The owner says stop ("그만", "통과", "여기까지", "스킵").

On exit, render the 종료 요약: which axes passed cleanly, which needed rounds, and which items remain not-understood. Append 예상 리뷰 질문 when at least two are genuinely likely (mainly `pr` granularity). Suggest archiving the remaining items with `/wiki:note 무지`.

---

## 주의사항

- Granularity defaults to `task` even when the user hands over a single step's link. Narrow only on an explicit ask.
- `source: local-branch` on a PR collect means no PR exists yet. Say "PR 미생성, 로컬 브랜치 기준" in the scope line so the owner knows answers came from commit messages.
- The plan frontmatter parser reads the standard `todos:` shape only. A hand-edited plan yields fewer units, never wrong ones.
- A work item touching many files usually has one load-bearing change. Build the 해결 방법 answer around it; do not enumerate everything.
- When the work is someone else's, the gap section matters more than the questions. It is the handover checklist.
- This skill does not review correctness. Use the code review flow for that.
- If the owner declines to answer and asks for the answers ("답만 줘", "그냥 보여줘"), fall back to one-shot mode: reveal all model answers, 한 문장 요약, and 게이트 기준답 at once, and end the loop. Do not push the loop on an owner who opted out.

---

## Related

- `git:pr` creates the PR this skill can quiz.
- `tasks:tech-spec` and the plan writer produce the phases and steps this skill addresses.
- `learn:interview` quizzes a topic; this quizzes one specific unit of work.
