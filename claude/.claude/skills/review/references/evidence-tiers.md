# Evidence Tiers for `review`

Tier assignment for every evidence item, the named-source seed list, and the confidence rules. Freshness, versioned-docs trap, and stale labels are not redefined here: apply `~/.claude/skills/research/references/source-tiers.md` as is.

---

## Tiers

| Tier | Name | Includes | Link required | Can alone carry SUPPORTED / REFUTED |
|------|------|----------|---------------|-------------------------------------|
| **T1** | Primary | Official docs, API reference, release notes, changelog, RFC / KEP / PEP, the project's source code, vendor docs (`docs.aws.amazon.com` etc.) | Yes (URL) | Yes |
| **T2** | Named engineers and big-tech engineering | Writings by engineers listed below, big-tech engineering blogs (seed: `~/.claude/skills/research/references/tech-blogs.md`), peer-reviewed papers, conference talks with published material | Yes (URL) | Yes, when 2 independent T2 items converge; otherwise `PARTIAL` |
| **TX** | Our experience | Project memory (`MEMORY.md` entries), `devops-wiki/04-issues/`, `04-postmortems/`, `03-guardrails/` Lessons, merged PRs, past sessions via `claude-mem:mem-search` | Yes (repo path or PR URL) | Only for claims about our own infra, and only with the measurement that produced the conclusion |
| **T3** | Model knowledge | What the model believes without a fetched source | No (label `(model knowledge, unverified)`) | No. Max `UNDETERMINED` |

Rules:
- Same fact in several tiers: cite the highest tier.
- T2 vendor material arguing its own product's superiority: downgrade one step unless an independent source agrees.
- TX is scoped: it says what happened here under those conditions. Do not generalize `n=1`. Count impact by affected units (pods, requests, users), not tool units (alerts, log lines).
- T3 must be tried last, after a T1 and a T2 search both returned nothing relevant. Record that the searches were made.

---

## Named engineers (T2 seed)

Start here; extend by domain when the target is outside this list. A person qualifies when their primary writing is first-hand engineering work, not aggregation.

| Person | Domain | Primary source |
|--------|--------|----------------|
| Linus Torvalds | Linux kernel, git, systems design | `lore.kernel.org` (LKML archives), `git.kernel.org` commit messages |
| Brendan Gregg | Performance, observability, eBPF, USE method | `brendangregg.com` |
| Martin Fowler | Architecture, refactoring, patterns | `martinfowler.com` |
| Martin Kleppmann | Distributed data systems, consistency | `martin.kleppmann.com` |
| Marc Brooker | Distributed systems, AWS internals, reliability | `brooker.co.za/blog` |
| Werner Vogels | Distributed systems, AWS | `allthingsdistributed.com` |
| Dan Luu | Systems, measurement, latency | `danluu.com` |
| Julia Evans | Linux internals, networking, debugging | `jvns.ca` |
| Bryan Cantrill | OS, systems debugging | `bcantrill.dtrace.org`, Oxide blog |
| Kelsey Hightower | Kubernetes operations | `github.com/kelseyhightower` |
| Tim Hockin | Kubernetes networking and API design | `github.com/thockin`, KEP discussions |
| Liz Rice | eBPF, container security | `lizrice.com` |
| Charity Majors | Observability, ops culture | `charity.wtf` |
| Cindy Sridharan | Distributed systems, observability | `copyconstruct.medium.com` |
| Tanya Reilly | SRE, staff engineering | `noidea.dog` |
| Will Larson | Engineering management, infra strategy | `lethain.com` |
| Kent Beck | Testing, XP, design | `tidyfirst.substack.com` |
| Aleksey Shipilev | JVM internals, GC, benchmarks | `shipilev.net` |
| Gil Tene | Latency measurement, HdrHistogram, JVM | `latencytipoftheday.blogspot.com`, Azul talks |
| Rich Hickey | Language and system design (Clojure) | `github.com/richhickey` talk transcripts |

Big-tech engineering blogs: use the seed tables in `~/.claude/skills/research/references/tech-blogs.md` (Netflix, Cloudflare, AWS Builders' Library, Google SRE, Meta, Uber, Stripe, 토스, 우아한형제들, 카카오, 네이버 D2, and others).

---

## Link rules

- A link is a URL that was fetched with `WebFetch`, or a repo path (`devops-wiki/04-postmortems/postmortem-x.md`, `src/santa/http-api/infra-k8s-prod/values.yaml:42`), or a PR URL (`https://github.com/riiid/kubernetes/pull/8796`).
- A search snippet is not a link. A URL remembered from training is not a link until fetched.
- Versioned or archived official URLs are normalized to `current` / `latest` before citing (table in the research skill's `source-tiers.md`).
- References list format: `[n] <title> · <URL or path> (<tier>, <date or version>[, stale label])`.

---

## Confidence per claim

Decision rules, not a score.

1. Start from the best evidence tier on the winning side: T1 → `high`, T2 → `medium`, TX → `medium` (own-infra claims) or `low` (generalized), T3 → `low`.
2. Raise one step (max `high`) when two independent items converge. Independent means not citing, translating, or scraping each other.
3. Lower one step for each: stale-suspect or undated source, vendor self-interest, counter-evidence of the same tier left unanswered.
4. `low` on a time-variable claim (defaults, API fields, GA status, quotas, numbers): do not issue `SUPPORTED` / `REFUTED`; issue `UNDETERMINED` and name the T1 page that would settle it.
