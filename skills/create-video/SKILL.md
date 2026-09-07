---
name: create-video
description: Route creation or continuation of an OfficeKit narrated video built with HyperFrames and offline text-to-speech. Use whenever the user wants an explainer, product video, motion graphic, narrated walkthrough, social clip, training video, voiceover animation, or to turn a script, document, or deck into video—even if they only say “make a video” or ask to resume an existing video project. Do not use for Slidev decks, standalone HTML documents, transcription, or brand-only work.
---

# Create Video

Act only as the orchestration router. Do not research, script, storyboard,
implement HyperFrames, synthesize speech, review, render, or export in primary
context. Delegate work and relay only approval or user-input gates and stage
status, including preview, review, and delivery status.

## Fixed production stack

Use HyperFrames for visuals and rendering. Narration must go through the
`text-to-speech` skill (Kokoro via `uv run`, one WAV per segment plus a measured
manifest) so timing and revisions stay local and isolated. Do not substitute
cloud TTS, ElevenLabs, or a new synthesis stack, and do not run TTS in primary
context.

Visual styling originates in the generated workspace brand outputs. HyperFrames
cannot serve files above a project root, so `video-agent` must copy the files
listed in `config.toml` `[video.brand_snapshot]` into the project-local
`brand/` directory immediately after scaffolding. This is a generated snapshot,
not a second source of truth; refresh it after `init-brand` changes the
workspace brand, and never hand-edit it.

## Resume from durable state

Resolve `projects/<slug>/`, then inspect `BRIEF.md`, `plan/PLAN.md`,
`reports/{research,build,review,delivery}.md`, and existing script, segment,
audio, preview, and render artifacts. `PLAN.md` must declare `status: draft` or
`status: approved`.

Resume at the first incomplete stage. Send new, ambiguous, stale, or
contradictory state to `intake-agent`. Never regenerate accepted segments or
infer approval from prior chat, media files, or a render.

## Stage routing

1. `intake-agent` confirms purpose, audience, platform, duration, aspect ratio,
   narration needs, delivery request, assets, and project state; it writes
   `BRIEF.md`.
2. `research-agent` verifies claims, sources, and references and writes
   `reports/research.md`.
3. `plan-agent` writes or revises `plan/PLAN.md` with `status: draft`, the
   script, segment-by-segment storyboard, visual direction, narration text,
   timing, accessibility, and acceptance criteria.
4. Relay the plan and wait for explicit approval. Have `plan-agent` change
   the status to `approved`; no video implementation may begin while it is
   `draft`.
5. `video-agent` builds approved segments incrementally in HyperFrames, invokes
   the existing offline TTS once per segment, synchronizes each segment to its
   narration, creates early low-cost previews, and records checkpoints in
   `reports/build.md`. Relay preview status by logical segment group.
6. `review-agent` checks claims, pacing, synchronization, safe areas,
   readability, accessibility, brand fidelity, audio quality, and acceptance
   criteria; it writes `reports/review.md`. Route fixes to `video-agent`, then
   re-review affected segments.
7. Only when requested, `delivery-agent` renders exactly the requested video
   and companion outputs, verifies them, and writes `reports/delivery.md`.

Preserve user assets and approved audio. Keep production work inside subagents.
