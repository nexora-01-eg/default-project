"""Phase 14 — caption planning: transcript -> cues -> CaptionPlan.

Pure timeline/text logic (no FFmpeg, no models, no network). The transcript
is the source of truth: words are never rewritten, timing never invented.
SRT/VTT/ASS live in formats.py; fonts in fonts.py.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from engine.core import config as config_mod
from engine.core.logging_utils import log_event
from engine.core.models import CaptionCue, CaptionPlan, CaptionWord
from engine.core.pipeline import cache_key, cached, store
from engine.core.project_store import (
    load_project,
    mark_stage,
    project_dir,
    write_artifact,
)
from engine.editing.decisions import hash_analysis

CAPTION_VERSION = "1.0.0"
CAPTION_KEYS = ("caption_style", "caption_mode", "caption_min_duration",
                "caption_max_duration",
                "caption_max_lines", "caption_max_chars_per_line",
                "caption_max_total_chars", "caption_max_words",
                "caption_max_cps", "caption_max_wpm", "caption_min_gap",
                "caption_font_family", "caption_font_file",
                "caption_position", "caption_margin_v", "caption_margin_h")
TERMINAL_PUNCT = (".", "?", "!", "…", "؟", "。")
_AR_RANGES = ("\u0600\u06ff", "\u0750077f", "\u08a008ff",
              "\ufb50\ufdff", "\ufe70\ufeff")


class CaptionError(RuntimeError):
    pass


def _r3(x: float) -> float:
    return round(float(x), 3)


def has_rtl(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f"
               or "\u08a0" <= ch <= "\u08ff" or "\ufb50" <= ch <= "\ufdff"
               or "\ufe70" <= ch <= "\ufeff" for ch in text)


def resolve_caption_config(overrides: dict | None = None) -> dict:
    cfg = config_mod.resolve(overrides=overrides)
    out = {k: cfg[k] for k in CAPTION_KEYS}
    for key in ("caption_min_duration", "caption_max_duration",
                "caption_max_cps", "caption_max_wpm", "caption_min_gap"):
        try:
            out[key] = float(out[key])
        except (TypeError, ValueError):
            raise CaptionError(f"{key} must be a number") from None
    for key in ("caption_max_lines", "caption_max_chars_per_line",
                "caption_max_total_chars", "caption_max_words",
                "caption_margin_v", "caption_margin_h"):
        try:
            out[key] = int(out[key])
        except (TypeError, ValueError):
            raise CaptionError(f"{key} must be an integer") from None
    if out["caption_position"] not in ("bottom", "center", "top"):
        raise CaptionError("caption_position must be bottom|center|top")
    if not (0 < out["caption_min_duration"] <= out["caption_max_duration"]):
        raise CaptionError("need 0 < min_duration <= max_duration")
    if out["caption_max_lines"] < 1 or out["caption_max_chars_per_line"] < 1:
        raise CaptionError("line/char limits must be >= 1")
    return out


def flatten_words(transcript: dict) -> list[dict]:
    """Transcript words -> plan words (display text stripped, timing kept)."""
    out: list[dict] = []
    for seg in transcript.get("segments", []) or []:
        for idx, w in enumerate(seg.get("words", []) or []):
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if not we > ws:
                continue
            text = str(w.get("word", "")).strip()
            if not text:
                continue
            out.append({"word_id": f"s{seg.get('id', 0)}w{idx}", "text": text,
                        "start": ws, "end": we,
                        "probability": round(float(w.get("probability", 0.0) or 0.0), 4),
                        "segment_id": seg.get("id", 0),
                        "terminal": text.endswith(TERMINAL_PUNCT)})
    out.sort(key=lambda x: (x["start"], x["end"]))
    return out


def _scene_of(scenes: list[dict], t: float) -> int:
    for sc in scenes:
        if float(sc["start"]) - 1e-6 <= t < float(sc["end"]) - 1e-6:
            return int(sc.get("scene_id", -1))
    return int(scenes[-1].get("scene_id", -1)) if scenes else -1


def segment_cues(words: list[dict], scenes: list[dict],
                 config: dict) -> tuple[list[list[dict]], list[str]]:
    """Chunk words into cue word-groups. Returns (groups, notes)."""
    groups: list[list[dict]] = []
    notes: list[str] = []
    i, n = 0, len(words)
    while i < n:
        cur = [words[i]]
        j = i
        while j + 1 < n:
            if words[j]["terminal"]:
                break  # never extend past a sentence end
            nxt = words[j + 1]
            gap = nxt["start"] - words[j]["end"]
            if gap >= 0.5:
                break  # pause boundary: next word starts a new cue
            trial = cur + [nxt]
            trial_chars = len(" ".join(w["text"] for w in trial))
            trial_dur = nxt["end"] - cur[0]["start"]
            if len(trial) > config["caption_max_words"]:
                break
            if trial_chars > config["caption_max_total_chars"]:
                break
            if trial_dur > config["caption_max_duration"]:
                break
            if _scene_of(scenes, words[j]["end"]) != _scene_of(scenes, nxt["start"]):
                notes.append(f"scene cut inside speech near {nxt['start']:.2f}s")
                break
            cur.append(nxt)
            j += 1
        groups.append(cur)
        i = j + 1
    return groups, notes


def reading_metrics(text: str, n_words: int, duration: float) -> tuple[float, float]:
    chars = len(text.replace("\n", ""))
    if duration <= 0:
        return 0.0, 0.0
    return round(chars / duration, 2), round(n_words / duration * 60.0, 1)


def wrap_lines(tokens: list[str], max_chars: int,
               max_lines: int) -> list[str] | None:
    """Deterministic balanced wrapping. Tokens atomic (never hyphenated);
    breaks at spaces only (bidi-safe: logical order preserved). Returns None
    when impossible within max_lines (caller splits instead)."""
    if not tokens:
        return []
    if len(" ".join(tokens)) <= max_chars:
        return [" ".join(tokens)]
    n = len(tokens)
    best = None  # (max_len, imbalance, orphan_penalty, breaks)
    chars = [len(t) for t in tokens]

    def search(start: int, lines_left: int):
        # Returns (plan_lines | None, cost) for tokens[start:].
        if start >= n:
            return [], (0, 0, 0)
        if lines_left == 0:
            return None, None
        best_local, best_cost = None, None
        used = -1
        for end in range(start + 1, n + 1):
            used = used + 1 + chars[end - 1] if end - 1 >= start else used
            line = " ".join(tokens[start:end])
            if len(line) > max_chars:
                break
            rest, rest_cost = search(end, lines_left - 1)
            if rest is None and end < n:
                continue
            if end == n:
                rest, rest_cost = [], (0, 0, 0)
            if rest is None:
                continue
            lines_here = [line] + rest
            mx = max(len(x) for x in lines_here)
            imb = max(len(x) for x in lines_here) - min(len(x) for x in lines_here)
            orphan = 0
            if len(lines_here) > 1:
                last_words = len(lines_here[-1].split())
                if last_words == 1 and len(tokens) > 2 and len(lines_here[-1]) < 10:
                    orphan = 1  # avoid lonely short second line
            cost = (mx, imb, orphan)
            if best_cost is None or cost < best_cost:
                best_cost, best_local = cost, lines_here
        return best_local, best_cost

    plan, _ = search(0, max_lines)
    return plan


def _extend_into_gap(start: float, end: float, words: list[dict], idx_next: int,
                     cap: float = 0.4) -> float:
    """Extend cue end into following silence (never past next word start)."""
    if idx_next < len(words):
        return min(end + cap, words[idx_next]["start"])
    return end + cap


def build_cues(transcript: dict, scenes: list[dict],
               config: dict) -> tuple[list[CaptionCue], list[str]]:
    """Full cue construction with CPS enforcement (extend > split > warn)."""
    words = flatten_words(transcript)
    language = transcript.get("language", "") or ""
    if not words:
        return [], ["no transcript words: empty caption plan"]
    scene_list = sorted(scenes, key=lambda s: (s["start"], s["end"])) if scenes else []
    groups, notes = segment_cues(words, scene_list, config)
    cues: list[CaptionCue] = []
    warnings: list[str] = list(notes)
    flat_index = {id(w): i for i, w in enumerate(words)}
    for gi, group in enumerate(groups):
        start, end = group[0]["start"], group[-1]["end"]
        tokens = [w["text"] for w in group]
        text = " ".join(tokens)
        dur = end - start
        cps, wpm = reading_metrics(text, len(group), dur)
        split_reason = ""
        if cps > config["caption_max_cps"] or dur > config["caption_max_duration"]:
            # 1. extend into following silence where safe.
            following = words[flat_index[id(group[-1])] + 1] \
                if flat_index[id(group[-1])] + 1 < len(words) else None
            if following and following["start"] - end > 1e-6:
                end = _extend_into_gap(start, end, words, flat_index[id(group[-1])] + 1)
                dur = end - start
                cps, wpm = reading_metrics(text, len(group), dur)
                split_reason = "extended_into_pause"
            # 2. split at the largest internal gap (prefer sentence ends).
            if cps > config["caption_max_cps"] or dur > config["caption_max_duration"]:
                gaps = [(words[i + 1]["start"] - words[i]["end"], i)
                        for i in range(len(group) - 1)]
                gaps.sort(key=lambda g: (-g[0], -int(group[g[1]]["terminal"])))
                if gaps and gaps[0][0] > 0.05:
                    cut = gaps[0][1] + 1
                    first, second = group[:cut], group[cut:]
                    cues.extend(_finalize([first, second], language, config,
                                          scene_list, "split_for_readability"))
                    continue
                warnings.append(f"cue {gi} exceeds readability caps "
                                f"(cps={cps}, dur={dur:.2f}s): kept with warning")
                split_reason = split_reason or "unbreakable_kept"
        cues.extend(_finalize([group], language, config, scene_list,
                              split_reason or "word_group"))
    # Order + gap enforcement (clamp overlaps, never invent time).
    cues.sort(key=lambda c: (c.start, c.end))
    for prev, cur in zip(cues, cues[1:]):
        if cur.start < prev.end - 1e-3:
            over = prev.end - cur.start
            prev.end = _r3(cur.start)
            if over > 0.1:
                warnings.append(f"cue {prev.cue_id} clamped by {over:.2f}s overlap")
    # Minimum duration pass (extend into gaps, else warn).
    for idx, cue in enumerate(cues):
        dur = cue.end - cue.start
        if dur < config["caption_min_duration"] - 1e-6:
            nxt_start = cues[idx + 1].start if idx + 1 < len(cues) else None
            room = (nxt_start - cue.end) if nxt_start is not None else 0.4
            if room > 1e-6:
                cue.end = _r3(min(cue.end + 0.4, cue.end + room))
                cue.reading_cps, cue.reading_wpm = reading_metrics(
                    cue.text.replace("\n", " "),
                    sum(1 for _ in cue.text.split()), cue.end - cue.start)
            else:
                warnings.append(f"cue {cue.cue_id} shorter than minimum "
                                f"({dur:.2f}s): kept with warning")
    # Renumber deterministically.
    for i, cue in enumerate(cues):
        cue.cue_id = f"cue_{i + 1:04d}"
    return cues, warnings


def _scrub_undecodable(text: str) -> str:
    """Strip U+FFFD replacement chars (undecodable bytes from STT).

    Renders as tofu in every font; carries zero information. Applied
    consistently to cue text AND word refs so integrity holds; callers
    record an explicit warning (never silent).
    """
    return str(text).replace("�", "")


def _finalize(groups: list[list[dict]], language: str, config: dict,
              scenes: list[dict], reason: str) -> list[CaptionCue]:
    out: list[CaptionCue] = []
    for group in groups:
        scrubbed = sum(w.get("text", "").count("�") for w in group)
        clean = []
        for w in group:
            t = _scrub_undecodable(w.get("text", ""))
            if t.strip():
                clean.append({**w, "text": t})
        if scrubbed and not clean:
            # degenerate: stripping would erase the cue; keep original so
            # no content vanishes, flag it loudly instead.
            clean = list(group)
        tokens = [w["text"] for w in clean]
        lines = wrap_lines(tokens, config["caption_max_chars_per_line"],
                           config["caption_max_lines"])
        if lines is None:
            # Unsplittable within line caps: emit single overflowing line + warn.
            lines = [" ".join(tokens)]
        text = "\n".join(lines)
        start, end = clean[0]["start"], clean[-1]["end"]
        cps, wpm = reading_metrics(text, len(clean), end - start)
        refs = [{"word_id": w["word_id"], "text": w["text"], "start": w["start"],
                 "end": w["end"], "probability": w["probability"]} for w in clean]
        conf = round(sum(w["probability"] for w in clean) / len(clean), 3)
        sid = _scene_of(scenes, start) if scenes else -1
        out.append(CaptionCue(
            start=_r3(start), end=_r3(end), text=text, lines=lines,
            word_refs=refs, language=language, confidence=conf,
            line_count=len(lines), character_count=len(text.replace("\n", "")),
            reading_cps=cps, reading_wpm=wpm, split_reason=reason,
            scene_id=sid,
            warnings=((["line_overflow"] if lines and
                       any(len(l) > config["caption_max_chars_per_line"] for l in lines)
                       else []) + (["undecodable_chars"] if scrubbed else []))))
    return out


def validate_cues(cues: list[CaptionCue],
                  source_duration: float | None = None) -> list[str]:
    """Timing/text integrity. Returns issues (empty = clean)."""
    issues: list[str] = []
    for i, c in enumerate(cues):
        if not c.end > c.start:
            issues.append(f"{c.cue_id or i}: end not > start")
        if not c.text.strip():
            issues.append(f"{c.cue_id or i}: empty text")
        try:
            c.text.encode("utf-8", "strict")
        except UnicodeError:
            issues.append(f"{c.cue_id or i}: invalid unicode")
        for w in c.word_refs:
            if w["start"] < c.start - 0.05 or w["end"] > c.end + 0.05:
                issues.append(f"{c.cue_id or i}: word outside cue timing")
        joined = " ".join(w["text"] for w in c.word_refs)
        if joined != c.text.replace("\n", " "):
            issues.append(f"{c.cue_id or i}: text/word mismatch (integrity)")
        if i > 0:
            prev = cues[i - 1]
            if c.start < prev.end - 1e-3:
                issues.append(f"{c.cue_id or i}: overlaps previous cue")
        if source_duration is not None and c.end > source_duration + 0.05:
            issues.append(f"{c.cue_id or i}: exceeds source duration")
    return issues


def caption_plan_hash(plan: dict) -> str:
    import hashlib
    import json as _json
    canonical = {k: v for k, v in plan.items() if k not in ("processing_s", "cached")}
    return hashlib.sha256(_json.dumps(canonical, sort_keys=True, default=str)
                          .encode()).hexdigest()[:32]


def keeps_from_edl(edl: dict) -> list[tuple[float, float]]:
    """Source KEEP spans (sorted). Raises CaptionError on invalid EDL."""
    from engine.rendering.execution import validate_edl
    issues = validate_edl(edl)
    if issues:
        raise CaptionError(f"invalid base EDL: {'; '.join(issues[:5])}")
    return sorted([(float(d["start"]), float(d["end"])) for d in edl["decisions"]
                     if d.get("action") == "KEEP"])


def _versions() -> dict:
    import platform
    return {"python": platform.python_version(), "engine": "0.1.0"}


def _code_hash() -> str:
    """Hash of this module's source: engine edits invalidate caption caches
    automatically (stale logic must never serve old plans)."""
    import hashlib
    from pathlib import Path as _Path
    try:
        return hashlib.sha256(_Path(__file__).read_bytes()).hexdigest()[:16]
    except OSError:
        return "unknown"


def map_cues_to_output(cues: list[dict], keeps: list[tuple]) -> tuple[list[dict], list[str], dict]:
    """Map source-timeline cues onto output coordinates via EDL keeps.

    keeps: [(src_start, src_end), ...] sorted. Output offsets accumulate.
    Words outside keeps are dropped (never split); cues with no surviving
    words are dropped with a warning; surviving words split by output gaps
    >= 0.8 s become sub-cues. Returns (mapped, warnings, stats).
    """
    offsets: list[tuple[float, float, float]] = []
    cursor = 0.0
    for span in sorted(keeps):
        ks, ke = float(span[0]), float(span[1])  # accepts (s,e) or (s,e,os,oe)
        offsets.append((ks, ke, cursor))
        cursor += ke - ks
    mapped: list[dict] = []
    warnings: list[str] = []
    kept_words = dropped_words = split_cues = 0
    for cue in cues:
        surviving = []
        for w in cue.get("word_refs", []) or []:
            hit = next(((ks, ke, off) for ks, ke, off in offsets
                        if w["start"] >= ks - 1e-3 and w["end"] <= ke + 1e-3), None)
            if hit is None:
                dropped_words += 1
                continue
            ks, ke, off = hit
            surviving.append({**w, "start": _r3(w["start"] - ks + off),
                              "end": _r3(w["end"] - ks + off)})
            kept_words += 1
        if not surviving:
            warnings.append(f"cue {cue.get('cue_id')} dropped: no surviving words")
            continue
        groups: list[list[dict]] = [[surviving[0]]]
        for w in surviving[1:]:
            if w["start"] - groups[-1][-1]["end"] >= 0.8:
                groups.append([w])
            else:
                groups[-1].append(w)
        if len(groups) > 1:
            split_cues += 1
        for gi, group in enumerate(groups):
            text = " ".join(w["text"] for w in group)
            lines = text.split(" ")  # re-wrap below if needed
            new_id = cue.get("cue_id", "") + (f"+{gi + 1}" if len(groups) > 1 else "")
            dur = group[-1]["end"] - group[0]["start"]
            cps, wpm = reading_metrics(text, len(group), dur)
            mapped.append({
                "cue_id": new_id, "start": group[0]["start"], "end": group[-1]["end"],
                "text": text, "lines": [text],
                "word_refs": group, "language": cue.get("language", ""),
                "confidence": cue.get("confidence", 0.0),
                "style": cue.get("style", "default"),
                "scene_id": cue.get("scene_id", -1),
                "line_count": 1, "character_count": len(text),
                "reading_cps": cps, "reading_wpm": wpm,
                "split_reason": "edit_split" if len(groups) > 1 else cue.get("split_reason", ""),
                "warnings": [],
                "source_cue_id": cue.get("cue_id", ""),
                "source_start": cue.get("start"), "source_end": cue.get("end")})
    mapped.sort(key=lambda c: (c["start"], c["end"]))
    stats = {"kept_words": kept_words, "dropped_words": dropped_words,
             "split_cues": split_cues, "mapped_cues": len(mapped)}
    return mapped, warnings, stats


def approve_captions(project_id: str, mode: str = "sidecar",
                     style: str | None = None, font_family: str | None = None,
                     font_file: str | None = None,
                     approver: str = "operator") -> dict:
    """Explicit caption approval (separate artifact; base approval untouched)."""
    import json
    from engine.subtitles.fonts import FontError, resolve_font, validate_font_for_text
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    if mode not in ("sidecar", "burned_in"):
        raise CaptionError(f"caption mode must be sidecar|burned_in (got {mode!r})")
    plan_path = project_dir(pid) / "captions" / "caption_plan.json"
    if not plan_path.is_file():
        raise CaptionError("missing captions/caption_plan.json (run captions first)")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaptionError(f"corrupt caption plan: {exc}") from exc
    from engine.subtitles.formats import resolve_style
    try:
        style_def = resolve_style(style or plan.get("style", "default"))
        style_name = style or plan.get("style", "default")
    except Exception as exc:
        raise CaptionError(str(exc)) from exc
    cfg_family = (plan.get("config", {}) or {}).get("caption_font_family", "Arial")
    try:
        font = resolve_font(font_family or cfg_family, font_file)
    except FontError as exc:
        raise CaptionError(str(exc)) from exc
    sample = " ".join(c.get("text", "") for c in plan.get("cues", [])[:5])
    check = validate_font_for_text(font["file"], sample)
    if check["status"] == "invalid":
        raise CaptionError(f"font rejected: {check['reason']}")
    warnings = []
    if check["status"] == "uncertain":
        warnings.append(f"font coverage uncertain: {check['reason']}")
    approval = {"schema_version": "caption-approval-1.0",
                "caption_plan_hash": caption_plan_hash(plan),
                "mode": mode, "style": style_name,
                "font": {"family": font["family"], "file": font["file"],
                         "source": font["source"],
                         "validation": check["status"]},
                "warnings": warnings, "approved_at": datetime.now(timezone.utc).isoformat(),
                "approver": approver}
    write_artifact(pid, "editing", "approved_captions.json", approval)
    mark_stage(project, "caption_approval", "done", "editing/approved_captions.json")
    log_event(log_file, "captions", "approve", "ok", 0.0,
              "editing/approved_captions.json", _versions(),
              {"mode": mode, "style": style_name, "cues": plan.get("cue_count", 0)})
    return {"project": pid, "approval": approval}


def validate_captions_approval(project_id: str) -> dict:
    """Revalidate caption approval: plan hash, font file, mode."""
    import json
    from engine.subtitles.fonts import validate_font_for_text
    project = load_project(project_id)
    pid = project.id
    ap_path = project_dir(pid) / "editing" / "approved_captions.json"
    if not ap_path.is_file():
        raise CaptionError("missing caption approval (run approve-captions first)")
    try:
        approval = json.loads(ap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaptionError(f"corrupt caption approval: {exc}") from exc
    if approval.get("schema_version") != "caption-approval-1.0":
        raise CaptionError(f"unsupported caption approval schema "
                           f"{approval.get('schema_version')!r}")
    plan_path = project_dir(pid) / "captions" / "caption_plan.json"
    if not plan_path.is_file():
        raise CaptionError("caption plan vanished since approval")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaptionError(f"corrupt caption plan: {exc}") from exc
    if caption_plan_hash(plan) != approval.get("caption_plan_hash"):
        raise CaptionError("caption plan changed since approval: re-approve")
    font_file = (approval.get("font", {}) or {}).get("file", "")
    sample = " ".join(c.get("text", "") for c in plan.get("cues", [])[:5])
    check = validate_font_for_text(font_file, sample)
    if check["status"] == "invalid":
        raise CaptionError(f"approved font now invalid: {check['reason']}")
    return {"approval": approval, "plan": plan}


def build_caption_plan(transcript: dict, scenes: list[dict],
                       config: dict, source: str = "") -> object:
    """Assemble the deterministic CaptionPlan (raises CaptionError never;
    empty transcripts yield an empty plan with a warning)."""
    from engine.core.models import CaptionPlan as _CP
    cues, warnings = build_cues(transcript, scenes or [], config)
    issues = validate_cues(cues, None)
    warnings.extend(f"validation: {i}" for i in issues)
    plan = _CP(source=source,
               transcript_hash=hash_analysis(transcript),
               cues=cues, cue_count=len(cues),
               style=config.get("_style_name", "default"),
               language=transcript.get("language", "") or "",
               warnings=warnings,
               expected_duration=_r3(max((c.end for c in cues), default=0.0)),
               config={k: v for k, v in config.items() if not k.startswith("_")})
    return plan


def caption_plan_for_project(project_id: str,
                             policy_overrides: dict | None = None,
                             force: bool = False) -> dict:
    """Build + validate + cache the caption plan. No video touched."""
    import json
    from engine.core.models import CaptionPlan as _CP
    project = load_project(project_id)
    pid = project.id
    log_file = project_dir(pid) / "logs" / "run.jsonl"
    config = resolve_caption_config(policy_overrides)
    style = config.get("_style_name", config.get("caption_style", "default"))
    from engine.subtitles.formats import resolve_style as _resolve_style
    try:
        _resolve_style(style)  # fail fast on unknown styles (never silent fallback)
    except Exception as exc:
        raise CaptionError(str(exc)) from exc

    tr_path = project_dir(pid) / "analysis" / "transcript.json"
    if not tr_path.is_file():
        raise CaptionError("missing analysis/transcript.json (run transcribe first)")
    try:
        transcript = json.loads(tr_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CaptionError(f"corrupt transcript.json: {exc}") from exc
    scenes = []
    sc_path = project_dir(pid) / "analysis" / "scenes.json"
    if sc_path.is_file():
        try:
            scenes = json.loads(sc_path.read_text(encoding="utf-8")).get("scenes", [])
        except json.JSONDecodeError:
            scenes = []

    key = cache_key(project.input_path, "captions",
                    {"transcript": hash_analysis(transcript),
                     "style": style, "config": {k: config[k] for k in CAPTION_KEYS
                                                if not k.startswith("caption_font")},
                     "font_family": config.get("caption_font_family"),
                     "version": CAPTION_VERSION, "code_hash": _code_hash()})
    t0 = time.perf_counter()
    hit = None if force else cached(key)
    if hit is not None:
        payload = json.loads(hit.read_text(encoding="utf-8"))
        payload["cached"] = True
        write_artifact(pid, "captions", "caption_plan.json", payload)
        mark_stage(project, "captions", "cached", "captions/caption_plan.json")
        log_event(log_file, "captions", "plan", "cached",
                  time.perf_counter() - t0, "captions/caption_plan.json",
                  _versions(), {"cues": payload.get("cue_count", 0)})
        return {"project": pid, "cached": True, "plan": payload}

    config["_style_name"] = style
    plan = build_caption_plan(transcript, scenes, config,
                              source=project.input_path)
    payload = asdict(plan)
    write_artifact(pid, "captions", "caption_plan.json", payload)
    store(key, payload)
    mark_stage(project, "captions", "done", "captions/caption_plan.json")
    log_event(log_file, "captions", "plan", "ok",
              time.perf_counter() - t0, "captions/caption_plan.json",
              _versions(), {"cues": plan.cue_count,
                            "warnings": len(plan.warnings)})
    return {"project": pid, "cached": False, "plan": payload}
