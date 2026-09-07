# Notes: capa-overview

**Request:** `/create-doc about https://github.com/infragate/capa` — an
informative overview of CAPA for someone evaluating or adopting it.
**Audience:** developers and teams already using AI coding agents. Technical,
but not an internal product spec.
**Built:** 2026-09-07. **Migrated** to the one-file pipeline on 2026-09-07:
`capa-overview.html`, verified with `doc.py check`.

## Decisions

- OfficeKit branding only — no CAPA logos or banners.
- Marketing claims are hedged, deliberately: no GitHub star count (it dates
  instantly), and the README's 19–40% token-saving figure is omitted in favour
  of describing the on-demand loading mechanism.
- MIT is **not** stated as fact: the repo shows a licence badge but no LICENSE
  file was confirmed.
- Agent coverage cites the 39 providers named on capa.sh, and calls out that
  GitHub Copilot is MCP-only (not wrappable) and Windsurf is skills-only.
- CLI section reflects v2.1.2 as researched.
- Getting-started is deliberately thin: install → `init` → `add` → `install`
  or `wrap`. This is an overview, not a handbook.

## Migration note

Was `index.html` + `styles.css` + `script.js` loading `../../brand/tokens.css`,
which needed a static server on port 4200 to render branded. Now one
self-contained file that opens over `file://`. Content is unchanged; the
project's own CSS still sits in the second `<style>` block rather than the
template's `officekit:styles` region.

## Sources

capa.sh and github.com/infragate/capa only. Both cited in the document's
sources section.
