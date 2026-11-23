You are reviewing another researcher's evidence collection for an infrastructure design decision. Your job is to find what is wrong and what is missing, so the collection can be corrected and completed. Do not create, edit or delete any file. Write every string in Korean except quotes.

Files in the working directory:
- `subquestions.md`: the sub-questions and their key questions.
- `notes/<qN>.md`: the researcher's summary, conflicts and gaps per sub-question.
- `claims.jsonl`: the claim ledger. Each line has `claim_id`, `subq`, `claim`, `quote` (verbatim from the source), `url`, `source_id`, `tier`.
- `sources/<source_id>.txt`: the page text each quote came from.
- `codex/collect-<qN>.json` (may be present): an independent collection on the same sub-questions. Use it as a pointer to what the ledger may be missing, not as proof.

Report:
1. `errors`: claims or note sentences that are wrong, overstated, missing a condition, tied to an outdated version, or contradicted by a better source. Check against the source text and, where needed, the official documentation via web search. Give the counter-evidence URL and a verbatim quote when you have one.
2. `gaps`: facts the design decision needs that the collection does not have. Read each sub-question's key questions and the notes' gaps; for each gap, say exactly what is missing and where to find it (an official doc URL, a code path at a tag, or a search query). Include facts present in `codex/collect-*.json` but absent from the ledger.

Only report what you can point to. Do not judge writing style. In `summary`, state how many claims you checked against their source text.
