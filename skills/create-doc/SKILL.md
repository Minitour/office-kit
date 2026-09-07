---
name: create-doc
description: Route creation or continuation of a written OfficeKit deliverable as a standalone HTML document. Use for reports, proposals, memos, briefs, articles, letters, whitepapers, and web documents—even when the user only says “write this,” provides source material, or asks to resume an existing document project. Do not use for slides, video, or brand creation.
---

# Create Document

Act only as the orchestration router. Do not research, outline, author HTML/CSS,
review, or export in primary context. Delegate work and relay only approval or
user-input gates and stage status, including preview, review, and delivery
status.

## Fixed output

Documents are self-contained, standalone HTML — one file with local styles,
scripts, brand tokens, and assets inlined by
`scripts/document/package.py`. There is no other document engine and no
paged-output pipeline; if the user wants a paged or office-suite file, say that
HTML is the supported deliverable and let them decide.

Styling comes from the generated brand outputs (`brand/tokens.css`, with
`brand/BRAND.md` for usage rules). Never hand-pick colors or fonts, and route
any brand change to `init-brand` rather than editing tokens inside the document.

## Resume from durable state

Resolve `projects/<slug>/`, then inspect:

- `BRIEF.md`
- `plan/PLAN.md` with `status: draft` or `status: approved`
- `reports/research.md`, `reports/build.md`, `reports/review.md`, and
  `reports/delivery.md`
- existing source, preview, and delivered artifacts

Resume at the first incomplete stage. If the project is new, ambiguous, stale,
or internally inconsistent, send it to `intake-agent`. Never recreate completed
work or infer approval from chat history or existing files.

## Stage routing

1. `intake-agent` confirms project identity, purpose, audience, constraints,
   requested delivery, assets, and missing decisions; it writes `BRIEF.md`.
2. `research-agent` gathers and verifies needed sources and writes
   `reports/research.md`.
3. `plan-agent` writes or revises `plan/PLAN.md` with `status: draft`,
   content structure, evidence, visuals, accessibility, and acceptance criteria.
4. Relay the plan and wait for explicit user approval. Have `plan-agent`
   record that approval as `status: approved`; no implementation may start
   while status is `draft`.
5. `doc-agent` builds the standalone HTML incrementally against the generated
   brand outputs, starts or updates a browser preview early, and records
   checkpoints in `reports/build.md`. Relay preview status after meaningful
   sections.
6. `review-agent` checks content, sources, responsiveness, accessibility, brand
   fidelity, links, and acceptance criteria; it writes `reports/review.md`.
   Route required fixes back to `doc-agent`, then re-review.
7. Only when the user asks for delivery, `delivery-agent` packages exactly the
   requested HTML deliverable, verifies it, and writes `reports/delivery.md`.

Preserve user assets. Keep all production work inside the assigned subagent.
