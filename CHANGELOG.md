# Changelog

All notable changes to OfficeKit are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-18

### Added

- Presentation template: `ok-figure`, `ok-shot`, `ok-split`, `ok-code`,
  `ok-table`, and the `OkBars` grouped bar chart component, with scaffold
  slides drawn from `public/figure-placeholder.svg` (#23).
- `deck.py audit` renders every slide with Playwright when a preview is
  running (`--render` starts one, `--no-render` skips, `--dark` adds a
  dark-scheme pass), fails on content past the canvas or a broken image, and
  writes `reports/render/slide-NN.png` (#26).
- `deck.py audit` checks the `ok-flow` / `ok-band` / `ok-hero-num` markup
  contracts, that every `src="/…"` resolves under `public/`, and that every
  `<img>` has `alt` (#20).
- `deck.py dev` and `audit` surface distinct console errors from the preview
  log.
- `--ok-accent` token alias in `brand.css` (#24).
- A brandable `layouts/end.vue` override for the closing slide (#18).
- Windows support: `npm`/`npx` shim resolution, a Windows process layer for
  `dev`/`stop`, UTF-8 console output (#17, #21).
- GitHub Actions CI on Ubuntu and Windows, a tag-driven release workflow,
  issue and PR templates, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`.

### Changed

- The portable workspace installs as `.office-kit/`; a legacy `office-kit/`
  is still updated in place (#16).
- `capabilities.yaml` points CAPA straight at `plugins/office-kit/skills/`;
  the repo-root `skills` symlink is gone, which is what broke `capa install`
  on Windows.
- Scaffolded decks pin `colorSchema: light`, and inline code is styled from
  tokens in every scheme (#25, #22).
- `.ok-hero-num` carries a display type scale; `.ok-rule` centres under
  centred layouts; the footer mark is positioned inside the slide so export
  no longer clips it (#22).
- Icons inside `ok-band` and other inverted containers follow `currentColor`
  (#19).
- `floating-vue` is pinned to 5.2.2 through the workspace `package.json`
  `overrides`, which silences the twoslash `Failed to patch FloatingVue`
  error on every page load (#27).
- `playwright-chromium` is installed with every scaffolded deck (export
  needed it already).
- `package-lock.json` is no longer committed; it named gitignored
  workspaces and broke `npm ci`.

### Removed

- The `OVERFLOW_CHARS` character-count heuristic in `deck.py audit`; it did
  not predict overflow (#26).

## [0.1.0] - 2026-06-03

Initial public workspace: standalone HTML documents, Slidev decks, HyperFrames
video with offline Kokoro narration and a Strudel/Dough music bed, brand
catalog, CAPA workflow, and the portable Agent Plugin.

[Unreleased]: https://github.com/Minitour/office-kit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Minitour/office-kit/compare/083f1dc...v0.2.0
[0.1.0]: https://github.com/Minitour/office-kit/commit/083f1dc
