"""Internal creative quality model: 20 criteria, critical-FAIL override.

Each criterion returns PASS/REVIEW/FAIL + evidence from records (no new
rendering). A high aggregate NEVER overrides a critical FAIL. Pure.
Critical checks: caption_correctness, audio_no_clip, av_sync_ok,
arabic_rtl_ok, story_arc.
"""
from __future__ import annotations


def _rec(name, verdict, evidence):
    return {"criterion": name, "verdict": verdict, "evidence": evidence}


def score(inputs: dict) -> dict:
    """Score 20 criteria from a production record. Pure."""
    g = inputs.get
    out = {}

    def put(name, verdict, evidence):
        out[name] = _rec(name, verdict, evidence)

    put("narrative_clarity", "PASS" if g("scenes_with_text", 0) > 0 else "FAIL",
        [f"scenes_with_text={g('scenes_with_text', 0)}"])
    put("hook", "PASS" if g("hook_shots", 0) >= 3 and g("hook_question",
                                                        False) else "REVIEW",
        [f"shots={g('hook_shots', 0)}", f"q={g('hook_question', False)}"])
    put("visual_relevance", "PASS" if not g("irrelevant_shots", []) else "FAIL",
        [f"irrelevant={g('irrelevant_shots', [])}"])
    put("visual_variety", "PASS" if g("distinct_sources", 0) >= 3 else "REVIEW",
        [f"distinct={g('distinct_sources', 0)}"])
    lens = g("shot_lengths", [])
    import statistics
    rhythm_ok = bool(lens) and statistics.pstdev(lens) > 1.0 and \
        max(lens) <= 20
    put("pacing", "PASS" if rhythm_ok else "REVIEW", [f"lens={lens}"])
    put("motion_quality", "PASS" if g("motion_events", 0) >= g("scenes", 1)
        else "REVIEW",
        [f"events={g('motion_events', 0)}"])
    put("typography", "PASS" if g("font_families", 1) == 1 and
        g("max_layers", 9) <= 2 else "REVIEW",
        [f"fonts={g('font_families', 1)}", f"layers={g('max_layers', 9)}"])
    put("caption_quality", "PASS" if g("caption_correct", True) else "FAIL",
        [f"correct={g('caption_correct', True)}"])
    put("composition", "PASS" if not g("composition_issues", []) else "REVIEW",
        [f"issues={g('composition_issues', [])}"])
    put("audio_quality", "PASS" if (g("peak_db", -99) or -99) <= -1.0 else
        "FAIL", [f"peak={g('peak_db', '?')}"])
    gains = g("music_gains", [])
    put("music_behavior", "PASS" if len(set(gains)) > 1 else "REVIEW",
        [f"gains={sorted(set(gains))}"])
    put("sfx_purpose", "PASS" if g("sfx_documented", False) else "REVIEW",
        [f"documented={g('sfx_documented', False)}"])
    put("visual_consistency", "PASS" if g("consistent", True) else "REVIEW",
        [f"consistent={g('consistent', True)}"])
    put("asset_quality", "PASS" if not g("weak_assets", []) else "REVIEW",
        [f"weak={g('weak_assets', [])}"])
    put("storytelling", "PASS" if g("arc_complete", False) else "REVIEW",
        [f"arc={g('arc_complete', False)}"])
    put("payoff", "PASS" if g("payoff_present", False) else "REVIEW",
        [f"payoff={g('payoff_present', False)}"])
    put("ending", "PASS" if g("ending_ok", False) else "FAIL",
        [f"ok={g('ending_ok', False)}"])
    put("technical_qc", "PASS" if g("tech_ok", False) else "FAIL",
        [f"ok={g('tech_ok', False)}"])
    put("reviewer_confidence", "PASS" if g("reviewer_verdict",
                                           "") == "PASS" else "REVIEW",
        [f"verdict={g('reviewer_verdict', '')}"])
    put("reproducibility", "PASS" if g("manifest", False) else "REVIEW",
        [f"manifest={g('manifest', False)}"])

    crit_fail = [k for k in ("caption_quality", "audio_quality", "ending",
                             "technical_qc") if out[k]["verdict"] == "FAIL"]
    extra = []
    if inputs.get("av_sync_ok") is False:
        extra.append("av_sync")
    if inputs.get("arabic_rtl_ok") is False:
        extra.append("arabic_rtl")
    if inputs.get("story_arc") is False:
        extra.append("story_arc")
    score_val = round(sum(1 for v in out.values()
                          if v["verdict"] == "PASS") / 20, 3)
    blocked = bool(crit_fail or extra)
    verdict = ("FAIL" if blocked else
               "REVIEW" if any(v["verdict"] != "PASS" for v in out.values())
               else "PASS")
    return {"criteria": out, "score": score_val,
            "critical_fail": crit_fail + extra, "verdict": verdict}
