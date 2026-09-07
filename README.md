<p align="center">
  <img src="brand/assets/logo.svg" alt="OfficeKit" width="120" />
</p>

<h1 align="center">OfficeKit</h1>

<p align="center">
  An AI-powered workspace for branded documents, slide decks, and narrated video.<br/>
  You describe the deliverable; the agent routes work, waits for approval, and builds it in stages.
</p>

---

OfficeKit produces three kinds of output:

- **Documents** — one self-contained HTML file, written in a single pass and opened straight from disk
- **Presentations** — Markdown/Slidev decks, previewed live and exportable to PDF or PowerPoint when you ask
- **Video** — [HyperFrames](https://hyperframes.heygen.com/) compositions with **offline** narration via Hugging Face / [Kokoro](https://github.com/hexgrad/kokoro) (local inference, no TTS API key)

Skills, subagents, and agent instructions are installed by [CAPA](https://github.com/infragate/capa).

## How work is organized

Process is matched to the cost of the deliverable.

**A document is written directly**, in the chat context, in one pass: scaffold, author, verify, hand over. No subagent, no plan file, no approval gate, no preview server, no packaging step. Budget is three minutes. The output is `projects/<slug>/<slug>.html` — styles, brand tokens, marks, and images all inlined — plus a short `NOTES.md`.

**A deck or a video is staged**, because the build is long and the export is expensive to redo. There the primary context is a router: it selects the skill, delegates each stage to a named subagent, and relays approval gates plus status. It should not author slides, scenes, narration, or exports itself.

That split is a **workflow contract**, not a hard sandbox. CAPA and the host provider (Cursor, Claude Code, and others) may restrict tools, but enforcement varies — do not assume the primary context is mechanically prevented from editing files.

**Four primary skills:**

| Skill | Use for | Shape |
|---|---|---|
| `create-doc` | Reports, proposals, memos, briefs, articles, letters, whitepapers | Direct, one pass |
| `create-slides` | Pitches, lectures, talks, kickoffs → Slidev | Routed, plan-gated |
| `create-video` | Explainers, motion pieces, narrated walkthroughs → HyperFrames + local TTS | Routed, plan-gated |
| `init-brand` | Create or revise the shared visual identity | Routed, proposal-gated |

Supporting skill: `text-to-speech` (Kokoro clips and timing manifests; used by video, not a user-facing entry point).

**Seven stage subagents**, for decks, video, and brand only: `plan-agent`, `research-agent`, `slides-agent`, `video-agent`, `brand-agent`, `review-agent`, `delivery-agent`. Documents have none.

**Durable state** lives on disk under `projects/<slug>/`, not only in chat:

| Modality | State |
|---|---|
| Document | `<slug>.html` (the deliverable itself) and `NOTES.md` |
| Deck, video | `plan/PLAN.md` with frontmatter `status: draft` or `status: approved`, plus `reports/build.md` and `reports/review.md` (and `research.md` / `delivery.md` when those stages run) |

**Approval gates apply to decks and video:** plan → **explicit user approval** → implementation. Silence, an old chat yes, a running preview, or an existing file is not approval. Export and final render happen only when you request a specific deliverable. Documents are draft-first instead — you get the file, then redirect it. Brand-only work (`init-brand`) uses a brand-proposal gate.

## Brand contract

Workspace-level, not per project:

| File | Role |
|---|---|
| `brand/brand.json` | Canonical, machine-readable source of truth |
| `brand/BRAND.md` | Generated usage rules |
| `brand/tokens.css` | Generated CSS custom properties (documents and decks) |
| `brand/frame.md` | Generated HyperFrames framing / safe areas |
| `brand/assets/` | Supplied logos and marks, preserved byte-for-byte |

Change identity by updating `brand.json` (via `init-brand` / `brand-agent`) and regenerating derivatives. Do not hand-edit generated files or copy colors/fonts into `config.toml` or project sources.

Two consumers hold *generated copies* rather than reading `brand/` live, and both must be refreshed after an identity change:

- **Documents** embed the token sheet and the marks so the file stands alone. Run `python scripts/document/doc.py refresh --all`; `doc.py check` fails on a document whose brand region has drifted, so staleness cannot pass silently.
- **Video** projects need a project-local snapshot because HyperFrames cannot serve files above a project root. Scaffolding copies the files listed in `[video.brand_snapshot]` into the project's `brand/` directory.

Operational defaults (templates, canvas size, preview ports, TTS flags, export dirs) live in `config.toml`. A project's plan may override those values for that project only.

## Prerequisites

- [Node.js](https://nodejs.org/) **22+** and **npm**
- [uv](https://docs.astral.sh/uv/) (root Python environment for TTS and packaging scripts)
- [FFmpeg](https://ffmpeg.org/) (HyperFrames render)
- [CAPA](https://github.com/infragate/capa) (`capa` on your `PATH`)

Kokoro weights download from Hugging Face on first synthesis and then reuse the local cache. Use `--offline` only after those assets are cached. Some languages also need `espeak-ng`.

## Setup

```bash
git clone https://github.com/Minitour/office-kit.git
cd office-kit
capa install
npm install
uv sync
```

`capa install` resolves skills and subagents from `capabilities.yaml`. `npm install` at the **workspace root** hoists Node dependencies (`package.json` workspaces: `projects/*`). `uv sync` creates the **single root** `.venv` from `pyproject.toml`. Do not create per-project `node_modules` or virtualenvs; add a project dep with `npm install <pkg> -w projects/<name>` from the root.

Then open the repo in your agent and start chatting.

## Directory layout

```
office-kit/
├── brand/                 # Shared identity contract
├── config.toml            # Operational defaults (not brand)
├── capabilities.yaml      # CAPA skills and subagents
├── WORKFLOW.md            # Orchestration contract (primary context)
├── .templates/
│   ├── document-html/     # Standalone HTML document
│   ├── presentation/      # Slidev
│   └── video/             # HyperFrames
├── skills/                # Local entry skills + TTS
├── scripts/
│   ├── brand/generate.py  # brand.json → derivatives
│   └── document/
│       ├── doc.py         # new | toc | check | refresh | embed
│       └── package.py     # asset-inlining library used by `doc.py embed`
├── package.json           # npm workspaces (root node_modules)
├── pyproject.toml         # Root uv / Python tooling
└── projects/<slug>/       # One deliverable per directory
    ├── <slug>.html        # a document: the whole deliverable
    ├── NOTES.md           # a document: the whole durable state
    ├── plan/PLAN.md       # a deck or video
    ├── reports/           # a deck or video
    └── …source, dist/ or renders/
```

Deck and video templates are copied into `projects/<name>/` at scaffold time. Documents are generated from `.templates/document-html/document.html` by `doc.py new`, which also inlines the brand. Add a custom template under `.templates/` and point `config.toml` at its directory name.

## Quick usage

Examples of what to say:

- “Write a two-page product brief for engineering leads as a standalone HTML doc.”
- “Build a 12-slide kickoff deck for the Q3 launch.”
- “Turn this script into a 60-second branded explainer with voiceover.”
- “Set up our brand from this logo and palette.”

For a **document**, you get the finished file back in about three minutes, then say what to change. For a **deck or video**: a draft plan → your explicit approval → an incremental build you watch in a live preview → review → a named export when you ask for one.

If modality is unclear, you should get one routing question — not a mixed project. One directory is one engine.

## Working with the output

| Kind | Look at it | Export |
|---|---|---|
| Document | `open projects/<slug>/<slug>.html` — no server; it is already one file | Nothing to export. Print to PDF from the browser if you need paper |
| Presentation | `npx slidev --port 3030` from the project (via root `node_modules`) | `npx slidev export` → PDF/PPTX/PNG under `dist/`, only when requested |
| Video | `npx hyperframes preview --port 3002` | `npx hyperframes render` → file under `renders/`, only when requested |

Verify a document with `python scripts/document/doc.py check projects/<slug>/<slug>.html`: it proves the file is self-contained, brand-current, and accessible without opening a browser.

For decks and video, do not treat a live preview or a leftover `dist/` / `renders/` file as the approved delivery. Ports and default export dirs are in `config.toml`.
