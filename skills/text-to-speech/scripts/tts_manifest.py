#!/usr/bin/env python3
"""Validate narration segments and build timing metadata from WAV files."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
VOICE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
MAX_TEXT_LENGTH = 100_000


class ManifestError(ValueError):
    """Raised when segment input or audio metadata is invalid."""


@dataclass(frozen=True)
class Segment:
    id: str
    text: str
    voice: str | None = None


def _require_regular_file(path: Path, label: str) -> Path:
    path = path.expanduser()
    if not path.exists():
        raise ManifestError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise ManifestError(f"{label} is not a regular file: {path}")
    return path.resolve()


def _validate_segment(raw: Any, index: int) -> Segment:
    label = f"segment {index + 1}"
    if not isinstance(raw, dict):
        raise ManifestError(f"{label} must be a JSON object")

    unknown = set(raw) - {"id", "text", "voice"}
    if unknown:
        names = ", ".join(sorted(str(name) for name in unknown))
        raise ManifestError(f"{label} has unsupported field(s): {names}")

    segment_id = raw.get("id")
    if not isinstance(segment_id, str) or not ID_PATTERN.fullmatch(segment_id):
        raise ManifestError(
            f"{label} id must match {ID_PATTERN.pattern!r}; got {segment_id!r}"
        )

    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ManifestError(f"{label} ({segment_id!r}) text must be a non-empty string")
    if "\x00" in text:
        raise ManifestError(f"{label} ({segment_id!r}) text must not contain NUL bytes")
    if len(text) > MAX_TEXT_LENGTH:
        raise ManifestError(
            f"{label} ({segment_id!r}) text exceeds {MAX_TEXT_LENGTH} characters"
        )

    voice = raw.get("voice")
    if voice is not None and (
        not isinstance(voice, str) or not VOICE_PATTERN.fullmatch(voice)
    ):
        raise ManifestError(
            f"{label} ({segment_id!r}) voice must match "
            f"{VOICE_PATTERN.pattern!r}; got {voice!r}"
        )

    return Segment(id=segment_id, text=text.strip(), voice=voice)


def load_segments(path: Path) -> list[Segment]:
    """Load and validate a JSON list or an object containing `segments`."""
    input_path = _require_regular_file(path, "segment input")
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ManifestError(f"segment input is not valid UTF-8: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"invalid JSON in {input_path} at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc

    if isinstance(data, dict):
        unknown = set(data) - {"segments"}
        if unknown:
            names = ", ".join(sorted(str(name) for name in unknown))
            raise ManifestError(f"segment input has unsupported top-level field(s): {names}")
        data = data.get("segments")

    if not isinstance(data, list):
        raise ManifestError("segment input must be a JSON list or an object with a segments list")
    if not data:
        raise ManifestError("segment input contains no segments")

    segments = [_validate_segment(raw, index) for index, raw in enumerate(data)]
    seen: set[str] = set()
    for segment in segments:
        if segment.id in seen:
            raise ManifestError(f"duplicate segment id: {segment.id!r}")
        seen.add(segment.id)
    return segments


def wav_duration(path: Path) -> float:
    """Return measured duration for an uncompressed WAV file."""
    wav_path = _require_regular_file(path, "WAV file")
    try:
        with wave.open(str(wav_path), "rb") as audio:
            frame_rate = audio.getframerate()
            frame_count = audio.getnframes()
            if frame_rate <= 0:
                raise ManifestError(f"WAV file has an invalid sample rate: {wav_path}")
            duration = frame_count / frame_rate
    except (wave.Error, EOFError) as exc:
        raise ManifestError(f"invalid or unsupported WAV file {wav_path}: {exc}") from exc

    if not math.isfinite(duration) or duration <= 0:
        raise ManifestError(f"WAV file has no measurable audio frames: {wav_path}")
    return duration


def _seconds(value: float) -> float:
    return round(value, 6)


def build_manifest(
    segments: Sequence[Segment],
    audio_dir: Path,
    *,
    padding: float = 0.0,
    default_voice: str | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Build timeline metadata using measured `<segment-id>.wav` durations."""
    if not math.isfinite(padding) or padding < 0:
        raise ManifestError("padding must be a finite, non-negative number")
    if default_voice is not None and not VOICE_PATTERN.fullmatch(default_voice):
        raise ManifestError(f"default voice is invalid: {default_voice!r}")
    if not segments:
        raise ManifestError("cannot build a manifest without segments")

    audio_dir = audio_dir.expanduser().resolve()
    base_dir = (manifest_path or (audio_dir / "manifest.json")).expanduser().resolve().parent
    cursor = 0.0
    entries: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        wav_path = audio_dir / f"{segment.id}.wav"
        duration = wav_duration(wav_path)
        padding_after = padding if index < len(segments) - 1 else 0.0
        end = cursor + duration
        try:
            relative_file = os.path.relpath(wav_path, base_dir)
        except ValueError as exc:
            raise ManifestError(
                f"cannot express WAV path relative to manifest: {wav_path}"
            ) from exc

        entries.append(
            {
                "sequence": index + 1,
                "id": segment.id,
                "text": segment.text,
                "voice": segment.voice or default_voice,
                "file": Path(relative_file).as_posix(),
                "start_seconds": _seconds(cursor),
                "audio_duration_seconds": _seconds(duration),
                "padding_after_seconds": _seconds(padding_after),
                "end_seconds": _seconds(end),
            }
        )
        cursor = end + padding_after

    return {
        "schema_version": 1,
        "default_voice": default_voice,
        "padding_seconds": _seconds(padding),
        "total_duration_seconds": _seconds(cursor),
        "segments": entries,
    }


def write_manifest(manifest: dict[str, Any], output_path: Path, *, overwrite: bool) -> None:
    """Atomically write a manifest, protecting existing output by default."""
    output_path = output_path.expanduser().resolve()
    if output_path.exists() and not overwrite:
        raise ManifestError(
            f"manifest already exists: {output_path} (pass --overwrite to replace it)"
        )
    if output_path.exists() and not output_path.is_file():
        raise ManifestError(f"manifest output is not a regular file: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a narration timing manifest from existing segment WAV files."
    )
    parser.add_argument("segments", type=Path, help="JSON segment list")
    parser.add_argument("audio_dir", type=Path, help="directory containing <id>.wav files")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="output path (default: <audio-dir>/manifest.json)",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.0,
        help="timeline gap after each non-final segment in seconds",
    )
    parser.add_argument("--voice", help="default voice recorded for segments without one")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing manifest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        segments = load_segments(args.segments)
        output_path = args.manifest or (args.audio_dir / "manifest.json")
        resolved_output = output_path.expanduser().resolve()
        resolved_input = args.segments.expanduser().resolve()
        wav_paths = {
            (args.audio_dir / f"{segment.id}.wav").expanduser().resolve()
            for segment in segments
        }
        if resolved_output == resolved_input:
            raise ManifestError(f"manifest path collides with segment input: {resolved_output}")
        if resolved_output in wav_paths:
            raise ManifestError(
                f"manifest path collides with a segment WAV: {resolved_output}"
            )
        manifest = build_manifest(
            segments,
            args.audio_dir,
            padding=args.padding,
            default_voice=args.voice,
            manifest_path=output_path,
        )
        write_manifest(manifest, output_path, overwrite=args.overwrite)
    except (ManifestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"Wrote {len(segments)} segment timings to "
        f"{output_path.expanduser().resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
