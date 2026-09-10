---
name: review
description: |
  메커니즘 검토 스킬. 트러블슈팅·심층 분석 중 세운 "원리·동작 방식·인과" 가설을 신뢰 자료로 동조 없이 검증한다.
  대상은 "X는 Y 때문에 이렇게 동작한다" 류의 메커니즘 주장과 그것으로 관측을 설명하는 추론이다.
  반증 우선 수집, 우리 클러스터 설치 버전 기준 공식 문서 대조, 사용자 입장을 모르는 블라인드 평가,
  근거 tier(공식 문서·소스코드 > 네임드 엔지니어·빅테크 블로그 > 모델 지식), 링크 필수를 강제한다.
  사용 시점: 사용자 메시지가 명시적으로 "검토", "검토 해", "검토 한다"로 끝날 때, 또는 "/review"를 호출할 때만.
  이 문구 없이 자동 호출하지 않는다. "리뷰해줘", "봐줘", "어때?", "맞아?" 류는 트리거가 아니다.
  비대상: 상태·용량 판단("replicas 늘릴까", "리소스 얼마"), 이력서·글쓰기·문장 교정·Notion 문서·블로그 리뷰.
  트리거 키워드: 문장 끝 "검토", "검토 해", "검토 한다", "/review".
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

Take a mechanism hypothesis formed during troubleshooting or deep analysis, split it into mechanism claims, observations, and the inference linking them, verify the mechanism against primary sources for the version we actually run, verify observations against measurements, then judge whether the inference holds.

---

## Core principles

- **Neither agreement nor disagreement is the goal.** The weight of evidence decides. Forced contrarianism is a bias too.
- **Mechanism claims are verified against the version we run.** A doc for another version is not evidence. Anchor the component version first (values, kustomization, `cluster-summary.md`), then read that version's docs, release notes, or source.
- **Disconfirm first.** For each mechanism claim, look for the condition that makes it false before looking for support.
- **Observations are data only when they come with the query.** A sentence written earlier in the session ("CPU was fine") is not an observation; the query and its result are. Negative observations ("no OOM") need the query that returned zero.
- **The inference is where sycophancy bites.** "Your theory fits the data" is the answer the user hopes for during an RCA. The `blind-evaluator` judges the inference without knowing whose theory it is.
- **Fixed verdicts**: `SUPPORTED` / `PARTIAL` / `REFUTED` / `UNDETERMINED`, each with `[n]`. Model knowledge (T3) has no link, is labeled, and caps at `UNDETERMINED`. Tier rules: `references/evidence-tiers.md`.
- **Pushback needs new evidence** to flip a verdict. Protocol: `references/bias-checklist.md`.
- **Output in Korean, formal register, conclusion first.** Template: `assets/output-format.md`.

---

## Workflow

### Step 0: Scope gate, target, stance

1. **Scope gate.** The target must contain at least one **mechanism claim**: how or why a component behaves, what causes what, what a setting does internally. If the request is a state or capacity judgement with no mechanism in it ("should we raise replicas", "how much memory", "is prod OK"), stop and answer in one line: `이 요청은 메커니즘 검토 대상이 아니라 상태·용량 판단입니다. <devops:infra-rca / cost-analyzer-agent / 직접 답변>으로 진행하겠습니다.` Resumes, prose, Notion wording, blog posts: same one-liner, route to `resume:bullet`, `notion-review`, `blog:review`.
2. **Target** = the text preceding the trigger word, or the hypothesis under discussion in the current analysis if that text only points to it. Two equally plausible candidates: ask one question.
3. **Stance** (internal): what the user believes and how strongly. In an RCA this is usually `favors` their own hypothesis. This is what the blind evaluator must not see and what Step 4 must resist.

### Step 1: Decompose into mechanism, observation, inference

| Kind | Definition | Example | Falsified if |
|------|-----------|---------|--------------|
| **M** mechanism | General statement about how a component works | "Envoy closes an idle upstream connection after `idleTimeout` and a request racing that close gets 503 UC" | The doc or source for our version says otherwise, or the behavior is version-gated |
| **O** observation | A fact about our system, with the query that produced it | "503 UC count rose 40x at 14:02 (Loki query Q1)" | Re-running the query gives a different result, or the claim has no query |
| **I** inference | The causal link: M plus O explains the symptom | "Therefore the 503s are idle-close races, not upstream crashes" | An alternative mechanism explains O equally well, or M and O do not predict the symptom's shape (timing, magnitude, distribution) |
| **P** premise | Unstated assumption everything rests on | "The app uses keep-alive", "traffic is HTTP/1.1" | Checked against config or a measurement |

Strip evaluative words. Write each claim so that it can be false. List the alternative mechanisms the inference competes with (at least one; "no alternative" is itself a claim needing evidence).

