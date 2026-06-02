# `_quarto.yml` Configuration Reference

This reference covers the `_quarto.yml` settings used in OfficeKit document projects.

## Minimal Example

```yaml
project:
  type: default
  output-dir: _output

format:
  html:
    toc: true
    theme: default
  pdf:
    documentclass: article
    papersize: a4
    margin-left: 2.5cm
    margin-right: 2.5cm
    margin-top: 2.5cm
    margin-bottom: 2.5cm
  docx:
    reference-doc: _reference.docx
```

## Project Section

| Field | Description |
|---|---|
| `project.type` | Always `default` for documents. |
| `project.output-dir` | Directory for rendered files. Use `_output` (gitignored). |

## Format: HTML

| Field | Description | Default |
|---|---|---|
| `toc` | Include table of contents | `true` |
| `toc-depth` | Heading depth for TOC | `3` |
| `number-sections` | Auto-number sections | `false` |
| `theme` | Bootstrap theme name or `[brand, theme-name]` for layered branding | `default` |
| `css` | Additional CSS file(s) | — |
| `code-fold` | Collapse code blocks | `false` |
| `embed-resources` | Self-contained HTML (inline images/CSS) | `false` |

Brand integration: Quarto discovers `_brand.yml` automatically. To layer brand under a theme:

```yaml
format:
  html:
    theme: [brand, cosmo]
```

To make brand take priority over the theme:

```yaml
format:
  html:
    theme:
      - cosmo
      - brand
```

## Format: PDF (Typst)

Quarto uses Typst for PDF rendering by default. Typst is bundled with Quarto — no separate install needed.

| Field | Description | Default |
|---|---|---|
| `documentclass` | Typst document class | `article` |
| `papersize` | Paper size | `a4` |
| `margin-left/right/top/bottom` | Page margins | `2.5cm` |
| `toc` | Include table of contents | `true` |
| `number-sections` | Auto-number sections | `false` |
| `mainfont` | Override base font (normally from `_brand.yml`) | — |

Brand integration: `_brand.yml` colors and fonts are applied to Typst output automatically.

## Format: Word (docx)

| Field | Description | Default |
|---|---|---|
| `reference-doc` | Path to a `.docx` template for styling | — |
| `toc` | Include table of contents | `true` |
| `number-sections` | Auto-number sections | `false` |

`_brand.yml` does **not** auto-apply to `.docx` output. Use a reference document for Word styling (see `word-styling.md`).

## Common Cross-Format Options

These apply to all formats:

| Field | Description |
|---|---|
| `title` | Document title (can also be set in `.qmd` YAML frontmatter) |
| `author` | Author name(s) |
| `date` | Document date (`today` for auto-date) |
| `lang` | Language code (e.g. `en`) |
| `bibliography` | Path to `.bib` file |
| `csl` | Citation Style Language file |

## Frontmatter in `.qmd` Files

Document metadata can also be set in the `.qmd` YAML frontmatter. Frontmatter values override `_quarto.yml` for that file:

```yaml
---
title: "My Report"
author: "Author Name"
date: today
abstract: |
  A brief summary of the document.
---
```
