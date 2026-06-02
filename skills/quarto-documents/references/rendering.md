# Multi-Format Rendering and Export

## Rendering Commands

```bash
cd projects/<name>

quarto render                     # all formats defined in _quarto.yml
quarto render --to html           # HTML only
quarto render --to pdf            # PDF via Typst
quarto render --to docx           # Word document
quarto render index.qmd --to pdf  # specific file, specific format
```

Output lands in the `_output/` directory (configured by `project.output-dir` in `_quarto.yml`).

## Live Preview

```bash
quarto preview --port 4200
```

- Watches `.qmd` files for changes and reloads the browser automatically.
- Defaults to HTML preview. Use `--to pdf` to preview PDF (slower, no live-reload).
- Port is configurable in `config.toml` under `[preview].document_port`.

## PDF Output (Typst)

Quarto bundles Typst, so PDF rendering works out of the box without installing LaTeX or Typst separately.

Brand colors and fonts from `_brand.yml` are applied automatically to Typst output.

### Troubleshooting PDF

- **Missing fonts**: Typst embeds Google Fonts from `_brand.yml` automatically. For local fonts, ensure the font files are accessible.
- **Page layout**: Set `papersize` and margins in `_quarto.yml` under `format.pdf`.
- **Complex layouts**: For advanced PDF styling, use Typst template partials (see Quarto docs on custom Typst templates).

## HTML Output

HTML output is self-contained when `embed-resources: true` is set. Otherwise, it references external CSS/JS files in `_output/`.

Brand styles from `_brand.yml` are applied automatically. The result is a styled, responsive web page.

## Word Output (.docx)

Word output uses a reference document for styling. See `word-styling.md` for details on creating and customizing the reference doc.

Key points:
- `_brand.yml` does NOT auto-apply to Word output.
- Brand consistency for Word requires a reference `.docx` with styles pre-configured.
- The reference doc controls heading styles, fonts, colors, margins, and page layout.

## Rendering Multiple Files

For multi-file projects, list all `.qmd` files in `_quarto.yml`:

```yaml
project:
  type: default
  output-dir: _output
  render:
    - index.qmd
    - chapter-01.qmd
    - chapter-02.qmd
```

Or use a book project type for structured multi-chapter documents:

```yaml
project:
  type: book
  output-dir: _output

book:
  title: "My Book"
  chapters:
    - index.qmd
    - intro.qmd
    - methods.qmd
```

## Post-Render Verification

After rendering, verify:
1. Open each output file and check visual quality.
2. Confirm brand colors and fonts are applied.
3. Check TOC, cross-references, and citations resolve correctly.
4. Verify images and tables render at appropriate size.
5. For Word, open in Word/LibreOffice and check styles pane.
