"""Phase 25 — independent reviewer (new package, additive only).

Evaluates produced artifacts INDEPENDENTLY: it recomputes every check from
source files and never trusts editor decisions, manifests, or prior QC
verdicts as truth. Approval-state validators are reused (they report facts
about files, not editorial judgment).

Verdicts per check: PASS | REVIEW | FAIL | UNKNOWN.
Report verdict: FAIL if any FAIL; REVIEW if any REVIEW or any UNKNOWN;
PASS only when everything verifiable passes and nothing is unknown.

Media-stream inspection needs ffprobe. When absent, stream checks report
UNKNOWN (explicit) — the report can never be PASS on uninspected media.
"""
from __future__ import annotations

import time
from dataclasses import asdict

from engine.core.models import QCCheck, QCReport
from engine.core.project_store import load_project, project_dir

REVIEWER_VERSION = "1.0.0"
ENGINE_TAG = "phase25-1.0"

CATEGORIES = ("technical", "editing", "captions", "visual", "audio",
              "provenance")


class ReviewError(RuntimeError):
    """Reviewer infrastructure failure (not a review verdict)."""


def _ffprobe_present() -> bool:
    try:
        from engine.core.media import ffprobe_path
        return ffprobe_path() is not None
    except Exception:
        return False


def _read_json(path, default=None):
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _srt_cues(path):
    """Independent SRT parse (not the editor's writer)."""
    import re
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    blocks = re.split(r"\r?\n\r?\n", text.strip())
    cues = []
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 2:
            continue
        m = re.search(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
                      r"(\d{2}:\d{2}:\d{2}[,.]\d{3})", lines[1])
        if not m:
            continue
        cues.append({"start": _ts(m.group(1)), "end": _ts(m.group(2)),
                     "text": "\n".join(lines[2:])})
    return cues


