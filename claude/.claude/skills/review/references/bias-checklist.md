# Bias Checklist for `review`

Banned openings, the self-check that gates output, and the pushback protocol.

---

## Banned openings

Do not begin the report, or any claim's verdict, with:

- "맞습니다", "정확히 보셨습니다", "좋은 지적입니다", "훌륭한 접근입니다", "말씀하신 대로"
- "You're right", "Great point", "Exactly", "As you said"
- Any sentence that states agreement before the evidence has been shown

Also banned as a compromise move: restating the same verdict with softer adjectives ("대체로 맞지만", "거의 지지됨"). Verdicts are discrete.

---

## Self-check before output (MUST)

Walk every item. A failed item is fixed by collecting evidence or removing the claim, never by rewording.

1. Did I search for counter-evidence for every claim before searching for support? Is that search recorded (query or path) even when it found nothing?
2. Did I write my own preliminary verdict before reading the blind evaluator's output?
3. Does the blind evaluator's prompt contain any of: the user's original wording, the stance, authorship, "the user thinks / wants"? If yes, the result is contaminated; rerun.
4. Does every verdict have at least one `[n]`? Does every `[n]` resolve to a fetched URL or a read path?
5. Is any `SUPPORTED` / `REFUTED` resting on T3 only? Downgrade to `UNDETERMINED`.
6. Is any premise `P` unverified while the claims that depend on it are `SUPPORTED`?
7. Is there a negative conclusion ("no impact", "not a problem", "safe") without the query or measurement that produced it?
8. Is any TX item generalized beyond its conditions, or counted in tool units instead of affected units?
9. Does every claim, including `SUPPORTED` ones, carry a strongest counterargument and a "what would change this"?
10. Does every proposal have a link?
11. Does the report open with a banned phrase?
12. If the blind evaluator disagreed with my preliminary verdict, is the disagreement reported as its own section rather than averaged away?
13. Would the verdict be the same if the user had stated the opposite stance with the same evidence? If not, name what the stance changed.
14. Is every M citation for the version anchor `A1`, or accompanied by an explicit version delta from the changelog?
15. Did I list at least one alternative mechanism for each inference, and is each alternative ruled out by evidence rather than by not having looked?

---

## Pushback protocol

Applies after the report when the user disagrees.

1. Identify the disputed claim and evidence item. Ask if unclear; do not guess at what they object to.
2. Re-run evidence collection for that claim only. New evidence: a fetched page, a read path, a measurement, a version fact. Not new evidence: the user's restated conviction, tone, or seniority.
3. Outcome is one of:
   - `판정 변경: C2 PARTIAL → SUPPORTED, 근거 [7]` with the new item listed in References
   - `판정 유지: C2 PARTIAL. 새 근거 없음. 반박은 [3]의 해석 문제이며 [3]은 ...` with the specific reason
4. A verdict flipped without a new `[n]` is a self-check failure. Report it as such if it happened.
