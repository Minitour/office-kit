# Craft

Rules gathered from reels made with this pipeline and from public work on code-driven motion. Treat numbers as defaults to deviate from on purpose, not laws.

> "You know what happens because you wrote the code. The viewer doesn't: they see it once, at full speed, for the first time."
>
> "A render that exits 0 proves nothing."

## Contents
1. Grounding
2. Story and structure
3. Composition
4. Motion
5. Type and copy
6. Sound
7. Formats
8. QA checklist
9. Pitfalls met in practice

## 1. Grounding

- **Real brand material.** Colours and faces come from the project's `brand/tokens.css` snapshot; the mark comes from `brand/assets/`. When a product needs a new identity, create it with `init-brand` first rather than sampling values into the page. To animate a mark's pieces separately, rebuild it from its SVG as canvas rects and paths. A reel in the wrong purple reads as fake.
- **Real features, real wording.** Read the code (API handlers, tool names, UI strings) and show only what exists, with its real labels. If a story beat needs a capability you can't confirm (e.g. "the agent is notified by an @mention"), show something that does exist instead and tell the user what you left out.
- **The product's own agent.** If an agent appears, use the product's own agent name and handle (ask when unknown). Don't default to a model vendor's assistant, and don't borrow its glyphs.
- **Invented "old way".** Contrast scenes use generic, unbranded UI: grey toolbars, a floppy save icon, `plan_v3_FINAL_final2.docx`, "RE: RE: FW:". Never another company's logo, name or recognisable layout. Catalog/integration grids use neutral lettered tiles with generic names ("Issues", "CRM").
- **References.** A frame: say what to take (palette, type, grain) and what not (subject). A video: extract frames with ffmpeg and describe the pacing shot by shot before coding. A gallery: write `style_guide.md` from it first. Name a style rather than describing one.

## 2. Story and structure

- **Pick an arc before beats.** Before/after/bridge (old way → turn → new way), demo loop (one task shown end to end), problem → agitate → solve, feature cascade. Give every beat one role: hook, pain, turn, feature, proof, payoff, lockup.
- **Hook in the first 2 seconds**, a visual payoff every 3 to 5 seconds, the promise by the second beat, lockup in the last 2 to 3.
- **One shape, never cut.** A single element morphs size, radius and colour through states (tile → document → grid cell → back to the mark). A cursor drives changes with real clicks. If the last frame equals the first, it loops.
- **Reads sheet.** For each shot list what the viewer must understand, each with a start and end; no two important reads overlap. If reads don't fit a shot, lengthen it or cut a read; don't squeeze. (A first version that packed a whole interaction into 1.3s was unreadable.)
- **Declare the rhythm** before code, e.g. "fast-fast-SLOW-fast-hold", and a motion verb per element (slams, draws, types on, peels, stacks). If you can't name the verb, the element isn't designed yet.
- **Every beat has an end state.** Write the key action mid-shot, not at the cut. A cut must add information.
- **Contrast pacing.** The slowest scene about 3x slower than the fastest. For "old vs new", make the old world literally stiffer: lower frame rate feel (quantise t to 8fps), linear motion, muffled lo-fi; then snap into springs and full sound at the turn.

## 3. Composition

- Hero text fills 60 to 80% of the frame width; anchor elements to edges or a grid, not floating in the middle of empty space.
- At least three layers (background texture, content, foreground accents/cursor). Never a flat empty background; a slow drift keeps frames alive.
- Pause test: stop at any second and something meaningful should be mid-flight. No idle "breathing" loops standing in for direction; each hold needs a route (staged reveal, camera with intent, a cursor doing something).
- Pull-backs that shrink the hero to a thumbnail lose it; keep the hero legible or hand the read to a new element.
- Banned by default (they read as AI-generic): shockwave rings, particle bursts, RGB split, camera shake, lens flares, neon glows, grid floors, flashing backgrounds, bouncy elastic easing, centred text on a gradient with everything fading in.

## 4. Motion

- **Springs** (template `spring`, `track`): SNAPPY {w:30,z:.78} UI and leading edges; DEF {w:17,z:.86} cards, containers, camera; HEAVY {w:11,z:1} big type and logos, no overshoot; PLAY {w:22,z:.48} mascots and stickers. Tiny overshoot on UI, none on type. Any value with more than one target uses `track()` so motion stays continuous.
- **Durations.** Entries at most about 0.8s, exits about 75% of the entry, total stagger under 0.5s. Offset the first motion 0.1 to 0.3s from t=0. 0.3 to 0.75s of stillness before the climax makes it land.
- **Snap, then hold.** A state change reads in 1 to 2 frames; ease the settle, not the change.
- **Vector law at transitions.** Exit and entry share axis, direction and speed, and the cut lands mid-motion on both sides. On Z, match the sign: a shrinking exit wants a grow-from-small entry, not a push-in. Keep one dominant direction of travel for the film; reverse only with a visible cause.
- **Staggered words.** Heavy words travel 60 to 80px over about 0.18s, light words 30 to 48px over about 0.12s; each gap shrinks by about 0.84.
- **Cursor.** Oversized (about 7% of width) on social formats, enters from off-screen, click = 0.1s press + 0.22s release, and the click ignites the next beat.
- **Perceptual scale.** Interpolate big scale changes in log space (`Math.exp(lerp(Math.log(a), Math.log(b), p))`); linear scale looks slow at large values.
- **Optional motion blur.** Render subframes at t ± 1/240s and blend (average the PNGs, or ffmpeg `tmix`) for fast moves.

