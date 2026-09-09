---
name: create-video
description: Create or revise a branded narrated video with OfficeKit and HyperFrames. Use for explainers, product videos, motion graphics, narrated walkthroughs, social clips, training videos, or turning a script, document, or deck into video.
compatibility: Requires an OfficeKit workspace, Node.js 22+, npm, Python 3.10+, uv, ffmpeg, and network access for uncached HyperFrames/Kokoro dependencies.
metadata:
  author: OfficeKit
  version: "0.1.0"
---

# Create an OfficeKit video

Work in `office-kit/`. Use `setup-office-kit` first when absent. Author the
video in the main agent. HyperFrames is an external runtime dependency; this
plugin does not bundle its source or skills.

## Boundary

Edit the composition HTML, project CSS, narration data, and project media.
Follow the timing and frame guidance in the scaffolded `frame.md` and
`hyperframes.json`. Never inspect or edit `node_modules`, lockfiles, or
HyperFrames internals. OfficeKit's `video.py` owns preview and audit.

Brand state comes from `brands/<id>/`; the video receives a generated local
snapshot because its runtime cannot serve parent paths. Refresh snapshots with
`video.py refresh`, never by hand.

## Pass

Write `projects/<slug>/plan/PLAN.md`: brief, audience, brand ID, storyboard,
narration per segment, expected durations, visual direction, accessibility,
assets, requested delivery, and acceptance criteria. Research factual claims
directly using host-provided tools when needed and record sources in
`reports/research.md`. No plan approval gate.

Scaffold and start the health-checked preview:

```bash
uv run python scripts/video/video.py new <slug> --title "…" [--brand <id>]
uv run python scripts/video/video.py dev <slug>
```

Tell the user only the URL printed by `dev`. Build one seek-safe scene at a
time. Use semantic HTML and the composition's `data-*` timing attributes;
keep content within the configured frame and safe areas. Derive segment timing
from measured narration instead of guessing.

Use the `text-to-speech` skill for local narration: one WAV per segment plus a
measured `manifest.json`. Do not substitute cloud TTS. Preserve supplied media
byte-for-byte and keep generated assets separately named.

Record checkpoints in `reports/build.md`, then run:

```bash
uv run python scripts/video/video.py audit <slug>
```

Audit must exit 0. Review claims, pacing, synchronization, safe areas,
readability, accessibility, brand fidelity, and audio levels. Fix findings and
write `reports/review.md`.

Render only when the user names a final encoded deliverable, using `[video]`
format/output defaults and the scaffold's render command. Record the output in
`reports/delivery.md`; previews and stale renders are not deliveries.
