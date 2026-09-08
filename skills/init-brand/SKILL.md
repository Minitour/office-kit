---
name: init-brand
description: Route creation, migration, or revision of the OfficeKit brand system. Use whenever the user wants to initialize branding, change colors or typography, adopt logos, edit design tokens, refresh brand guidelines, add a second identity, or make documents, slides, and videos share one identity—even if they never say init-brand and only mention tokens.css, BRAND.md, or “make these look consistent.” Do not use for producing a document, deck, or video.
---

# Initialize Brand

Act only as the orchestration router for identity. Delegate brand writes to
`brand-agent` and relay the proposal gate. Do not write brand files in
primary context. The only other subagent is `research-agent`.

## Brand contract

The workspace holds one directory per identity: `brands/<id>/`.
`brands/<id>/brand.json` is the canonical machine-readable source of truth
for that identity. `brands/<id>/BRAND.md`, `brands/<id>/tokens.css`, and
`brands/<id>/frame.md` are generated from it by
`scripts/brand/generate.py` and must not become independent sources. Preserve
supplied assets byte-for-byte under `brands/<id>/assets/`; never edit or
overwrite originals. Record provenance and derived variants separately.

`config.toml` `[brand] default` names the identity used when a project does
not pick one. Brand ids are lowercase letters, digits, and hyphens.

## Resume from durable state

Inspect `brands/`, `config.toml` `[brand]`, and each identity's generated
files and `assets/` first. A `projects/<slug>/` directory matters only when
the brand work is scoped to a specific deliverable; in that case also read
its `plan/PLAN.md` and reports, or its `NOTES.md` for a document, and note
which brand id that project already uses.

- No `brands/*/brand.json` → first-time initialization. Pick an id (often
  a product slug) before proposing the identity.
- User wants another company, client, or product look → a **new**
  `brands/<id>/`. Do not overwrite an existing identity.
- Generated files disagree with that id's `brand.json` → stale
  derivatives; delegate regeneration for that id.
- User wants to change which identity is the fallback → update
  `[brand] default` after approval. Never infer approval from existing files.

## Stage routing

1. `research-agent` — only when the identity direction depends on evidence
   (audience, competitive, or accessibility research) rather than
   user-supplied direction. Skip it otherwise.
2. `brand-agent` inventories the user's goals, existing identities,
   constraints, and supplied assets, proposes an identity direction
   (including the brand id), and **waits for explicit user approval**
   before writing anything. Relay that proposal and the approval.
3. After approval, `brand-agent` preserves assets, writes
   `brands/<id>/brand.json`, and regenerates `BRAND.md`, `tokens.css`, and
   `frame.md` with `uv run python scripts/brand/generate.py <id>`. It may
   write only the `[brand]` table in `config.toml` when the default id
   changes. It then propagates the change to the consumers that hold
   generated copies: existing standalone documents via
   `uv run python scripts/document/doc.py refresh --all`, and any video
   project's `brand/` snapshot that was taken from this identity. Relay
   what it touched.
4. Check canonical/generated parity, contrast, typography, asset provenance,
   and cross-media usability here. Route fixes back to `brand-agent`.

A brand-only initialization needs no `PLAN.md`. If a deck or video project is
in scope, update its `plan/PLAN.md` here after the brand lands (including the
`brand:` id). Brand work is never gated on a plan.

Keep brand file writes inside `brand-agent`.
