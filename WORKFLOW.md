# Document & Presentation Authoring — Agent Guidance

These are your instructions when creating and iterating on documents and presentations. You act as a collaborative authoring partner: you do not generate an entire deliverable in one shot, you always work top-down (purpose and structure first, then content), and you keep the user in the loop at key decision points.

---

## Guiding Principles

- **Single brand, zero duplication**: `_brand.yml` at the workspace root is the sole source of brand identity (colors, fonts, logos). Never duplicate brand values into `config.toml` or hardcode them in project files. For Quarto, the project `_quarto.yml` must explicitly reference it via `brand: ../../_brand.yml` (the template already does this). For Slidev, map the same values into the deck's headmatter or theme config.
- **Configuration-first**: Read both `_brand.yml` and `config.toml` at the start of every workflow. `config.toml` provides operational defaults — output formats, page size, slide aspect ratio, preview ports, and template names. Use these values as defaults unless the user overrides them.
- **Iterative and incremental**: Propose an outline, get the user's review, and implement only after approval. Show previews early and often.
- **Top-down construction**: Establish purpose, audience, and structure before writing content or building slides.
- **Skill-driven development**: Always load the relevant skill before writing engine-specific code. Read the **quarto-authoring** skill for Quarto syntax and features, and the **officekit-documents** skill for OfficeKit project conventions (scaffolding, brand-to-Word pipeline, config.toml usage). Read the **slidev** skill before authoring Slidev decks. Read the **brand-yml** skill when creating or modifying `_brand.yml`.
- **Template-first scaffolding**: Every new project starts by copying from `.templates/`. Never scaffold from scratch when a template exists. The templates already wire up `_brand.yml`, output formats, and baseline structure.
- **Shared workspace environments**: All projects share a single root `node_modules` managed by npm workspaces (declared in the root `package.json`). Never create per-project `node_modules` or run `npm install` from inside a project directory. Add project-specific deps via `npm install -w projects/<name>` from the workspace root.
- **Project isolation** (source): Each deliverable lives in its own directory under `projects/`. Projects are independent — never share content across project boundaries.
- **Plan approval before implementation**: Write the project plan and present it in conversation. Do **not** proceed to content authoring until the user has **explicitly approved** the plan.
- **Preview before polish**: Get content and structure working in the browser before fine-tuning styles, transitions, or layout details.
- **Preserve user assets**: Never modify or overwrite user-provided assets (images, logos, data files). Copy or reference them in place.

---

## Engine Selection

| Deliverable | Engine | How it works |
|---|---|---|
| Text document (report, article, memo, letter, proposal) | **Quarto** | Markdown → HTML, PDF (via Typst), and/or Word .docx |
| Presentation (slide deck, pitch, lecture) | **Slidev** | Markdown → interactive HTML slides, exportable to PDF/PPTX |

When the user's intent is ambiguous, ask which format they need. A single project is always one engine — never mix Quarto and Slidev in the same project directory.

---

## Branding — How `_brand.yml` flows

### Quarto documents

Quarto does **NOT** auto-discover `_brand.yml` from parent directories for projects nested under `projects/`. Every project's `_quarto.yml` must explicitly reference the brand file with `brand: ../../_brand.yml`. The default template already includes this — do not remove it. Brand colors, fonts, and logo are then applied to HTML and Typst-PDF output automatically. For Word `.docx`, brand colors and fonts are applied through a reference document (see the officekit-documents skill for details).

### Slidev presentations

Slidev does not consume `_brand.yml` natively. The agent reads `_brand.yml` at project creation and maps brand values into:

1. **Headmatter** in `slides.md` — `themeConfig` section carries brand colors as CSS custom properties.
2. **`styles/brand.css`** — generated CSS that sets `--slidev-theme-primary`, `--slidev-theme-background`, font stacks, etc.
3. **`global-bottom.vue`** — renders the brand logo in the slide footer (if a logo path is configured).

Whenever `_brand.yml` is updated, re-run the brand mapping for any existing Slidev project that needs to stay in sync. Quarto document projects pick up changes on the next render (the `brand:` reference in `_quarto.yml` always points to the root file).

---

## Global Configuration (`config.toml`)

`config.toml` stores operational defaults only — no brand fields.

| Section | Controls |
|---|---|
| `[document]` | Output formats (html/pdf/docx), template name |
| `[document.page]` | Paper size, margins |
| `[document.output]` | TOC, section numbering |
| `[presentation]` | Template name, Slidev theme, aspect ratio, canvas width |
| `[presentation.export]` | Export format (pdf/pptx/png), click animations, dark mode |
| `[preview]` | Ports for `quarto preview` and `slidev` dev server |
| `[style]` | Watermark toggle |

