# OfficeKit Agent Plugin

OfficeKit creates branded standalone HTML documents, Slidev decks, and
HyperFrames videos. This package follows
[Agent Plugins 1.0](https://agent-plugins.org/specification) and contains six
OfficeKit-authored Agent Skills.

## What is included

- `setup-office-kit` — install/update an isolated workspace
- `init-brand` — create or revise a shared brand identity
- `create-doc` — author and audit one-file HTML documents
- `create-slides` — scaffold, preview, author, audit, and export Slidev decks
- `create-video` — scaffold, preview, author, and audit HyperFrames videos
- `text-to-speech` — local segmented Kokoro narration and timing manifests

The root `plugin.json` is authoritative. `.claude-plugin/plugin.json` and
`.codex-plugin/plugin.json` are metadata-only compatibility adapters.
The skill implementations in this directory are canonical. The repository-root
`skills/` path is a symlink to this tree.

## What is not included

The package intentionally contains no third-party skills, MCP servers, agents,
hooks, `capabilities.yaml`, extra brand identities, dependencies,
`node_modules`, virtual environments, model weights, or generated locks.

Slidev, Lucide, HyperFrames, Jinja, PyYAML, Kokoro, SoundFile, and their
transitive packages are external runtime dependencies. They are resolved into
the generated workspace by npm and uv; their source is not bundled here.

## Prerequisites

- Python 3.10–3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and npm
- ffmpeg for final video encoding
- network access for initial package/model resolution

## Load in Claude Code

For local development:

```bash
claude plugin validate ./plugins/office-kit --strict
claude --plugin-dir ./plugins/office-kit
```

Skills appear under the `office-kit` namespace, for example
`/office-kit:setup-office-kit`.

See [Claude Code plugins](https://code.claude.com/docs/en/plugins) for
marketplace distribution and installation.

## Load in Cursor

In Cursor's plugin/customization interface, install or import the
`plugins/office-kit` directory (or this repository and select that path).
Cursor reads the root Agent Plugins manifest and discovers immediate child
skills under `skills/`.

## Load in Codex

This repository includes `.agents/plugins/marketplace.json`, which exposes the
local `plugins/office-kit` directory. Add the repository as a marketplace:

```bash
codex plugin marketplace add /absolute/path/to/office-kit
```

Then install `office-kit` from the Plugins Directory or the Codex plugin
commands. The `.codex-plugin/plugin.json` adapter supports clients that still
expect Codex's client-specific entry point.

See [Codex plugin packaging](https://developers.openai.com/plugins/build/plugins)
for personal and repository marketplace alternatives.

## First run

From the repository where deliverables should be associated, invoke
`setup-office-kit`. It creates:

```text
your-repository/
└── office-kit/
    ├── brands/
    ├── projects/
    ├── scripts/
    ├── .templates/
    ├── config.toml
    ├── package.json
    └── pyproject.toml
```

The dedicated subdirectory avoids collisions with the host repository.
Deliverables live in `office-kit/projects/`; Node packages share the single
`office-kit/node_modules/`.

Setup is idempotent. Updates compare hashes in
`office-kit/.officekit-managed.json` and refuse to overwrite a user-modified
managed file. Back up intentional changes before using `--force`.

## Updating and developing

Rebuild generated manifests and the workspace payload:

```bash
uv run python scripts/plugin/build.py
uv run python scripts/plugin/build.py --check
uv run python -m unittest tests.test_plugin_package
```

Claude reloads local changes with `/reload-plugins`. Cursor and Codex may
require a plugin reload or client restart depending on how the package was
installed.
