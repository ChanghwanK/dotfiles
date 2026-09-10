#!/usr/bin/env python3
"""
UserPromptSubmit hook: trailing "검토" trigger for the `review` skill.

When the user's prompt ends with the word "검토" (optionally followed by punctuation),
inject an instruction telling Claude to invoke the `review` skill before answering.
Description-based skill matching is probabilistic; this hook makes the trigger
deterministic, which is the whole point of a "put 검토 at the end" convention.

Invariants (same as detect-future-todo.py):
  - Exit code is always 0. Exit 2 would block the prompt, and a trigger bug must
    never block the user's input.
  - Only the trailing "검토" family triggers ("검토", "검토 해", "검토 한다", "검토해줘").
    "검토해서 고쳐줘" or "검토 결과 정리해줘" are ordinary requests and must not
    trigger; matching them would hijack normal work.
  - The hook cannot judge domain. The scope gate (engineering only, no resume or
    prose review) is stated in the hint and enforced by the skill's Step 0.
  - No output when there is no match (no-op).
"""
import json
import re
import sys

# Trailing "검토" family only: "검토", "검토 해", "검토해", "검토 한다", "검토한다",
# "검토 해줘", "검토해줘", "검토 하자", each optionally followed by closing punctuation.
# Anything after the verb ending ("검토해서 고쳐줘", "검토 결과 정리") does not match.
_TRAILING_REVIEW = re.compile(r"검토\s*(?:해줘|해\s?봐|한다|하자|해)?\s*[.!?。~]*\s*$")

# Cheap negative guard for targets the skill explicitly excludes (resume, prose,
# document wording). The skill's Step 0 scope gate remains the authority; this only
# avoids injecting the hint in the obvious cases. False negatives are recoverable
# with an explicit /review.
_OUT_OF_SCOPE = re.compile(
    r"이력서|경력\s?기술서|자소서|자기소개서|포트폴리오|맞춤법|띄어쓰기|문장\s?(교정|다듬|검토)|"
    r"글\s?(검토|다듬)|블로그\s?(글|포스트)|노션\s?(문서|페이지)|Notion\s?(문서|페이지)|"
    r"\bresume\b|\bCV\b|cover\s?letter",
    re.IGNORECASE,
)

_HINT = """[review-trigger] The user's prompt ends with an explicit "검토" trigger.
Scope gate first: the `review` skill verifies MECHANISM hypotheses (how or why a component behaves, what causes what) formed during troubleshooting or deep analysis, against primary sources for the installed version.
If the target is a state or capacity judgement with no mechanism in it (raise replicas?, how much memory?, is prod OK?), or a resume, prose, Notion wording, or blog post, do NOT invoke the skill; say so in one line and route (devops:infra-rca, cost-analyzer-agent, resume:bullet, notion-review, blog:review) or answer plainly.
If in scope: invoke the `review` skill via the Skill tool (skill: "review") BEFORE composing the answer and follow its workflow.
The review target is the text preceding the trigger, or the artifact currently under discussion if that text only points to it."""


def main():
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    prompt = data.get("prompt") or ""
    if not isinstance(prompt, str):
        return
    text = prompt.strip()
    if _TRAILING_REVIEW.search(text) and not _OUT_OF_SCOPE.search(text):
        print(_HINT)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
