"""Phase 30 — full autonomous production DRY-RUN (integration).

Director -> Arsenal-X HTTP (plan/match/verify) -> reviewer -> repair ->
memory -> controller checkpoint. Media rendering is expected to BLOCK
explicitly (no FFmpeg on this machine); the test asserts the honest
terminal state instead of a fabricated artifact.
"""
import json
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from engine.autonomy import controller, director, memory
from engine.core.project_store import create_project, write_artifact
from engine.review import repair, reviewer

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
AX = Path("F:/Arsenal/_projects/arsenal-x")
PORT = 8791
BASE = f"http://localhost:{PORT}"


def _get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


def _wait_port(timeout_s=120):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=2).close()
            return True
        except OSError:
            time.sleep(2)
    return False


def test_p30_dryrun_chain():
    proc = subprocess.Popen(
        ["D:/node.js/node.exe", "./node_modules/next/dist/bin/next",
         "dev", "--port", str(PORT)],
        cwd=str(AX), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_port(), "arsenal-x dev server did not start (ENVIRONMENT_FAILURE)"
        # 1. director
        plan = director.plan_production(
            "The speaker explains AI infrastructure.", style="cinematic",
            duration_s=60.0, platform="youtube")
        assert plan["asset_requirements"]
        # 2-4. asset chain over HTTP for two BROLL requirements
        chain = []
        for req in [r for r in plan["asset_requirements"]
                    if r["kind"] == "BROLL"][:2]:
            m = _get("/api/match", {"intent": req["request"]["intent"],
                                    "type": "video", "limit": 3})
            assert m["total"] > 0
            top = m["candidates"][0]
            assert top["match_reasons"], "candidate without evidence"
            v = _get("/api/verify", {"path": top["path"], "ar": "16:9"})
            assert v["verdict"] in ("PASS", "CAUTION", "REJECT", "UNKNOWN")
            chain.append({"requirement": req["id"], "candidate": top["path"],
                          "score": top["score"], "verdict": v["verdict"]})
        assert len(chain) == 2
        # 5. hand project + review + repair + memory
        pid = create_project(str(FIX / "tone_5s.mp4")).id
        write_artifact(pid, "edit", "edit_decision.json",
                       {"decisions": [{"decision_id": "k", "action": "KEEP",
                                        "start": 0, "end": 5, "reason": "t"}],
                        "duration": 5.0})
        rev = reviewer.review_project(pid)
        assert rev["verdict"] in ("PASS", "REVIEW", "FAIL")
        rep = repair.plan_repair(pid, rev["payload"])
        assert rep["action"] in ("REPAIR_PLANNED", "NONE",
                                 "BLOCKED_REQUIRES_HUMAN_REVIEW")
        memory.remember(pid, "project_config",
                        {"idea": plan["idea"], "style": "cinematic"})
        for c in chain:
            memory.remember(pid, "asset_selected",
                            {"asset_id": c["candidate"],
                             "score": c["score"]})
        # 6. controller orchestration with honest render gate
        log = []

        def runner(name, status, **kw):
            def _run(p, state):
                log.append(name)
                return {"status": status, **kw}
            return _run

        st = controller.run_pipeline(
            pid,
            ["preproduction", "assets", "review", "render", "final"],
            {"preproduction": runner("preproduction", "OK"),
             "assets": runner("assets", "OK", candidates=len(chain)),
             "review": runner("review", "OK", verdict=rev["verdict"]),
             "render": runner("render", "BLOCKED",
                              reason="ffmpeg MISSING: render blocked"),
             "final": runner("final", "OK")})
        assert st["status"] == "BLOCKED"  # render gate holds; final never ran
        assert "final" not in log and "render" in log
        assert controller.recover(pid)["status"] == "BLOCKED"
        assert len(memory.recall(pid)) == 3
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
