---
name: create-slides
description: Create or continue an OfficeKit Slidev presentation in this conversation. Load the slidev, slidev-layouts, and slidev-themes skills before authoring. Use whenever the user wants a pitch deck, lecture, talk, seminar, workshop, demo, kickoff, internal review, slides, PDF export, or PowerPoint—even when they only paste notes, ask for a “deck,” or resume an existing presentation. Do not use for written documents, standalone HTML reports, video, or brand creation.
---

# Create Slides

Write the deck yourself, here. Do not delegate planning, authoring, review,
or export to a subagent — a fresh agent drops the conversation prefix and
wastes the KV cache. The only subagent you may spawn is `research-agent`,
and only when claims need checking.

## Fixed engine

Author and preview in Slidev. Export PDF or PPTX only when explicitly requested.

**Load these skills before writing a slide — do not guess:**

- `slidev` — syntax, frontmatter, anti-patterns, assets, export
- `slidev-layouts` — which built-in layout each slide uses (`cover`,
  `intro`, `section`, `two-cols`, `two-cols-header`, `fact`, `quote`,
  `statement`, `image-right`, `end`, and the rest). Name a layout in the
  plan for every slide and set `layout:` in that slide's frontmatter.
  Never invent a layout name.
- `slidev-themes` — how `theme`, `colorSchema`, and `themeConfig` work.
  Use `[presentation] theme` from `config.toml` (the scaffold is
  `default`). Do not install a community theme and do not set
  `themeConfig` colors or a `fonts:` block: `brands/<id>/tokens.css` already
  aliases `--slidev-theme-primary`, `--slidev-theme-background`, and the
  Slidev font tokens.

Deck styling comes from those generated brand outputs
(`brands/<id>/tokens.css`, with `brands/<id>/BRAND.md` for usage rules).
The project's brand is the one the user named, or `[brand] default`. Never
hardcode brand colors, fonts, or logo paths. Route any brand change to
`init-brand`.

## Icons

The presentation template already depends on `@iconify-json/lucide`.
Slidev turns collection names into Vue components:

```html
<lucide-eye class="ok-icon" />
```

Pick names from https://icon-sets.iconify.design/lucide/. Color and size
come from `.ok-icon` in `styles/brand.css` (`currentColor` →
`--ok-primary`). Do not hardcode a fill, do not add a second Iconify
collection unless the user names one, and do not ship a content slide
that is only a heading plus a bullet list with no mark.

## Resume from durable state

Resolve `projects/<slug>/`, then inspect `plan/PLAN.md`,
`reports/{research,build,review,delivery}.md`, and existing deck artifacts.
`PLAN.md` carries the brief and the slide sequence.

Resume at the first incomplete piece. Never recreate completed work. A
follow-up request is the revision: update the plan when purpose, audience,
outline, or runtime changes; otherwise edit the slides in place. If the
preview is not running, start it before you edit.

## The pass

The user should see a live deck within the first minute. Do not write a
finished plan, then scaffold, then start the server. Preview first.

1. If the project is not scaffolded, run
   `uv run python scripts/presentation/deck.py new <slug> --title "…" [--brand <id>]`.
   That copies `.templates/presentation/`, renders the Jinja (`*.j2`)
   files, and points `style.css` at `../../brands/<id>/tokens.css`.
   Install from the workspace root with `npm install -w projects/<slug>`
   — never create a per-project `node_modules`. Do not hand-copy the
   template or hand-edit brand paths.
2. Start the Slidev preview on `config.toml`'s `[preview] presentation_port`
   **immediately**, keep it running, and tell the user the URL
   (`http://localhost:<port>`). The scaffolded template is the first
   paint. Do not author blind. Do not wait for `PLAN.md` before this
   step.
3. Write a short `plan/PLAN.md` **while the preview is up** (purpose,
   audience, constraints, `brand: <id>`, the slide sequence with a
   `slidev-layouts` layout per slide, visual intent, accessibility notes,
   asset inventory, requested delivery, acceptance criteria). Ask only what
   would change the whole deck. Keep the plan shorter than the deck. No
   status field, no approval checklist. `research-agent` writes
   `reports/research.md` only when the deck turns on claims that need
   checking. Skip it otherwise.
4. Replace the template slides in `slides.md` (and `pages/`,
   `components/`, `layouts/`, `styles/` as needed) one logical group at a
   time. Slidev HMR is the review loop — the user watches the deck get
   built. Every slide declares a real `layout:` from `slidev-layouts`.
   Put a Lucide icon on every content slide that is a list, a card row, or
   a section opener. Leave no placeholder slides. Record checkpoints in
   `reports/build.md`.
5. Review the deck yourself against the plan: narrative, layouts, overflow,
   readability, accessibility, brand fidelity, icons, speaker flow,
   acceptance criteria. Write `reports/review.md` and fix what you find.
6. Export only when the user names a PDF and/or PPTX. Use
   `[presentation.export]` in `config.toml` (`with_clicks`, `dark`,
   `output_dir`). Record the paths in `reports/delivery.md`. A running
   preview or a leftover `dist/` file is not a delivery.

Preserve user assets: reference supplied images in place or copy them into
`public/`; never modify or overwrite an original.
