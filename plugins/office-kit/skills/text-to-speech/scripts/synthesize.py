#!/usr/bin/env python3
"""Synthesize one Kokoro WAV file per validated JSON narration segment."""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from tts_manifest import (
    configure_console,
    LANG_CODE_PATTERN,
    ManifestError,
    build_manifest,
    format_voice_list,
    load_segments,
    resolve_voice,
    write_manifest,
)

KOKORO_SAMPLE_RATE = 24_000


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate per-segment WAV narration with local Kokoro inference."
    )
    parser.add_argument("segments", nargs="?", type=Path, help="JSON segment list")
    parser.add_argument("output_dir", nargs="?", type=Path, help="directory for WAV files")
    parser.add_argument(
        "--model",
        default="hexgrad/Kokoro-82M",
        help="Hugging Face Kokoro model repository",
    )
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="default Kokoro voice id (see --list-voices)",
    )
    parser.add_argument(
        "--lang-code",
        help="force one Kokoro G2P language for every segment; omit to derive "
        "it from each voice id (af_/am_ → a, bf_/bm_ → b, …)",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="print bundled Kokoro-82M voice ids and exit",
    )
    parser.add_argument(
        "--allow-unknown-voice",
        action="store_true",
        help="accept voice ids that are not in the bundled catalog",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="positive speech speed")
    parser.add_argument(
        "--padding",
        type=float,
        default=0.0,
        help="timeline gap after each non-final segment in seconds",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="manifest path (default: <output-dir>/manifest.json)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use cached Hugging Face assets and prohibit downloads",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing outputs")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    resolve_voice(
        args.voice,
        override_lang_code=args.lang_code,
        allow_unknown=args.allow_unknown_voice,
    )
    if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$", args.model):
        raise ManifestError(
            "model must be a Hugging Face repository id such as "
            "'hexgrad/Kokoro-82M'"
        )
    if args.lang_code is not None and not LANG_CODE_PATTERN.fullmatch(args.lang_code):
        raise ManifestError(
            f"language code must match {LANG_CODE_PATTERN.pattern!r}; "
            f"got {args.lang_code!r}"
        )
    if not math.isfinite(args.speed) or args.speed <= 0:
        raise ManifestError("speed must be a finite number greater than zero")
    if not math.isfinite(args.padding) or args.padding < 0:
        raise ManifestError("padding must be a finite, non-negative number")


def _prepare_outputs(
    segments: Sequence[Any],
    input_path: Path,
    output_dir: Path,
    manifest_path: Path,
    *,
    overwrite: bool,
) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ManifestError(f"output path is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_paths = [output_dir / f"{segment.id}.wav" for segment in segments]
    if manifest_path in wav_paths:
        raise ManifestError(f"manifest path collides with a segment WAV: {manifest_path}")
    if manifest_path == input_path:
        raise ManifestError(f"manifest path collides with segment input: {manifest_path}")

    paths = [*wav_paths, manifest_path]
    if not overwrite:
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            preview = "\n  ".join(existing[:10])
            suffix = "\n  ..." if len(existing) > 10 else ""
            raise ManifestError(
                "output files already exist; pass --overwrite to replace them:\n  "
                f"{preview}{suffix}"
            )
    for path in paths:
        if path.exists() and not path.is_file():
            raise ManifestError(f"output path is not a regular file: {path}")


def _load_runtime() -> tuple[Any, Any, Any]:
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as exc:
        raise ManifestError(
            "Kokoro runtime is unavailable. Run `uv sync` in the OfficeKit "
            "workspace, then invoke this skill script through that environment "
            "with `uv run --project <office-kit> python <script> ...`."
        ) from exc
    return np, sf, KPipeline


def _as_audio_array(audio: Any, np: Any) -> Any:
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    array = np.asarray(audio, dtype=np.float32).reshape(-1)
    if array.size == 0:
        raise ManifestError("Kokoro returned an empty audio chunk")
    if not np.all(np.isfinite(array)):
        raise ManifestError("Kokoro returned non-finite audio samples")
    return array


def synthesize_segment(
    pipeline: Any,
    text: str,
    voice: str,
    speed: float,
    output_path: Path,
    *,
    np: Any,
    sf: Any,
) -> None:
    """Run Kokoro and atomically write a 24 kHz mono PCM WAV."""
    chunks = []
    try:
        for _graphemes, _phonemes, audio in pipeline(
            text, voice=voice, speed=speed
        ):
            chunks.append(_as_audio_array(audio, np))
    except Exception as exc:
        raise ManifestError(f"Kokoro inference failed: {exc}") from exc

    if not chunks:
        raise ManifestError("Kokoro produced no audio")
    samples = np.concatenate(chunks)

    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        sf.write(
            temporary,
            samples,
            KOKORO_SAMPLE_RATE,
            format="WAV",
            subtype="PCM_16",
        )
        temporary.replace(output_path)
    except Exception as exc:
        raise ManifestError(f"could not write WAV file {output_path}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    configure_console()
    args = _parser().parse_args(argv)
    if args.list_voices:
        sys.stdout.write(format_voice_list())
        return 0
    if args.segments is None or args.output_dir is None:
        _parser().error("segments and output_dir are required unless --list-voices is set")

    try:
        _validate_args(args)
        segments = load_segments(args.segments)
        output_dir = args.output_dir.expanduser().resolve()
        manifest_path = (
            args.manifest.expanduser().resolve()
            if args.manifest
            else output_dir / "manifest.json"
        )
        _prepare_outputs(
            segments,
            args.segments.expanduser().resolve(),
            output_dir,
            manifest_path,
            overwrite=args.overwrite,
        )

        if args.offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        np, sf, pipeline_class = _load_runtime()
        pipelines: dict[str, Any] = {}

        def pipeline_for(lang_code: str) -> Any:
            if lang_code not in pipelines:
                try:
                    pipelines[lang_code] = pipeline_class(
                        lang_code=lang_code,
                        repo_id=args.model,
                    )
                except Exception as exc:
                    cache_hint = (
                        " The requested assets were not found in the Hugging Face cache."
                        if args.offline
                        else " The first run may need network access to download model assets."
                    )
                    raise ManifestError(
                        f"could not initialize Kokoro for lang_code={lang_code!r}: "
                        f"{exc}.{cache_hint}"
                    ) from exc
            return pipelines[lang_code]

        for index, segment in enumerate(segments, start=1):
            voice, lang_code, info = resolve_voice(
                segment.voice or args.voice,
                override_lang_code=args.lang_code,
                allow_unknown=args.allow_unknown_voice,
            )
            if info is None:
                print(
                    f"warning: {voice!r} is not in the bundled Kokoro catalog; "
                    f"using lang_code={lang_code!r}. Pass --list-voices to see "
                    "known ids.",
                    file=sys.stderr,
                    flush=True,
                )
            output_path = output_dir / f"{segment.id}.wav"
            print(
                f"[{index}/{len(segments)}] {segment.id} ({voice}, {lang_code})",
                flush=True,
            )
            try:
                synthesize_segment(
                    pipeline_for(lang_code),
                    segment.text,
                    voice,
                    args.speed,
                    output_path,
                    np=np,
                    sf=sf,
                )
            except ManifestError as exc:
                raise ManifestError(f"segment {segment.id!r}: {exc}") from exc

        manifest = build_manifest(
            segments,
            output_dir,
            padding=args.padding,
            default_voice=args.voice,
            manifest_path=manifest_path,
        )
        write_manifest(manifest, manifest_path, overwrite=args.overwrite)
    except (ManifestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {len(segments)} WAV files and {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
