"""Layered config: defaults < template < preset < CLI flags (Phase 1 minimal)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

DEFAULTS: dict = {
    "template": "youtube",
    "preset": "youtube_1080p",
    "silence_db": -35,
    "min_silence_s": 0.5,
    "max_retries": 3,
    "encoder_priority": ["h264_nvenc", "h264_qsv", "h264_amf", "libx264"],
    "whisper_model": "small",
    "whisper_device": "auto",          # auto | cpu | cuda
    "whisper_compute_type": "auto",    # auto | int8 | int8_float32 | float16 | float32
    "whisper_word_timestamps": True,
    "whisper_spans": "full",           # full | non_silent
    "scene_method": "content",         # content | threshold | ffmpeg
    "scene_threshold": None,           # None -> method default (content 27.0, threshold 12.0, ffmpeg 0.4)
    "scene_min_len_s": 0.6,
    "edit_min_silence_s": 0.8,         # RULE A: silences shorter than this are kept
    "edit_silence_pad_before": 0.15,   # breathing room preserved around removals
    "edit_silence_pad_after": 0.15,
    "edit_remove_fillers": True,       # RULE B: remove annotated filler words
    "edit_filler_pad_s": 0.08,
    "edit_min_removal_s": 0.2,         # never emit removals shorter than this
    "intel_safety_net": True,          # revert UNSAFE removals to KEEP
    "intel_safety_mode": "conservative",  # conservative (UNSAFE only) | strict (+CAUTION)
    "intel_repetition_removal": False, # opt-in: remove 2nd+ exact repetitions
    "intel_repetition_min_words": 4,
    "intel_min_keep_s": 0.5,           # short keeps flagged CAUTION (not deleted)
    "intel_min_remove_s": 0.2,
    "intel_enable_jumpcut": True,
    "intel_enable_pacing": True,
    "intel_enable_repetition": True,
    "intel_word_gap_s": 0.15,          # preferred-point gap threshold
    "visual_mode": "bme",              # middle | bme | per_scene | fps
    "visual_samples_per_scene": 3,
    "visual_fps": 1.0,
    "visual_max_frames": 128,
    "visual_dark_thr": 25.0,           # mean brightness below -> dark_frame
    "visual_bright_thr": 230.0,        # mean brightness above -> bright_frame
    "visual_contrast_thr": 15.0,       # std below -> low_contrast
    "visual_sharpness_thr": 100.0,     # Laplacian var below -> blurry (tune per content)
    "visual_dup_hamming_thr": 5,       # dHash distance for near-duplicate
    "visual_hist_thr": 0.9,            # hist correlation for stable continuity
    "visual_change_thr": 0.5,          # hist correlation below -> large_change
    "visual_enable_face": True,        # attempted; reported honestly
    "visual_enable_object": True,
    "visual_enable_embeddings": False, # off until a model is configured
    "visual_face_cascade_path": None,  # user-supplied Haar XML (optional)
    "visual_object_weights": None,     # user-supplied detector weights (optional)
    "visual_embedding_model": None,    # user-supplied embedding model (optional)
    "visual_timeout": 900,
    "editor_style": "general",
    "editor_target_duration": None,
    "editor_aggressive": False,
    "caption_style": "default",       # default|clean|social|cinematic|minimal
    "caption_mode": "sidecar",        # sidecar|burned_in (explicit default)
    "caption_min_duration": 0.8,
    "caption_max_duration": 7.0,
    "caption_max_lines": 2,
    "caption_max_chars_per_line": 42,
    "caption_max_total_chars": 84,
    "caption_max_words": 14,
    "caption_max_cps": 20.0,          # characters per second
    "caption_max_wpm": 200.0,
    "caption_min_gap": 0.08,          # min gap between cues
    "caption_font_family": "Arial",
    "caption_font_file": None,        # explicit file overrides family lookup
    "caption_position": "bottom",     # bottom|center|top
    "caption_margin_v": 24,           # safe-area margins, px at 1080p (scaled)
    "caption_margin_h": 40,
    "visual_caption_version": "1.0.0",
    "visual_caption_band_top": 0.05,  # sampled bands as frame fractions
    "visual_caption_band_mid": 0.35,
    "visual_caption_band_bot": 0.62,
    "visual_caption_good_thr": 150.0,  # band mean below -> GOOD_CONTRAST
    "visual_caption_poor_thr": 200.0,  # band mean above -> POOR_CONTRAST
    "visual_caption_busy_thr": 45.0,  # band std above -> busy background
    "visual_caption_outline_max": 3,
    "visual_caption_enable_emphasis": True,
    "visual_caption_max_emphasis_ratio": 0.3,
    "pacing_caption_cps_fast": 17.0,   # CPS at/above -> HIGH_CAPTION_DENSITY
    "pacing_caption_cps_extreme": 22.0,  # CPS at/above -> severity high
    "pacing_caption_gap_long": 1.2,    # caption-free gap at/above -> LONG_SILENCE-adjacent signal
    "pacing_caption_words_per_cue_high": 9,
    "pacing_caption_density_window": 3.0,  # rolling density window, seconds
    "pacing_pause_s": 0.6,             # inter-word gap at/above -> NATURAL_PAUSE
    "pacing_static_motion_thr": 0.05,  # motion_mean below -> static visual
    "pacing_long_scene_ratio": 2.0,    # scene dur vs median -> outlier signal
}

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


def load_template(name: str) -> dict:
    for suffix in (".json", ""):
        for base in (TEMPLATE_DIR, TEMPLATE_DIR / name):
            cand = base / f"{name}{suffix}" if base == TEMPLATE_DIR else base.with_suffix(".json")
            if cand.is_file():
                return json.loads(cand.read_text(encoding="utf-8"))
    return {}


def resolve(template: str = "youtube", preset: str = "youtube_1080p", overrides: dict | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    cfg.update({"template": template, "preset": preset})
    tpl = load_template(template)
    if isinstance(tpl, dict):
        cfg.update({k: v for k, v in tpl.items() if k != "presets"})
        presets = tpl.get("presets", {})
        if isinstance(presets, dict) and preset in presets:
            cfg.update(presets[preset])
    if overrides:
        cfg.update(overrides)
    return cfg
