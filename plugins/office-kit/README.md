# OfficeKit Agent Plugin

This is the **standalone plugin** install path: six OfficeKit-authored Agent
Skills, with no CAPA, subagents, or MCP. If you are working *in the
office-kit git checkout* itself, use [CAPA](https://github.com/infragate/capa)
on that repository instead — see the [root README](../../README.md#install).

OfficeKit creates branded standalone HTML documents, Slidev decks, and
HyperFrames videos. This package follows
[Agent Plugins 1.0](https://agent-plugins.org/specification).

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

## Load in Cursor

In Cursor Agent chat:

```text
/add-plugin https://github.com/Minitour/office-kit
```

Then install **OfficeKit** from the imported marketplace. Teams can instead
import `https://github.com/Minitour/office-kit` under **Dashboard → Plugins**
and enable auto-refresh.

See [Cursor plugins](https://cursor.com/docs/plugins).

## Load in Claude Code

In Claude Code:

```text
/plugin marketplace add Minitour/office-kit
/plugin install office-kit@office-kit
```

Skills appear under the `office-kit` namespace, for example
`/office-kit:setup-office-kit`. Reload with `/reload-plugins` after updates.

See [Claude Code plugins](https://code.claude.com/docs/en/plugins).

## Load in Codex

Register the GitHub repository as a marketplace:

```bash
codex plugin marketplace add Minitour/office-kit
```

Then install `office-kit` from the Plugin Directory. The
`.codex-plugin/plugin.json` adapter supports clients that still expect Codex's
client-specific entry point.

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

Marketplace installs do not require a clone. Clone only to develop or validate
the package locally:

```bash
git clone https://github.com/Minitour/office-kit.git
cd office-kit
claude --plugin-dir ./plugins/office-kit
```

Rebuild generated manifests and the workspace payload:

```bash
uv run python scripts/plugin/build.py
uv run python scripts/plugin/build.py --check
uv run python -m unittest tests.test_plugin_package
```

Claude reloads local changes with `/reload-plugins`. Cursor and Codex may
require a plugin reload or client restart depending on how the package was
installed.
