---
name: review
description: |
  메커니즘 검토 스킬. 트러블슈팅·심층 분석 중 세운 "X는 Y 때문에 이렇게 동작한다" 류의 가설을 반증 우선, 설치 버전 기준 공식 문서, 블라인드 평가로 동조 없이 검증한다.
  사용 시점: 사용자 메시지가 "검토", "검토 해", "검토 한다"로 끝나거나 "/review"를 부를 때만. "리뷰해줘", "봐줘", "어때?", "맞아?"는 트리거가 아니다.
  비대상: 상태·용량 판단("replicas 늘릴까"), 이력서·글쓰기·Notion 문서·블로그 리뷰.
model: opus
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebSearch
  - WebFetch
  - Agent
  - Bash(kubectl get *)
  - Bash(kubectl describe *)
  - Bash(kubectl logs *)
  - mcp__victoriametrics-prod__query
  - mcp__victoriametrics-prod__query_range
  - mcp__victoriametrics-idc__query
  - mcp__victoriametrics-idc__query_range
  - mcp__grafana__query_prometheus
  - mcp__grafana__query_loki_logs
---
# review Skill

Split a mechanism hypothesis into mechanism claims, observations, and the inference linking them; verify mechanisms against primary sources for the version we run, observations against measurements, then judge the inference.

## Core principles

- **Neither agreement nor disagreement is the goal.** The weight of evidence decides; forced contrarianism is a bias too.
- **Fixed verdicts**: `SUPPORTED` / `PARTIAL` / `REFUTED` / `UNDETERMINED`, each with `[n]`. Tier and confidence rules: `references/evidence-tiers.md`.
- **Output template**: `assets/output-format.md`. Length is proportional: one M claim settled by T1 is a few lines; a full RCA hypothesis is a full report.
- **Read-only.** Measure, read, propose; never change cluster or repo state.

## Workflow

### Step 0: Scope gate, target, stance

1. **Scope gate.** The target must contain at least one **mechanism claim**: how or why a component behaves, what causes what, what a setting does internally. If the request is a state or capacity judgement with no mechanism in it ("should we raise replicas", "how much memory", "is prod OK"), stop and answer in one line: `이 요청은 메커니즘 검토 대상이 아니라 상태·용량 판단입니다. <devops:infra-rca / cost-analyzer-agent / 직접 답변>으로 진행하겠습니다.` Resumes, prose, Notion wording, blog posts: same one-liner, route to `resume:bullet` or `blog:review`.
2. **Target** = the text preceding the trigger word, or the hypothesis under discussion if that text only points to it. Two equally plausible candidates: ask one question.
3. **Stance** (internal): what the user believes and how strongly (in an RCA, usually `favors` their own hypothesis). The blind evaluator must not see it; Step 4 must resist it.

### Step 1: Decompose into mechanism, observation, inference

| Kind | Definition | Example | Falsified if |
|------|-----------|---------|--------------|
| **M** mechanism | How a component works in general | "Envoy closes an idle upstream connection after `idleTimeout`; a request racing that close gets 503 UC" | The doc for our version says otherwise, or the behavior is version-gated |
| **O** observation | A fact about our system, with the query that produced it | "503 UC rose 40x at 14:02 (Loki query Q1)" | Re-running the query differs, or there is no query |
| **I** inference | M plus O explains the symptom | "So the 503s are idle-close races, not upstream crashes" | An alternative explains O equally well, or M and O do not predict the symptom's shape (timing, magnitude, distribution) |
| **P** premise | Unstated assumption everything rests on | "The app uses keep-alive", "traffic is HTTP/1.1" | Checked against config or a measurement |

Strip evaluative words; write each claim so it can be false. List at least one alternative mechanism the inference competes with ("no alternative" is itself a claim needing evidence).

### Step 2: Evidence collection, routed by kind