### Per-project overrides

A project's plan document is the authoritative source for that project's settings. When the user specifies values that differ from `config.toml`, record them in the plan and use the plan values. The config file is never modified per-project.

---

## Project Directory Structure

All projects live under `projects/` at the workspace root.

### Quarto document project

```
projects/<name>/
├── plan/
│   └── PLAN.md               # Outline and plan (Step 3 output)
├── _quarto.yml                # Quarto project config (inherits _brand.yml from root)
├── index.qmd                  # Main document (or multiple .qmd files)
├── references.bib             # Bibliography (if needed)
├── assets/                    # Images, data files
└── _output/                   # Rendered output (gitignored)
```

### Slidev presentation project

```
projects/<name>/
├── plan/
│   └── PLAN.md               # Outline and plan (Step 3 output)
├── slides.md                  # Main slide deck
├── pages/                     # Additional slide pages (if split)
├── components/                # Custom Vue components
├── layouts/                   # Custom layouts
├── styles/
│   └── brand.css              # Brand-mapped CSS variables
├── public/                    # Static assets (images, logos)
├── global-bottom.vue          # Footer with logo
├── package.json               # Slidev deps (hoisted to root node_modules)
└── dist/                      # Exported output (gitignored)
```

---

## Templates (`.templates/`)

Default templates ship with OfficeKit under `.templates/`. Each template is a ready-to-copy directory that the agent uses as the starting point for every new project.

| Template | Path | Engine |
|---|---|---|
| Default document | `.templates/document/` | Quarto |
| Default presentation | `.templates/presentation/` | Slidev |

Users can create additional templates by adding directories under `.templates/`. The `config.toml` fields `document.template` and `presentation.template` specify which template to use by default.

When scaffolding a new project, the agent:
1. Copies the template directory into `projects/<name>/`.
2. Creates `projects/<name>/plan/PLAN.md`.
3. Applies any per-project overrides from the plan.

---

## Development Workflow

Follow these steps when creating a project. Skip steps that do not apply, but never skip planning (Steps 1–3) or user approval (Step 4).

### Step 0 — Load Configuration

Read `_brand.yml` and `config.toml` before anything else. These inform every decision downstream.

### Step 1 — Concept Definition

Help the user clarify what they want to create. Present the configured defaults so the user knows what they're starting with.

**Gather:**
- **Type** — Document or presentation?
- **Topic and purpose** — What is this about? Who is the audience?
- **Target formats** — Which output formats? Default from config.
- **Page size / aspect ratio** — Default from config.
- **Template** — Use the default or a custom template from `.templates/`?
- **Style preferences** — Anything beyond the brand defaults?
- **Assets provided** — Does the user have images, data, or content to incorporate?

**Output:** A concise project brief (2–5 sentences) that captures the above, noting any deviations from defaults. Confirm with the user before proceeding.

### Step 2 — Outline and Structure

Develop the content structure:

**For documents:**
1. Draft a **section outline** — title, section headings, key points per section.
2. Identify **tables, figures, or diagrams** that should appear.
3. Note **citations or data sources** if applicable.

**For presentations:**
1. Draft a **slide outline** — slide titles and key talking points.
2. Identify **visual elements** per slide (images, charts, code blocks, diagrams).
3. Plan **transitions and animations** if applicable.

Present this to the user for feedback before proceeding.

### Step 3 — Project Plan

Formalize the outline into a structured plan. Write it to `projects/<name>/plan/PLAN.md` and present it in conversation.

**The plan document must include:**

1. **Project Brief** — Type, topic, audience, target formats.
2. **Effective Configuration** — Resolved values: brand colors/fonts from `_brand.yml`, operational settings from `config.toml`, plus any per-project overrides. This is the single source of truth for the project.
3. **Content Outline** — For documents: section breakdown with descriptions. For presentations: slide-by-slide breakdown.
4. **Visual Style Notes** — Brand application, any custom styling, layout preferences.
5. **Asset Inventory** — Images, logos, data files, fonts. Mark each as "provided", "to create", or "to source".
6. **Open Questions** — Anything needing user clarification.

Close with a **"What I need from you"** checklist.

### Step 4 — User Approval

**Wait for explicit approval.** Support revisions, partial approval, and blanket approval. Update the plan file in place when revising.

### Step 5 — Project Initialization

**5a. Verify tools:**

```bash
quarto --version      # Quarto (documents)
node -v               # Node.js (presentations)
npm -v                # npm (presentations)
```

Stop and resolve if anything is missing.

**5b. Scaffold from template:**

Copy the appropriate template from `.templates/` into `projects/<name>/`:

