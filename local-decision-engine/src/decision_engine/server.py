"""HTTP service — Jev-wire-compatible API on localhost only (stdlib only).

Routes:
  POST /v1/systemone   one state + N questions -> {model, answers, usage}
  GET  /v1/models      {"models": [...]} incl. jev-latest style aliases
  GET  /healthz        {"ok": true, ...}
  GET  /              pointer (API only, no UI, no database)

Headers: x-typesafe-request-id on every response, x-local-jev-truncated
when the state was shortened. Errors: 422 detail list, 404 unknown model,
503 model_unavailable, 401 when LOCAL_DECISION_API_KEY is set and missing.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .engine import (
    DEFAULT_MODEL,
    MODEL_ALIASES,
    ContextOverflow,
    LocalDecisionEngine,
    QuestionError,
)

REQUEST_ID_HEADER = "x-typesafe-request-id"
MAX_BODY_BYTES = 2_000_000

_engine = LocalDecisionEngine()
_started_at = time.time()


def _send(handler: BaseHTTPRequestHandler, code: int, payload: dict,
          extra: dict | None = None):
    body = json.dumps(payload, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header(REQUEST_ID_HEADER, uuid.uuid4().hex)
    for k, v in (extra or {}).items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.log_message("%s %s -> %s", handler.command, handler.path, code)
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass


def _err(loc, msg, kind="value_error", status=422):
    return status, {"detail": [{"loc": ["body", *loc], "msg": msg, "type": kind}]}


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalDecisionEngine/" + __version__
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep logs machine-readable on stdout
        print(f"[{time.strftime('%H:%M:%S')}]", *args, flush=True)

    def _auth_ok(self) -> bool:
        want = os.environ.get("LOCAL_DECISION_API_KEY")
        if want and self.path.startswith("/v1/"):
            return self.headers.get("Authorization", "") == f"Bearer {want}"
        return True

    def do_GET(self):
        if not self._auth_ok():
            _send(self, 401, {"detail": "Missing or invalid API key."})
            return
        if self.path == "/healthz":
            _send(self, 200, {"ok": True, "version": __version__,
                              "default_model": DEFAULT_MODEL,
                              "uptime_s": round(time.time() - _started_at, 1)})
        elif self.path == "/v1/models":
            cards = list(LocalDecisionEngine.MODELS)
            default = cards[0]
            cards += [{"name": a, "description": f"Alias of {default['name']}.",
                       "release_date": default["release_date"]} for a in MODEL_ALIASES]
            _send(self, 200, {"models": cards})
        elif self.path in ("/", "/docs"):
            _send(self, 200, {"name": "local-decision-engine", "version": __version__,
                              "api": "/v1/systemone", "models": "/v1/models",
                              "health": "/healthz", "ui": "off (API only)"})
        else:
            _send(self, 404, {"detail": "not found"})

    def do_POST(self):
        if self.path != "/v1/systemone":
            _send(self, 404, {"detail": "not found"})
            return
        if not self._auth_ok():
            _send(self, 401, {"detail": "Missing or invalid API key."})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            code, payload = _err(["body"], "empty or oversized request body")
            _send(self, code, payload)
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            code, payload = _err(["body"], "invalid JSON")
            _send(self, code, payload)
            return
        if not isinstance(body, dict):
            code, payload = _err(["body"], "request must be a JSON object")
            _send(self, code, payload)
            return
        state, model, questions = body.get("state"), body.get("model", "jev-latest"), body.get("questions")
        if "questions" not in body or not isinstance(questions, dict) or not questions:
            code, payload = _err(["questions"], "questions must be a non-empty object")
            _send(self, code, payload)
            return
        try:
            t0 = time.time()
            res = _engine.system_one(state, questions, model or "jev-latest")
            latency_ms = round((time.time() - t0) * 1000, 1)
            extra = {"x-local-jev-truncated": "true"} if res.truncated else {}
            print(f"[decision] model={res.model} q={len(questions)} {latency_ms}ms", flush=True)
            _send(self, 200, {"model": res.model, "answers": res.answers,
                              "usage": res.usage}, extra)
        except QuestionError as err:
            code, payload = _err(list(err.loc), err.msg)
            _send(self, code, payload)
        except ContextOverflow as err:
            code, payload = _err(["state"], str(err), "context_length_exceeded")
            _send(self, code, payload)
        except KeyError as err:
            _send(self, 404, {"detail": [{"loc": ["body", "model"], "msg": str(err),
                                          "type": "value_error"}]})
        except RuntimeError as err:
            msg = str(err)
            kind = "model_unavailable" if msg.startswith("model_unavailable") else "internal"
            code = 503 if kind == "model_unavailable" else 500
            _send(self, code, {"detail": [{"loc": ["body", "model"], "msg": msg, "type": kind}]})
        except Exception as err:  # never leak internals
            _send(self, 500, {"detail": [{"loc": ["body"], "msg": "internal error",
                                          "type": "internal"}]})
            print("[error]", str(err)[:300], flush=True)


def run(host: str = "127.0.0.1", port: int = 8765):
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("refusing non-loopback bind (local by default)")
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    print(f"  model     {DEFAULT_MODEL}  (offline, no downloads)", flush=True)
    print(f"  api       http://{host}:{port}/v1/systemone", flush=True)
    print(f"  health    http://{host}:{port}/healthz", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown ok", flush=True)
    finally:
        srv.server_close()


def run_in_background(host="127.0.0.1", port=8765) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
