---
name: officekit-documents
description: >
  OfficeKit-specific document conventions. Use when scaffolding a new Quarto document
  project from templates, wiring _brand.yml into Word reference docs, reading config.toml
  for output format and page defaults, or managing the project directory structure under
  projects/. This skill complements the quarto-authoring skill (Quarto syntax and features)
  and the brand-yml skill (_brand.yml creation and format).
---

# OfficeKit Document Conventions

This skill covers the OfficeKit-specific layer on top of Quarto — project scaffolding from templates, brand-to-Word pipeline, operational config, and workspace conventions.

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

## Project Structure

Every document project lives under `projects/<name>/` and is scaffolded by copying `.templates/document/`:

```
projects/<name>/
├── _quarto.yml          # Project config — formats, page settings
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
   - `document.page.size` → `papersize` under `format.pdf`
   - `document.page.margin` → margin fields under `format.pdf`
   - `document.output.toc` → `toc` in each format block
   - `document.output.number-sections` → `number-sections` in each format block

3. Write `plan/PLAN.md` with the project outline.

## Brand Integration

### HTML and PDF

Quarto auto-discovers `_brand.yml` from the workspace root. No action needed — brand colors, fonts, and logo are applied automatically to HTML and Typst-PDF output.

### Word (.docx)

`_brand.yml` does **not** auto-apply to Word output. A reference `.docx` document bridges the gap. See `references/word-styling.md` for the full pipeline.

**Quick summary:**
1. Generate a baseline reference doc: `quarto pandoc -o _reference.docx --print-default-data-file reference.docx`
2. Open it and modify Word styles (Heading 1, Normal, etc.) to match `_brand.yml` values.
3. Point `_quarto.yml` at it: `format.docx.reference-doc: _reference.docx`

## Preview and Render

```bash
cd projects/<name>
quarto preview --port 4200         # live browser preview (HTML)
quarto render                      # all formats from _quarto.yml
quarto render --to html            # single format
quarto render --to pdf             # PDF via Typst
quarto render --to docx            # Word
```

The preview port default comes from `config.toml` → `[preview].document_port`.

## Tools

This skill does not require any tools. It provides context for using the `quarto` CLI and OfficeKit conventions.
