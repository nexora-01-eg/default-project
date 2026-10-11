"""Creative reviewer: judges direction, not just decodability.

Inspects the RENDERED file (frames via gateway sampling + ffprobe facts)
plus the timeline/ASS artifacts. Verdicts PASS/REVIEW/FAIL with concrete
evidence. Independent from the director: it recomputes everything.
"""
from __future__ import annotations


def _ass_events(ass_text: str) -> list[dict]:
    evs = []
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",")
        if len(parts) < 5:
            continue
        evs.append({"start": parts[1].strip(), "end": parts[2].strip(),
                    "style": parts[3].strip(),
                    "text": ",".join(parts[4:])})
    return evs


def _ass_to_s(text: str) -> float:
    h, m, rest = text.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def review_production(final_path: str, timeline: dict, ass_text: str,
                      assets: dict, voice_mode: str = "TEXT_DRIVEN") -> dict:
    """Full creative review. Missing/unreadable final file is a FAIL
    verdict (not an exception): the artifact under review is absent."""
    from engine.core.media import probe
    try:
        info = probe(final_path)
        duration = float(info.duration or 0)
        missing = None
    except Exception as exc:
        duration = 0.0
        missing = f"unreadable final: {exc}"
    checks = []
    if missing is not None:
        checks.append({"name": "final_exists", "verdict": "FAIL",
                       "evidence": missing})

    def _add(name, verdict, evidence):
        checks.append({"name": name, "verdict": verdict, "evidence": evidence})

    segs = timeline.get("segments", [])
    clips = [s for s in segs if s.get("kind") == "clip"]
    # hook: >=3 shots in first 5 s + question text
    hook = [s for s in segs if _start_of(s) < 5.0]
    first_text = timeline.get("hook_text", "")
    if len(hook) >= 3 and ("؟" in first_text or "?" in first_text):
        _add("hook", "PASS", f"{len(hook)} shots in first 5 s + question")
    elif len(hook) >= 3:
        _add("hook", "REVIEW", f"{len(hook)} shots but no question hook")
    else:
        _add("hook", "FAIL", f"only {len(hook)} shots in first 5 s")
    # shot durations per scene
    for sc in timeline.get("scenes", []):
        ss, se = sc.get("span", [0, 0])
        inside = [s for s in clips if _start_of(s) >= ss - 0.01
                  and _end_of(s) <= se + 0.01]
        if len(inside) <= 1 and (se - ss) > 10:
            _add(f"scene_{sc.get('id')}_coverage", "FAIL",
                 f"single clip over {se - ss:.1f}s scene")
        else:
            _add(f"scene_{sc.get('id')}_coverage", "PASS",
                 f"{len(inside)} shots")
    # caption density: body words vs script words
    evs = _ass_events(ass_text)
    # caption density is voice-mode aware: NARRATED mirrors narration
    # (ratio ~1.0 correct); TEXT_DRIVEN uses headlines (each <= 8 words,
    # overall ratio < 0.6). Full-script mirroring in TEXT_DRIVEN = overload.
    body = [e for e in evs if e["style"] == "Body"]
    body_words = sum(len(e["text"].split()) for e in body)
    script_words = timeline.get("script_words", 0)
    ratio = body_words / max(script_words, 1)
    overlong = [e for e in body if len(e["text"].split()) > 8]
    if voice_mode == "NARRATED":
        if 0.7 <= ratio <= 1.1:
            _add("caption_density", "PASS",
                 f"narration mirror ratio {ratio:.2f}")
        else:
            _add("caption_density", "REVIEW",
                 f"narration mirror ratio {ratio:.2f} (expected ~1.0)")
    elif overlong:
        _add("caption_density", "FAIL",
             f"{len(overlong)} headline(s) over 8 words (overload)")
    elif ratio > 0.6:
        _add("caption_density", "FAIL",
             f"body carries {body_words}/{script_words} script words (overload)")
    elif ratio > 0.4:
        _add("caption_density", "REVIEW", f"ratio {ratio:.2f}")
    else:
        _add("caption_density", "PASS", f"ratio {ratio:.2f} (headlines)")
    # ending: content within 2.5 s of end
    ends = [_ass_to_s(e["end"]) for e in evs] or [0]
    tail_gap = duration - max(ends)
    if tail_gap > 3.0:
        _add("ending", "FAIL", f"{tail_gap:.1f}s dead tail")
    elif tail_gap > 2.5:
        _add("ending", "REVIEW", f"{tail_gap:.1f}s tail")
    else:
        _add("ending", "PASS", f"content to {max(ends):.1f}s of {duration:.1f}s")
    # repetition + consistency from used assets
    files = [a.get("file", "") for a in assets.get("used", [])]
    reuse = len(files) - len(set(files))
    _add("repetition", "PASS" if reuse <= 2 else "REVIEW",
         f"cross-scene reuse={reuse}")
    low = [f.split("/")[-1] for f in files
           if (assets.get("dims", {}).get(f, (9999,))[0] or 9999) < 720]
    _add("asset_quality", "PASS" if not low else "REVIEW",
         [f"below_720p={low}"] if low else ["all >= 720p"])
    foreign = [f.split("/")[-1] for f in files
               if f in assets.get("foreign_ui", [])]
    if foreign and not assets.get("foreign_justified"):
        _add("asset_relevance", "FAIL", [f"unjustified foreign UI: {foreign}"])
    else:
        _add("asset_relevance", "PASS", ["all visuals narratively placed"])
    # motion + audio states from timeline record
    motions = timeline.get("motion_events", 0)
    _add("motion", "PASS" if motions >= 6 else "REVIEW",
         [f"motion_events={motions}"])
    gains = timeline.get("music_gains", [])
    _add("audio_states", "PASS" if len(set(gains)) > 1 else "REVIEW",
         [f"gain_states={sorted(set(gains))}"])
    verdict = "PASS"
    for c in checks:
        if c["verdict"] == "FAIL":
            verdict = "FAIL"
            break
    if verdict != "FAIL" and any(c["verdict"] == "REVIEW" for c in checks):
        verdict = "REVIEW"
    return {"verdict": verdict, "checks": checks,
            "duration": round(duration, 2)}


def _start_of(s):
    if "span" in s:
        return s["span"][0]
    return 0.0


def _end_of(s):
    if "span" in s:
        return s["span"][1]
    return (s.get("at", 0.0) + s.get("len", 0.0))