```bash
# Document
cp -r .templates/document projects/<name>

# Presentation
cp -r .templates/presentation projects/<name>
```

Create `projects/<name>/plan/` and move `PLAN.md` there if not already present.

**5c. Start live preview immediately:**

Start the preview server right after scaffolding, BEFORE writing any content. Keep it running throughout the session so the user sees every change live in the browser.

```bash
# Document
cd projects/<name>
quarto preview --port 4200

# Presentation
cd projects/<name>
npx slidev --port 3030
```

The user must have a live browser preview open from this point forward. Do not skip this step.

**5d. For Slidev presentations — wire up npm workspace:**

Ensure the root `package.json` has `"workspaces"` that covers `"projects/*"`. Then:

```bash
npm install            # from workspace root — hoists deps
```

**5d. Apply brand mapping (presentations only):**

Read `_brand.yml` and generate `styles/brand.css` and `global-bottom.vue` in the project. Map:

| `_brand.yml` field | Slidev target |
|---|---|
| `color.primary` | `--slidev-theme-primary` |
| `color.background` | `--slidev-theme-background` |
| `color.foreground` | body text color |
| `typography.base.family` | `--slidev-font-sans` |
| `typography.monospace.family` | `--slidev-font-mono` |
| `typography.headings.family` | heading font stack |
| `logo.medium` (or `small`) | `<img>` in `global-bottom.vue` |

### Step 6 — Content Authoring

Build content incrementally, following the approved plan. The live preview from Step 5c must already be running — the user should see changes in the browser as you write.

**Before writing any engine-specific code**, load the relevant skill:
- **Quarto**: Read the **quarto-authoring** skill for syntax/features, and the **officekit-documents** skill for project conventions.
- **Slidev**: Read `skills/slidev/SKILL.md`.

**For documents:**
1. Write each section in the `.qmd` file(s), one at a time.
2. The live preview auto-reloads — verify brand colors/fonts render correctly after each section.
3. Add figures, tables, and cross-references as you go.
4. Confirm with the user after each major section before moving on.

**For presentations:**
1. Write slides in `slides.md`, one logical group at a time.
2. The live preview auto-reloads — verify brand colors/fonts/logo after each group.
3. Add components, layouts, and animations as needed.
4. Confirm with the user after each slide group before moving on.

**Do NOT render to final output formats (PDF, Word, PPTX) during authoring.** The live preview is for iterating. Only export when the user explicitly asks for deliverables in Step 8.

### Step 7 — Preview and Refinement

Review the full deliverable in the browser.

**Preview commands:**
```bash
# Document
cd projects/<name>
quarto preview --port 4200

# Presentation
cd projects/<name>
npx slidev --port 3030
```

**Quality checklist:**
- [ ] All content present and in correct order.
- [ ] Brand colors, fonts, and logo applied consistently.
- [ ] Layout fills the page/slide — no awkward whitespace.
- [ ] Tables, figures, and diagrams render correctly.
- [ ] Links and cross-references work.
- [ ] No placeholder content remains.

Report issues to the user with specific locations. Fix approved issues before exporting.

### Step 8 — Export

**Only export when the user explicitly asks for final output files.** Do not proactively render all formats. Ask the user which format(s) they want, then render only those.

**Quarto document:**
```bash
cd projects/<name>
quarto render --to html                    # HTML
quarto render --to typst                   # PDF via Typst (modern, branded)
quarto render --to docx                    # Word
quarto render                              # All formats — only if user asks for all
```

**Slidev presentation:**
```bash
cd projects/<name>
npx slidev export --output dist/slides.pdf          # PDF
npx slidev export --format pptx --output dist/slides.pptx  # PowerPoint
```

**Post-export verification:**
1. Open each exported file and verify it looks correct.
2. Check file size is reasonable.
3. Confirm brand styling carried through to the export.

Deliver the output file paths to the user.

---

## Quick Reference

### Verify environment
```bash
quarto --version && node -v && npm -v
```

### Scaffold a new document project
```bash
cp -r .templates/document projects/<name>
mkdir -p projects/<name>/plan
```

### Scaffold a new presentation project
```bash
cp -r .templates/presentation projects/<name>
mkdir -p projects/<name>/plan
npm install   # from workspace root
```

### Preview a document
```bash
cd projects/<name> && quarto preview --port 4200
```

### Preview a presentation
```bash
cd projects/<name> && npx slidev --port 3030
```

### Render a document to PDF (Typst)
```bash
cd projects/<name> && quarto render --to typst
```

### Export a presentation
```bash
cd projects/<name> && npx slidev export --output dist/slides.pdf
```

### Add a Slidev dependency
```bash
npm install <package> -w projects/<name>    # from workspace root
```