### Step 2: Evidence collection, routed by kind

**Version anchor first (MUST for M claims).** Find the installed version: `values.yaml` / `kustomization.yaml` image tag or chart version, or `devops-wiki/02-context/cluster-summary.md`. Record it as `A1`. Every M citation must be for that version or state the version delta explicitly.

| Kind | Sources, in order | Link form |
|------|------------------|-----------|
| **M** | (1) against: T1 docs for `A1`, release notes and changelog between the doc version and `A1`, source code; (2) for: same T1, then T2 named engineers and big-tech blogs (`references/evidence-tiers.md`); (3) TX: `devops-wiki/04-postmortems/`, `04-issues/`, `03-guardrails/` Lessons, project memory, `claude-mem:mem-search`. Freshness and versioned-docs trap: `~/.claude/skills/research/references/source-tiers.md` | URL, source path with tag, wiki path |
| **O** | The query in the conversation. If the observation is a conclusion without a query, re-measure now: VictoriaMetrics, Loki, `kubectl get/describe/logs`. Record query and result | query text + result, or `path:line` |
| **I** | No separate source. Judged in Step 3 and 4 from verified M and O, against the listed alternatives | derived |
| **P** | Config (`Grep`/`Read`) or one measurement | `path:line` or query |

**Delegate** M-claim research to `agents/agent-evidence-collector.md` (model `sonnet`) when there are 2+ M claims or any web fetch is needed. Pass only `{claims}` (M and P), `{version_anchor}`, `{domain_hints}`. Never pass the user's wording, stance, or the inference. O claims are measured by the main flow, not the agent.

Each evidence item: `id`, `claim_id`, `direction` (`against` / `for`), `tier`, `title`, `url_or_path`, `date_or_version`, `quote` (verbatim, short), `note`.

### Step 3: Blind evaluation of the inference

Run when there is at least one I claim (the usual case in an RCA). Skip only for a bare M fact check already settled by T1 for `A1`.

1. **Write your own preliminary verdict per claim first** (internal). Forming it after reading the agent's output defeats the purpose.
2. Spawn `agents/agent-blind-evaluator.md` (model `opus`) with `{claims}` (M, O, I, P), `{alternatives}`, `{evidence_pack}`. Forbidden: the user's original text, stance, authorship, phrases like "the user thinks".
3. Compare. A mismatch is reported in `판정 불일치` with both positions and the evidence each relied on. Do not average.

### Step 4: Verdict

Per claim, worst news first:

- verdict + confidence (`high` / `medium` / `low`, rules in `references/evidence-tiers.md`)
- evidence `[n]` for and against
- **strongest counterargument**, mandatory even for `SUPPORTED`
- **what would change this verdict**: a measurement, a version, a doc page

Gates:
- M claim cited from a doc for a version other than `A1` without a changelog check: at most `PARTIAL`.
- O claim without a query: `UNDETERMINED`, and the query to run is named.
- I claim: `SUPPORTED` only when every M it depends on is `SUPPORTED` for `A1`, every O has a query, and the listed alternatives are ruled out by evidence, not by absence of evidence.
- A refuted P refutes the I claims that depend on it.
- T3 only: `UNDETERMINED`.

### Step 5: What resolves the remaining ambiguity

This section MUST be present. For every `PARTIAL` / `UNDETERMINED` claim and every alternative not ruled out, list the concrete action: the PromQL or LogQL, the `kubectl` command, the doc page for `A1`, the config to read. Run the ones that are read-only and available now; report the result inline. The report must not end at "measurement needed" when the measurement is one query away.

### Step 6: Self-check and validate (MUST), then output

Walk `references/bias-checklist.md`. Fix failures by adding evidence or removing the claim, never by softening wording. Output with `assets/output-format.md`.

Fail conditions that block output:
- a verdict without `[n]`
- an M claim with no version anchor `A1`
- an O claim presented as fact without its query
- an I claim `SUPPORTED` with an alternative that was never addressed
- a `SUPPORTED` / `REFUTED` resting on T3 only
- an opening sentence from the banned-agreement list

---

## After the report: pushback handling

1. Ask which claim and which evidence item is disputed, or what new evidence exists.
2. Re-run Step 2 for that claim only. New evidence flips the verdict: `판정 변경: I1 PARTIAL → SUPPORTED, 근거 [7]`. No new evidence: `판정 유지`, with the specific reason.
3. Never restate the same verdict in softer words as a compromise.

---

## Notes

- Do not open with agreement or praise. Banned openings: `references/bias-checklist.md`.
- Do not fabricate URLs. Cite only fetched pages, read paths, or executed queries.
- Proportional length: one M claim with a T1 answer is a few lines; a full RCA hypothesis is a full report.
- Read-only. This skill measures, reads, and proposes; it does not change cluster or repo state.
