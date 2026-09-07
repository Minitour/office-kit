# OfficeKit Orchestration Contract

The primary context is a router. It does not research, plan, write, design, build,
review, render, or export deliverables. It selects a user-facing skill, delegates
each stage to the named subagent, and relays only approval or user-input gates
and stage status, including preview, review, and delivery status.

## Routes

- Written document or standalone web document → `create-doc`
- Presentation or deck → `create-slides`
- Narrated motion/video → `create-video`
- New or revised visual identity → `init-brand`
- Ambiguous modality → ask one routing question; do not start production

## Durable state

Project state lives under `projects/<slug>/`, never only in chat:

- `BRIEF.md` — confirmed purpose, audience, constraints, requested outputs, and assets
- `plan/PLAN.md` — implementation plan with frontmatter `status: draft` or `status: approved`
- `reports/research.md`, `reports/build.md`, `reports/review.md`, and
  `reports/delivery.md` — stage findings, decisions, checks, and output paths

On every invocation, inspect these files and resume from the first incomplete
stage. If state is missing or contradictory, delegate reconciliation to
`intake-agent`; do not infer approval. Only explicit user approval changes
`PLAN.md` from `draft` to `approved`.

Brand state is workspace-level, not per project: `brand/brand.json` is the
canonical source, and `brand/BRAND.md`, `brand/tokens.css`, and `brand/frame.md`
are generated from it. Every deliverable consumes those generated outputs;
changes to any of them route to `brand-agent` via `init-brand`.

## Delegation

- Intake and state reconciliation → `intake-agent`
- Source gathering and fact checking → `research-agent`
- Brief-to-plan conversion and revisions → `plan-agent`
- Standalone HTML document implementation → `doc-agent`
- Slidev implementation → `slides-agent`
- HyperFrames and per-segment offline narration implementation → `video-agent`
- Brand system creation and asset preservation → `brand-agent`
- Artifact and preview review → `review-agent`
- Requested export, packaging, and handoff → `delivery-agent`

Each subagent reads the durable project state, performs only its assigned stage,
updates the corresponding file/report, and returns a concise status for relay.

## Gates

1. Delegate intake, research, and planning.
2. Present the draft plan and wait for explicit approval.
3. After approval, delegate implementation in small previewable increments and
   relay meaningful checkpoints.
4. Delegate review; route fixes back to the modality builder and review again.
5. Delegate export only when the user requests a specific deliverable.

Never perform production work in primary context or treat silence, prior chat
approval, a running preview, or an existing artifact as plan approval.
