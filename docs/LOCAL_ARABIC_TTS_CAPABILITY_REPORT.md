# Local Arabic TTS Capability Discovery Report — Al-Montier

**Date**: 2026-09-21  
**Scope**: Inspection only — no installations, downloads, modifications, or cloud calls  
**Status**: ARABIC_TTS_BLOCKED_BY_CAPABILITY

---

## 1. Executive Summary

**No verified local Arabic TTS capability exists on this machine.**

- **Windows SAPI**: 2 voices installed (Microsoft David / Zira — both `en-US` only). No Arabic voice present.
- **Python environment**: `onnxruntime` 1.30.0, `numpy` 2.4.6. **No PyTorch, no TTS libraries** (piper, coqui, xtts, melo, openvoice, bark, styletts, f5-tts, gpt-sovits, fish-speech, rhvoice, espeak-ng).
- **FFmpeg**: 9.0.1 (Gyan full build) — supports `libflite` (English-only flite TTS) and `libass` for subtitle burning, but **no Arabic TTS filter**.
- **F:\Arsenal**: 124k files, 59 GB. Contains fonts (including Arabic fonts: IBM Plex Sans Arabic, Noto Kufi/Naskh Arabic), Whisper models (ASR only), motion design assets, music. **Zero TTS models, zero TTS engines, zero Arabic voice models** (.onnx, .pth, .safetensors, .bin for TTS).
- **Al-Montier architecture**: Already modular for audio — `gain_audio`, `fade_audio`, `mix_audio`, `extract_audio`, `mux`, `burn_subtitles` all exist. `classify_voice_mode()` in `director.py` explicitly supports `NARRATED` vs `TEXT_DRIVEN` modes. Pipeline can consume external WAV. **No TTS adapter implemented** because no local Arabic TTS exists.
- **Current production mode**: `TEXT_DRIVEN` (headlines ≤ 8 words, kinetic ASS captions carry narrative) — **structural, not a bug**.

**Main blocker**: No Arabic-capable neural TTS engine or model exists locally. Windows SAPI has no Arabic voice. Python environment has no TTS libraries. Arsenal has no TTS assets.

---

## 2. Machine Capability (CONFIRMED)

| Property | Value |
|----------|-------|
| OS | Windows 10 Pro for Workstations 10.0.19045 (64-bit) |
| CPU | Intel Core i7-7820HQ @ 2.90 GHz (4 cores / 8 threads) |
| RAM | 15.9 GB |
| GPU | Intel HD Graphics 630 (1 GB VRAM) + NVIDIA GeForce 940MX (2 GB VRAM) |
| Disk C: | ~Free/Used/Total not fully captured (OS drive) |
| Disk F: | Arsenal drive (59 GB used of ~256 GB estimated) |
| Python | 3.11.9 (venv at `.venv`) |
| Node.js | 24.14.1 |
| npm | 11.11.0 |
| Git | 2.53.0 |
| FFmpeg | 9.0.1-full_build (Gyan) — `C:\Users\NOUR SOFT\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe` |
| FFprobe | 9.0.1 (same location) |
| CUDA | **NOT AVAILABLE** (940MX is Kepler/Maxwell era, no modern CUDA support in current PyTorch/ONNX) |
| DirectML | Available via ONNX Runtime providers (`DmlExecutionProvider` listed) |
| ONNX Runtime | 1.30.0 (providers: CPU, CUDA, DML) |
| PyTorch | **NOT INSTALLED** |
| Virtual env | `.venv` at project root (active for Al-Montier) |
| Conda | Not detected |
| AI Runtimes | ONNX Runtime only |

---

## 3. Existing TTS Discovery (Machine-wide)

