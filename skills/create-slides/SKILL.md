---
name: create-slides
description: >
  Launch the OfficeKit presentation authoring workflow — the /create-slides command. Use whenever
  the user wants to create, build, or design a slide deck or presentation: a pitch deck, lecture,
  talk, seminar, kickoff, internal review, or anything destined for interactive HTML slides, PDF,
  or PowerPoint (.pptx) — even if they never say "Slidev" or "/create-slides". This skill drives the
  flow from concept to an exported deck and pulls in the deeper skills for the details. Reach for it
  the moment slides (not a written document) are the goal.
---

# Create a Presentation (`/create-slides`)

This is the entry point for authoring a **slide deck** in OfficeKit. The engine is **Slidev** (Markdown → interactive HTML slides, exportable to PDF/PPTX). For a written document, use `create-docs` instead.

You are a collaborative authoring partner: build top-down (purpose and narrative before slide content), keep the user in the loop at each gate, and never generate the whole deck in one shot.

## Skills to load as you go

Read these when you reach the relevant step — don't front-load everything:

- **slidev** — Slidev syntax: frontmatter, layouts, animations, code highlighting, diagrams, export. Load before writing slides.
- **brand-yml** — `_brand.yml` format, needed to map brand values into the deck (Slidev does not read `_brand.yml` natively).

## Workflow

### 1. Load configuration
Read `_brand.yml` (brand identity) and `config.toml` (operational defaults: theme, aspect ratio, canvas width, export format, preview port). These are the defaults for everything below unless the user overrides them.

### 2. Concept
Confirm it's a presentation (not a document). Gather topic, audience, purpose, target export format, and aspect ratio — presenting the `config.toml` defaults so the user only has to change what they want. Produce a 2–5 sentence brief and confirm it.

### 3. Outline
Draft a slide-by-slide outline (slide titles + key talking points) and note visual elements per slide (images, charts, code, diagrams) and any transitions/animations. Present it for feedback.

### 4. Plan + approval (gate)
Write `projects/<name>/plan/PLAN.md` capturing the brief, effective configuration (resolved brand + config values plus any overrides), the slide breakdown, visual/style notes, and an asset inventory. Present it and **wait for explicit approval** before authoring.

### 5. Scaffold, brand-map, and start preview

Copy the template, create the plan folder, and install workspace deps from the root:

```bash
cp -r .templates/presentation projects/<name>
mkdir -p projects/<name>/plan
npm install                  # from the workspace root — never inside the project
```

Slidev does not consume `_brand.yml` directly, so map brand values into the deck:

| `_brand.yml` field | Slidev target |
|---|---|
| `color.primary` | `--slidev-theme-primary` (in `styles/brand.css`) |
| `color.background` | `--slidev-theme-background` |
| `color.foreground` | body text color |
| `typography.base.family` | `--slidev-font-sans` + headmatter `fonts.sans` |
| `typography.monospace.family` | `--slidev-font-mono` + headmatter `fonts.mono` |
| `logo.medium` (or `small`) | `<img>` in `global-bottom.vue` |

The template already wires `styles/brand.css` and `global-bottom.vue`; update them to match the current `_brand.yml`.

**Start the live preview immediately, BEFORE writing any slides:**

```bash
cd projects/<name>
npx slidev --port 3030       # port from config.toml [preview].presentation_port
```

Keep this running for the entire session. The user must see live progress in the browser from this point forward.

### 6. Author incrementally

Write slides in `slides.md`, one logical group at a time. The live preview auto-reloads — verify brand colors/fonts and the footer logo in the browser after each group.

Confirm with the user after each slide group before continuing. Do NOT export to PDF/PPTX during this step.

### 7. Export (only when asked)

**Do not export unless the user explicitly asks for final output files.** Ask which format(s) they want; only export those.

```bash
cd projects/<name>
npx slidev export --output dist/slides.pdf                 # PDF
npx slidev export --format pptx --output dist/slides.pptx  # PowerPoint
```

Deliver the output file paths.

## Guardrails

- `_brand.yml` is the single source of truth for brand — map it into the deck; never invent colors/fonts. Re-run the mapping when `_brand.yml` changes.
- Always scaffold from `.templates/presentation` — never build a deck from scratch.
- Use the shared root `node_modules` (npm workspaces) — never run `npm install` inside a project; add deps with `npm install <pkg> -w projects/<name>` from the root.
- Start the live preview before writing any slides. Never skip the preview step.
- Don't export to PDF/PPTX unless the user explicitly asks. The live preview is for iterating; export is for final delivery.
- Don't author slides before the plan is explicitly approved.
- Preserve user-provided assets; reference them in place rather than modifying them.
