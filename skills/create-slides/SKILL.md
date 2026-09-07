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

Resolve `projects/<slug>/`, then inspect `BRIEF.md`, `plan/PLAN.md`,
`reports/{research,build,review,delivery}.md`, and existing deck artifacts.
`PLAN.md` must declare `status: draft` or `status: approved`.

Resume at the first incomplete stage. Send new, ambiguous, stale, or
contradictory state to `intake-agent`. Never recreate completed work or infer
approval from chat history, a running preview, or an existing deck.

## Stage routing

1. `intake-agent` confirms purpose, audience, venue, duration, aspect ratio,
   delivery request, assets, and project state; it writes `BRIEF.md`.
2. `research-agent` verifies content and sources and writes
   `reports/research.md`.
3. `plan-agent` writes or revises `plan/PLAN.md` with `status: draft`, the
   narrative arc, slide sequence, visual intent, accessibility, and acceptance
   criteria.
4. Relay the plan and wait for explicit approval. Have `plan-agent` change
   the status to `approved`; no deck implementation may begin while it is
   `draft`.
5. `slides-agent` implements the approved plan in Slidev, wires in the generated
   brand outputs, starts or updates the live preview early, builds in logical
   slide groups, and records checkpoints in `reports/build.md`. Relay each
   meaningful preview checkpoint.
6. `review-agent` checks narrative, factual accuracy, layouts, overflow,
   readability, accessibility, brand fidelity, speaker flow, and acceptance
   criteria; it writes `reports/review.md`. Route fixes to `slides-agent`, then
   re-review.
7. Only when requested, `delivery-agent` exports exactly the requested Slidev,
   PDF, and/or PPTX outputs, verifies them, and writes `reports/delivery.md`.

Preserve user assets. Keep all production work inside the assigned subagent.
