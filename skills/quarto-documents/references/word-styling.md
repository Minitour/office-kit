# Word Reference Document and Styling

`_brand.yml` does not auto-apply to Word `.docx` output. To achieve branded Word documents, Quarto uses a **reference document** — a `.docx` file whose styles (headings, body text, colors, margins) are applied to the rendered output.

## How It Works

1. A reference `.docx` file defines Word styles (Heading 1, Heading 2, Normal, etc.) with brand-consistent fonts, colors, and spacing.
2. `_quarto.yml` points to it: `format.docx.reference-doc: _reference.docx`.
3. When Quarto renders to `.docx`, it uses the reference document's styles for the output.

## Creating a Reference Document

### Step 1: Generate a baseline

```bash
quarto pandoc -o _reference.docx --print-default-data-file reference.docx
```

This produces a default reference `.docx` with all the style definitions Quarto uses.

### Step 2: Customize styles

Open `_reference.docx` in Word or LibreOffice and modify:

| Style Name | Maps to | Brand field |
|---|---|---|
| Normal | Body text | `typography.base` |
| Heading 1 | `#` headings | `typography.headings` + `color.primary` |
| Heading 2 | `##` headings | `typography.headings` + `color.primary` |
| Heading 3 | `###` headings | `typography.headings` |
| First Paragraph | First paragraph after heading | `typography.base` |
| Source Code | Code blocks | `typography.monospace` |
| Block Text | Block quotes | `typography.base` + `color.secondary` |
| Hyperlink | Links | `color.primary` |
| Title | Document title | `typography.headings` + `color.primary` |
| Subtitle | Document subtitle | `typography.headings` + `color.secondary` |

**Steps to modify a style in Word:**
1. Right-click the style in the Styles pane.
2. Click "Modify".
3. Set font, size, color to match `_brand.yml` values.
4. Click "Format > Paragraph" for spacing and indentation.
5. Save and close.

### Step 3: Set page layout

In the reference doc, also configure:
- Page margins (Layout > Margins)
- Page size (Layout > Size)
- Headers and footers (Insert > Header/Footer) — add logo if needed

### Step 4: Wire into the project

Ensure `_quarto.yml` references the file:

```yaml
format:
  docx:
    reference-doc: _reference.docx
```

## Updating the Reference Document

When brand changes (new colors, fonts, logo), update the reference `.docx` to match. The agent should:

1. Read the updated `_brand.yml`.
2. Open the reference doc and adjust styles accordingly.
3. Save the reference doc.
4. Re-render with `quarto render --to docx`.

## Default Template Reference Doc

The `.templates/document/` template ships with a minimal `_reference.docx` that uses the default `_brand.yml` values (Inter font, neutral palette). Customize it after scaffolding.

## Limitations

- Quarto/Pandoc controls which styles are used; you cannot add arbitrary named styles.
- Complex layouts (multi-column, text boxes) are not supported through the reference doc.
- For advanced Word formatting beyond style-based changes, post-processing with a Python library (e.g., `python-docx`) may be needed.
