from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "text-to-speech" / "scripts" / "tts_manifest.py"
SPEC = importlib.util.spec_from_file_location("tts_manifest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
tts_manifest = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tts_manifest
SPEC.loader.exec_module(tts_manifest)


def write_silent_wav(path: Path, duration: float, sample_rate: int = 8_000) -> None:
    frame_count = round(duration * sample_rate)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frame_count)


class TtsManifestTests(unittest.TestCase):
    def test_loads_list_and_object_forms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            list_path = root / "list.json"
            object_path = root / "object.json"
            payload = [
                {"id": "intro", "text": "  Hello.  ", "voice": "af_heart"},
                {"id": "part-2", "text": "Next."},
            ]
            list_path.write_text(json.dumps(payload), encoding="utf-8")
            object_path.write_text(json.dumps({"segments": payload}), encoding="utf-8")

            for path in (list_path, object_path):
                segments = tts_manifest.load_segments(path)
                self.assertEqual([segment.id for segment in segments], ["intro", "part-2"])
                self.assertEqual(segments[0].text, "Hello.")
                self.assertEqual(segments[0].voice, "af_heart")

    def test_rejects_duplicate_and_unsafe_ids(self) -> None:
        cases = [
            [
                {"id": "same", "text": "One"},
                {"id": "same", "text": "Two"},
            ],
            [{"id": "../escape", "text": "No"}],
            [{"id": "/absolute", "text": "No"}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "segments.json"
            for payload in cases:
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(tts_manifest.ManifestError):
                    tts_manifest.load_segments(path)

    def test_rejects_empty_text_unknown_fields_and_bad_voice(self) -> None:
        cases = [
            [{"id": "empty", "text": "  "}],
            [{"id": "extra", "text": "Hi", "command": "echo unsafe"}],
            [{"id": "voice", "text": "Hi", "voice": "../../voice"}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "segments.json"
            for payload in cases:
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(tts_manifest.ManifestError):
                    tts_manifest.load_segments(path)

    def test_measures_wav_and_builds_padded_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio_dir = Path(directory)
            write_silent_wav(audio_dir / "intro.wav", 0.5)
            write_silent_wav(audio_dir / "body.wav", 1.25)
            segments = [
                tts_manifest.Segment("intro", "Hello", "af_heart"),
                tts_manifest.Segment("body", "World"),
            ]

            manifest = tts_manifest.build_manifest(
                segments,
                audio_dir,
                padding=0.2,
                default_voice="am_adam",
            )

            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["total_duration_seconds"], 1.95)
            first, second = manifest["segments"]
            self.assertEqual(first["audio_duration_seconds"], 0.5)
            self.assertEqual(first["padding_after_seconds"], 0.2)
            self.assertEqual(first["start_seconds"], 0.0)
            self.assertEqual(first["end_seconds"], 0.5)
            self.assertEqual(first["voice"], "af_heart")
            self.assertEqual(second["start_seconds"], 0.7)
            self.assertEqual(second["end_seconds"], 1.95)
            self.assertEqual(second["padding_after_seconds"], 0.0)
            self.assertEqual(second["voice"], "am_adam")

    def test_rejects_invalid_wav_and_padding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio_dir = Path(directory)
            invalid = audio_dir / "bad.wav"
            invalid.write_text("not audio", encoding="utf-8")
            segment = tts_manifest.Segment("bad", "Bad")

            with self.assertRaises(tts_manifest.ManifestError):
                tts_manifest.wav_duration(invalid)
            with self.assertRaises(tts_manifest.ManifestError):
                tts_manifest.build_manifest([segment], audio_dir, padding=-0.1)

    def test_manifest_write_requires_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            manifest = {"schema_version": 1, "segments": []}
            tts_manifest.write_manifest(manifest, output, overwrite=False)

            with self.assertRaises(tts_manifest.ManifestError):
                tts_manifest.write_manifest(manifest, output, overwrite=False)

            replacement = {"schema_version": 1, "segments": [{"id": "new"}]}
            tts_manifest.write_manifest(replacement, output, overwrite=True)
            self.assertEqual(json.loads(output.read_text()), replacement)


if __name__ == "__main__":
    unittest.main()
