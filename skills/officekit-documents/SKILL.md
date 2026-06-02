---
name: officekit-documents
description: >
  OfficeKit conventions for Quarto document projects — the reference layer behind the
  create-docs workflow. Use whenever you scaffold a document project from .templates/document,
  wire _brand.yml into a Word reference doc, apply config.toml defaults (formats, page size,
  margins, TOC) to _quarto.yml, manage the projects/ directory structure, or preview and
  render documents. Complements quarto-authoring (Quarto syntax) and brand-yml (_brand.yml
  format). Read this before touching any OfficeKit document project, even if the user only
  says "make a report" or "render to Word".
---

# OfficeKit Document Conventions

This skill is the OfficeKit-specific layer on top of Quarto: project scaffolding from templates, the brand-to-Word pipeline, operational config, and workspace conventions.

For Quarto syntax, cross-references, callouts, and YAML features, load the **quarto-authoring** skill.
For `_brand.yml` creation and format details, load the **brand-yml** skill.

## When to Use

- Scaffolding a new document project from `.templates/document/`
- Wiring `_brand.yml` brand values into a Word reference document
- Reading `config.toml` to apply output format, page size, and margin defaults
- Setting up the project directory structure under `projects/`
- Configuring `_quarto.yml` for multi-format output (HTML, PDF, Word)
- Previewing and rendering documents within the OfficeKit workspace

## Reference Files

| Topic | File |
|---|---|
| Word reference document and brand-to-Word pipeline | `references/word-styling.md` |

## Critical Rules

1. **Brand MUST be explicitly referenced.** Quarto does NOT auto-discover `_brand.yml` from parent directories for projects nested under `projects/`. Every project's `_quarto.yml` must include `brand: ../../_brand.yml` (the relative path from the project to the workspace root). The default template already has this — do not remove it.

2. **PDF uses Typst, NOT LaTeX.** OfficeKit uses `format: typst` for PDF output. Typst is bundled with Quarto — no extra install needed. Never use `format: pdf` with `documentclass` (that triggers LaTeX which requires a separate TeX installation and produces academic-looking output). Use `format: typst` which produces modern, branded PDFs.

3. **Preview FIRST, render LAST.** Start `quarto preview` immediately after scaffolding and before writing any content. Keep it running throughout authoring. The user must see live progress in the browser. Only run `quarto render` at the very end when the user asks for final output files.

4. **Render only what is asked for.** Do not render all formats unless the user explicitly requests it. If the user says "create a document", author the content and show the live preview. Only render to specific formats (PDF, Word, etc.) when the user asks.

## Project Structure

Every document project lives under `projects/<name>/` and is scaffolded by copying `.templates/document/`:

```
projects/<name>/
├── _quarto.yml          # Project config (includes brand: ../../_brand.yml)
├── index.qmd            # Main document content
├── assets/              # Images, data files
├── plan/
│   └── PLAN.md          # Project plan and outline
└── _output/             # Rendered output (gitignored)
```

## Scaffolding a New Project

1. Copy the template:
   ```bash
   cp -r .templates/document projects/<name>
   mkdir -p projects/<name>/plan
   ```

2. Read `config.toml` and apply defaults to `_quarto.yml`:
   - `document.formats` → enable/disable format blocks in `_quarto.yml`
   - `document.page.size` → `papersize` under `format.typst`
   - `document.page.margin` → margin fields under `format.typst`
   - `document.output.toc` → `toc` in each format block
   - `document.output.number-sections` → `number-sections` in each format block

3. **Start the live preview immediately:**
   ```bash
   cd projects/<name>
   quarto preview --port 4200
   ```
   Keep this running throughout the authoring session.

4. Write `plan/PLAN.md` with the project outline.

## Brand Integration

### HTML and Typst (PDF)

The `_quarto.yml` template includes `brand: ../../_brand.yml` which tells Quarto where to find the brand file. This applies brand colors, fonts, and styling to both HTML and Typst-PDF output automatically.

If a project is at a different nesting depth, adjust the relative path accordingly.

### Word (.docx)

`_brand.yml` does **not** auto-apply to Word output. A reference `.docx` document bridges the gap. See `references/word-styling.md` for the full pipeline.

**Quick summary:**
1. Generate a baseline reference doc: `quarto pandoc -o _reference.docx --print-default-data-file reference.docx`
2. Open it and modify Word styles (Heading 1, Normal, etc.) to match `_brand.yml` values.
3. Point `_quarto.yml` at it: `format.docx.reference-doc: _reference.docx`

## Preview and Render

**Preview (use throughout authoring — start FIRST):**
```bash
cd projects/<name>
quarto preview --port 4200         # live browser preview (HTML)
```

**Render (use only when user asks for final output):**
```bash
quarto render --to html            # HTML only
quarto render --to typst           # PDF via Typst
quarto render --to docx            # Word
quarto render                      # all formats (only if explicitly asked)
```

The preview port default comes from `config.toml` → `[preview].document_port`.

## Tools

This skill does not require any tools. It provides context for using the `quarto` CLI and OfficeKit conventions.
