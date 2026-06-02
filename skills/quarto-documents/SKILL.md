---
name: quarto-documents
description: >
  Author branded text documents with Quarto. Use when creating reports, articles,
  memos, proposals, or any multi-format document that renders to HTML, PDF, or Word.
  Covers: project setup, _quarto.yml configuration, _brand.yml integration, multi-format
  output (HTML/Typst-PDF/docx), reference-doc for Word styling, live browser preview,
  and OfficeKit template usage.
---

# Quarto Document Authoring

Create professional, branded documents with Quarto that render to HTML, PDF (via Typst), and Word (.docx) from a single Markdown source.

## When to Use

- User wants to create a text document (report, article, memo, letter, proposal, etc.)
- User needs multi-format output from a single source
- User asks about Quarto project setup or configuration
- User needs to brand a document with `_brand.yml`
- User wants to preview a document in the browser
- User needs to generate a reference `.docx` for Word styling

## Reference Files

| Topic | File |
|---|---|
| `_quarto.yml` configuration and format options | `references/quarto-yml.md` |
| Multi-format rendering and export | `references/rendering.md` |
| Word reference document and advanced styling | `references/word-styling.md` |

## Core Concepts

### Project Structure

Every Quarto document project lives under `projects/<name>/` and is scaffolded from `.templates/document/`:

```
projects/<name>/
├── _quarto.yml          # Project config — formats, brand, page settings
├── index.qmd            # Main document content
├── assets/              # Images, data files
├── plan/
│   └── PLAN.md          # Project plan and outline
└── _output/             # Rendered output (gitignored)
```

### Brand Integration

Quarto auto-discovers `_brand.yml` when placed at or above the project root. Since OfficeKit keeps `_brand.yml` at the workspace root, Quarto projects under `projects/` inherit it automatically for `html` and `typst` (PDF) formats.

**Supported formats:**
- `html` — full brand application (colors, fonts, logo)
- `typst` — colors and fonts applied via Typst theming
- `docx` — requires a reference document for full styling (see `references/word-styling.md`)

Do **not** duplicate brand values into `_quarto.yml`. Let auto-discovery handle it.

### `_quarto.yml` Configuration

The `_quarto.yml` file in each project configures Quarto's behavior. The template provides sensible defaults; override only what the project plan requires.

Key sections:
- `project.output-dir` — where rendered files land (default: `_output`)
- `format.html` / `format.pdf` / `format.docx` — per-format settings
- `toc`, `number-sections` — structural options from `config.toml`

See `references/quarto-yml.md` for the full reference.

### Multi-Format Output

Quarto renders to multiple formats from a single `.qmd` source:

```bash
quarto render                   # all formats in _quarto.yml
quarto render --to html         # HTML only
quarto render --to pdf          # PDF via Typst
quarto render --to docx         # Word document
```

For PDF output, Quarto uses Typst by default (bundled with Quarto, no external install needed). Brand colors and fonts carry through.

### Live Preview

```bash
cd projects/<name>
quarto preview --port 4200
```

This starts a live-reload browser preview. Changes to `.qmd` files are reflected immediately. Use this throughout authoring — preview early and often.

### Authoring Patterns

1. **One section at a time** — write and preview each section before moving on.
2. **Cross-references** — use `@fig-`, `@tbl-`, `@sec-` prefixes for automatic numbering.
3. **Figures** — place in `assets/`, reference with `![Caption](assets/image.png){#fig-label}`.
4. **Tables** — use pipe tables or code-generated tables.
5. **Citations** — add to `references.bib`, cite with `[@key]`.
6. **Callouts** — use `:::{.callout-note}` / `.callout-warning` / `.callout-tip` for emphasis boxes.
7. **Code blocks** — fenced blocks with language tags; use `echo: false` to hide source in output.

### Conditional Content

Use format-specific divs when content should differ across outputs:

```markdown
::: {.content-visible when-format="html"}
This only appears in HTML output.
:::

::: {.content-visible when-format="pdf"}
This only appears in PDF output.
:::
```

## Workflow Summary

1. Read `_brand.yml` and `config.toml`.
2. Copy `.templates/document/` to `projects/<name>/`.
3. Write `PLAN.md` and get approval.
4. Author content in `index.qmd`, previewing with `quarto preview`.
5. Render to all configured formats with `quarto render`.
6. Deliver output files to the user.

## Tools

This skill does not require any tools. It provides context and guidance for using the `quarto` CLI directly from the terminal.