**Version anchor first (MUST for M claims).** Find the installed version (`values.yaml` / `kustomization.yaml` image tag or chart version, or `devops-wiki/02-context/cluster-summary.md`) and record it as `A1`. Every M citation is for `A1` or states the version delta explicitly.

| Kind | Sources, in order (search against before for) | Link form |
|------|------------------|-----------|
| **M** | (1) against: T1 docs for `A1`, release notes and changelog between the doc version and `A1`; (2) for: same T1, then T2 (`references/evidence-tiers.md`); (3) TX: `devops-wiki/04-postmortems/`, `04-issues/`, `03-guardrails/` Lessons, project memory, `claude-mem:mem-search`. Ambiguous docs are not a reason to read source: `UNDETERMINED` instead. Freshness and versioned-docs trap: `~/.claude/skills/research/references/source-tiers.md` | URL, wiki path |
| **O** | The query in the conversation. A conclusion without a query (including negatives like "no OOM") is re-measured now: VictoriaMetrics, Loki, `kubectl get/describe/logs`. Record query and result | query text + result, or `path:line` |
| **I** | No separate source; judged in Step 3 and 4 from verified M and O against the alternatives | derived |
| **P** | Config (`Grep`/`Read`) or one measurement | `path:line` or query |

**Delegate** M-claim research to `agents/agent-evidence-collector.md` (model `sonnet`) when there are 2+ M claims or any web fetch is needed. Pass only `{claims}` (M and P), `{version_anchor}`, `{domain_hints}`; never the user's wording, stance, or the inference. O claims are measured by the main flow.

Each evidence item: `id`, `claim_id`, `direction` (`against` / `for`), `tier`, `title`, `url_or_path`, `date_or_version`, `quote` (verbatim, short), `note`.

### Step 3: Blind evaluation of the inference

Run when there is at least one I claim. Skip only for a bare M fact check already settled by T1 for `A1`.

1. **Write your own preliminary verdict per claim first** (internal), before reading the agent's output.
2. Spawn `agents/agent-blind-evaluator.md` (model `opus`) with `{claims}` (M, O, I, P), `{alternatives}`, `{evidence_pack}`. Forbidden: the user's original text, stance, authorship, phrases like "the user thinks".
3. Compare. Report a mismatch in `판정 불일치` with both positions and their evidence. Do not average.

### Step 4: Verdict

Per claim, worst news first: verdict + confidence (`high` / `medium` / `low`), evidence `[n]` for and against, the **strongest counterargument** (mandatory even for `SUPPORTED`), and **what would change this verdict** (a measurement, a version, a doc page).

Gates:
- M claim cited from a doc for a version other than `A1` without a changelog check: at most `PARTIAL`.
- O claim without a query: `UNDETERMINED`, naming the query to run.
- I claim: `SUPPORTED` only when every M it depends on is `SUPPORTED` for `A1`, every O has a query, and every alternative is ruled out by evidence, not by absence of evidence.
- A refuted P refutes the I claims that depend on it.
- T3 only: `UNDETERMINED`.

### Step 5: What resolves the remaining ambiguity

MUST be present. For every `PARTIAL` / `UNDETERMINED` claim and every alternative not ruled out, list the concrete action (PromQL/LogQL, `kubectl` command, doc page for `A1`, config to read). Run the read-only ones available now and report the result inline; do not stop at "measurement needed" when it is one query away.

### Step 6: Self-check and validate (MUST), then output

Walk `references/bias-checklist.md`. Fix failures by adding evidence or removing the claim, never by softening wording.

Fail conditions that block output:
- a verdict without `[n]`
- an M claim with no version anchor `A1`
- an O claim presented as fact without its query
- an I claim `SUPPORTED` with an alternative never addressed
- a `SUPPORTED` / `REFUTED` resting on T3 only
- an opening sentence from the banned-agreement list

## After the report: pushback handling

Follow the pushback protocol in `references/bias-checklist.md`: a verdict flips only on new evidence; never restate the same verdict in softer words as a compromise.
