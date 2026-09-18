## Summary

<!-- What changes and why. Link the issue: Fixes #123 -->

## Kind of change

- [ ] Bug fix
- [ ] New affordance / feature
- [ ] Template or skill text
- [ ] Docs
- [ ] Tooling / CI

## Checklist

- [ ] Tests added or updated, and `uv run python -m pytest -q` passes locally
- [ ] `uv run python scripts/plugin/build.py` was run if a source the payload copies changed (`scripts/`, `.templates/`, `brands/officekit/`, `config.toml`, `package.json`, `pyproject.toml`), and the result is committed
- [ ] `CHANGELOG.md` has an entry under **Unreleased** for anything a user would notice
- [ ] For template changes: rendered a scaffolded deck (`deck.py audit --render`) and looked at the PNGs

## How it was verified

<!-- Commands run, platforms, screenshots for visual changes. -->
