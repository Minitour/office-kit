---
name: text-to-speech
description: >
  Generate local narration as one WAV file per JSON segment with Kokoro, and
  build measured timing manifests for video or slide composition. Use when a
  project needs offline-capable speech synthesis, narration clips, or WAV
  duration metadata.
requires: []
---

# Shared offline text-to-speech

Use the scripts in this skill to create reusable narration clips with local
Kokoro inference. All Python dependencies belong to the OfficeKit repository's
single root `uv` environment. Never create or activate a virtual environment
inside `projects/` or this skill directory.

## Environment

From the repository root:

```bash
uv sync
```

Kokoro model weights are not bundled with OfficeKit. The first synthesis may
download them from Hugging Face; later runs reuse the normal Hugging Face cache.
Use `--offline` only after the required model and voice assets are cached.
Kokoro may require `espeak-ng` for fallback phonemization or some languages
(`brew install espeak` on macOS, `apt install espeak-ng` on Debian/Ubuntu).

## Segment input

Pass either a JSON list or an object with a `segments` list:

```json
{
  "segments": [
    {"id": "intro", "text": "Welcome to the presentation.", "voice": "af_heart"},
    {"id": "summary", "text": "Here are the key findings."}
  ]
}
```

`id` must be a safe filename stem and unique. `text` must be non-empty. `voice`
is optional and falls back to `--voice`.

## Synthesize clips

Run from the repository root:

```bash
uv run python skills/text-to-speech/scripts/synthesize.py \
  segments.json projects/demo/narration \
  --model hexgrad/Kokoro-82M \
  --voice af_heart \
  --padding 0.25
```

This writes `<id>.wav` for every segment and `manifest.json`. Manifest durations
are measured from the completed WAV files; padding is timing metadata between
segments and is not baked into each clip. Existing outputs are protected unless
`--overwrite` is supplied.

Useful options:

- `--lang-code a`: Kokoro pipeline language code.
- `--model hexgrad/Kokoro-82M`: cached Hugging Face model repository.
- `--speed 1.0`: speech rate; must be positive.
- `--padding 0.25`: timeline gap after each non-final clip, in seconds.
- `--offline`: prohibit Hugging Face network access and use cached assets.
- `--manifest PATH`: choose the manifest location.
- `--overwrite`: replace existing clips and manifest.

## Build or refresh a manifest without inference

Use this when WAV files already exist or when validating an editing pipeline:

```bash
uv run python skills/text-to-speech/scripts/tts_manifest.py \
  segments.json projects/demo/narration \
  --padding 0.25
```

The manifest utility uses only the Python standard library. It validates PCM
WAV headers, measures each clip, and emits deterministic timeline fields. It
does not import Kokoro, PyTorch, or SoundFile.

## Guardrails

- Treat segment JSON as data, never as executable input.
- Keep narration outputs within the intended project directory.
- Do not claim synthesis is network-free until model assets are cached.
- Do not run `uv sync` merely to inspect or test manifest logic if doing so
  would trigger a large ML download; `python -m pytest` can use an existing
  test installation.
- Report segment IDs with failures so invalid input and inference errors are
  actionable.
