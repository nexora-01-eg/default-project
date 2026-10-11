"""Creative Reviewer 2.0 (Phase O): shot-level review, no scene bins.

Reviews at FRAME (sampled facts), SHOT (record), TIMELINE, AUDIO, TEXT,
ASSET, COMPOSITION, MOTION, STORY levels. Every FAIL carries exact time,
affected shot, evidence, likely cause, repair action. No aggregate score
here (see quality_score); a critical FAIL stands alone.
"""
from __future__ import annotations


def _fail(time: float, shot: str, check: str, evidence: str, cause: str,
          repair_capability: str, **repair_kw) -> dict:
    return {"verdict": "FAIL", "time": round(time, 2), "shot": shot,
            "check": check, "evidence": evidence, "likely_cause": cause,
            "repair": {"capability": repair_capability, **repair_kw}}


def _ok(check: str, evidence: str = "") -> dict:
    return {"verdict": "PASS", "time": -1.0, "shot": "",
            "check": check, "evidence": evidence, "likely_cause": "",
            "repair": {}}


def review_hook(shots: list[dict]) -> dict:
    """Hook: >=3 shots starting <5 s + question text somewhere in first cue."""
    early = [s for s in shots if s.get("start", 99) < 5.0]
    q = any("؟" in str(s.get("hook_text", "")) or
            "?" in str(s.get("hook_text", "")) for s in early)
    if len(early) >= 3 and q:
        return _ok("hook_strength", f"{len(early)} shots + question")
    if len(early) >= 3:
        return {"verdict": "REVIEW", "time": 0.0, "shot": early[0].get(
            "shot_id", ""), "check": "hook_strength",
            "evidence": "shots without question hook", "likely_cause":
            "weak hook text", "repair": {"capability": "HOOK_REWRITE"}}
    return _fail(0.0, "", "hook_strength", f"{len(early)} shots in first 5 s",
                 "thin opening", "HOOK_RESHOOT")


def review_shots(shots: list[dict], frames: dict | None = None) -> list[dict]:
    """Per-shot checks: pacing, text count, motion presence, asset dupes."""
    frames = frames or {}
    out, seen = [], {}
    for s in shots:
        sid = s.get("shot_id", "?")
        a, b = s.get("start", 0.0), s.get("end", 0.0)
        dur = round(b - a, 2)
        if dur <= 0:
            out.append(_fail(a, sid, "dead_time", f"duration {dur}",
                             "zero-length shot", "SHOT_REMOVE"))
        if dur > 20:
            out.append(_fail(a, sid, "pacing", f"{dur}s single shot",
                             "overlong hold", "SHOT_SPLIT"))
        texts = s.get("texts", [])
        if len(texts) > 2:
            out.append(_fail(a, sid, "typography_clarity",
                             f"{len(texts)} layers", "text overload",
                             "CAPTION_SIMPLIFY"))
        if not s.get("motion") and dur >= 4.0:
            out.append(_fail(a, sid, "motion_variety",
                             f"{dur}s without motion", "static hold",
                             "CAMERA_PUSH", strength=0.12))
        if s.get("kind") == "card":
            continue
        key = s.get("asset") or s.get("label", "")
        if not key:
            out.append(_fail(a, sid, "no_asset", "no asset selected",
                             "matcher found nothing", "ASSET_REPLACE"))
            continue
        if key in seen:
            out.append({"verdict": "REVIEW", "time": a, "shot": sid,
                        "check": "repetitive_visuals",
                        "evidence": f"reuses {seen[key]}",
                        "likely_cause": "asset reuse",
                        "repair": {"capability": "ASSET_REPLACE"}})
        elif key:
            seen[key] = sid
        fr = frames.get(sid)
        if isinstance(fr, dict):
            if fr.get("foreign_ui"):
                out.append(_fail(a, sid, "foreign_ui_contamination",
                                 str(fr.get("evidence", "")),
                                 "unvetted asset", "ASSET_REPLACE"))
            if fr.get("tofu"):
                out.append(_fail(a, sid, "arabic_rtl_integrity", "tofu/box",
                                 "font fallback", "FONT_FIX"))
    return out


def review_audio(mean_db: float | None, peak_db: float | None,
                 duck_states: list | None) -> list[dict]:
    out = []
    if peak_db is not None and peak_db > -1.0:
        out.append(_fail(-1.0, "", "audio_balance", f"peak {peak_db} dB",
                         "hot mix", "GAIN_REDUCE"))
    if mean_db is not None and mean_db < -28.0:
        out.append(_fail(-1.0, "", "audio_balance", f"mean {mean_db} dB",
                         "quiet mix", "GAIN_RAISE"))
    if not duck_states:
        out.append({"verdict": "REVIEW", "time": -1.0, "shot": "",
                    "check": "music_ducking", "evidence": "no duck states",
                    "likely_cause": "flat bed",
                    "repair": {"capability": "DUCK_ADD"}})
    return out


def review_ending(total: float, last_content_end: float,
                  has_endcard: bool) -> dict:
    gap = round(total - last_content_end, 2)
    if gap > 3.0 or not has_endcard:
        return _fail(last_content_end, "end", "ending_quality",
                     f"tail gap {gap}s, endcard={has_endcard}",
                     "unresolved close", "ENDING_FIX")
    if gap > 2.5:
        return {"verdict": "REVIEW", "time": last_content_end, "shot": "end",
                "check": "ending_quality", "evidence": f"tail {gap}s",
                "likely_cause": "loose tail",
                "repair": {"capability": "ENDING_TRIM"}}
    return _ok("ending_quality", f"content to {last_content_end}s")


def review_all(shots: list[dict], total: float, hook_text: str = "",
               frames: dict | None = None, mean_db: float | None = None,
               peak_db: float | None = None, duck_states: list | None = None,
               last_content_end: float | None = None,
               has_endcard: bool = False) -> dict:
    """Full shot-level review. Returns {verdict, checks[]}."""
    for s in shots:
        if "hook_text" not in s:
            s["hook_text"] = hook_text
    checks = ([review_hook(shots)] + review_shots(shots, frames)
              + review_audio(mean_db, peak_db, duck_states)
              + [review_ending(total, last_content_end
                               if last_content_end is not None else total,
                               has_endcard)])
    verdict = "PASS"
    for c in checks:
        if c["verdict"] == "FAIL":
            verdict = "FAIL"
            break
    if verdict != "FAIL" and any(c["verdict"] == "REVIEW" for c in checks):
        verdict = "REVIEW"
    return {"verdict": verdict, "checks": checks}
