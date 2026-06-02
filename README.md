<p align="center">
  <img src="assets/logo.svg" alt="OfficeKit" width="120" />
</p>

<h1 align="center">OfficeKit</h1>

<p align="center">
  An AI-powered workspace for authoring branded documents and presentations.<br/>
  Describe what you need, and the agent builds it — section by section, slide by slide.
</p>

---

Under the hood, OfficeKit combines [Quarto](https://quarto.org/) (multi-format document publishing) and [Slidev](https://sli.dev/) (developer-friendly presentation slides) into a single workspace with unified branding, live browser preview, and multi-format export. You don't need to know either tool — the agent handles the markup.

Skills, tools, and agent instructions are managed by [CAPA](https://github.com/infragate/capa) — a capabilities manager for AI agents.

## What You Can Make

- **Documents** — reports, proposals, memos, articles, letters → HTML, PDF, Word
- **Presentations** — pitch decks, lectures, internal talks → interactive HTML slides, PDF, PowerPoint

Every output inherits your brand (colors, fonts, logo) from a single `_brand.yml` file.

## How It Works

1. **Tell the agent what you need** — document or presentation, topic, audience, format
2. **Review the plan** — the agent drafts an outline for your approval
3. **Watch it come together** — content is built incrementally, with live browser preview
4. **Get your deliverable** — rendered to your configured output formats

The agent reads your brand identity from `_brand.yml` and operational defaults from `config.toml`, so every project starts with a consistent look and feel.

## Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Quarto](https://quarto.org/docs/get-started/) 1.6+
- [CAPA](https://github.com/infragate/capa) (AI capabilities manager)

## Setup

```bash
git clone https://github.com/Minitour/office-kit.git
cd office-kit
capa install
```

`capa install` resolves the agent skills (Quarto authoring, Slidev, brand.yml) and verifies that the required CLI tools are on your PATH. Then install Node.js dependencies:

```bash
npm install
```

After installation, open the project in your AI agent of choice (Cursor, Claude Code, etc.) and start chatting.

## Configuration

### Brand — `_brand.yml`

The single source of truth for all visual identity. Quarto discovers it automatically; the agent maps the same values into Slidev themes.

| Section | What you can customize |
|---|---|
| `meta` | Brand name, website link |
| `logo` | Logo images for light and dark backgrounds |
| `color` | Palette, foreground, background, primary, secondary |
| `typography` | Fonts (base, headings, monospace), sizes, weights |

### Defaults — `config.toml`

Operational settings only — no brand fields.

| Section | What you can customize |
|---|---|
| `[document]` | Output formats, template, page size, margins, TOC |
| `[presentation]` | Slidev theme, aspect ratio, canvas width, export format |
| `[preview]` | Ports for document and presentation preview servers |
| `[style]` | Watermark toggle |

## Templates

Default templates ship under `.templates/`. The agent copies them into `projects/` when scaffolding a new project.

| Template | Path | Engine |
|---|---|---|
| Document | `.templates/document/` | Quarto |
| Presentation | `.templates/presentation/` | Slidev |

Add your own templates by creating new directories under `.templates/` and setting the template name in `config.toml`.

## Project Layout

Each deliverable lives in its own directory under `projects/`. The agent creates and manages this structure for you.

```
office-kit/
├── _brand.yml             # Brand identity (single source of truth)
├── config.toml            # Operational defaults
├── capabilities.yaml      # CAPA skills and agent config
├── .templates/            # Starter templates (document, presentation)
├── skills/                # Local agent skills
├── assets/                # Shared assets (logos)
└── projects/
    ├── quarterly-report/  # Quarto document project
    └── team-kickoff/      # Slidev presentation project
```

## Skills

OfficeKit loads agent skills on demand via CAPA:

| Skill | Source | Purpose |
|---|---|---|
| `quarto-authoring` | [posit-dev/skills](https://github.com/posit-dev/skills) | Quarto syntax, cross-references, callouts, extensions |
| `brand-yml` | [posit-dev/skills](https://github.com/posit-dev/skills) | Creating and using `_brand.yml` for consistent branding |
| `slidev` | [marcoshaber99/slidev-skills](https://github.com/marcoshaber99/slidev-skills) | Slidev best practices and patterns |
| `officekit-documents` | local | Template scaffolding, brand-to-Word pipeline, project structure |

> [!TIP]
> You don't need to install or manage skills manually. The agent discovers and loads them as needed during the authoring workflow.