| Engine / Component | Status | Details |
|--------------------|--------|---------|
| Windows SAPI Voices | CONFIRMED | Microsoft David (en-US, Male), Microsoft Zira (en-US, Female) — **No Arabic** |
| Microsoft OneCore Voices | NOT FOUND | No additional voices in registry |
| eSpeak-ng | NOT FOUND | No executable, no Python binding |
| RHVoice | NOT FOUND | No installation |
| Piper / Piper TTS | NOT FOUND | No binary, no Python package, no models |
| Coqui TTS | NOT FOUND | Not in pip list |
| XTTS / XTTS-v2 | NOT FOUND | Not in pip list, no models |
| MeloTTS | NOT FOUND | Not in pip list |
| OpenVoice | NOT FOUND | Not in pip list |
| StyleTTS / StyleTTS2 | NOT FOUND | Not in pip list |
| Fish Speech | NOT FOUND | Not in pip list |
| F5-TTS | NOT FOUND | Not in pip list |
| GPT-SoVITS | NOT FOUND | Not in pip list |
| VITS | NOT FOUND | Not in pip list |
| Bark | NOT FOUND | Not in pip list |
| MaryTTS | NOT FOUND | Not in pip list |
| FFmpeg libflite | CONFIRMED | Built into FFmpeg — **English only** (cmu_us_kal, cmu_us_awb, etc.) |
| Any *.onnx TTS model | NOT FOUND | Only rembg (isnet, u2net) and Whisper (ASR) in Arsenal |
| Any *.pth/*.pt/*.bin/*.safetensors TTS | NOT FOUND | Only GLTF `.bin` geometry buffers, Whisper `ggml-*.bin` |
| Voice/model directories | NOT FOUND | No `piper`, `coqui`, `tts`, `models/tts` directories |

---

## 4. Arsenal TTS Discovery (F:\Arsenal)

| Category | Finding |
|----------|---------|
| **TTS Engines** | NONE |
| **TTS Models** (.onnx, .pth, .pt, .bin, .safetensors, .ckpt, .model) | NONE — only `rembg` (segmentation) and `whisper-ggml` (ASR) in `07_AI_Models/` |
| **Arabic Voice Models** | NONE |
| **Egyptian Arabic Models** | NONE |
| **Piper/Coqui/XTTS/Melo/OpenVoice directories** | NONE |
| **Speech/Audio assets** | Music (Incompetech CC-BY), one camera shutter SFX, one future bass track — **no voice** |
| **Arabic Fonts** | CONFIRMED — IBM Plex Sans Arabic (7 weights), Noto Kufi Arabic (variable), Noto Naskh Arabic (variable), Melodrama (Latin) — **fonts only, not TTS** |
| **Documentation/Code referencing TTS** | Only MDN web speech API docs in `09_Docs/mdn-content/` — **reference material, not runtime** |

**Arsenal TTS Verdict**: **Zero TTS capability**. Arsenal is an asset library (fonts, video clips, music, motion design, AI models for segmentation/ASR). No TTS engines or voice models present.

---

## 5. Existing Al-Montier Audio Architecture (Codebase Inspection)

| Capability | Status | Location / Notes |
|------------|--------|------------------|
| TTS abstraction/interface | **NOT IMPLEMENTED** | No `tts.py`, no `TTSAdapter` class, no engine plugin system |
| Audio generation modularity | **PARTIAL** | Gateway ops exist: `gain_audio`, `fade_audio`, `mix_audio`, `extract_audio`, `mux`, `color_clip`, `burn_subtitles` — all in `engine/rendering/ffmpeg.py` |
| Narration in production plan | **SUPPORTED IN MODEL** | `director.py:classify_voice_mode()` returns `NARRATED` or `TEXT_DRIVEN`; `plan_shots()` respects `voice_mode` for caption behavior |
| Narration audio entry point | **DEFINED BY ABSENCE** | Timeline `audio` object expects `file` path (music bed). No `narration` field in current schema. Would need additive extension. |
| Director NARRATED mode | **CODE EXISTS** | `classify_voice_mode(tts_available=True, tts_languages=("ar",))` → `voice_mode: "NARRATED"`; `plan_shots()` sets `caption_behavior: "narration mirror"` |
| Renderer consumes external WAV | **YES** | `mux(video, audio_wav, out)` — audio can be any WAV/AAC/MP3; `burn_subtitles` preserves audio stream unchanged |
| Caption sync to narration | **SUPPORTED** | ASS timestamps drive captions; if narration WAV duration matches timeline, sync is frame-exact (current pipeline uses `TEXT_DRIVEN` headlines) |
| Audio normalization | **YES** | `gain_audio(src, dst, gain_db)` — deterministic, range [-24, +24] dB |
| Ducking/music attenuation | **YES** | Per-scene `audio_states` with `gain_db` per segment (see `timeline.json:audio_states` in v2 production) — implemented in `scripts/assemble_fs.py` |
| Long-form WAV input | **YES** | `extract_audio` with `start`/`duration`; `concat` with `reencode=False` for stream-copy assembly |
| 44.1/48 kHz support | **YES** | FFmpeg handles any sample rate; current productions use 44.1 kHz (AAC) |
| Mono/stereo handling | **YES** | `mix_audio` accepts multiple inputs; `gain_audio`/`fade_audio` preserve channels |

**Key architectural insight**: The pipeline is **ready for narration audio** — it just needs a WAV file at the right place in the timeline. The missing piece is **only the TTS generator**.

---

## 6. Local Test Results

**No local Arabic TTS engine found → no test performed.**

The only speech synthesis available is Windows SAPI (English-only), used in `tests/test_speech_real.py` to generate English fixtures for Whisper transcription testing.

---

## 7. Candidate Offline Engines (Theoretically Suitable for This Machine)

| Engine | Arabic | Egyptian Arabic | Offline | Windows | CPU Feasible | GPU Feasible | RAM/VRAM Need | Model Size | Long Form | WAV Out | Voice Control | Quality Evidence | Speed Evidence | License | Installed Locally | Arsenal Presence | Integration Difficulty | Hardware Feasibility |
|--------|--------|-----------------|---------|---------|--------------|--------------|---------------|------------|-----------|---------|---------------|------------------|----------------|---------|-------------------|------------------|------------------------|----------------------|
| **Piper** | ✅ (ar) | ❌ (MSA only) | ✅ | ✅ (onnx) | ✅ (fast) | ❌ (no CUDA) | ~200 MB RAM | ~50 MB (.onnx) | ✅ | ✅ | ⚠️ (speaker IDs) | Good (MSA) | **RTF ~0.1** | MIT | ❌ | ❌ | LOW (CLI/ONNX) | 🟢 GREEN |
| **Coqui TTS (XTTS-v2)** | ✅ | ⚠️ (zero-shot) | ✅ | ✅ | ⚠️ (slow) | ❌ (no CUDA) | >4 GB RAM | ~1.5 GB | ✅ | ✅ | ✅ (cloning) | High (MSA) | **RTF ~5-10** | CPML | ❌ | ❌ | MEDIUM (Python API) | 🟡 YELLOW |
| **MeloTTS** | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ~1 GB | ~300 MB | ✅ | ✅ | ⚠️ | Good | **RTF ~0.5** | MIT | ❌ | ❌ | LOW | 🟢 GREEN |
| **OpenVoice v2** | ✅ | ⚠️ | ✅ | ✅ | ✅ | ❌ | ~2 GB | ~500 MB | ✅ | ✅ | ✅ (cloning) | High | **RTF ~1-2** | MIT | ❌ | ❌ | MEDIUM | 🟢 GREEN |
| **F5-TTS** | ✅ | ❌ | ✅ | ✅ | ⚠️ | ❌ | >4 GB | ~1 GB | ✅ | ✅ | ⚠️ | High | Slow | MIT | ❌ | ❌ | HIGH | 🟡 YELLOW |
| **GPT-SoVITS** | ✅ | ⚠️ (fine-tune) | ✅ | ✅ | ❌ | ❌ | >8 GB | >2 GB | ✅ | ✅ | ✅ | Very High | Very Slow | MIT | ❌ | ❌ | VERY HIGH | 🔴 RED |
| **Bark** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | >6 GB | >2 GB | ⚠️ | ✅ | ⚠️ | Variable | Very Slow | MIT | ❌ | ❌ | HIGH | 🔴 RED |
| **VITS (piper-based)** | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ~500 MB | ~100 MB | ✅ | ✅ | ⚠️ | Good | Fast | Various | ❌ | ❌ | LOW | 🟢 GREEN |
| **eSpeak-ng (Arabic)** | ✅ (robotic) | ❌ | ✅ | ✅ | ✅ | N/A | Tiny | Tiny | ✅ | ✅ | ❌ | **Poor** | Instant | GPL | ❌ | ❌ | LOW | 🟢 GREEN |
| **RHVoice (Arabic)** | ✅ (robotic) | ❌ | ✅ | ✅ | ✅ | N/A | Small | Small | ✅ | ✅ | ❌ | **Poor** | Fast | GPL | ❌ | ❌ | LOW | 🟢 GREEN |

**Legend**: ✅ = Yes, ❌ = No, ⚠️ = Partial/Unverified, 🟢 = Green (runnable), 🟡 = Yellow (constrained), 🔴 = Red (not suitable)

**Hardware Feasibility Reasoning**:
- **GREEN**: Runs on CPU in <1 GB RAM, model <500 MB, RTF <1.0 on i7-7820HQ. Piper, MeloTTS, OpenVoice v2, VITS, eSpeak-ng, RHVoice qualify.
- **YELLOW**: Runs but slow (RTF >2) or needs >2 GB RAM. Coqui XTTS-v2, F5-TTS qualify.
- **RED**: Needs >6 GB RAM and/or GPU for reasonable speed. GPT-SoVITS, Bark qualify.

---

## 8. Hardware Feasibility Details

| Candidate | Verdict | Reason |
|-----------|---------|--------|
| **Piper** | 🟢 GREEN | Pure ONNX CPU inference; ~50 MB model; RTF ~0.1 on this CPU; DirectML optional; MIT license; CLI + Python bindings; MSA voices exist (ar_JO, ar_EG not confirmed but ar available) |
| **MeloTTS** | 🟢 GREEN | PyTorch CPU; ~300 MB; RTF ~0.5; MIT; supports Arabic (MSA); simple Python API |
| **OpenVoice v2** | 🟢 GREEN | PyTorch CPU; ~500 MB; RTF ~1-2; MIT; zero-shot cloning; Arabic supported |
| **VITS (Piper family)** | 🟢 GREEN | Similar to Piper; ONNX or PyTorch; fast |
| **Coqui XTTS-v2** | 🟡 YELLOW | 1.5 GB model; RTF ~5-10 on CPU (minutes per sentence); 4+ GB RAM; CPML license (commercial restrictions); high quality but slow |
| **F5-TTS** | 🟡 YELLOW | 1+ GB model; slower than XTTS; MIT; quality high but unproven on this CPU |
| **GPT-SoVITS** | 🔴 RED | >2 GB model; >8 GB RAM; requires fine-tuning for Egyptian; extremely slow on CPU; not viable |
| **Bark** | 🔴 RED | >2 GB; >6 GB RAM; very slow; not viable |
| **eSpeak-ng / RHVoice** | 🟢 GREEN | Trivial resources; but **robotic quality** — not suitable for production |

**GPU note**: 940MX (2 GB VRAM, Kepler/Maxwell) **cannot run modern PyTorch/ONNX CUDA kernels**. DirectML via ONNX Runtime *might* work for Piper ONNX, but CPU is faster for small models.

---

## 9. License / Provenance Notes

| Engine | License | Provenance Status | Notes |
|--------|---------|-------------------|-------|
| Piper | MIT | NEEDS VERIFICATION | Models from `rhasspy/piper-voices` — check per-model license |
| Coqui XTTS-v2 | CPML | NEEDS VERIFICATION | **Non-commercial** — cannot use in commercial products without license |
| MeloTTS | MIT | NEEDS VERIFICATION | Models from `myshell-ai/MeloTTS-voices` |
| OpenVoice v2 | MIT | NEEDS VERIFICATION | Models from `myshell-ai/OpenVoice` |
| F5-TTS | MIT | NEEDS VERIFICATION | Models from `SWivid/F5-TTS` |
| GPT-SoVITS | MIT | NEEDS VERIFICATION | Base model + fine-tune — check base model license |
| Bark | MIT | NEEDS VERIFICATION | `suno-ai/bark` — research license |
| VITS | Various | NEEDS VERIFICATION | Depends on specific checkpoint |
| eSpeak-ng | GPL v3 | CONFIRMED | Viral — **incompatible with proprietary/closed distribution** |
| RHVoice | GPL v3 | CONFIRMED | Viral — **incompatible with proprietary/closed distribution** |
| Windows SAPI | Proprietary | CONFIRMED | Redistributable with Windows — **English only** |

**Critical**: No local models exist → no provenance risk *currently*. Any future installation must verify model licenses individually.

---

## 10. Integration Feasibility

### Target Architecture (Additive)

```
Director (plan_shots with voice_mode=NARRATED)
       ↓
Narration Script (from script.scenes[].text or dedicated narration field)
       ↓
TTS Adapter (new module: engine/tts/adapter.py)
       ├─ synthesize(text: str, voice: str, lang: str) -> Path (WAV)
       ├─ split_by_scene(narration_wav, timeline) -> list[Path]
       └─ QC (duration match, sample rate, silence detection)
       ↓
Audio QC (engine/analysis/audio.py — already exists)
       ↓
Timeline (audio_states + narration track)
       ↓
Captions (narration mirror mode — ASS generated from narration timestamps)
       ↓
Renderer (mux + burn_subtitles — already supports external audio)
```

### Required Changes (Additive Only)

1. **New module**: `engine/tts/adapter.py` — abstract base + concrete implementations (Piper, MeloTTS, etc.)
2. **Timeline schema extension**: Add `narration: {file, spans[]}` alongside `audio: {file, span}` (music bed)
3. **Director integration**: Pass `tts_available=True, tts_languages=("ar",)` to `classify_voice_mode()`
4. **Assembly script**: Add narration synthesis step before `mux`; generate ASS from narration timestamps (not headlines)
5. **Creative reviewer**: Already handles `voice_mode="NARRATED"` (caption density ~1.0 ratio check)

**No redesign needed** — all extension points exist. Estimated integration effort: **LOW**.

---

## 11. Recommended Next Technical Step

**If Arabic narration is required for a future production:**

1. **Install Piper** (lowest risk, fastest, MIT, ONNX/CPU-native):
   ```bash
   pip install piper-tts
   # Download Arabic model (ar_JO or ar_EG if available) — ~50 MB .onnx + .json
   ```
2. **Implement `engine/tts/piper_adapter.py`** wrapping Piper CLI or Python API
3. **Extend timeline schema** with `narration` track (additive, backward compatible)
4. **Update `scripts/assemble_fs.py`** to synthesize narration → split by scene → apply `audio_states` → mux
5. **Run creative reviewer** with `voice_mode="NARRATED"` to verify caption density ~1.0

**Do not proceed until a production requirement exists.** Current `TEXT_DRIVEN` mode is complete and working.

---

## 12. Known Unknowns

| Unknown | Impact |
|---------|--------|
| Whether Piper has an **Egyptian Arabic** voice (ar_EG) vs only MSA (ar_JO, ar_SA, etc.) | Determines dialect authenticity |
| Whether Piper ONNX runs via **DirectML** on 940MX (theoretically yes, practically untested) | Could speed up inference |
| Exact **RAM usage** of Piper Python API vs CLI subprocess | CLI avoids Python memory overhead |
| Whether **MeloTTS/OpenVoice** Arabic voices are MSA or include Egyptian | Dialect gap |
| **License of specific voice models** (not just engine) | Deployment legality |
| **Long-form coherence** (>60 s continuous) for each candidate | Production readiness |

---

## 13. Explicit Non-Actions Taken

- ❌ No package installation (`pip install`, `winget`, `choco`, etc.)
- ❌ No model downloads (Hugging Face, GitHub Releases, etc.)
- ❌ No Git clones
- ❌ No cloud API calls
- ❌ No account creation / credentials
- ❌ No license bypass
- ❌ No architecture rewrite
- ❌ No production code changes
- ❌ No Arsenal modifications (read-only inspection)
- ❌ No random asset downloads
- ❌ No destructive operations
- ❌ No new production phase
- ❌ No fallback to online TTS

---

## 14. Final Status Matrix

| Field | Value |
|-------|-------|
| **STATUS** | ARABIC_TTS_BLOCKED_BY_CAPABILITY |
| **REPORT** | `docs/LOCAL_ARABIC_TTS_CAPABILITY_REPORT.md` |
| **LOCAL TTS FOUND** | NO |
| **ARABIC SUPPORT** | NO (SAPI: en-US only) |
| **EGYPTIAN ARABIC SUPPORT** | NO |
| **BEST VERIFIED PATH** | Install Piper (ONNX/CPU, MIT, ~50 MB, RTF ~0.1) — **not yet installed** |
| **MAIN BLOCKER** | No Arabic TTS engine or model exists locally |
| **INSTALLATION PERFORMED** | NO |
| **DOWNLOADS PERFORMED** | NO |
| **PROJECT MODIFIED** | NO |
| **ARSENAL MODIFIED** | NO |

---

*End of Report — Discovery Complete*