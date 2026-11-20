You are reviewing a research report draft for faithfulness to its evidence. Do not search the web. Do not create, edit or delete any file.

Files in the working directory:
- `draft.md`: the draft. Citations look like `[@c012]`, where the id is a claim id in `claims.jsonl`; each cited claim is the evidence for the sentence it is attached to. A few may be `[@s1a2b3c4]` (a source id) for whole-source references such as an example block.
- `claims.jsonl`: the claim ledger. Each line has `claim_id`, `claim`, `quote` (verbatim from the source), `source_id`, `url`.
- `verdicts/*.json`: independent verdicts per claim (`SUPPORTED`, `PARTIAL`, `REFUTED`, `UNVERIFIABLE`) with notes.
- `sources/<source_id>.txt`: raw page text of each source, if you need to look closer.

Go through every sentence in `draft.md` that states a fact, number, default, version, behavior or recommendation, and report a problem when:
- `unsourced`: the sentence states a fact but has no citation, and it is not plainly the report's own synthesis of cited sentences around it.
- `wrong_citation`: the cited claim does not back this sentence (or, for a source id citation, no claim in the ledger with that source_id supports it).
- `distorted`: the sentence changes the meaning of the ledger claim or quote it relies on.
- `overstated`: the sentence widens the scope, drops a condition, or makes a number or certainty stronger than the claim or quote.
- `uses_refuted`: the sentence relies on a claim whose verdict is `REFUTED` or `UNVERIFIABLE`, or on a `PARTIAL` claim without the limitation from its note.

For each problem give the sentence verbatim, the kind, the related claim_ids (empty if none), and a concrete fix. Report every problem you find; do not stop at a few. In `summary`, give the number of factual sentences you checked and the number of problems.

Code blocks quoted from a source (YAML, commands) must match the cited source text in `sources/<source_id>.txt`; report a mismatch as `distorted`.

Only report problems you can point to in the files. Do not judge style or structure.
