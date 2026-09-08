---
name: create-video
description: Create or continue an OfficeKit narrated video in this conversation, built with HyperFrames and offline text-to-speech. Use whenever the user wants an explainer, product video, motion graphic, narrated walkthrough, social clip, training video, voiceover animation, or to turn a script, document, or deck into video—even if they only say “make a video” or ask to resume an existing video project. Do not use for Slidev decks, standalone HTML documents, transcription, or brand-only work.
---

# Create Video

Write the video yourself, here. Do not delegate planning, authoring,
narration, review, or export to a subagent — a fresh agent drops the
conversation prefix and wastes the KV cache. The only subagent you may
spawn is `research-agent`, and only when claims need checking.

## Fixed production stack

Use HyperFrames for visuals and rendering. Load the `hyperframes` skill
first, then the specific skill for the task (core, cli, animation,
keyframes, creative). Narration must go through the `text-to-speech` skill
(Kokoro via `uv run`, one WAV per segment plus a measured manifest). Pick
voices from `skills/text-to-speech/voices.json` (`af_heart`, `am_michael`,
`bf_emma`, and the rest); do not substitute cloud TTS, ElevenLabs, or a new
synthesis stack.

Visual styling originates in the generated workspace brand outputs under
`brands/<id>/`. The project's brand is the one the user named, or
`[brand] default`. HyperFrames cannot serve files above a project root, so
immediately after scaffolding copy the files listed in `config.toml`
`[video.brand_snapshot]` from `brands/<id>/` into the project-local
`brand/` directory. This is a generated snapshot, not a second source of
truth; refresh it after `init-brand` changes that workspace identity, and
never hand-edit it. Link only `./brand/tokens.css`. Record `brand: <id>` in
`plan/PLAN.md`. Run `hyperframes check` after snapshotting.

## Resume from durable state

Resolve `projects/<slug>/`, then inspect `plan/PLAN.md`,
`reports/{research,build,review,delivery}.md`, and existing script, segment,
audio, preview, and render artifacts. `PLAN.md` carries the brief,
storyboard, and narration script.

Resume at the first incomplete piece. Never regenerate accepted segments. A
follow-up request is the revision: update the plan when purpose, audience,
storyboard, or runtime changes; otherwise edit the scenes in place.

## The pass

1. Write `plan/PLAN.md` with the brief, the segment-by-segment storyboard,
   narration text, per-scene durations, visual direction, accessibility
   notes, asset inventory, requested delivery, and acceptance criteria. Ask
   only what would change the whole video. Defaults come from `config.toml`.
   No status field, no approval checklist.
2. `research-agent` writes `reports/research.md` only when the script turns
   on claims that need checking. Skip it otherwise. You still write the
   video.
3. If the project is not scaffolded, copy `.templates/video/` to
   `projects/<slug>/`, then copy the brand snapshot. Install from the
   workspace root with `npm install -w projects/<slug>` — never create a
   per-project `node_modules`. Use `uv` for Python tooling and `ffmpeg` for
   muxing.
4. Start the HyperFrames preview on `config.toml`'s `[preview] video_port`
   before building scenes and keep it running. Do not build blind.
5. Synthesize narration locally, one WAV per planned script segment, via
   `uv run python skills/text-to-speech/scripts/synthesize.py`. Use `--voice`
   from the plan or `[audio].voice`. Do not pass `--lang-code` unless the
   plan overrides G2P. Keep clips and `manifest.json` in the project's
   narration directory. Apply `[audio.levels]` with HyperFrames audio
   normalization. Narration comes from the planned script, never improvised
   copy.
6. Build one scene at a time, synchronize it to its clip, verify it in the
   preview, and record the checkpoint in `reports/build.md`. Leave no
   placeholder scenes or scratch audio.
7. Review the piece yourself against the plan: claims, pacing,
   synchronization, safe areas, readability, accessibility, brand fidelity,
   audio quality. Write `reports/review.md` and fix what you find.
8. Render the final encoded file only when the user names it. Use `[video]`
   `format` and `output_dir`. Record the path in `reports/delivery.md`. A
   preview render or a leftover `renders/` file is not a delivery.

Preserve user assets and accepted audio. Supplied footage, images, logos,
and audio are read-only inputs.
