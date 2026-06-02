# Word Reference Document and Brand-to-Word Pipeline

`_brand.yml` does not auto-apply to Word `.docx` output. To achieve branded Word documents, Quarto uses a **reference document** — a `.docx` file whose styles are applied to the rendered output.

## How It Works

1. A reference `.docx` defines Word styles (Heading 1, Normal, etc.) with brand-consistent fonts, colors, and spacing.
2. `_quarto.yml` points to it: `format.docx.reference-doc: _reference.docx`
3. Quarto uses those styles when rendering to `.docx`.

## Creating a Reference Document

### Step 1: Generate a baseline

```bash
quarto pandoc -o _reference.docx --print-default-data-file reference.docx
```

### Step 2: Map `_brand.yml` values to Word styles

Open `_reference.docx` in Word or LibreOffice. Modify these styles to match the brand:

| Word Style | Brand field |
|---|---|
| Normal | `typography.base` (family, size, weight) |
| Heading 1 | `typography.headings` + `color.primary` |
| Heading 2 | `typography.headings` + `color.primary` |
| Heading 3 | `typography.headings` |
| First Paragraph | `typography.base` |
| Source Code | `typography.monospace` |
| Block Text | `typography.base` + `color.secondary` |
| Hyperlink | `color.primary` |
| Title | `typography.headings` + `color.primary` |
| Subtitle | `typography.headings` + `color.secondary` |

**To modify a style in Word:**
1. Right-click the style in the Styles pane → Modify.
2. Set font, size, color from `_brand.yml`.
3. Format → Paragraph for spacing.
4. Save and close.

### Step 3: Set page layout

In the reference doc, also configure:
- Page margins (matching `config.toml` → `document.page.margin`)
- Page size (matching `config.toml` → `document.page.size`)
- Headers/footers — add brand logo if needed

### Step 4: Place in the project

Save `_reference.docx` in the project root alongside `_quarto.yml`. The template's `_quarto.yml` already points to it:

```yaml
format:
  docx:
    reference-doc: _reference.docx
```

## Updating After Brand Changes

When `_brand.yml` is updated:
1. Re-open `_reference.docx` and adjust styles to match the new brand values.
2. Save the reference doc.
3. Re-render: `quarto render --to docx`

## Limitations

- Only Pandoc-recognized styles are usable; arbitrary named styles are ignored.
- Complex layouts (multi-column, text boxes) are not supported through the reference doc.
- For advanced formatting, post-processing with `python-docx` may be needed.
