# -*- coding: utf-8 -*-
"""Harvest per-voice reference metadata (gender + style chips) via preview_reference."""
import json
import urllib.request

HOST = "https://mohammedaly22-voicetut-tts.hf.space"
VOICES = ["Abdelrahman", "Abdullah", "Kamal", "Hossam", "Mohamed",
          "Omar", "Sayed", "Zaki", "Aly", "Essam", "Ahmed"]


def submit(voice):
    payload = {"data": [voice]}
    req = urllib.request.Request(
        HOST + "/gradio_api/call/preview_reference",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))["event_id"]


def poll(event_id, deadline_s=300):
    import time
    url = HOST + "/gradio_api/call/predict/" + event_id
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    t0 = time.perf_counter()
    buf = b""
    with urllib.request.urlopen(req, timeout=120) as r:
        while time.perf_counter() - t0 < deadline_s:
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk
            if b"event: complete" in buf or b"event: error" in buf:
                break
    return buf.decode("utf-8", "replace")


def main():
    out = []
    for v in VOICES:
        try:
            eid = submit(v)
            raw = poll(eid)
            out.append({"voice": v, "event": eid, "raw_tail": raw[-1200:]})
        except Exception as exc:
            out.append({"voice": v, "error": str(exc)})
    print(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    main()
