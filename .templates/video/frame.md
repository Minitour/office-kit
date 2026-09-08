# Frame brief

Per-project companion to the project's **brand snapshot**. Fill this in for
this video; do not restate brand values.

## Required scaffold-time brand snapshot

HyperFrames serves and validates the project root only. It rejects runtime
references such as `../../brands/<id>/tokens.css`, even when the workspace
file exists. `video.py new` copies the snapshot; `video.py refresh`
re-copies it after a brand change. Manual setup, if you ever need it:

1. Create `brand/assets/` inside the new video project.
2. Copy the generated workspace `brands/<id>/tokens.css` to
   `<project>/brand/tokens.css`.
3. Copy the generated workspace `brands/<id>/frame.md` to
   `<project>/brand/frame.md`.
4. Copy every logo or other file referenced by that frame spec from workspace
   `brands/<id>/assets/` to `<project>/brand/assets/`, preserving filenames.
5. Add this line in the `head` of `index.html`, before its inline style:

   ```html
   <link rel="stylesheet" href="./brand/tokens.css" />
   ```

6. Only after the required logo exists, add it with a project-local URL such
   as `./brand/assets/<logo-file>`. Never reference a workspace-parent path.
7. Run `npx hyperframes@latest check` again.

This is a deliberate generated snapshot, not a second brand source. Refresh it
from the workspace-generated files whenever `brands/<id>/brand.json` changes.
Do not hand-edit the snapshot. `<id>` is the project's brand, or
`[brand] default` in `config.toml`.

The untouched template intentionally has no token link, logo, media element,
or animation dependency. Its neutral CSS fallbacks allow HyperFrames check to
pass before the snapshot exists.

## Brand use after snapshot

- Read `brand/frame.md` first. It is normative for palette, typography, safe
  area, and frame composition.
- Use the `--color-*` and `--font-*` variables supplied by
  `brand/tokens.css`; never paste literal current-brand values into this file.
- The composition root sets `container-type: size`, so display sizes are
  authored in `cqw` against the frame, never `vw`.
- Add media markup only after its source exists inside the project. Do not
  keep missing-source elements in comments; HyperFrames parses them.
- Use only finite, seekable, locally available animation code. Do not add CDN
  scripts or wall-clock animation.

## This video

- **Purpose:** _one sentence — what the viewer should do or understand._
- **Audience:** _who is watching, and what they already know._
- **Duration:** 5 s placeholder. The root `data-duration` in `index.html` is
  the render length and must match the final beat sheet.
- **Aspect:** 1920x1080. Consult the local `brand/frame.md` snapshot before
  adapting to another aspect ratio.

## Beat sheet

One row per beat. Durations must sum to the root `data-duration`.

| # | Start | Duration | On screen | Narration / audio |
| - | ----- | -------- | --------- | ----------------- |
| 1 | 0.0   | 5.0      | Title card | _none yet_ |

## Assets

- **Media:** files in `media/` (video, images, music). Note the source and
  licence of anything not generated locally.
- **Narration:** segment JSON and generated speech in `narration/`. Synthesise
  offline with the text-to-speech skill using the voice, speed, and padding in
  `config.toml` `[audio]`; mix to the targets in `[audio.levels]`.

## Claims

Never invent metrics, dates, or percentages. Leave unset values as
placeholders (`{metric}`) until the script supplies them.
