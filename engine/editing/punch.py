"""Talking-head punch-in reframing (planner + approved post-process stage).

Planning is pure and deterministic: punch ranges derive from sentence
terminals + pauses in the transcript, spaced apart, scaled by phrase
length. Execution reuses gateway primitives only (trim + apply_vf crop /
scale + concat) — the same post-process pattern as the burned-in caption
layer. No new renderer, no new gateway.

Face safety: the crop centers on an explicit focus point (default frame
center). Productions pass a measured focus; the plan records it, so the
choice is auditable, never a hidden guess.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path

from engine.core.logging_utils import log_event
from engine.core.models import PunchApproval, PunchPlan, PunchRange
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)

PUNCH_VERSION = "1.0.0"
ENGINE_TAG = "punch-1.0"
BASE_SCALE = 1.08
EMPHASIS_SCALE = 1.12
MIN_GAP_S = 8.0
MIN_PHRASE_S = 3.0
MAX_PUNCH_S = 20.0
MAX_PUNCHES = 10


class PunchError(RuntimeError):
    """Punch planning/approval/execution failure."""


def _r6(x: float) -> float:
    return round(float(x), 6)


def _hex(payload) -> str:
    import hashlib
    import json as _json
    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def plan_punch_ins(transcript: dict | None, duration: float,
                   focus: tuple[float, float] = (0.5, 0.5),
                   min_gap: float = MIN_GAP_S,
                   max_punches: int = MAX_PUNCHES) -> PunchPlan:
    """Derive punch ranges from sentence terminals + pauses (pure)."""
    if not (0.0 < focus[0] < 1.0 and 0.0 < focus[1] < 1.0):
        raise PunchError(f"focus must be inside frame, got {focus}")
    if duration <= 0:
        raise PunchError("invalid duration")
    words = []
    for seg in (transcript.get("segments", []) or []) if transcript else []:
        for w in seg.get("words", []) or []:
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            # engine transcripts use "word"; caption refs use "text"
            text = str(w.get("text", w.get("word", "")))
            if we > ws and text.strip():
                words.append({"text": text, "start": ws, "end": we})
    words.sort(key=lambda w: (w["start"], w["end"]))
    # phrases: split at sentence terminals; long word gaps (>= 0.8 s) act
    # as sentence proxies for unpunctuated transcripts (tiny-model Arabic).
    phrases = []
    cur = []
    prev_end = None
    for w in words:
        if cur and prev_end is not None and w["start"] - prev_end >= 0.8:
            phrases.append(cur)
            cur = []
        cur.append(w)
        prev_end = w["end"]
        if w["text"].rstrip().endswith((".", "!", "?", "。", "؟")):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    candidates = []
    for ph in phrases:
        s, e = ph[0]["start"], ph[-1]["end"]
        if e - s >= MIN_PHRASE_S and s >= 0 and e <= duration + 0.05:
            # start punch slightly after phrase start (settle-in), never
            # before speech begins
            candidates.append({"start": _r6(s), "end": _r6(min(e, duration)),
                               "length": round(e - s, 3)})
    # longest-first greedy with spacing, then chronological
    candidates.sort(key=lambda c: (-c["length"], c["start"]))
    accepted = []
    for c in candidates:
        if len(accepted) >= max_punches:
            break
        if all(abs(c["start"] - a["start"]) >= min_gap for a in accepted):
            scale = EMPHASIS_SCALE if c["length"] >= 12.0 else BASE_SCALE
            # a punch is a moment, not a chapter: cap single-punch length
            # at the phrase opening (remainder returns to normal framing)
            end = min(c["end"], c["start"] + MAX_PUNCH_S)
            accepted.append({"start": c["start"], "end": end,
                             "scale": scale,
                             "reason": "sentence-boundary phrase; "
                             f"{c['length']}s uninterrupted",
                             "confidence": 0.65 if scale == BASE_SCALE else 0.7})
    accepted.sort(key=lambda c: c["start"])
    return PunchPlan(focus_x=focus[0], focus_y=focus[1],
                     ranges=[PunchRange(**a) for a in accepted])


def punch_filter(width: int, height: int, scale: float,
                 cx: float, cy: float) -> str:
    """Deterministic crop+scale filter preserving output dimensions."""
    if scale < 1.0:
        raise PunchError(f"scale must be >= 1.0, got {scale}")
    cw = max(2, int(width / scale) // 2 * 2)
    ch = max(2, int(height / scale) // 2 * 2)
    x = min(max(int(cx * width - cw / 2), 0), width - cw)
    y = min(max(int(cy * height - ch / 2), 0), height - ch)
    x -= x % 2
    y -= y % 2
    return f"crop={cw}:{ch}:{x}:{y},scale={width}:{height}:flags=lanczos"


def map_punches_to_output(punches: list[dict],
                          keeps: list[tuple]) -> tuple[list[dict], list[dict]]:
    """Translate source-timed punches into output-timed ranges.

    keeps: [(source_start, source_end, output_start, output_end), ...].
    A punch fully inside one keep maps linearly; a punch straddling a cut
    is shrunk to the largest surviving sub-span (>= 1 s) or dropped with
    an explicit record. Returns (mapped, dropped).
    """
    mapped, dropped = [], []
    for p in punches:
        s, e = float(p["start"]), float(p["end"])
        best = None
        for ks, ke, os, oe in keeps:
            lo, hi = max(s, ks), min(e, ke)
            if hi - lo <= 1e-3:
                continue
            cov = hi - lo
            if best is None or cov > best[0]:
                best = (cov, ks, ke, os, lo, hi)
        if best is None:
            dropped.append({**p, "reason": "punch fully removed by cuts"})
            continue
        _, ks, ke, os, lo, hi = best
        if lo > s + 1e-3 or hi < e - 1e-3:
            if hi - lo < 1.0:
                dropped.append({**p, "reason": "punch cut below 1 s by edits"})
                continue
            p = {**p, "start": _r6(lo), "end": _r6(hi),
                 "reason": p.get("reason", "") + " [shrunk to surviving span]",
                 "warnings": ["shrunk by edit decision"]}
        off = os - ks
        mapped.append({**p, "source_start": p["start"],
                       "source_end": p["end"],
                       "start": _r6(lo + off), "end": _r6(hi + off)})
    mapped.sort(key=lambda m: m["start"])
    return mapped, dropped


def apply_punch_ins(src, punches: list[dict], dst, *,
                    width: int, height: int, duration: float,
                    encoder: str = "auto",
                    preset: str = "veryfast", timeout: int = 600,
                    log_file=None) -> Path:
    """Apply approved punches via trim + apply_vf + concat (gateway only)."""
    from engine.rendering.ffmpeg import apply_vf, concat, trim
    src_p, dst_p = Path(src), Path(dst)
    if width <= 0 or height <= 0:
        raise PunchError("invalid frame dimensions")
    if duration <= 0:
        raise PunchError("invalid duration")
    bounds = sorted({0.0, _r6(duration)} | {float(p["start"]) for p in punches} |
                    {float(p["end"]) for p in punches})
    work = dst_p.parent / f"_punch_{time.time_ns()}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        parts = []
        for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
            if b - a <= 1e-3:
                continue
            seg = work / f"seg{i:03d}.mp4"
            trim(src_p, a, b, seg, encoder=encoder, preset=preset,
                 timeout=timeout, log_file=log_file)
            hit = next((p for p in punches
                        if abs(float(p["start"]) - a) < 1e-3
                        and abs(float(p["end"]) - b) < 1e-3), None)
            if hit is None:
                parts.append(seg)
                continue
            vf = punch_filter(width, height, float(hit["scale"]),
                              float(hit.get("cx", 0.5)),
                              float(hit.get("cy", 0.5)))
            out = work / f"punch{i:03d}.mp4"
            apply_vf(seg, vf, out, encoder=encoder, preset=preset,
                     timeout=timeout, log_file=log_file)
            parts.append(out)
        if not parts:
            raise PunchError("no segments to render")
        # Stream-copy concat: all parts share codec/resolution/rate by
        # construction (same encoder settings throughout), so re-encoding
        # would only risk frame drops (observed: QSV concat re-encode drops
        # ~2% across 21 parts) and AAC padding accumulation. Copy is exact.
        return concat(parts, dst_p, reencode=False,
                      timeout=timeout, log_file=log_file)
    finally:
        for p in work.glob("*.mp4"):
            p.unlink(missing_ok=True)
        try:
            work.rmdir()
        except OSError:
            pass


def _plan_hash(plan: dict) -> str:
    return _hex({k: v for k, v in plan.items() if k != "cached"})


def approve_punch_plan(project_id: str, focus: tuple[float, float] = (0.5, 0.5),
                       approver: str = "operator") -> dict:
    """Plan from transcript + explicit approval (focus recorded)."""
    import json
    from engine.editing.decisions import hash_analysis
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    t0 = time.perf_counter()
    try:
        transcript = json.loads(
            (project_dir(pid) / "analysis" / "transcript.json")
            .read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PunchError(f"transcript unreadable: {exc}") from exc
    edl = json.loads((project_dir(pid) / "edit" / "edit_decision.json")
                     .read_text(encoding="utf-8"))
    duration = float(edl.get("duration") or 0)
    plan = plan_punch_ins(transcript, duration, focus=focus)
    payload = asdict(plan)
    payload["transcript_hash"] = hash_analysis(transcript)
    payload["duration"] = duration
    write_artifact(pid, "editing", "punch_plan.json", payload)
    approval = PunchApproval(
        project_id=pid, plan_hash=_plan_hash(payload),
        transcript_hash=payload["transcript_hash"],
        focus_x=focus[0], focus_y=focus[1], approver=approver)
    import datetime
    approval.approved_at = datetime.datetime.now(
        datetime.timezone.utc).isoformat()
    apayload = asdict(approval)
    write_artifact(pid, "editing", "approved_punch_plan.json", apayload)
    mark_stage(project, "punch_approval", "done",
               "editing/approved_punch_plan.json")
    log_event(log_file, "punch", "approve", "ok",
              time.perf_counter() - t0,
              "editing/approved_punch_plan.json",
              {"engine": ENGINE_TAG},
              {"ranges": len(plan.ranges)})
    return {"project": pid, "approval": apayload, "plan": payload}


def validate_punch_approval(project_id: str) -> dict:
    """Revalidate plan hash + transcript binding."""
    import json
    from engine.editing.decisions import hash_analysis
    project = load_project(project_id)
    pid = project.id
    approval = json.loads(
        (project_dir(pid) / "editing" / "approved_punch_plan.json")
        .read_text(encoding="utf-8"))
    if approval.get("schema_version") != "punch-approval-1.0":
        raise PunchError("unsupported punch approval schema")
    plan = json.loads((project_dir(pid) / "editing" / "punch_plan.json")
                      .read_text(encoding="utf-8"))
    if _plan_hash(plan) != approval.get("plan_hash"):
        raise PunchError("punch plan changed: re-approve")
    transcript = json.loads(
        (project_dir(pid) / "analysis" / "transcript.json")
        .read_text(encoding="utf-8"))
    if hash_analysis(transcript) != approval.get("transcript_hash"):
        raise PunchError("transcript changed: re-approve punch plan")
    return {"approval": approval, "plan": plan}
