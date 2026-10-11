# -*- coding: utf-8 -*-
"""ASR-transcribe the 5 audition reference clips (local faster-whisper tiny)."""
import json
from pathlib import Path

AUD = Path(__file__).resolve().parent / "audition"


def main():
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    out = {}
    for v in ("mohamed", "zaki", "kamal", "aly", "omar"):
        path = str(AUD / ("voice_" + v + ".wav"))
        segs, info = model.transcribe(path, language="ar")
        out[v] = {"lang": info.language,
                  "prob": round(float(info.language_probability), 2),
                  "segs": [{"s": round(s.start, 1), "e": round(s.end, 1),
                            "t": s.text} for s in segs]}
    (AUD / "audition_asr.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("transcribed: %s" % sorted(out))


if __name__ == "__main__":
    main()
