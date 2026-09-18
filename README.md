<p align="center">
  <img src="brands/officekit/assets/logo.svg" alt="OfficeKit" width="120" />
</p>

<h1 align="center">OfficeKit</h1>

<p align="center">
  An AI-agent workspace for branded documents, slide decks, and narrated video.<br/>
  You describe the deliverable; the agent scaffolds, builds, audits, and revises it on request.
</p>

<p align="center">
  <a href="https://github.com/Minitour/office-kit/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/Minitour/office-kit?display_name=tag&sort=semver" /></a>
  <a href="https://github.com/Minitour/office-kit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Minitour/office-kit/actions/workflows/ci.yml/badge.svg" /></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-informational" />
  <a href="CHANGELOG.md"><img alt="Changelog" src="https://img.shields.io/badge/changelog-keep%20a%20changelog-orange" /></a>
</p>

---

## What you get

| Output | Engine | What lands on disk |
|---|---|---|
| **Documents** | Standalone HTML | One self-contained `.html` file (styles, brand tokens, marks, and images inlined). Opens straight from disk, prints to PDF from the browser. |
| **Presentations** | [Slidev](https://sli.dev/) | A Markdown deck with a branded template, live preview, a render-based audit, and PDF / PPTX / PNG export on request. |
| **Video** | [HyperFrames](https://hyperframes.heygen.com/) | A composition with **offline** narration ([Kokoro](https://github.com/hexgrad/kokoro)) and an optional **offline** music bed (Strudel / Dough). Nothing leaves your machine. |

Every output is styled from one **brand catalog** (`brands/<id>/brand.json`), so a palette or logo change flows into documents, decks, and video alike.

Things you can say to the agent:

- "Write a two-page product brief for engineering leads as a standalone HTML doc."
- "Build a 12-slide kickoff deck for the Q3 launch, with the results table as a chart."
- "Turn this script into a 60-second branded explainer with voiceover."
- "Set up our brand from this logo and palette."

## Quick start

There are two ways to run OfficeKit. Pick one per working directory.

| | **Plugin** (use OfficeKit in your own repo) | **This repository** (develop OfficeKit, full CAPA workflow) |
|---|---|---|
| Install | Through your agent client's plugin manager, no clone | `git clone` + [CAPA](https://github.com/infragate/capa) |
| Workspace | An isolated `.office-kit/` directory that `setup-office-kit` creates | This checkout; deliverables under `projects/` |
| Extras | The seven OfficeKit skills | Plus `research-agent`, `brand-agent`, and the `WORKFLOW.md` contract |

### Prerequisites (both paths)

- [Python](https://www.python.org/) 3.10–3.12 and [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/) 22+ with npm
- [FFmpeg](https://ffmpeg.org/) for final video encoding (`brew install ffmpeg`, `winget install Gyan.FFmpeg`, or your distro package)
- Network access on first run (npm packages, Python packages, Kokoro weights, a Chromium build for the render audit and export)

macOS, Linux, and Windows are supported. On Windows use PowerShell, cmd, or Git Bash; the scripts locate `npm.cmd` / `npx.cmd` themselves and switch the console to UTF-8.

### Option A: the plugin, inside another repository

Install the plugin, then ask the agent to run `setup-office-kit` from the repository where the deliverables belong.

<details>
<summary><strong>Claude Code</strong></summary>

```text
/plugin marketplace add Minitour/office-kit
/plugin install office-kit@office-kit
```

Skills appear under the `office-kit` namespace, for example `/office-kit:setup-office-kit`. Reload with `/reload-plugins` after updates.
</details>

<details>
<summary><strong>Cursor</strong></summary>

In Agent chat:

```text
/add-plugin https://github.com/Minitour/office-kit
```

Then install **OfficeKit** from the imported marketplace. Teams can import the same URL under **Dashboard → Plugins** with auto-refresh. See [Cursor plugins](https://cursor.com/docs/plugins).
</details>

<details>
<summary><strong>Codex</strong></summary>

```bash
codex plugin marketplace add Minitour/office-kit
```

Then install **OfficeKit** from the Plugin Directory. See [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins).
</details>

`setup-office-kit` writes:

```text
your-repository/
└── .office-kit/
    ├── brands/            # identities (officekit by default)
    ├── projects/          # one deliverable per directory
    ├── scripts/           # doc.py, deck.py, video.py, brand generator
    ├── .templates/        # document, presentation, video scaffolds
    ├── config.toml
    ├── package.json       # one shared node_modules
    └── pyproject.toml     # one shared .venv
```

Setup is idempotent: it records the hash of every file it manages and refuses to overwrite one you changed unless you pass `--force`. A workspace installed as `office-kit/` by an earlier version keeps being updated in place.

More client detail lives in the [plugin README](plugins/office-kit/README.md).

### Option B: this repository, with CAPA

```bash
git clone https://github.com/Minitour/office-kit.git
cd office-kit
capa install      # skills + subagents from capabilities.yaml into your agent's files
uv sync           # one root .venv
```

Open the checkout in your agent and start chatting. Decks and video install their Node dependencies into the root `node_modules` the first time they are scaffolded (npm workspaces). You do **not** run `setup-office-kit` here.

Plugin skills are canonical under `plugins/office-kit/skills/`; `capabilities.yaml` points CAPA at that same tree, so the two install paths never drift.

## How the work is organised

Process is matched to the cost of the deliverable.

- **A document is written directly**, in the conversation, in one pass: scaffold, author, verify, hand over. No plan file, no approval gate, no preview server. The output is `projects/<slug>/<slug>.html` plus a short `NOTES.md`.
- **A deck or a video is authored in the same conversation.** The agent writes a short `plan/PLAN.md`, starts the live preview, builds in groups while you watch, and runs the audit before calling it done. Export and final render happen only when you ask for a named deliverable.
- **Brand work is proposal-gated.** `init-brand` shows you the identity before any brand file is written, because a revision changes every deliverable that uses that id.

| Skill | Use for |
|---|---|
| `create-doc` | Reports, proposals, memos, briefs, articles, letters, whitepapers |
| `create-slides` | Pitches, lectures, talks, kickoffs, workshops |
| `create-video` | Explainers, motion pieces, narrated walkthroughs |
| `init-brand` | Create or revise an identity under `brands/<id>/` |
| `setup-office-kit` | Install or update the `.office-kit/` workspace (plugin path only) |
| `text-to-speech` | Offline Kokoro narration, one WAV per segment, measured timing manifest |
| `strudel-offline` | Offline Strudel / Dough music bed under narration |

In the CAPA path two subagents exist: `research-agent` (opt-in fact checking with recorded sources) and `brand-agent` (identity writes behind the proposal gate). Authoring never leaves the primary conversation.

**Durable state** lives on disk, not only in chat: a document keeps its HTML and `NOTES.md`; a deck or video keeps `plan/PLAN.md`, `reports/build.md`, `reports/review.md`, and `research.md` / `delivery.md` when those stages run. Resuming a project means reading those files.

## Commands

The Python scripts own install, preview, audit, stop, and export. Agents never run Slidev, Vite, or HyperFrames by hand. From the workspace root:

```bash
# Documents: one file, no server
uv run python scripts/document/doc.py new <slug> --title "…"
uv run python scripts/document/doc.py check projects/<slug>/<slug>.html
uv run python scripts/document/doc.py refresh --all        # re-apply brand + template shell

# Presentations
uv run python scripts/presentation/deck.py new <slug> --title "…"   # scaffold + npm install
uv run python scripts/presentation/deck.py dev <slug>              # live preview, health-checked
uv run python scripts/presentation/deck.py audit <slug>            # static + render pass (see below)
uv run python scripts/presentation/deck.py export <slug> --format pdf|pptx|png
uv run python scripts/presentation/deck.py stop <slug>

# Video
uv run python scripts/video/video.py new <slug> --title "…"
uv run python scripts/video/video.py dev <slug>
uv run python scripts/video/video.py audit <slug>
uv run python scripts/video/video.py refresh <slug>                # re-copy the brand snapshot
uv run python scripts/video/video.py stop <slug>

# Brand
uv run python scripts/brand/generate.py <id>                       # brand.json → BRAND.md, tokens.css, frame.md
```

### The deck audit

`deck.py audit` is the guardrail an agent trusts before telling you a deck is done, so it checks what actually breaks decks:

- Headmatter (`theme`, `aspectRatio`, `canvasWidth`, a pinned `colorSchema`), layout names against the installed Slidev, Lucide icon names, tag balance.
- The `ok-*` component contracts that fail silently in CSS: `ok-flow` holds exactly three steps, `ok-band` holds a mark plus one wrapper, `ok-hero-num` holds text.
- Every `src="/…"` and `image: /…` resolves under `public/`; every `<img>` has `alt`.
- **Render pass**: with the preview running, every slide is loaded at the canvas size in Chromium; content past the slide box or an image that failed to load is an error, and one PNG per slide lands in `reports/render/`. `--render` starts a preview if none is running, `--no-render` skips the pass, `--dark` adds a `prefers-color-scheme: dark` run.
- Distinct console errors from the preview log, so a component error is not buried in plugin noise.

## Brand contract

The workspace can hold several identities. Each one is a directory:

| Path | Role |
|---|---|
| `brands/<id>/brand.json` | Canonical, machine-readable source of truth |
| `brands/<id>/BRAND.md` | Generated usage rules |
| `brands/<id>/tokens.css` | Generated CSS custom properties (documents and decks) |
| `brands/<id>/frame.md` | Generated HyperFrames framing and safe areas |
| `brands/<id>/assets/` | Supplied logos and marks, preserved byte-for-byte |
| `config.toml` `[brand] default` | Identity used when a project does not name one |

Change an identity by editing its `brand.json` (through `init-brand`) and regenerating. Never hand-edit a generated file and never copy colours or fonts into `config.toml` or a project. Two consumers hold generated copies and must be refreshed after a brand changes: documents (`doc.py refresh --all`; `doc.py check` fails on drift) and video projects (`video.py refresh`, because HyperFrames cannot serve files above the project root). Decks read `tokens.css` live.

Operational defaults (templates, canvas size, preview ports, TTS flags, export directories) live in `config.toml`; a project's plan may override them for that project only.

## Directory layout

```text
office-kit/                       # this repository; the plugin installs the same layout as .office-kit/
├── brands/<id>/                  # one identity per directory (default: officekit)
├── config.toml                   # operational defaults plus [brand] default
├── capabilities.yaml             # CAPA skills and subagents
├── WORKFLOW.md                   # orchestration contract (primary context)
├── plugins/office-kit/           # the portable Agent Plugin; canonical skills live here
│   └── skills/<name>/SKILL.md
├── .templates/
│   ├── document-html/            # standalone HTML document
│   ├── presentation/             # Slidev: slides.md.j2, styles/brand.css, components/, layouts/, public/
│   └── video/                    # HyperFrames
├── scripts/
│   ├── common.py                 # config, brand, Jinja, cross-platform process helpers
│   ├── brand/                    # catalog + generator
│   ├── document/doc.py           # new | toc | check | refresh | embed
│   ├── presentation/deck.py      # new | dev | audit | export | stop
│   ├── presentation/render-audit.mjs
│   ├── video/video.py            # new | dev | audit | refresh | stop
│   └── plugin/build.py           # regenerates the plugin payload and manifests
├── tests/
├── package.json                  # npm workspaces (projects/*), one root node_modules
├── pyproject.toml                # one root .venv
└── projects/<slug>/              # deliverables (gitignored)
```

Add a custom template under `.templates/` and point `config.toml` at its directory name.

## What OfficeKit builds on

- [Slidev](https://sli.dev/) and [Lucide](https://lucide.dev/) icons for presentations, with [Playwright](https://playwright.dev/) for the render audit and export
- [HyperFrames](https://hyperframes.heygen.com/) for video composition and rendering
- [Kokoro](https://github.com/hexgrad/kokoro) (via Hugging Face) for offline narration
- [Strudel](https://strudel.cc/) and Dough for the offline music bed (**AGPL-3.0-or-later**, see below)
- [CAPA](https://github.com/infragate/capa) for the in-repo agent workflow, and the [Agent Plugins 1.0](https://agent-plugins.org/specification) packaging for everything else

Bugs inside those tools belong with their projects; a note here is welcome when OfficeKit should work around one.

## Contributing

Issues and pull requests are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the local setup, the generated-files rule, and the test suite; templates for [bug reports and feature requests](https://github.com/Minitour/office-kit/issues/new/choose) ask for what makes a report actionable. The project follows a [Code of Conduct](CODE_OF_CONDUCT.md), and security reports go through [SECURITY.md](SECURITY.md).

Releases are tagged `vX.Y.Z` and published on the [Releases](https://github.com/Minitour/office-kit/releases) page with notes from [CHANGELOG.md](CHANGELOG.md).

## License

See [`LICENSE`](LICENSE). The optional Strudel / Dough music-bed renderer (`plugins/office-kit/skills/strudel-offline/`, including vendored Dough and the `@strudel/*` / `supradough` packages) is **AGPL-3.0-or-later**; the complete text is in that skill's [`LICENSE`](plugins/office-kit/skills/strudel-offline/LICENSE).