def _ts(s: str) -> float:
    s = s.replace(",", ".")
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def review_project(project_id: str) -> dict:
    """Independently review a project's produced artifacts."""
    project = load_project(project_id)
    pid = project.id
    proot = project_dir(pid)
    checks: list[QCCheck] = []

    def _add(category: str, name: str, verdict: str, evidence: str):
        checks.append(QCCheck(name=f"{category}:{name}", passed=(verdict == "PASS"),
                              detail=f"{verdict} | {evidence}"))

    # ---- technical: file existence (independent of manifests) ----
    renders = sorted((proot / "renders").glob("*.mp4")) if \
        (proot / "renders").is_dir() else []
    if not renders:
        _add("technical", "output_exists", "FAIL", "no .mp4 in renders/")
    else:
        _add("technical", "output_exists", "PASS",
             f"{len(renders)} file(s), latest non-empty="
             f"{renders[-1].stat().st_size > 0}")
        if renders[-1].stat().st_size == 0:
            _add("technical", "output_nonempty", "FAIL", "latest render is 0 bytes")
        else:
            _add("technical", "output_nonempty", "PASS", "latest render non-empty")
    if _ffprobe_present():
        _add("technical", "stream_probe", "REVIEW",
             "probe available but stream review not implemented in Phase 25")
    else:
        _add("technical", "stream_probe", "UNKNOWN",
             "ffprobe absent: codec/resolution/fps/sync unverifiable")

    # ---- editing: EDL sanity recomputed from the base file ----
    edl = _read_json(proot / "edit" / "edit_decision.json")
    if not edl:
        _add("editing", "edl_present", "FAIL", "edit/edit_decision.json missing/unreadable")
    else:
        decs = edl.get("decisions", []) or []
        bad = [d for d in decs
               if not (float(d.get("end", 0)) > float(d.get("start", 0)))]
        _add("editing", "edl_intervals", "PASS" if not bad else "FAIL",
             f"{len(decs)} decisions, {len(bad)} invalid intervals")
        cont = all(float(decs[i + 1].get("start", -1)) >=
                   float(decs[i].get("end", -1)) - 0.05
                   for i in range(len(decs) - 1)) if len(decs) > 1 else True
        _add("editing", "edl_order", "PASS" if cont else "REVIEW",
             "decisions ordered" if cont else "possible overlap/regression")

    # ---- captions: independent SRT audit ----
    srt = sorted((proot / "captions").glob("*.srt")) + \
        sorted((proot / "renders").glob("*.srt"))
    plan = _read_json(proot / "captions" / "caption_plan.json")
    if plan is None and not srt:
        _add("captions", "presence", "REVIEW", "no caption plan or sidecar found")
    else:
        if srt:
            cues = _srt_cues(srt[-1])
            if cues is None:
                _add("captions", "sidecar_parse", "FAIL", "SRT unreadable")
            else:
                over = sum(1 for a, b in zip(cues, cues[1:])
                           if b["start"] < a["end"] - 1e-3)
                empty = sum(1 for c in cues if not c["text"].strip())
                bad_iv = sum(1 for c in cues if c["end"] <= c["start"])
                _add("captions", "sidecar_overlap",
                     "PASS" if over == 0 else "FAIL", f"{over} overlaps in {len(cues)} cues")
                _add("captions", "sidecar_intervals",
                     "PASS" if bad_iv == 0 else "FAIL", f"{bad_iv} cues with end<=start")
                _add("captions", "sidecar_empty",
                     "PASS" if empty == 0 else "FAIL", f"{empty} empty cues")
                fast = [c for c in cues
                        if (c["end"] - c["start"]) > 0 and
                        len(c["text"]) / (c["end"] - c["start"]) > 25.0]
                _add("captions", "sidecar_readspeed",
                     "PASS" if not fast else "REVIEW",
                     f"{len(fast)} cues over 25 cps" if fast else "all cues readable")
        if plan is not None:
            try:
                from engine.subtitles.captions import validate_captions_approval
                validate_captions_approval(pid)
                _add("captions", "approval_valid", "PASS", "caption approval bindings hold")
            except Exception as exc:
                _add("captions", "approval_valid", "FAIL", f"caption approval broken: {exc}")

    # ---- visual: black/frozen frames need decode; placement files checked ----
    if _ffprobe_present():
        _add("visual", "frame_health", "REVIEW", "decode review not implemented in Phase 25")
    else:
        _add("visual", "frame_health", "UNKNOWN", "no decode without ffprobe")
    vis_plan = (proot / "captions" / "visual_caption_plan.json").is_file()
    vis_appr = (proot / "captions" / "approved_visual_caption_plan.json").is_file()
    if vis_plan and not vis_appr:
        _add("visual", "placement_approval", "REVIEW", "visual plan present but unapproved")
    elif vis_plan:
        _add("visual", "placement_approval", "PASS", "visual approval present")
    else:
        _add("visual", "placement_approval", "PASS", "no visual plan (nothing to approve)")

    # ---- audio: stream-level needs ffprobe ----
    if _ffprobe_present():
        _add("audio", "stream_check", "REVIEW", "audio review not implemented in Phase 25")
    else:
        _add("audio", "stream_check", "UNKNOWN", "codec/clipping/loudness unverifiable")

    # ---- provenance: approvals must exist and validate ----
    for label, loader in (
            ("pacing_approval", "editing/approved_caption_pacing_plan.json"),
            ("execution_approval", "editing/approved_caption_pacing_execution.json")):
        if not (proot / loader).is_file():
            _add("provenance", label, "REVIEW", f"{loader} absent")
    try:
        from engine.editing.caption_pacing import validate_caption_pacing_approval
        if (proot / "editing" / "approved_caption_pacing_plan.json").is_file():
            validate_caption_pacing_approval(pid)
            _add("provenance", "pacing_bindings", "PASS", "pacing approval bindings hold")
    except Exception as exc:
        _add("provenance", "pacing_bindings", "FAIL", f"pacing approval broken: {exc}")

    verdict = "PASS"
    for c in checks:
        status = c.detail.split(" | ", 1)[0]
        if status == "FAIL":
            verdict = "FAIL"
            break
    if verdict != "FAIL" and any(c.detail.split(" | ", 1)[0] in ("REVIEW", "UNKNOWN")
                                 for c in checks):
        verdict = "REVIEW"
    report = QCReport(verdict=verdict,
                      suggested_fix="" if verdict == "PASS" else
                      "see failing/review checks",
                      checks=checks)
    payload = {"schema_version": "independent-review-1.0",
               "project": pid, "reviewer_version": REVIEWER_VERSION,
               "ffprobe_present": _ffprobe_present(),
               "verdict": verdict, "checks": [asdict(c) for c in checks]}
    from engine.core.project_store import write_artifact
    write_artifact(pid, "qc", "independent_review.json", payload)
    return {"project": pid, "verdict": verdict,
            "report": asdict(report), "payload": payload}
