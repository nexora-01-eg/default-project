"""Concrete provider adapters (lazy imports; safe pre-install).

ffmpeg/whisper/piper/opencv/scenedetect delegate to the existing engine
or validated local paths. TIER 0 providers (librosa, loudness, vad, otio,
svg, rembg, colour, moviepy, pydub, soundfile, jsonschema) activate once
installed; before that they report TOOL_UNAVAILABLE.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import ExecutionAdapter, ToolUnavailable


def _have(module: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(module) is not None


class FFmpegAdapter(ExecutionAdapter):
    provider_id = "ffmpeg"
    capabilities = ("CUT", "TRIM", "CONCAT", "SPEED_CHANGE", "AUDIO_DUCKING",
                    "MIX", "MUX", "BURN_CAPTIONS", "CAMERA_PUSH", "SCOPES")

    def available(self):
        try:
            from engine.rendering.ffmpeg import which_ffmpeg
            exe = which_ffmpeg()
            return (exe is not None, "ffmpeg resolved" if exe else "no ffmpeg")
        except Exception as exc:
            return False, str(exc)

    def run(self, contract):
        self._require()
        from engine.rendering import ffmpeg as F
        op = contract.get("op")
        if op == "camera_push":
            # Deterministic Ken-Burns-style push via zoompan (CPU, in-FFmpeg).
            src, dst = contract["src"], contract["dst"]
            dur = float(contract.get("duration") or F.probe(src).duration or 0)
            n = max(1, int(round(dur * 30)))
            z0, z1 = float(contract.get("zoom_from", 1.0)), float(
                contract.get("zoom_to", 1.12))
            vf = (f"scale=2160:3840,zoompan=z='{z0}+({z1}-{z0})*on/{n}':"
                  f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                  f"s=1080x1920:fps=30")
            F.apply_vf(src, vf, dst,
                       encoder=contract.get("encoder", "libx264"))
            return self.artifact("clip", dst, self.provider_id, op=op,
                                 zoom=(z0, z1))
        if op == "scopes":
            src, dst = contract["src"], contract["dst"]
            F.apply_vf(src, "signalstats,metadata=print", dst)
            return self.artifact("scopes", dst, self.provider_id, op=op)
        raise ToolUnavailable(self.provider_id, f"unknown op {op!r}")


class WhisperAdapter(ExecutionAdapter):
    provider_id = "faster-whisper"
    capabilities = ("SPEECH_TO_TEXT", "WORD_TIMING", "CAPTION_ALIGNMENT")

    def available(self):
        return (_have("faster_whisper"), "faster-whisper import"
                if _have("faster_whisper") else "faster_whisper missing")

    def run(self, contract):
        self._require()
        from engine.analysis.speech import transcribe_file
        t = transcribe_file(contract["src"], model=contract.get("model", "tiny"),
                            language=contract.get("language"),
                            word_timestamps=True)
        words = [{"w": w.word, "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "p": round(float(w.probability or 0.0), 3)}
                 for s in t.segments for w in s.words]
        out = Path(contract.get("out") or
                   (str(Path(contract["src"]).parent / "words.json")))
        out.write_text(json.dumps({"words": words,
                                   "language": t.language}, indent=1),
                       encoding="utf-8")
        return self.artifact("word_timing", out, self.provider_id,
                             words=len(words), language=t.language)


class PiperAdapter(ExecutionAdapter):
    provider_id = "piper"
    capabilities = ("TEXT_TO_SPEECH_AR",)
    EXE = (Path("tools/tts/piper/piper/piper.exe"))
    MODEL = Path("tools/tts/piper/ar_JO-kareem-medium.onnx")
    ESPDATA = Path("tools/tts/piper/piper/espeak-ng-data")

    def available(self):
        ok = self.EXE.is_file() and self.MODEL.is_file()
        return ok, "validated install" if ok else "piper files missing"

    def run(self, contract):
        self._require()
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = contract["text"].encode("utf-8")
        cmd = [str(self.EXE), "--model", str(self.MODEL),
               "--output_file", str(dst),
               "--espeak_data", str(self.ESPDATA),
               "--length_scale", str(contract.get("length_scale", 1.0)),
               "--sentence_silence",
               str(contract.get("sentence_silence", 0.2))]
        r = subprocess.run(cmd, input=data, capture_output=True, timeout=900)
        if r.returncode != 0 or not dst.is_file():
            raise ToolUnavailable(
                self.provider_id, f"piper exit={r.returncode} "
                                  f"{r.stderr.decode()[-300:]}")
        return self.artifact("wav", dst, self.provider_id,
                             chars=len(contract["text"]))


class SceneDetectAdapter(ExecutionAdapter):
    provider_id = "scenedetect"
    capabilities = ("SCENE_DETECTION", "SHOT_DETECTION")

    def available(self):
        return (_have("scenedetect"), "ok" if _have("scenedetect")
                else "scenedetect missing")

    def run(self, contract):
        self._require()
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
        video = open_video(contract["src"])
        mgr = SceneManager()
        mgr.add_detector(ContentDetector(
            threshold=contract.get("threshold", 27.0)))
        mgr.detect_scenes(video)
        scenes = [{"start": round(s[0].get_seconds(), 2),
                   "end": round(s[1].get_seconds(), 2)}
                  for s in mgr.get_scene_list()]
        out = Path(contract.get("out") or
                   (str(Path(contract["src"]).parent / "scenes.json")))
        out.write_text(json.dumps({"scenes": scenes}, indent=1),
                       encoding="utf-8")
        return self.artifact("scenes", out, self.provider_id,
                             count=len(scenes))


class LibrosaAdapter(ExecutionAdapter):
    provider_id = "librosa"
    capabilities = ("BEAT_DETECTION", "ONSET_DETECTION", "AUDIO_ANALYSIS")

    def available(self):
        return (_have("librosa"), "ok" if _have("librosa")
                else "librosa missing")

    def run(self, contract):
        self._require()
        import librosa
        y, sr = librosa.load(contract["src"], sr=contract.get("sr", 22050),
                             mono=True)
        import numpy as _np
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(_np.atleast_1d(tempo)[0])
        onset = librosa.onset.onset_detect(y=y, sr=sr, units="time")
        out = Path(contract.get("out") or
                   (str(Path(contract["src"]).parent / "beats.json")))
        out.write_text(json.dumps(
            {"tempo_bpm": round(tempo, 1),
             "beats_s": [round(float(b), 2) for b in beats],
             "onsets_s": [round(float(o), 2) for o in onset]}, indent=1),
            encoding="utf-8")
        return self.artifact("beats", out, self.provider_id,
                             tempo_bpm=round(tempo, 1))


class LoudnessAdapter(ExecutionAdapter):
    provider_id = "pyloudnorm"
    capabilities = ("LOUDNESS_NORMALIZATION",)

    def available(self):
        return (_have("pyloudnorm") and _have("soundfile"),
                "ok" if (_have("pyloudnorm") and _have("soundfile"))
                else "pyloudnorm/soundfile missing")

    def run(self, contract):
        self._require()
        import soundfile as sf
        import pyloudnorm as pyln
        data, rate = sf.read(contract["src"])
        meter = pyln.Meter(rate)
        loud = meter.integrated_loudness(data)
        norm = pyln.normalize.loudness(
            data, loud, contract.get("target_lufs", -16.0))
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), norm, rate)
        return self.artifact("wav", dst, self.provider_id,
                             measured_lufs=round(float(loud), 1))


class VadAdapter(ExecutionAdapter):
    provider_id = "webrtcvad"
    capabilities = ("VOICE_ACTIVITY",)

    def available(self):
        return (_have("webrtcvad"), "ok" if _have("webrtcvad")
                else "webrtcvad missing")

    def run(self, contract):
        self._require()
        import wave
        import webrtcvad
        vad = webrtcvad.Vad(int(contract.get("aggressiveness", 2)))
        with wave.open(contract["src"], "rb") as w:
            assert w.getframerate() in (8000, 16000, 32000, 48000), \
                "VAD needs 8/16/32/48 kHz mono s16"
            assert w.getnchannels() == 1 and w.getsampwidth() == 2
            rate, n = w.getframerate(), w.getnframes()
            raw = w.readframes(n)
        ms = int(contract.get("frame_ms", 30))
        step = rate * ms // 1000 * 2
        spans, cur = [], None
        for i in range(0, len(raw) - step + 1, step):
            t = (i // 2) / rate
            if vad.is_speech(raw[i:i + step], rate):
                cur = t if cur is None else cur
            elif cur is not None:
                spans.append({"start": round(cur, 2), "end": round(t, 2)})
                cur = None
        if cur is not None:
            spans.append({"start": round(cur, 2),
                          "end": round(len(raw) // 2 / rate, 2)})
        out = Path(contract.get("out") or
                   (str(Path(contract["src"]).parent / "vad.json")))
        out.write_text(json.dumps({"spans": spans}, indent=1),
                       encoding="utf-8")
        return self.artifact("vad", out, self.provider_id,
                             spans=len(spans))


class OtioAdapter(ExecutionAdapter):
    provider_id = "opentimelineio"
    capabilities = ("TIMELINE_IO", "EDL", "OTIO")

    def available(self):
        return (_have("opentimelineio"), "ok" if _have("opentimelineio")
                else "opentimelineio missing")

    def run(self, contract):
        self._require()
        import opentimelineio as otio
        op = contract.get("op", "export")
        if op == "export":
            tl = otio.schema.Timeline(name=contract.get("name", "al-montier"))
            track = otio.schema.Track(name="V1",
                                      kind=otio.schema.TrackKind.Video)
            rate = float(contract.get("fps", 30))
            for seg in contract["segments"]:
                dur = float(seg.get("len") or
                            (seg["span"][1] - seg["span"][0]))
                clip = otio.schema.Clip(
                    name=seg.get("label", "shot"),
                    source_range=otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(0, rate),
                        duration=otio.opentime.RationalTime(
                            round(dur * rate), rate)),
                    metadata={"al_montier": {
                        k: seg[k] for k in ("kind", "file", "span", "label")
                        if k in seg}})
                track.append(clip)
            tl.tracks.append(track)
            dst = Path(contract["dst"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            otio.adapters.write_to_file(tl, str(dst))
            return self.artifact("otio", dst, self.provider_id,
                                 clips=len(contract["segments"]))
        if op == "read":
            tl = otio.adapters.read_from_file(contract["src"])
            clips = [{"name": c.name,
                      "duration_s": round(
                          c.source_range.duration.to_seconds(), 2)}
                     for t in tl.tracks for c in t
                     if isinstance(c, otio.schema.Clip)]
            return self.artifact("timeline", contract["src"],
                                 self.provider_id, clips=clips)
        raise ToolUnavailable(self.provider_id, f"unknown op {op!r}")


class SvgAdapter(ExecutionAdapter):
    provider_id = "svgwrite"
    capabilities = ("SVG_AUTHORING", "CALLOUTS", "ARROWS", "STAT_CARD",
                    "LOWER_THIRDS")

    def available(self):
        return (_have("svgwrite"), "ok" if _have("svgwrite")
                else "svgwrite missing")

    def run(self, contract):
        self._require()
        import svgwrite
        kind = contract.get("kind", "stat_card")
        w, h = int(contract.get("w", 1080)), int(contract.get("h", 1080))
        dwg = svgwrite.Drawing(size=(w, h))
        bg = contract.get("bg", "#0B102E")
        dwg.add(dwg.rect(insert=(0, 0), size=(w, h), fill=bg))
        if kind in ("stat_card", "lower_third", "callout"):
            dwg.add(dwg.text(contract.get("title", ""),
                             insert=(w // 2, h // 2 - 40),
                             text_anchor="middle",
                             font_size=contract.get("title_size", 72),
                             fill=contract.get("fg", "#FFD98A"),
                             font_family="Arial"))
            dwg.add(dwg.text(contract.get("body", ""),
                             insert=(w // 2, h // 2 + 60),
                             text_anchor="middle",
                             font_size=contract.get("body_size", 44),
                             fill="#FFFFFF", font_family="Arial"))
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dwg.saveas(str(dst))
        return self.artifact("svg", dst, self.provider_id, card_kind=kind)


class RembgAdapter(ExecutionAdapter):
    provider_id = "rembg"
    capabilities = ("BACKGROUND_REMOVE",)

    def available(self):
        return (_have("rembg"), "ok" if _have("rembg") else "rembg missing")

    def run(self, contract):
        self._require()
        import os
        from rembg import new_session, remove
        os.environ.setdefault(
            "U2NET_HOME",
            r"F:\Arsenal\07_AI_Models\rembg")
        session = new_session(contract.get("model", "u2net"))
        with open(contract["src"], "rb") as f:
            data = f.read()
        out = remove(data, session=session)
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(out)
        return self.artifact("png", dst, self.provider_id,
                             model=contract.get("model", "u2net"))


class ColourAdapter(ExecutionAdapter):
    provider_id = "colour-science"
    capabilities = ("COLOR_MATCH", "COLOR_ANALYSIS")

    def available(self):
        return (_have("colour"), "ok" if _have("colour") else "colour missing")

    def run(self, contract):
        self._require()
        import cv2
        import numpy as np
        ref = cv2.imread(contract["ref"])
        src = cv2.imread(contract["src"])
        if ref is None or src is None:
            raise ToolUnavailable(self.provider_id, "unreadable image")
        out = {}
        for name, img in (("ref", ref), ("src", src)):
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float64)
            out[name] = {"L_mean": round(float(lab[..., 0].mean()), 1),
                         "sat_proxy": round(float(
                             np.hypot(lab[..., 1] - 128,
                                      lab[..., 2] - 128).mean()), 1)}
        dL = out["ref"]["L_mean"] - out["src"]["L_mean"]
        out["suggested_eq"] = {
            "brightness": round(float(dL / 100), 3),
            "saturation": round(float(out["ref"]["sat_proxy"] /
                                      max(out["src"]["sat_proxy"], 1e-6)), 3)}
        dst = Path(contract.get("out") or
                   (str(Path(contract["src"]).parent / "colormatch.json")))
        dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
        return self.artifact("colormatch", dst, self.provider_id, **out)


class MoviepyAdapter(ExecutionAdapter):
    provider_id = "moviepy"
    capabilities = ("PROGRAMMATIC_EDIT", "COMPOSITE")

    def available(self):
        if not _have("moviepy"):
            return False, "moviepy missing"
        try:
            import PIL
            from packaging.version import Version
            if Version(PIL.__version__) >= Version("12"):
                return False, (f"pillow {PIL.__version__} vs moviepy pin "
                               "<12 — conflict gate")
        except Exception:
            pass
        return True, "ok"

    def run(self, contract):
        self._require()
        from moviepy import VideoFileClip
        op = contract.get("op", "probe")
        if op == "probe":
            with VideoFileClip(contract["src"]) as clip:
                info = {"duration": round(float(clip.duration or 0), 2),
                        "fps": float(clip.fps or 0),
                        "size": [int(clip.w), int(clip.h)]}
            return self.artifact("probe", contract["src"], self.provider_id,
                                 **info)
        raise ToolUnavailable(self.provider_id, f"unknown op {op!r}")


class PydubAdapter(ExecutionAdapter):
    provider_id = "pydub"
    capabilities = ("AUDIO_SEGMENTS", "FADE", "SLICE")

    def available(self):
        return (_have("pydub"), "ok" if _have("pydub") else "pydub missing")

    def run(self, contract):
        self._require()
        from pydub import AudioSegment
        seg = AudioSegment.from_file(contract["src"])
        op = contract.get("op", "slice")
        if op == "slice":
            part = seg[int(contract.get("start_ms", 0)):
                       int(contract.get("end_ms", len(seg)))]
        elif op == "fade":
            part = seg.fade_in(int(contract.get("fade_in_ms", 0))).fade_out(
                int(contract.get("fade_out_ms", 0)))
        else:
            raise ToolUnavailable(self.provider_id, f"unknown op {op!r}")
        dst = Path(contract["dst"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        part.export(str(dst), format=contract.get("format", "wav"))
        return self.artifact("audio", dst, self.provider_id, op=op,
                             ms=len(part))


class JsonschemaAdapter(ExecutionAdapter):
    provider_id = "jsonschema"
    capabilities = ("CONTRACT_VALIDATION",)

    def available(self):
        return (_have("jsonschema"), "ok" if _have("jsonschema")
                else "jsonschema missing")

    def run(self, contract):
        self._require()
        import jsonschema
        doc = contract["document"]
        if isinstance(doc, str):
            doc = json.loads(Path(doc).read_text(encoding="utf-8"))
        schema = contract["schema"]
        if isinstance(schema, str):
            schema = json.loads(Path(schema).read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
        return self.artifact("validation", contract.get("dst", "inline"),
                             self.provider_id, valid=True)


ADAPTERS: dict[str, ExecutionAdapter] = {}


def _register(adapter: ExecutionAdapter) -> None:
    ADAPTERS[adapter.provider_id] = adapter


for _cls in (FFmpegAdapter, WhisperAdapter, PiperAdapter, SceneDetectAdapter,
             LibrosaAdapter, LoudnessAdapter, VadAdapter, OtioAdapter,
             SvgAdapter, RembgAdapter, ColourAdapter, MoviepyAdapter,
             PydubAdapter, JsonschemaAdapter):
    _register(_cls())


def get(provider_id: str) -> ExecutionAdapter:
    try:
        return ADAPTERS[provider_id]
    except KeyError:
        raise ToolUnavailable(provider_id, "no adapter registered")
