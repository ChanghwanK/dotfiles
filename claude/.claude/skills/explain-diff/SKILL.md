---
name: explain-diff
description: |
  Generates a rich, interactive self-contained HTML explanation (background, intuition, code walkthrough, quiz) of a code change, diff, branch, or PR. Use when the user wants deeper understanding of a change and to keep cognitive debt in check while vibe-coding.
  Use when: (1) the user asks to explain a diff/branch/PR/commit, (2) the user wants to verify they actually understood a change they (or an AI) just made, (3) onboarding onto unfamiliar code via its recent history.
  Trigger keywords: "diff 설명해줘", "이 변경 설명해줘", "이 PR 설명해줘", "explain this diff/PR/branch/commit", "코드 이해 도와줘", "인지 부채", "/explain-diff".
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git diff *)
  - Bash(git log *)
  - Bash(git show *)
  - Bash(gh pr diff *)
  - Bash(gh pr view *)
  - Write
  - Artifact
---

# explain-diff

Turn a code change (diff / branch / PR / commit) into a rich, interactive HTML explainer, so the reader actually understands what changed and why, not just that it changed. Built for vibe-coding: when code arrives faster than understanding, this closes the gap and controls the resulting cognitive debt.

Source: adapted from [geoffreylitt's explain-diff-html gist](https://gist.github.com/geoffreylitt/a29df1b5f9865506e8952488eac3d524).

---

## Core principles

- **Understanding over summary.** The goal is not "what changed" (that's what `git diff` already shows) but "why it changed this way, and could the reader explain it back." Every section should raise the reader's ability to reason about the change, not just recall it.
- **Depth is earned, not assumed.** Don't assume the reader knows the surrounding system. Explore broadly before writing Background.
- **The quiz is the actual test of success.** If the reader can't answer the quiz from the explanation alone, the explanation failed — go back and fix it, don't just add more quiz hints.

---

## Step 1: Identify the change

Determine what's being explained from the user's request or conversation context:
- A working-tree diff (`git diff`, `git diff <base>...<head>`)
- A specific commit (`git show <sha>`)
- A branch vs its base (`git diff main...HEAD` or similar)
- A GitHub PR (`gh pr diff <number>`, `gh pr view <number>` for description/discussion)

If ambiguous, ask which one before proceeding.

## Step 2: Explore for context

Broadly explore the surrounding code the change touches — read the files before and understand the pre-existing system, not just the diff hunks. This is required for a real Background section; a shallow read produces a shallow (and often wrong) explanation.

## Step 3: Write the explanation

Produce one long-scrolling document with a table of contents and these sections, in order:

1. **Background** — explain the existing system relevant to this change. Include a deep background for beginners (markable as skippable for readers who already know it), then a narrower background directly relevant to the change itself.
2. **Intuition** — the core idea behind the change. Focus on the essence, not exhaustive detail. Use concrete examples with toy data. Use diagrams liberally.
3. **Code** — a high-level walkthrough of the actual changes, grouped/ordered in a way that builds understanding (not necessarily file order).
4. **Quiz** — five interactive multiple-choice questions, medium difficulty (require actually understanding the substance of the change to answer, not gotchas or trivia). Each option click reveals correct/incorrect with a short explanation of why.

Writing style: clear, engaging, classic technical-writing style (think Martin Kleppmann) — smooth transitions between sections, no dry changelog tone.

### Diagram guidance

- Pick a small, reusable set of diagram families and reuse them across cases rather than inventing a new visual language per section. Useful families:
  - A simplified mock of the actual UI the user sees, for UI-facing changes.
  - A system/data-flow diagram between components, with concrete example data flowing through it.
- No ASCII diagrams. Build diagrams as plain HTML/CSS (divs, lists, simple flexbox layouts), not images or ASCII art.
- Code blocks: MUST use `<pre>` tags. If a custom-styled block is used instead, it MUST set `white-space: pre-wrap` (or `pre`) or the browser will collapse all newlines to one line. Before finalizing, scan every code block in the generated HTML and confirm this.
- Use callouts for key concepts, definitions, and important edge cases.

## Step 4: Deliver the output

This environment has two viable delivery mechanisms — pick based on context, don't drop the constraints above regardless of which you use:

- **Artifact (preferred for interactive quiz)**: publish the HTML via the `Artifact` tool. This renders inline with light/dark theme support. Note the strict CSP: no external CDN scripts/fonts/images — everything (CSS, JS, any diagram assets) must be inlined in the single file. Load the `artifact-design` skill first per its own trigger rule.
- **Local dated file**: if the user wants an offline/portable artifact instead, write a single self-contained HTML file (inline CSS + JS, no external deps) to the scratchpad directory (or another location the user specifies), named `YYYY-MM-DD-explanation-<slug>.html` using today's date — keeps files time-sorted and out of version control.

Either way the file must remain self-contained: inline CSS/JS, no external requests, responsive enough to read on a phone.

---

## Notes

- If the diff is large (many unrelated files), consider asking the user to scope it (a subset of files, or a specific logical change) rather than producing a shallow explanation of everything.
- If quiz answers end up guessable without reading the explanation, tighten the distractors — plausible wrong answers force real understanding.
