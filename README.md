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

- **Documents** — self-contained standalone HTML (one file: inline CSS/JS and embedded local assets)
- **Presentations** — Markdown/Slidev decks, previewed live and exportable to PDF or PowerPoint when you ask
- **Video** — [HyperFrames](https://hyperframes.heygen.com/) compositions with **offline** narration via Hugging Face / [Kokoro](https://github.com/hexgrad/kokoro) (local inference, no TTS API key)

Skills, subagents, and agent instructions are installed by [CAPA](https://github.com/infragate/capa).

## How work is organized

The **primary chat context is orchestration only**. It selects a user-facing skill, delegates each stage to a named subagent, and relays approval gates plus status (preview, review, delivery). It should not research, plan, write, design, render, or export in that context.

That split is a **workflow contract**, not a hard sandbox. CAPA and the host provider (Cursor, Claude Code, and others) may restrict tools, but enforcement varies — do not assume the primary context is mechanically prevented from editing files.

**Four primary skills** (load these; they only route):

| Skill | Use for |
|---|---|
| `create-doc` | Reports, proposals, memos, briefs, articles, letters, whitepapers → standalone HTML |
| `create-slides` | Pitches, lectures, talks, kickoffs → Slidev |
| `create-video` | Explainers, motion pieces, narrated walkthroughs → HyperFrames + local TTS |
| `init-brand` | Create or revise the shared visual identity |

Supporting skill: `text-to-speech` (Kokoro clips and timing manifests; used by video, not a user-facing entry point).

**Nine stage subagents:** `intake-agent`, `research-agent`, `plan-agent`, `doc-agent`, `slides-agent`, `video-agent`, `brand-agent`, `review-agent`, `delivery-agent`.

**Durable state** lives on disk under `projects/<slug>/`, not only in chat:

- `BRIEF.md` — purpose, audience, constraints, requested outputs, assets
- `plan/PLAN.md` — implementation plan; frontmatter `status: draft` or `status: approved`
- `reports/research.md`, `reports/build.md`, `reports/review.md`, `reports/delivery.md`

**Approval gates:** intake → research → draft plan, then **explicit user approval** before implementation. Silence, an old chat yes, a running preview, or an existing file is not approval. Export and final render happen only when you request a specific deliverable. Brand-only work (`init-brand`) uses a brand-proposal gate; it is not gated on a project `PLAN.md`.

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

HyperFrames cannot serve files above a video project root. Video scaffolding
therefore copies the generated files listed in `[video.brand_snapshot]` into
the project's `brand/` directory. That copy is a refreshable build input, not a
second source of truth.

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
├── scripts/               # Brand generator, HTML packager
├── package.json           # npm workspaces (root node_modules)
├── pyproject.toml         # Root uv / Python tooling
└── projects/<slug>/       # One deliverable per directory
    ├── BRIEF.md
    ├── plan/PLAN.md
    ├── reports/
    └── …source, preview, dist/ or renders/
```

Templates are copied into `projects/<name>/` when a project is scaffolded. Add a custom template under `.templates/` and point `config.toml` at its directory name.

## Quick usage

Examples of what to say:

- “Write a two-page product brief for engineering leads as a standalone HTML doc.”
- “Build a 12-slide kickoff deck for the Q3 launch.”
- “Turn this script into a 60-second branded explainer with voiceover.”
- “Set up our brand from this logo and palette.”

Typical loop:

1. The primary context routes to `create-doc`, `create-slides`, `create-video`, or `init-brand`.
2. Subagents write `BRIEF.md` and a draft `PLAN.md` (or a brand proposal).
3. You approve the plan (or brand direction) explicitly.
4. Implementation proceeds in previewable increments; you review in the browser.
5. You ask for a named export; `delivery-agent` packages only that.

If modality is unclear, you should get one routing question — not a mixed project. One directory is one engine.

## Preview vs export

**Preview is for iterating. Export is explicit.**

| Kind | Preview | Export (only when requested) |
|---|---|---|
| Document | Static server from the **workspace root** so `/projects/<name>/index.html` can load `brand/tokens.css` (default port **4200**) | `python scripts/document/package.py` → single HTML under `dist/` |
| Presentation | `npx slidev --port 3030` from the project (via root `node_modules`) | `npx slidev export` → PDF/PPTX/PNG under `dist/` |
| Video | `npx hyperframes preview --port 3002` | `npx hyperframes render` → file under `renders/` |

Do not treat a live preview or a leftover `dist/` / `renders/` file as the approved delivery. Ports and default export dirs are in `config.toml`.
