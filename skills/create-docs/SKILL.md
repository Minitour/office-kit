---
name: create-docs
description: >
  Launch the OfficeKit document authoring workflow — the /create-docs command. Use whenever
  the user wants to create, write, or draft a text document: a report, proposal, memo, letter,
  article, whitepaper, brief, or anything destined for PDF, Word (.docx), or HTML — even if they
  never say "Quarto" or "/create-docs". This skill drives the flow from concept to a rendered
  deliverable and pulls in the deeper skills for the details. Reach for it the moment a written
  document (not slides) is the goal.
---

# Create a Document (`/create-docs`)

This is the entry point for authoring a **text document** in OfficeKit. The engine is **Quarto** (Markdown → HTML, PDF, and/or Word). For a slide deck, use `create-slides` instead.

You are a collaborative authoring partner: build top-down (purpose and structure before content), keep the user in the loop at each gate, and never generate the whole deliverable in one shot.

## Skills to load as you go

Read these when you reach the relevant step — don't front-load everything:

- **officekit-documents** — scaffolding, the brand-to-Word pipeline, `config.toml` usage, project structure. Load before scaffolding.
- **quarto-authoring** — Quarto syntax: cross-references, callouts, citations, figures, YAML. Load before writing content.
- **brand-yml** — only if the user wants to change `_brand.yml` itself.

## Workflow

### 1. Load configuration
Read `_brand.yml` (brand identity) and `config.toml` (operational defaults: formats, page size, margins, TOC, preview port). These are the defaults for everything below unless the user overrides them.

### 2. Concept
Confirm it's a document (not slides). Gather topic, audience, purpose, target formats, and page size — presenting the `config.toml` defaults so the user only has to change what they want. Produce a 2–5 sentence brief and confirm it.

### 3. Outline
Draft a section outline (titles + key points per section) and note any tables, figures, diagrams, or citations. Present it for feedback.

### 4. Plan + approval (gate)
Write `projects/<name>/plan/PLAN.md` capturing the brief, effective configuration (resolved brand + config values plus any overrides), the section outline, visual/style notes, and an asset inventory. Present it and **wait for explicit approval** before authoring.

### 5. Scaffold and start preview

Copy the template and create the plan folder:

```bash
cp -r .templates/document projects/<name>
mkdir -p projects/<name>/plan
```

Apply `config.toml` defaults to `_quarto.yml` (formats, papersize, margins, TOC, section numbering). For Word output, set up the `_reference.docx` per the brand-to-Word pipeline. See **officekit-documents** for the specifics.

**Critical:** The template `_quarto.yml` already contains `brand: ../../_brand.yml` which is required for Quarto to find the brand file. Do not remove it.

**Start the live preview immediately, BEFORE writing any content:**

```bash
cd projects/<name>
quarto preview --port 4200   # port from config.toml [preview].document_port
```

Keep this running for the entire session. The user must see live progress in the browser from this point forward.

### 6. Author incrementally

Write one section at a time in the `.qmd` file(s). The live preview auto-reloads after every save — verify brand styling (colors, fonts) are applied in the browser.

Confirm with the user after each major section before continuing. Do NOT render to final output formats during this step.

### 7. Render (only when asked)

**Do not render unless the user explicitly asks for final output files.** Ask which format(s) they want; only render those.

```bash
cd projects/<name>
quarto render --to html            # HTML
quarto render --to typst           # PDF via Typst (modern, branded — NOT LaTeX)
quarto render --to docx            # Word
quarto render                      # all formats — only if user asks for all
```

Deliver the output file paths.

## Guardrails

- `_brand.yml` is the single source of truth for brand — never hardcode colors/fonts or duplicate them into `config.toml`.
- The `_quarto.yml` must include `brand: ../../_brand.yml` — Quarto does NOT auto-discover brand files from parent directories.
- PDF uses `format: typst`, NOT `format: pdf`. Typst is bundled with Quarto and produces modern branded output. Never use `documentclass` or LaTeX-based PDF.
- Always scaffold from `.templates/document` — never build a project from scratch.
- Don't author content before the plan is explicitly approved.
- Start the live preview before writing any content. Never skip the preview step.
- Don't render all formats unless the user explicitly asks. The live preview is for iterating; rendering is for final export.
- Preserve user-provided assets; reference them in place rather than modifying them.
