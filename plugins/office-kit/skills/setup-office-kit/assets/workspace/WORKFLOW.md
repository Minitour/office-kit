# OfficeKit Workspace Contract

This directory is an isolated OfficeKit workspace installed by the portable
OfficeKit Agent Plugin. Use the plugin's OfficeKit-authored skills for brand,
document, deck, video, and narration work. Perform production in the main
agent; no external skill, MCP server, hook, or subagent is required.

## Routes

- Written document or standalone web document → `create-doc`
- Presentation or deck → `create-slides`
- Narrated motion/video → `create-video`
- New or revised identity → `init-brand`
- Offline narration → `text-to-speech`

Ask one routing question only when the requested medium is ambiguous.

## Production commands

- Documents: `doc.py new` → author the HTML → `doc.py check`
- Decks: `deck.py new` → `deck.py dev` → author → `deck.py audit`
- Videos: `video.py new` → `video.py dev` → author → `video.py audit`

The Python scripts own install, preview, audit, stop, and export. Never invoke
Slidev, Vite, or HyperFrames directly when an OfficeKit wrapper exists.

## Edit boundaries

- Documents: edit the generated HTML and `NOTES.md`.
- Decks: edit `slides.md`, project CSS, `components/`, `layouts/`, `public/`,
  and project plan/reports.
- Videos: edit composition source, project media/narration, and project
  plan/reports.
- Brands: edit canonical `brands/<id>/brand.json` and preserve assets; generate
  `BRAND.md`, `tokens.css`, and `frame.md` with the brand script.

Never inspect or edit `node_modules`, `.venv`, generated lockfiles, or engine
internals. There is one shared Node environment at this workspace root.

## Brand state

Each identity lives under `brands/<id>/`. `brand.json` is canonical; the other
brand files are generated. `config.toml` `[brand].default` selects the fallback
identity. A second company or product gets a new brand ID.

Brand creation/revision has one explicit proposal approval gate. Documents,
decks, and videos do not have a plan approval gate.

## Durable state

Documents keep the HTML plus a short `NOTES.md`. Decks and videos keep
`plan/PLAN.md` plus `reports/build.md` and `reports/review.md`; add research or
delivery reports only when those stages actually occur. Resume existing work
instead of recreating it.

Research factual claims directly with tools provided by the host client. Record
sources and verification status in the project when research materially
informs the deliverable. Do not require an external MCP server.
