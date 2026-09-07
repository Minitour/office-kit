# OfficeKit Orchestration Contract

Match the process to the cost of the deliverable. A document is written here
and now, in one pass. A deck and a video are staged behind a plan, because
their builds are long and their exports are expensive to redo.

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

Delegate document work only when the user asks for genuine multi-source
research before writing; that goes to `research-agent`, and the writing still
happens here.

## Decks and video are staged

For `create-slides` and `create-video`, act as a router: select the skill,
delegate each stage, and relay only approval gates and stage status, including
preview, review, and delivery status. Do not author slides, scenes, narration,
or exports in primary context.

Durable state lives under `projects/<slug>/`, never only in chat:

- `plan/PLAN.md` — the brief and the implementation plan in one file, with
  frontmatter `status: draft` or `status: approved`
- `reports/build.md` and `reports/review.md` — stage records and checks
- `reports/research.md` and `reports/delivery.md` — only when those stages run

On every invocation, inspect that state and resume from the first incomplete
stage. If it is missing or contradictory, send it back to `plan-agent` to
reconcile; do not infer approval. Only explicit user approval moves `PLAN.md`
from `draft` to `approved`.

## Brand state

Brand is workspace-level, not per project. `brand/brand.json` is canonical, and
`brand/BRAND.md`, `brand/tokens.css`, and `brand/frame.md` are generated from
it. Every deliverable consumes those generated outputs; changes to any of them
route to `brand-agent` via `init-brand`. After a brand change, existing
documents need `python scripts/document/doc.py refresh --all`.

## Delegation

- Brand system creation, revision, and asset preservation → `brand-agent`
- Intake, planning, and plan revisions for decks and video → `plan-agent`
- Source gathering and fact checking, when asked for → `research-agent`
- Slidev implementation → `slides-agent`
- HyperFrames and per-segment offline narration implementation → `video-agent`
- Deck and video review → `review-agent`
- Requested deck and video export, packaging, and handoff → `delivery-agent`

Each subagent reads the durable project state, performs only its assigned
stage, updates the corresponding file, and returns a concise status for relay.
Documents have no subagent: `doc.py check` is their review and the authored
file is their deliverable.

## Gates

1. Documents: build, verify, hand over. Revise on request.
2. Decks and video: delegate intake and planning, then present the draft plan
   and wait for explicit approval.
3. After approval, delegate implementation in previewable increments and relay
   meaningful checkpoints.
4. Delegate review; route fixes back to the builder and review again.
5. Delegate export only when the user requests a specific deliverable.

Never treat silence, prior chat approval, a running preview, or an existing
artifact as plan approval for a deck or a video. Never add a stage to a
document to feel thorough — fix the template instead, so the fix lasts.
