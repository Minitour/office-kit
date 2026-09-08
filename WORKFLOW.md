# OfficeKit Orchestration Contract

Match the process to the cost of the deliverable. Documents, decks, and
video are authored here, in this conversation, so the prefix stays warm and
the KV cache is reused. The only production subagent is `research-agent`:
spawn it when claims need checking, then write here. Revisions come from
follow-up requests.

## Routes

- Written document or standalone web document → `create-doc`
- Presentation or deck → `create-slides`
- Narrated motion/video → `create-video`
- New or revised visual identity → `init-brand`
- Ambiguous modality → ask one routing question; do not start production

## Documents are direct

Load `create-doc` and build the document yourself: no subagent, no plan file,
no approval gate, no preview server, no packaging step. The output is one
self-contained HTML file at `projects/<slug>/<slug>.html`, scaffolded and
verified by `scripts/document/doc.py`, opened straight from disk. Budget three
minutes. Durable state is that file plus a short `projects/<slug>/NOTES.md`.
Edit only the HTML (and `NOTES.md`); verify with `doc.py check`.

Delegate only when the user asks for genuine multi-source research before
writing; that goes to `research-agent`, and the writing still happens here.

## Decks and video are authored here

Load `create-slides` or `create-video` and do the work yourself: write the
plan, scaffold with `scripts/presentation/deck.py` or
`scripts/video/video.py`, and author in this conversation.
For a deck: `deck.py new` (scaffold + install), then `deck.py dev` (owns the
port and health-checks before printing the URL), then author in place, then
`deck.py audit` before calling it done. For video: the same shape via
`video.py new` / `dev` / `audit`. Do not delegate planning, authoring,
review, or export to a subagent. Do not stop for a plan-approval gate. The
request is the start signal.

### Edit boundary and single node_modules

- Documents: edit the HTML file only.
- Decks: edit `slides.md` and CSS under the project (`styles/brand.css`,
  plus `components/`, `layouts/`, `public/` when needed).
- Videos: follow HyperFrames guidelines; edit the composition and project
  media only.

Never read, write, patch, or inspect `node_modules/`. Never touch
`package-lock.json`. Never run `npx slidev` or `npx hyperframes` by hand —
the Python scripts own install, preview, audit, and export. There is one
`node_modules` at the workspace root via npm workspaces; per-project
`node_modules` installs are forbidden. If audit passes and the preview is
blank, run `stop` then `dev` — never escalate into dependencies.

Durable state lives under `projects/<slug>/`, never only in chat:

- `plan/PLAN.md` — the brief and the implementation plan in one file
- `reports/build.md` and `reports/review.md` — what you built and what you
  checked
- `reports/research.md` and `reports/delivery.md` — only when those stages run

On every invocation, inspect that state and resume from the first incomplete
piece. If the plan is missing or contradictory, rewrite it here, then
continue. A follow-up request is the revision: update the plan when the brief
changes, then implement; otherwise edit the deliverable in place.

## Brand state

The workspace may hold several identities under `brands/<id>/`. Each
`brands/<id>/brand.json` is canonical for that identity, and
`brands/<id>/BRAND.md`, `brands/<id>/tokens.css`, and `brands/<id>/frame.md`
are generated from it. `config.toml` `[brand] default` names the identity
used when a project does not pick one. Changes to any brand file route to
`brand-agent` via `init-brand`. After a brand change, existing documents that
use that identity need
`uv run python scripts/document/doc.py refresh --all`.

## Delegation

- Brand system creation, revision, and asset preservation → `brand-agent`
- Source gathering and fact checking, when asked for → `research-agent`

Nothing else is a subagent. Planning, Slidev, HyperFrames, narration, review,
and export happen here. `research-agent` writes `reports/research.md` and
stops; you turn that into the deliverable.

## Gates

1. Documents: build, verify with `doc.py check`, hand over. Revise on request.
2. Decks and video: `new` → `dev` (live preview from the template) → author
   in previewable increments → `audit` (must pass) → review in
   `reports/review.md`. Relay checkpoints; do not wait for the user to
   approve the plan.
3. Review the work yourself against the plan and the brand; record it in
   `reports/review.md`. Fix what you find.
4. Export only when the user requests a specific deliverable (`deck.py export`
   for decks).

Brand-only work still waits for an explicit identity proposal. Never add a
plan-approval gate to a deck or a video. Never spawn a subagent to author.
Never add a stage to a document to feel thorough — fix the template instead,
so the fix lasts.
