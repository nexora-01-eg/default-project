# -*- coding: utf-8 -*-
"""Bounded VoiceTut audition via the official public Space API (no install).
Generates the SAME controlled script for each listed male voice, saves WAVs.
Usage: python run_audition.py [Voice1 Voice2 ...]  (default: all 11 male voices)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

HOST = "https://mohammedaly22-voicetut-tts.hf.space"
ENDPOINT = "run_b_oneshot"

AUDITION_SCRIPT = (
    "بص يا جماعة، الموضوع مش مجرد hype عابر. "
    "الذكاء الاصطناعي بدأ يدخل فعليًا في الـworkflow بتاع صناعة الفيديو، "
    "وده معناه إن الشغل اللي كان بياخد ساعات ممكن يخلص في وقت أقل بكتير. "
    "لكن في النهاية، الـcreative decision لسه عند الإنسان، "
    "والتكنولوجيا دي مجرد tool في إيده."
)

MALE_VOICES = ["Abdelrahman", "Abdullah", "Kamal", "Hossam", "Mohamed",
               "Omar", "Sayed", "Zaki", "Aly", "Essam", "Ahmed"]

SETTINGS = {"language": "العربية (Egyptian)", "steps": 32,
            "guidance": 2.0, "speed": 1.0, "normalize": True}

OUT_DIR = Path(__file__).resolve().parent / "wavs"


def post_json(url, payload, timeout=120):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call_predict(voice, text, per_call_timeout_s=1500):
    data = [voice, text, SETTINGS["language"], SETTINGS["steps"],
            SETTINGS["guidance"], SETTINGS["speed"], SETTINGS["normalize"]]
    t0 = time.perf_counter()
    submit = post_json(HOST + "/gradio_api/call/" + ENDPOINT,
                       {"data": data})
    event_id = submit.get("event_id")
    if not event_id:
        return {"voice": voice, "ok": False, "error": "no event_id: %s" % submit,
                "elapsed_s": round(time.perf_counter() - t0, 1)}
    url = HOST + "/gradio_api/call/predict/" + event_id
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    deadline = t0 + per_call_timeout_s
    buf = b""
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            while time.perf_counter() < deadline:
                chunk = r.read(65536)
                if not chunk:
                    break
                buf += chunk
                if b"event: complete" in buf or b"event: error" in buf:
                    break
    except Exception as exc:
        return {"voice": voice, "ok": False,
                "error": "stream: %s" % exc,
                "elapsed_s": round(time.perf_counter() - t0, 1)}
    text_buf = buf.decode("utf-8", "replace")
    result = None
    for block in text_buf.split("event:"):
        block = block.strip()
        if block.startswith("complete"):
            lines = [ln[5:].strip() for ln in block.splitlines()
                     if ln.strip().startswith("data:")]
            if lines:
                try:
                    result = json.loads(lines[-1])
                except Exception:
                    result = lines[-1]
        elif block.startswith("error"):
            return {"voice": voice, "ok": False,
                    "error": "server: %s" % block[:500],
                    "elapsed_s": round(time.perf_counter() - t0, 1)}
    elapsed = round(time.perf_counter() - t0, 1)
    if result is None:
        return {"voice": voice, "ok": False, "error": "no complete event",
                "elapsed_s": elapsed}
    audio, info = (result + [None, None])[:2]
    path = (audio or {}).get("path")
    furl = (audio or {}).get("url")
    if not path:
        return {"voice": voice, "ok": False,
                "error": "no audio path: %s" % str(result)[:300],
                "elapsed_s": elapsed}
    dl = furl if (furl or "").startswith("http") else HOST + (furl or "")
    if not furl:
        dl = HOST + "/gradio_api/file=" + path
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = str(OUT_DIR / ("voicetut_%s.wav" % voice))
    urllib.request.urlretrieve(dl, dest)
    return {"voice": voice, "ok": True, "wav": dest, "info": info,
            "elapsed_s": elapsed}


def main():
    voices = sys.argv[1:] or MALE_VOICES
    log = []
    for v in voices:
        print("AUDITION %s ..." % v, flush=True)
        rec = call_predict(v, AUDITION_SCRIPT)
        rec["settings"] = dict(SETTINGS)
        rec["endpoint"] = ENDPOINT
        log.append(rec)
        print(json.dumps(rec, ensure_ascii=True), flush=True)
    (OUT_DIR.parent / "audition_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
