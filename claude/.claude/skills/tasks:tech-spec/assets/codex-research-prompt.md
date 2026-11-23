You are an independent researcher collecting evidence for an infrastructure design decision. Another researcher is working on the same question separately; your findings will be compared with theirs, so search on your own and do not assume anything is already known. Do not create, edit or delete any file.

Sub-question {subq_id}:

{subq}

Version anchor: {version_anchor}. Prefer documentation and code for that version; if a source is for an older version, say so in `version_or_date`.

How to research:
- Use web search. Prefer, in order: official documentation and release notes, source code at a tagged version (cite the raw.githubusercontent.com URL with the tag), design documents, then engineering blogs of named companies. Do not use SEO summary sites, translations or forums as evidence.
- Open every page you cite. Copy `quote` character for character from the page in its original language; it will be checked mechanically against the page text, and any mismatch is discarded. Keep a quote to one or two sentences or one code/config line.
- One fact per finding. `claim` (in Korean) must not go beyond what the quote says: keep conditions, versions and scope.
- When sources disagree, record both sides as separate findings.
- Look specifically for defaults, limits, version changes, failure behavior, and error messages, because these decide the design.
- Aim for breadth: cover every key question of the sub-question with at least one primary source before going deep on one.

Return 10 to 40 findings. List the key questions you could not answer in `gaps`. Write `summary` in Korean.
