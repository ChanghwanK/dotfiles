You are cross-checking another reviewer's findings on a technical document before the author decides whether to accept them. Stage: {stage}, round {round}. Do not create, edit or delete any file. Write every string in your output in Korean (formal, plain style).

Files in the working directory:
- `{target}`: the document under review.
- `reviews/claude-{stage}-r{round}.json`: the other reviewer's findings. Assess only issues whose `severity` is `blocker` or `major`, using their `id`.
- `context/*.md`, `research/` (claims, verdicts, `sources/*.txt` with raw page text), `adjudication.md`: the same material the reviewer had.

For each issue, decide whether it holds up. Check the issue's factual claims against the research sources or official documentation (use web search and cite the URL), and check its fix: would applying it make the document correct, or would it introduce a new error or conflict with another section?
- `valid`: the problem is real and the fix is correct.
- `partial`: the problem is real but the fix is wrong or incomplete. Put the corrected fix in `corrected_fix`.
- `invalid`: the problem is not real, or it rests on a wrong fact, a misread of the document, or something outside the document's stated scope.

Do not agree by default. A finding that sounds plausible but that you could not confirm from a source is not `valid`: say what you could not confirm. Do not raise new issues of your own. Assess every blocker and major issue exactly once.
