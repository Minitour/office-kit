---
name: init-brand
description: Route creation, migration, or revision of the OfficeKit brand system. Use whenever the user wants to initialize branding, change colors or typography, adopt logos, edit design tokens, refresh brand guidelines, or make documents, slides, and videos share one identity—even if they never say init-brand and only mention tokens.css, BRAND.md, or “make these look consistent.” Do not use for producing a document, deck, or video.
---

# Initialize Brand

Act only as the orchestration router. Do not inspect assets creatively, propose
identity directions, write brand files, review visuals, or package outputs in
primary context. Delegate brand work and relay only approval or user-input
gates and stage status, including preview, review, and delivery status.

## Brand contract

`brand/brand.json` is the canonical machine-readable source of truth.
`brand/BRAND.md`, `brand/tokens.css`, and `brand/frame.md` are generated from it
by `scripts/brand/generate.py` and must not become independent sources. Preserve
supplied assets byte-for-byte under `brand/assets/`; never edit or overwrite
originals. Record provenance and derived variants separately.

## Resume from durable state

Brand state is workspace-level, so inspect `brand/brand.json`, the generated
files, and `brand/assets/` first. A `projects/<slug>/` directory matters only
when the brand work is scoped to a specific deliverable; in that case also read
its `BRIEF.md`, `plan/PLAN.md`, and reports.

Resume at the first incomplete stage. If `brand/brand.json` is absent, this is a
first-time initialization. If the generated files disagree with
`brand/brand.json`, treat them as stale and delegate regeneration. Never infer
approval from existing brand files.

## Stage routing

Brand-only initialization or revision needs just three stages — `brand-agent`
owns every change to the canonical and generated brand files:

1. `brand-agent` inventories the user's goals, existing identity, constraints,
   and supplied assets, proposes an identity direction, and **waits for explicit
   user approval** before writing anything. Relay that proposal and the
   approval.
2. After approval, `brand-agent` preserves assets, writes `brand/brand.json`,
   regenerates `brand/BRAND.md`, `brand/tokens.css`, and `brand/frame.md`, and
   shows incremental visual previews. Relay preview status.
3. `review-agent` checks canonical/generated parity, contrast, typography, asset
   provenance, and cross-media usability. Route fixes to `brand-agent`, then
   re-review.

Add stages only when the situation calls for them:

- `intake-agent` — when the request is ambiguous, spans multiple deliverables,
  or workspace state is contradictory and needs reconciliation into `BRIEF.md`.
- `research-agent` — when the identity direction depends on evidence (audience,
  competitive, or accessibility research) rather than user-supplied direction.
- `plan-agent` — only to sync an existing project's `plan/PLAN.md` after the
  brand changes. A brand-only initialization needs no `PLAN.md`, and brand work
  is never gated on plan approval.
- `delivery-agent` — only when the user asks for a packaged brand handoff.

Keep all production work inside the assigned subagent.
