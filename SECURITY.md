# Security policy

## Supported versions

Only the latest release on the [Releases](https://github.com/Minitour/office-kit/releases)
page receives fixes. Please reproduce against `main` or the latest release
before reporting.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Use GitHub's private vulnerability reporting:
<https://github.com/Minitour/office-kit/security/advisories/new>.

Include what you found, how to reproduce it, and what you think the impact is.
You will get an acknowledgement within a few days, and a fix or a decision as
soon as one is ready. Credit is given in the release notes unless you prefer
otherwise.

## What counts

OfficeKit runs local tooling on your machine (Node, Python, Playwright, FFmpeg)
and installs npm and PyPI packages into a workspace. Things worth reporting:

- A scaffold, skill, or script that executes untrusted input (for example
  from a deck, document, or brand file) in a way the author did not intend.
- Anything in the plugin payload or install path that writes outside the
  workspace it was asked to create.
- Dependency pins that pull a known-vulnerable version where a safe one is
  available.

Problems in upstream tools (Slidev, HyperFrames, Kokoro, Strudel/Dough) belong
with those projects, but a note here is welcome if OfficeKit should work
around them.