## 5. Type and copy

- Readable text holds at least one beat; "3 seconds on screen = readable in 2". A word held under a beat is texture, not copy.
- Minimum sizes at 1080 wide (vertical, in-feed): body ≥ 32px, headline ≥ 90px. Monospace UI/terminal text is the first thing to become unreadable on phones; enlarge it in vertical or cut lines.
- Headlines 3 to 8 words. The product's voice, specific over clever. No em dashes; use a full stop, colon or two lines.
- Load every face with `display=block` and `document.fonts.load()` for each weight actually used, or early frames paint a fallback font.

## 6. Sound

- The score reads the same `timeline.js`, so hits land on frames. Give each film its own key, tempo and palette of instruments; ambient films can hold drums back until the payoff.
- **Sound leads picture** by about 0.03s: schedule a hit slightly before its contact frame. Late reads as broken, early reads as synced. Align a sound's peak, not its start, to the event.
- Start the full bed late (after the hook) so the first cut hits harder; drop to near-silence for a serious beat or before the turn; a tape-stop or filter sweep sells an "old → new" turn.
- Master: tanh soft clip, normalise to about -1 dBFS peak (0.79 of full scale before AAC leaves headroom; AAC overshoot pushes 0.89 to 0.0 dB). For social, loudness about -14 LUFS: `ffmpeg -af loudnorm=I=-14:TP=-1.5:print_format=summary`. Individual SFX sit at 0.3 to 0.6 of the bed.
- User-supplied track: measure it first (onsets/BPM with ffmpeg or a small analyser), trim to its strongest 5 seconds of opening, calibrate the beat grid to real kicks, and cut on downbeats. Trust BPM only for rhythmic music; otherwise pace by phrases.
- Voice-over: write VO as discrete cues; each on-screen element reveals when the VO names it. Duck music about -50% under voice with a 0.35s envelope.

## 7. Formats

- Write scenes against the layout object `L`, never raw pixel positions. 16:9 side-by-side compositions become stacked in 9:16 (terminal above document, thread below document, mark above wordmark); grids change columns (4x3 → 3x4).
- Vertical needs larger type, fewer simultaneous elements, and content centred as a block. Watch for empty bands top and bottom; fill them with the next element or move the block to centre.
- Keep the same timeline and score for every format so they stay in sync and share one master WAV.
- Leave a caption-safe zone (bottom ~15% of 9:16) free of key reads for platform UI.

## 8. QA checklist

Run before calling a reel done:

- [ ] Critique loop passed: every shot scored 8+ on readability, composition, motion-in-flight, brand fidelity, in every format.
- [ ] Stills taken mid-transition and around every seam, not only at settled moments.
- [ ] `reel.py audit` passes: no clocks or randomness in the page, score headroom, and frames that hash the same rendered forward, reversed and repeated. Hidden state between frames breaks this.
- [ ] Final MP4 checked, not just the stills: `ffprobe` dims/duration/streams; `ffmpeg -i out.mp4 -vf "fps=2,scale=480:-2,tile=6x6" -frames:v 1 master.png` and look at it.
- [ ] Audio: `volumedetect` max_volume between -2 and -0.5 dB; hits line up in the animatic.
- [ ] Every product claim, feature name and UI string verified against the code or site.
- [ ] No third-party logos or names; any agent uses the product's own name.
- [ ] Copy has no em dashes and no typos; text is readable at phone size in vertical.
- [ ] Write contact sheets to fresh filenames when comparing iterations; a cached image fakes a pass.

## 9. Pitfalls met in practice

- **Unbalanced `ctx.save()`/`restore()`** silently hid every sync line in one reel. Wrap each scene's drawing in save/restore pairs and reset `setTransform`/`globalAlpha` at the top of `seek`.
- **`spring(Infinity, ...)`** returned NaN (0 x cos∞) and made shapes vanish; the template guards it. Use `Infinity` to mean "settled".
- **Many ffmpeg builds have no `drawtext`**; don't depend on it for labels. Print the still order instead.
- **Opaque ground under seams.** Always paint the full background first, or transitions flash white.
- **Legibility dies first in vertical**: small mono labels, terminal lines, card text in pull-backs. Fix these in the vertical layout specifically.
- **Busy fold-backs.** When many pieces converge into a logo, fade the non-primary pieces early (by ~40% of travel) so only the final pieces arrive.
- **Name tags and cursors covering copy** during drags; offset tags away from the line being selected.

## Credits

Several rules above were learned from public work on code-driven motion:
[HyperFrames](https://hyperframes.heygen.com/),
[Remotion](https://www.remotion.dev/), the ClaudeAnimationBase,
claude-animation-skill and PDoomVideo projects, the Austerlitz film, and the
awesome-ai-motion list. Nothing from them is copied into the template.
