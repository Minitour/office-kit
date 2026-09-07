---
name: create-slides
description: Route creation or continuation of an OfficeKit Slidev presentation. Use whenever the user wants a pitch deck, lecture, talk, seminar, workshop, demo, kickoff, internal review, slides, PDF export, or PowerPoint—even when they only paste notes, ask for a “deck,” or resume an existing presentation. Do not use for written documents, standalone HTML reports, video, or brand creation.
---

# Create Slides

Act only as the orchestration router. Do not research, outline, write Slidev,
design slides, review, or export in primary context. Delegate work and relay
only approval or user-input gates and stage status, including preview, review,
and delivery status.

## Fixed engine

Author and preview in Slidev. Export PDF or PPTX only when explicitly requested.
Deck styling comes from the generated brand outputs (`brand/tokens.css`, with
`brand/BRAND.md` for usage rules); route any brand change to `init-brand`.

## Resume from durable state

Resolve `projects/<slug>/`, then inspect `plan/PLAN.md`,
`reports/{research,build,review,delivery}.md`, and existing deck artifacts.
`PLAN.md` carries the brief and must declare `status: draft` or
`status: approved`.

Resume at the first incomplete stage. Send new, ambiguous, stale, or
contradictory state to `plan-agent`. Never recreate completed work or infer
approval from chat history, a running preview, or an existing deck.

## Stage routing

1. `plan-agent` does intake and planning in one stage: it confirms purpose,
   audience, venue, duration, aspect ratio, delivery request, and assets, then
   writes `plan/PLAN.md` with `status: draft`, the narrative arc, slide
   sequence, visual intent, accessibility, and acceptance criteria. It asks
   only what changes the plan and defaults the rest from `config.toml`.
2. `research-agent` verifies content and sources and writes
   `reports/research.md` — only when the deck turns on claims that need
   checking. Skip it otherwise.
3. Relay the plan and wait for explicit approval. Have `plan-agent` change the
   status to `approved`; no deck implementation may begin while it is `draft`.
4. `slides-agent` implements the approved plan in Slidev, wires in the generated
   brand outputs, starts or updates the live preview early, builds in logical
   slide groups, and records checkpoints in `reports/build.md`. Relay each
   meaningful preview checkpoint.
5. `review-agent` checks narrative, factual accuracy, layouts, overflow,
   readability, accessibility, brand fidelity, speaker flow, and acceptance
   criteria; it writes `reports/review.md`. Route fixes to `slides-agent`, then
   re-review.
6. Only when requested, `delivery-agent` exports exactly the requested PDF
   and/or PPTX outputs, verifies them, and writes `reports/delivery.md`.

A deck is staged because its build is long and its export is expensive to redo
— not so every stage can be run for its own sake. Skip research when there is
nothing to verify, and keep the plan shorter than the deck.

Preserve user assets. Keep all production work inside the assigned subagent.
