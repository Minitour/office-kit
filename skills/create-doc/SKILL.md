---
name: create-doc
description: Create or revise a written OfficeKit deliverable as one self-contained HTML file. Use whenever the user wants a report, proposal, memo, brief, article, letter, whitepaper, one-pager, web document, or asks to “write this up,” pastes source material, or returns to an existing document project—even if they never say create-doc or HTML. Do not use for slides, decks, video, motion graphics, or brand creation.
---

# Create Document

Write the document yourself, here, in one pass. Do not delegate a document to a
subagent, do not open a plan-approval gate, and do not start a preview server.
A document is small enough that staging it costs far more than it saves.

**Budget: three minutes and roughly six tool calls.** If you are heading past
that, you have added a stage that does not belong.

## The output

One file: `projects/<slug>/<slug>.html`. Styles, behaviour, brand tokens, the
brand mark, and any embedded image live inside it, so the user opens it
straight from disk. No server, no build step, no second artifact, no `dist/`.

HTML is the only document engine. If the user asks for Word, Google Docs, or a
print PDF, tell them HTML is what this produces — it prints cleanly from the
browser — and let them decide. Never improvise another pipeline.

## The pass

```bash
python scripts/document/doc.py new <slug> --title "…" [--subtitle "…"] [--footer "…"]
```

Then make one edit replacing the `<!-- officekit:content -->` marker in
`<main>` with every section, each shaped as:

```html
<section id="slug" aria-labelledby="slug-heading">
  <h2 id="slug-heading">Heading</h2>
  …
</section>
```

Then finish:

```bash
python scripts/document/doc.py toc   projects/<slug>/<slug>.html   # contents list
python scripts/document/doc.py check projects/<slug>/<slug>.html   # must pass
open projects/<slug>/<slug>.html                                   # hand it over
```

Write `projects/<slug>/NOTES.md` in the same pass — 20 lines at most: the
request, the audience, decisions you made, sources used, and anything you
deliberately left out. Those two files are the whole durable state for a
document: no separate brief, no plan file, no stage reports.

Report the file path and the `file://` URL from `check`, plus the one or two
judgement calls the user might want to overturn.

## Styling

Classes are already defined in the scaffold: `.lede` for the opening
paragraph, `.callout` for an aside, `.code-figure` for a captioned code block,
`.table-scroll` to wrap a wide table. Semantic HTML covers the rest.

When a document genuinely needs its own rule — a diagram, a comparison grid —
put it between `/* officekit:styles:start */` and `/* officekit:styles:end */`
and express colour through the `--doc-*` variables. Never use a `style`
attribute. If the rule would help every document, it belongs in the template.

Never hand-pick a colour, font, or logo path, and never hand-edit between
`/* officekit:brand:start */` and `/* officekit:brand:end */` — `doc.py` fills
that region from `brand/tokens.css` and `brand/brand.json`, and `check` fails
when it drifts. Route any brand change to `init-brand`, then run
`doc.py refresh`.

If the document needs a supplied image, reference it relatively and run
`doc.py embed` to pull it in as a data URI. Never modify, rename, or re-encode
a file the user gave you.

## Verification

`doc.py check` is the review step. It proves the file is self-contained,
branded, and accessible — one `<h1>`, no skipped heading levels, alt text on
every image, resolving in-page links, a contents list that matches the
sections, and no leftover placeholders. Read its output and fix what it
reports.

Do not start a server, do not drive a headless browser, and do not screenshot
a document to check layout. The template's layout, contents rail,
responsiveness, and print rules are already settled; trust them.

**When a defect is generic, fix `.templates/document-html/document.html`, not
the project.** The template owns two spans of every document: the shell CSS
between `/* officekit:brand:end */` and `/* officekit:styles:start */`, and the
script between `/* officekit:script:start */` and `/* officekit:script:end */`.
`doc.py refresh` re-applies both, so a template fix reaches documents that
already exist as well as future ones, while their content and their
`officekit:styles` region are left untouched. `check` says when a document is
running an older shell. A bug fixed only in one project is a bug you fix again
next week.

## Asking, and not asking

Default rather than interview. Unless the user says otherwise: an informative
document for a reader who knows the domain, OfficeKit branding, a contents
panel when there are four or more sections, today's date, no invented data.

Ask exactly one question, before building, only when the answer would change
the whole document — most often when the modality itself is unclear (document
or deck?). Otherwise build the draft and let the user redirect it; a one-file
draft is cheaper to correct than to specify.

Research is opt-in. Use the sources the user gave you plus what you already
know, and mark anything you could not confirm. When a document genuinely turns
on claims you cannot verify, say so and offer to research — do not silently
spend ten minutes on it.

## Revising

Read the existing `projects/<slug>/<slug>.html` and `NOTES.md`, edit the file
in place, re-run `toc` and `check`, and append the change to `NOTES.md`. Never
rebuild a document that already exists, and never treat an earlier document as
approval for a different one.
