---
name: create-motion-reel
description: Create or revise a short, unnarrated motion reel with OfficeKit, drawn in code on a canvas and rendered frame by frame to MP4 with a synthesized, beat-locked score, in 16:9, 9:16 and 1:1. Use for product launch films, brand reels, logo animations, animated ads, teasers, showreels, and vertical social cuts, even when the user does not say "motion". Use create-video instead when the piece is narrated or explains something segment by segment.
compatibility: Requires an OfficeKit workspace, Node.js 22+, npm, Python 3.10+, uv, ffmpeg, and network access for the first Playwright Chromium download and brand web fonts.
metadata:
  author: OfficeKit
  version: "0.2.0"
---

# Create an OfficeKit motion reel

Work in `.office-kit/`. Use `setup-office-kit` first when absent. Author the
reel in the main agent. Research factual claims directly with host-provided
tools and record sources in `reports/research.md`.

A reel is a small program, not a timeline in an editor: `index.html` whose
`seek(t)` paints the exact frame for any moment, `timeline.js` holding a beat
grid that both picture and sound read, and `score.mjs`, which synthesizes the
soundtrack from that grid. `scripts/motion/reel.py` screenshots frames in
headless Chromium and pipes them into ffmpeg. Every frame is a pure function
of time, so a render is identical every run and a fix is a one-line edit plus
a re-render.

## Reel or video?

- **create-motion-reel**: 5 to 30 seconds, no voice, the picture carries the
  message. Launch films, logo reveals, feature teasers, social loops. Motion
  is drawn with springs and the music is cut to the frame.
- **create-video**: narration drives timing. Explainers, walkthroughs,
  training, anything turned from a script, document, or deck.

When a request could be either, ask one routing question.

## Boundary

Edit `index.html`, `timeline.js`, `score.mjs`, and project `media/`. Never
inspect or edit `node_modules` or lockfiles. `reel.py` owns install, stills,
audit, and render; do not write your own render loop or call Playwright or
ffmpeg for frames by hand.

Brand state comes from `brands/<id>/`. The page reads colours and fonts from
the `brand/tokens.css` snapshot at runtime and draws the mark from
`brand/assets/`; never paste hex values or font names into the page. Refresh
the snapshot with `reel.py refresh`, never by hand.

## Pass

1. **Plan.** Write `projects/<slug>/plan/PLAN.md` before code, using
   `references/plan.md`: the film in one line, audience and the one thing to
   remember, brand ID, references, a beat sheet on the grid, every line of
   on-screen copy, formats, rules, and requested delivery. For a one-line
   request, fill it in yourself and tell the user your choices in a sentence
   or two. No plan approval gate.
2. **Ground it.** Show only features that exist, with their real names and
   wording; if the brief implies something the product does not do, leave it
   out and say so. Use the brand's own palette, type, and marks.
3. **Scaffold.**

   ```bash
   uv run python scripts/motion/reel.py new <slug> --title "…" [--brand <id>] [--duration 7.5]
   uv run python scripts/motion/reel.py stills <slug>
   ```

   The template is a working 7.5 s starter (mark lands, three kinetic lines,
   lockup) in every format. It exists so the pipeline runs in minute one;
   replace its scenes, do not decorate them.
4. **Style frames.** Paint two or three key moments
   (`reel.py stills <slug> --times 1.2,4.3,6.3`) and critique them before
   animating. The look is cheapest to change here.
5. **Timeline and animatic.** Put every event on the grid in `timeline.js`
   (`b(n)`, never raw seconds). `reel.py animatic <slug>` gives a 12 fps draft
   with sound; judge timing, not polish.
6. **Critique loop.** Build every scene, then loop: `reel.py stills` → read
   `reports/stills/<format>/contact.png` (and single stills at full size when
   detail matters) → score each shot 1 to 10 on readability, composition,
   motion in flight, and brand fidelity → write the three worst problems in
   `reports/build.md` → fix → repeat until every shot is 8 or more. Two passes
   minimum. Choose still times mid-motion and on transitions.
7. **Score.** Give `score.mjs` the film's own key, tempo feel, and
   instruments, with every hit keyed to a `TL.*` event. For a melodic bed,
   the `strudel-offline` skill can render `media/music-bed.wav`; the renderer
   mixes it under the synthesized hits when present.
8. **Formats.** Re-lay out, never crop: scenes read positions from the layout
   object `L`, keyed by format. `config.toml` `[motion] formats` lists the
   formats that stills, audit, and render loop over; `--format` picks one.
   Run the critique loop on each; vertical needs bigger type and stacking.
9. **Audit.** `reel.py audit <slug>` must exit 0: no clocks or randomness in
   the page, no em dashes in copy, score headroom, and frames that hash the
   same forward, reversed, and repeated in every format. Write
   `reports/review.md`.

Render only when the user names a final deliverable:

```bash
uv run python scripts/motion/reel.py render <slug> [--format vertical]
uv run python scripts/motion/reel.py poster <slug>
```

Outputs land in `renders/<slug>[-<format>].mp4`. Check the file with ffprobe,
look at three or four frames from it, record it in `reports/delivery.md`, and
tell the user the concept, the paths, and the honest weak spots in a few
sentences.

## Craft essentials

Read `references/craft.md` before building scenes. The short version:

- **One continuous idea.** One shape that morphs through states beats a
  slideshow of cuts. If the last frame can equal the first, the film loops.
- **Springs, not easing.** `spring(t, t0, preset)` and `track()` from the
  template: SNAPPY for UI, DEF for cards and camera, HEAVY (no overshoot) for
  big type and marks, PLAY for mascots. Any value that changes target more
  than once uses `track()`.
- **Beat grid.** Cuts, pops, and type land on beats. A hook in the first two
  seconds, a payoff every three to five.
- **Motion in flight.** A frame with nothing moving is a dead frame; keep a
  slow drift under everything.
- **Copy is design.** Short, specific lines in the brand's voice, no em
  dashes. The last line is the one thing to remember.
- **Invented, not impersonated.** Draw generic, unbranded UI for "the old
  way" or third-party tools; never another company's logo, name, or
  recognisable interface.
- **Every reel its own.** When making several, give each its own idea,
  palette emphasis, type treatment, and score.

## Revising

A follow-up request is the revision. Search the page for every place the
changed thing appears (labels, badges, status lines), change them together,
re-render stills around the change, then the affected formats. Keep the same
slug so paths the user has stay valid. For a new brand, `reel.py refresh
<slug> --brand <id>`.

## References

- `references/plan.md`: `PLAN.md` structure and a filled example.
- `references/craft.md`: grounding, structure, composition, motion, type,
  sound, formats, QA checklist, and pitfalls met in practice.
