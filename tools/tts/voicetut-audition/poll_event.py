# -*- coding: utf-8 -*-
"""Poll a Gradio SSE event id until complete/error/deadline. Prints result."""
import sys
import time
import urllib.request

HOST = "https://mohammedaly22-voicetut-tts.hf.space"


def main(event_id, deadline_s):
    url = HOST + "/gradio_api/call/predict/" + event_id
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    t0 = time.perf_counter()
    buf = b""
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        while time.perf_counter() - t0 < float(deadline_s):
            try:
                chunk = resp.read(65536)
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            if b"event: complete" in buf or b"event: error" in buf:
                break
    except Exception as exc:
        print("TRANSPORT-ERROR %s" % exc)
        return
    print("ELAPSED %.1f" % (time.perf_counter() - t0))
    print(buf.decode("utf-8", "replace")[-2000:])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "300")
