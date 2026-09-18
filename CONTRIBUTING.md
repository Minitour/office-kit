# Contributing to OfficeKit

Thanks for helping. This page covers the local setup, how the repository is
laid out, what the tests expect, and how a change gets in.

## Local setup

Prerequisites: Python 3.10–3.12, [uv](https://docs.astral.sh/uv/), Node.js 22+
with npm, and [CAPA](https://github.com/infragate/capa) if you want the full
agent workflow in this checkout. FFmpeg is only needed to encode video.

```bash
git clone https://github.com/Minitour/office-kit.git
cd office-kit
uv sync                 # root .venv (Kokoro pulls torch; give it a minute)
capa install            # optional: agent files for this checkout
```

Windows, macOS, and Linux are all supported. On Windows use any shell; the
scripts resolve `npm.cmd`/`npx.cmd` themselves and reconfigure the console to
UTF-8.

## Where things live

| Path | What it is |
|---|---|
| `plugins/office-kit/skills/<name>/SKILL.md` | **Canonical** skill sources. `capabilities.yaml` points CAPA here, so there is no second copy to keep in sync. |
| `scripts/` | Python CLIs: `document/doc.py`, `presentation/deck.py`, `video/video.py`, `brand/generate.py`, and shared `common.py`. |
| `scripts/presentation/render-audit.mjs` | Playwright render pass used by `deck.py audit`. |
| `.templates/` | Scaffolds for documents, decks (Slidev), and video (HyperFrames). |
| `brands/officekit/` | The default identity. `brand.json` is canonical; the rest is generated. |
| `plugins/office-kit/skills/setup-office-kit/assets/workspace/` | **Generated** payload the plugin installs into a host repo. Never edit by hand. |
| `tests/` | pytest suite. |

### Generated files

The plugin payload, `plugin.json`, and the three marketplace manifests are
produced from the canonical sources by:

```bash
uv run python scripts/plugin/build.py
```

Run it after touching anything under `scripts/`, `.templates/`,
`brands/officekit/`, `config.toml`, `package.json`, or `pyproject.toml`, and
commit the result. `uv run python scripts/plugin/build.py --check` (also run
in CI) fails when the payload is stale or a file is not on the allowlist in
`build.py`. Adding a file to a skill means adding it to that allowlist.

Brand derivatives are regenerated with `uv run python scripts/brand/generate.py`.

## Running the tests

```bash
uv run python -m pytest -q
```

A few deck tests read Slidev layouts and Lucide icon names from the workspace
`node_modules`. Scaffold any deck once to populate it (this is what CI does):

```bash
uv run python scripts/presentation/deck.py new smoke --title "Smoke"
```

`projects/` is gitignored, so scratch decks never end up in a commit.

To exercise the render pass locally:

```bash
uv run python scripts/presentation/deck.py dev smoke
uv run python scripts/presentation/deck.py audit smoke --dark
```

PNGs land in `projects/smoke/reports/render/`.

## Making a change

1. Branch from `main`.
2. Keep the change focused; template CSS, audit rules, and docs can each be
   their own PR.
3. Add or update a test. The template contract tests in
   `tests/test_presentation_deck.py` are the pattern for "a review found this,
   it must not regress".
4. Rebuild the plugin payload if you touched a source it copies.
5. Run the full suite on your platform; CI runs it on Ubuntu and Windows.
6. Open a PR using the template. Reference the issue with `Fixes #N`.

Commit messages follow a light conventional style: `fix:`, `feat:`, `docs:`,
`chore:`, optionally scoped like `feat(deck):`.

## Reporting a template bug

The most useful bug reports for the presentation template come with what the
reviewer actually saw: the slide markup, the brand's `tokens.css` values that
matter, and a screenshot or the `reports/render/slide-NN.png` from
`deck.py audit`. See the issue template.

## Releasing

Maintainers only.

1. Bump the version in `pyproject.toml`, `scripts/plugin/build.py`
   (`VERSION`), `plugins/office-kit/skills/setup-office-kit/scripts/bootstrap.py`
   (`VERSION`), and each skill's `metadata.version`. The
   `test_versions_agree` test enforces that they match.
2. Rebuild the payload, move the `Unreleased` section of `CHANGELOG.md` under
   the new version with today's date, and merge.
3. Tag `main` and push the tag:

   ```bash
   git tag -a v0.2.0 -m "OfficeKit 0.2.0"
   git push origin v0.2.0
   ```

   The release workflow zips `plugins/office-kit/`, attaches it, and publishes
   a GitHub Release with the changelog section as its notes. That release is
   what the repository page shows as "Latest".
