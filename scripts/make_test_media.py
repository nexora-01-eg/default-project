"""Generate synthetic test media with FFmpeg lavfi (no copyrighted footage needed).

Default: tests/fixtures/sample_10s.mp4 (color bars + tone).
--all: full deterministic fixture set for audio/render tests:
  tone_5s.wav      5 s 440 Hz sine (non-silent, PCM-exact)
  silence_5s.wav   5 s digital silence (PCM-exact)
  mixed_6s.wav     2 s tone + 2 s silence + 2 s tone (PCM-exact concat)
  tone_5s.mp4      640x360 video + tone (file-with-audio video case)
  silent_video.mp4 640x360 video, NO audio stream
  mixed_6s.mp4     640x360 video + mixed audio (render-pipeline case)
  scenes_3x2s.mp4  640x360 red/blue/green 2 s hard cuts (known scene bounds)
  static_3s.mp4    640x360 solid black 3 s (single-scene case)
  short_05s.mp4    640x360 testsrc 0.5 s (very-short case)
  fade_3s.mp4      640x360 white with 1 s fade in/out (fade case)
  static_12s.mp4   640x360 black 12 s + tone (long static scene, plan e2e)
  broll_test.mp4   640x360 testsrc 4 s + 880 Hz tone (local B-roll asset)

WAV fixtures use pcm_s16le (no codec padding -> sample-exact boundaries).
Existing files are skipped (idempotent).

Usage: python scripts/make_test_media.py [--all]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(r.stderr or '')[-1500:]}")


def _build(ffmpeg: str, name: str, cmd: list[str]) -> Path:
    dest = FIX / name
    if dest.is_file():
        print(f"skip (exists) {dest.name}")
        return dest
    print(f"build {dest.name} ...")
    _run([ffmpeg, "-y", *cmd, str(dest)])
    return dest


def build_all(ffmpeg: str) -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    tone = _build(ffmpeg, "tone_5s.wav",
                  ["-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                   "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le"])
    sil = _build(ffmpeg, "silence_5s.wav",
                 ["-f", "lavfi", "-i", "anullsrc=cl=mono:r=44100:d=5",
                  "-c:a", "pcm_s16le"])
    # Mixed 2+2+2 via trim + concat demuxer with -c copy (sample-exact, no re-encode).
    mixed = FIX / "mixed_6s.wav"
    if not mixed.is_file():
        print("build mixed_6s.wav ...")
        parts = []
        for i, (src, ss) in enumerate(((tone, "0"), (sil, "0"), (tone, "0"))):
            if i == 1:
                part = FIX / "_part_sil.wav"
                if not part.is_file():
                    _run([ffmpeg, "-y", "-i", str(src), "-t", "2", "-c:a", "pcm_s16le", str(part)])
            else:
                part = FIX / f"_part_tone{i}.wav"
                if not part.is_file():
                    _run([ffmpeg, "-y", "-i", str(src), "-t", "2", "-c:a", "pcm_s16le", str(part)])
            parts.append(part)
        lst = FIX / "_parts.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
        _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
              "-c:a", "pcm_s16le", str(mixed)])
        for p in parts:
            p.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)
    else:
        print("skip (exists) mixed_6s.wav")

    _build(ffmpeg, "tone_5s.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=5",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
    _build(ffmpeg, "silent_video.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    _build(ffmpeg, "mixed_6s.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=6",
            "-i", str(mixed),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
    _build(ffmpeg, "sample_10s.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
    # Phase 7 scene fixtures: hard cuts via filter concat (frame-exact joins).
    scenes = FIX / "scenes_3x2s.mp4"
    if not scenes.is_file():
        print("build scenes_3x2s.mp4 ...")
        _run([ffmpeg, "-y",
              "-f", "lavfi", "-i", "color=c=red:size=640x360:rate=30:duration=2",
              "-f", "lavfi", "-i", "color=c=blue:size=640x360:rate=30:duration=2",
              "-f", "lavfi", "-i", "color=c=green:size=640x360:rate=30:duration=2",
              "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", str(scenes)])
    else:
        print("skip (exists) scenes_3x2s.mp4")
    _build(ffmpeg, "static_3s.mp4",
           ["-f", "lavfi", "-i", "color=c=black:size=640x360:rate=30:duration=3",
            "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    _build(ffmpeg, "short_05s.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    _build(ffmpeg, "fade_3s.mp4",
           ["-f", "lavfi", "-i", "color=c=white:size=640x360:rate=30:duration=3",
            "-vf", "fade=t=in:st=0:d=1,fade=t=out:st=2:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p"])
    _build(ffmpeg, "static_12s.mp4",
           ["-f", "lavfi", "-i", "color=c=black:size=640x360:rate=30:duration=12",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
    _build(ffmpeg, "broll_test.mp4",
           ["-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
    print("fixtures ready")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="build the full fixture set")
    ns = ap.parse_args(argv)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print("ERROR: ffmpeg not found on PATH.")
        return 2
    try:
        if ns.all:
            return build_all(ffmpeg)
        _build(ffmpeg, "sample_10s.mp4",
               ["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:duration=10",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"])
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
