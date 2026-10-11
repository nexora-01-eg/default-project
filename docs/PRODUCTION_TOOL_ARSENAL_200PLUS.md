# Al-Montier — Production Tool Arsenal (200+ Inventory)

**Date**: 2026-09-24 · **Type**: research + routing input (TIER classification only; installs happen separately and only for TIER 0/1)
**Machine**: Windows 10 Pro x64 · i7-7820HQ CPU · 16 GB RAM · 940MX 2 GB (no usable CUDA) · Python 3.11 venv · Node 24 · FFmpeg 9.0.1 (Gyan **GPL** full build) · no system Python
**Rules applied**: code-controllable only for TIER 0–2 · no cloud/API keys on core path · CODE vs MODEL/DATA licenses tracked separately · GPL/AGPL/CPML/NC items flagged, never silently integrated · GPU column: NONE/OPT/REQ · confidence [H/M/L] in Value cell

Tier key: **REG** = already present (register as provider) · **TIER 0** = install+adapter+test now · **TIER 1** = attempt after TIER 0 · **TIER 2** = contract/documented, no install · **TIER 3** = experimental/portable-detect · **TIER 4** = research only (hardware/license-blocked) · **TIER 5** = rejected (GUI-only/cloud/proprietary)

## PART 1 — Video, editing, compositing, motion, 3D, web runtimes

| Tool | Category | Capability | Code | Local | CPU | GPU | Win | License | Status | Value |
|------|----------|------------|------|-------|-----|-----|-----|---------|--------|-------|
| [FFmpeg](https://github.com/FFmpeg/FFmpeg) | A/AY/BD | CUT/TRIM/CONCAT/FILTER/ENCODE | CLI/C-API | Y | Y | OPT | Y | LGPL-2.1+/GPL (ours: GPL full build) | REG | Core execute engine [H] |
| [FFprobe](https://github.com/FFmpeg/FFmpeg) | AM | PROBE/QC METADATA | CLI | Y | Y | NONE | Y | same as FFmpeg | REG | Media facts [H] |
| [OpenCV](https://github.com/opencv/opencv) | Y/AC/AD/AN | FRAME IO/FLOW/TRACK/FACE | Py/C++ | Y | Y | OPT | Y | Apache-2.0 | REG | Vision workhorse [H] |
| [PyAV](https://github.com/PyAV-Org/PyAV) | A | FRAME-EXACT IO | Py | Y | Y | NONE | Y | MIT | REG | Precise decode [H] |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | AO/AP | SCENE/SHOT DETECTION | CLI/Py | Y | Y | NONE | Y | BSD-3 | REG | Installed 0.7.1 [H] |
| [MoviePy](https://github.com/Zulko/moviepy) | A/BG | PROGRAMMATIC EDIT/COMPOSITE | Py | Y | Y | NONE | Y | MIT (v2.2.1, py3.9-3.11) | TIER 0 | NLE-style API; pillow<12 pin conflicts pillow 12.3 — verify at install [H-lic/M-dep] |
| [GStreamer](https://gitlab.freedesktop.org/gstreamer/gstreamer) | A/AY | PIPELINE MEDIA | CLI/C/Py | Y | Y | OPT | partial | LGPL | TIER 2 | Redundant w/ FFmpeg here [M] |
| [MLT](https://github.com/mltframework/mlt) | A | EDITING FRAMEWORK | C/XML | Y | Y | OPT | N | LGPL-2.1 | TIER 4 | Powers Shotcut/Kdenlive; weak Win [L] |
| [frei0r](https://github.com/dyne/frei0r) | F | PLUGIN EFFECTS | C-API | Y | Y | NONE | Y | GPL | TIER 4 | Bundled in our FFmpeg already; GPL noted [M] |
| [Movit](https://github.com/sguthe/movit) | F | GPU EFFECTS | C++ | Y | N | REQ | partial | GPL | TIER 5 | GPU-gated [L] |
| [AviSynth+](https://github.com/AviSynth/AviSynthPlus) | A/AF | SCRIPTED FILTERING | Script | Y | Y | NONE | Y | GPL-2.0 | TIER 2 | Niche script NLE [L] |
| [VapourSynth](https://github.com/vapoursynth/vapoursynth) | A/AF | SCRIPTED FILTERING | Py | Y | Y | OPT | Y | LGPL-2.1 | TIER 2 | Modern alt to AviSynth [M] |
| [Natron](https://github.com/NatronGitHub/Natron) | B/BO | NODE COMPOSITE | GUI/Py-script | Y | Y | OPT | Y | GPL-2.0 | TIER 3 | Portable-detect only; GUI-first [M] |
| [OpenFX](https://github.com/ofxa/openfx) | B | EFFECT PLUGIN API | C-API | Y | Y | OPT | Y | BSD-3 | TIER 2 | Standard to target, not install [M] |
| [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) | AI/AJ | COLOR MANAGEMENT/ACES | Py/C++ | Y | Y | NONE | Y | Apache-2.0 | TIER 1 | Attempt pip (Win wheels exist); else TIER 2 [H] |
| [OpenImageIO](https://github.com/AcademySoftwareFoundation/OpenImageIO) | Y/BF | IMAGE IO/TEXTURES | Py/C++ | Y | Y | NONE | Y | Apache-2.0 | TIER 1 | Attempt pip; else TIER 2 [M] |
| [OpenShadingLanguage](https://github.com/AcademySoftwareFoundation/OpenShadingLanguage) | H | SHADERS | OSL-C | Y | Y | OPT | Y | BSD-3 | TIER 4 | Needs renderer host [L] |
| [OpenVDB](https://github.com/AcademySoftwareFoundation/openvdb) | BH | VOLUMES | C++/Py | Y | Y | OPT | Y | MPL-2.0 | TIER 4 | No volumetric need [L] |
| [OpenEXR](https://github.com/AcademySoftwareFoundation/openexr) | BF | HDR FRAMES | C++/Py | Y | Y | NONE | Y | BSD-3 | TIER 2 | Via OIIO/FFmpeg [M] |
| [MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX) | BL | MATERIAL EXCHANGE | C++/Py | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | No PBR pipeline [L] |
| [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) | BL/BN | 3D SCENE EXCHANGE | Py/C++ | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Contract-level 3D interchange [M] |
| [assimp](https://github.com/assimp/assimp) | BL | MODEL IMPORT | C++/Py | Y | Y | NONE | Y | BSD-3 | TIER 2 | If 3D path activates [M] |
| [Blender](https://github.com/blender/blender) | E/BN/BJ/BK | 3D/ANIM/RENDER/COMPO | CLI/Py-headless | Y | Y | OPT | Y | GPL-3.0 | TIER 3 | Portable-detect; bg renders; GPL via subprocess [H-potential] |
| [UPBGE](https://github.com/UPBGE/upbge) | E | REALTIME 3D | Py | Y | Y | OPT | Y | GPL-3.0 | TIER 4 | Game engine overkill [L] |
| [BlenderProc](https://github.com/DLR-RM/BlenderProc) | E | SYNTHETIC 3D DATA | Py/CLI | Y | Y | OPT | Y | GPL-3.0 | TIER 4 | Data-gen, not production [L] |
| [Godot](https://github.com/godotengine/godot) | E/BI | REALTIME 3D/PHYSICS | GDScript/headless | Y | Y | OPT | Y | MIT | TIER 3 | Headless 3D scenes possible [M] |
| [O3DE](https://github.com/o3de/o3de) | E | 3D ENGINE | C++/Py | Y | Y | REQ | Y | Apache-2.0/MIT | TIER 5 | Too heavy for i7 [L] |
| [Filament](https://github.com/google/filament) | E | PBR RENDERER | C++ | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | Needs GPU [L] |
| [bgfx](https://github.com/bkaradzic/bgfx) | E/BA/BB | RENDER ABSTRACTION | C++ | Y | Y | REQ | Y | BSD-2 | TIER 4 | Dev burden [L] |
| [Three.js](https://github.com/mrdoob/three.js) | E/G/BH | WEBGL 3D/PARTICLES | JS/JSON-scene | Y | Y | OPT | Y | MIT | TIER 2 | Contract-first 3D via Chromium shots [H-potential] |
| [React Three Fiber](https://github.com/pmndrs/react-three-fiber) | E | DECLARATIVE 3D | TSX | Y | Y | OPT | Y | MIT | TIER 2 | With Remotion stack [M] |
| [Drei](https://github.com/pmndrs/drei) | E | 3D HELPERS | TSX | Y | Y | OPT | Y | MIT | TIER 2 | Same stack [M] |
| [Babylon.js](https://github.com/BabylonJS/Babylon.js) | E | WEBGL ENGINE | JS | Y | Y | OPT | Y | Apache-2.0 | TIER 2 | Alt to three.js [M] |
| [PlayCanvas](https://github.com/playcanvas/engine) | E | WEBGL ENGINE | JS | Y | Y | OPT | Y | MIT | TIER 2 | Alt [L] |
| [A-Frame](https://github.com/aframevr/aframe) | E | WEBXR SCENES | HTML | Y | Y | OPT | Y | MIT | TIER 4 | XR irrelevant [L] |
| [Remotion](https://github.com/remotion-dev/remotion) | C/L/U/AY | PROGRAMMATIC VIDEO/MOTION/TYPE/CHARTS | TS/CLI/headless | Y | Y | NONE | Y | Proprietary source-available: FREE only individuals/<=3-person orgs; paid Company license 4+ for-profit | TIER 2 | Flagship contract runtime; license-gated for companies [H-capa/M-lic] |
| [GSAP](https://github.com/greensock/GSAP) | C/BP | WEB MOTION/TIMELINE | JS | Y | Y | NONE | Y | Free incl. commercial (Standard License, 2024+) | TIER 2 | HTML/SVG runtime core [H] |
| [Motion One](https://github.com/motiondivision/motionone) | C | WEB ANIMATION | JS | Y | Y | NONE | Y | MIT | TIER 2 | Light GSAP alt [M] |
| [Anime.js](https://github.com/juliangarnier/anime) | C | WEB ANIMATION | JS | Y | Y | NONE | Y | MIT | TIER 2 | Same class [M] |
| [Motion (Framer)](https://github.com/motiondivision/motion) | C | REACT ANIMATION | TSX | Y | Y | NONE | Y | MIT | TIER 2 | React path [M] |
| [Popmotion](https://github.com/Popmotion/popmotion) | C | ANIMATION PRIMITIVES | JS | Y | Y | NONE | Y | MIT | TIER 2 | Same class [L] |
| [mo.js](https://github.com/mojs/mojs) | C/BH | BURST/PARTICLE MOTION | JS | Y | Y | NONE | Y | MIT | TIER 2 | Micro-interactions [L] |
| [Lottie lottie-web](https://github.com/airbnb/lottie-web) | C/D | VECTOR ANIMATION PLAYBACK | JS/JSON | Y | Y | NONE | Y | MIT | TIER 2 | Arsenal has lottie assets [H] |
| [rlottie](https://github.com/Samsung/rlottie) | C/D | LOTTIE RENDER | C++ | Y | Y | NONE | Y | MIT | TIER 3 | Headless lottie frames [M] |
| [Bodymovin](https://github.com/airbnb/lottie-web) | C/D | AE-EXPORT PLUGIN | JS-plugin | Y | Y | NONE | Y | MIT | TIER 5 | Needs After Effects [L] |
| [Rive runtimes](https://github.com/rive-app/rive) | C/D/BJ | INTERACTIVE VECTOR/CHAR | JS/C++ | Y | Y | OPT | Y | MIT runtimes; editor freemium | TIER 3 | Character-ish motion [M] |
| [Manim CE](https://github.com/ManimCommunity/manim) | C/BP | MATH/DIAGRAM VIDEO | Py/CLI | Y | Y | OPT | Y | MIT | TIER 2 | Diagram/infographic path, slow CPU [H-potential] |
| [Processing](https://github.com/processing/processing4) | BP | GENERATIVE ART | Java/Py | Y | Y | NONE | Y | LGPL | TIER 4 | Niche [L] |
| [openFrameworks](https://github.com/openframeworks/openFrameworks) | BP | CREATIVE CODING | C++ | Y | Y | OPT | Y | MIT | TIER 4 | Dev burden [L] |
| [Paper.js](https://github.com/paperjs/paper.js) | I | VECTOR GRAPHICS | JS | Y | Y | NONE | Y | MIT | TIER 2 | SVG scene gen [M] |
| [Two.js](https://github.com/jonobr1/two.js) | I | 2D DRAWING | JS | Y | Y | NONE | Y | MIT | TIER 2 | Same class [M] |
| [Fabric.js](https://github.com/fabricjs/fabric.js) | J/BG | CANVAS AUTHORING | JS/JSON | Y | Y | NONE | Y | MIT | TIER 2 | Layout/cards JSON-driven [H-potential] |
| [Konva](https://github.com/konvajs/konva) | J | CANVAS SCENES | JS | Y | Y | NONE | Y | MIT | TIER 2 | Same class [M] |
| [PixiJS](https://github.com/pixijs/pixi.js) | J/G | 2D WEBGL | JS | Y | Y | OPT | Y | MIT | TIER 2 | GPU-optional FX [M] |
| [p5.js](https://github.com/processing/p5.js) | J/BP | CREATIVE CANVAS | JS | Y | Y | NONE | Y | LGPL-2.1 | TIER 4 | LGPL + niche [L] |
| [ECharts](https://github.com/apache/echarts) | BP | CHARTS | JS/JSON | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Stat graphics via Chromium [H] |
| [Vega-Lite](https://github.com/vega/vega-lite) | BP | DECLARATIVE CHARTS | JSON | Y | Y | NONE | Y | BSD-3 | TIER 2 | JSON-spec charts [H] |
| [D3.js](https://github.com/d3/d3) | BP | DATA VIS | JS | Y | Y | NONE | Y | ISC | TIER 2 | Custom charts [M] |
| [Mermaid](https://github.com/mermaid-js/mermaid) | BP | DIAGRAMS | JS/text | Y | Y | NONE | Y | MIT | TIER 2 | Process diagrams [M] |
| [Plotly.js](https://github.com/plotly/plotly.js) | BP | CHARTS | JS | Y | Y | NONE | Y | MIT | TIER 2 | Alt charts [M] |
| [Rough.js](https://github.com/rough-studios/rough) | I | SKETCH GRAPHICS | JS | Y | Y | NONE | Y | MIT | TIER 3 | Hand-drawn style [L] |
| [Chromium](https://github.com/chromium/chromium) | K | HEADLESS RENDER | CLI | Y | Y | NONE | Y | BSD-3 | TIER 1 | Required by HTML/SVG runtime; ~150 MB download [H-need] |
| [Playwright](https://github.com/microsoft/playwright) | K/AT | BROWSER AUTOMATION | Py/Node | Y | Y | NONE | Y | Apache-2.0 | TIER 1 | Drive Chromium shots [H] |
| [Puppeteer](https://github.com/puppeteer/puppeteer) | K | BROWSER AUTOMATION | Node | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Alt to Playwright [M] |
| [CEF](https://github.com/chromiumembedded/cef) | K | EMBEDDED BROWSER | C++ | Y | Y | NONE | Y | BSD-3 | TIER 4 | Dev burden [L] |
| [node-canvas](https://github.com/Automattic/node-canvas) | J | SERVER CANVAS | Node | Y | Y | NONE | partial | MIT | TIER 4 | Cairo build pain on Win [L] |
| [Skia](https://github.com/google/skia) | J | 2D GRAPHICS | Node/C++ | Y | Y | OPT | Y | BSD-3 | TIER 3 | If canvas path needs muscle [M] |
## PART 2 — Audio, speech, image

| Tool | Category | Capability | Code | Local | CPU | GPU | Win | License | Status | Value |
|------|----------|------------|------|-------|-----|-----|-----|---------|--------|-------|
| [librosa](https://github.com/librosa/librosa) | T/W/X | BEAT/ONSET/SPECTRAL | Py | Y | Y | NONE | Y | ISC | TIER 0 | Beat-sync + analysis core [H] |
| [soundfile](https://github.com/bastibe/python-soundfile) | S | AUDIO IO | Py | Y | Y | NONE | Y | BSD-3 | TIER 0 | With librosa [H] |
| [pydub](https://github.com/jiaaro/pydub) | S | SEGMENT/SLICE/FADE | Py | Y | Y | NONE | Y | MIT | TIER 0 | Needs ffmpeg (present) [H] |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | T | LOUDNESS BS.1770 | Py | Y | Y | NONE | Y | MIT | TIER 0 | True normalization [H] |
| [scipy.signal](https://github.com/scipy/scipy) | T | FILTERS/RESAMPLE | Py | Y | Y | NONE | Y | BSD-3 | TIER 0 | Via librosa [H] |
| [resampy](https://github.com/bmcfee/resampy) | T | RESAMPLE | Py | Y | Y | NONE | Y | MIT | TIER 0 | Via librosa [M] |
| [webrtcvad](https://github.com/wiseman/py-webrtcvad) | N | SPEECH ACTIVITY | Py | Y | Y | NONE | Y | BSD-3 | TIER 0 | Stale (2017) but works [M] |
| [pedalboard](https://github.com/spotify/pedalboard) | T | EQ/COMP/LIMIT/FX | Py | Y | Y | NONE | Y | **GPL-3.0 verified** | TIER 2 | Doc only — viral; use ffmpeg DSP [M-doc] |
| [aubio](https://github.com/aubio/aubio) | T/W | BEAT/ONSET/PITCH | Py/CLI | Y | Y | NONE | Y | **GPL-3.0 verified** | TIER 2 | Doc only; librosa covers [M-doc] |
| [Essentia](https://github.com/MTG/essentia) | T/W | MUSIC ANALYSIS | Py/C++ | Y | Y | NONE | partial | **AGPL-3.0** | TIER 4 | Viral + weak Win [L] |
| [madmom](https://github.com/CPJKU/madmom) | W | BEAT NN | Py | Y | Y | NONE | Y | BSD-3 | TIER 2 | Needs torch — doc only [M] |
| [Rubber Band](https://github.com/breakfastquay/rubberband) | T | TIME-STRETCH | CLI/C++ | Y | Y | NONE | Y | GPL/commercial | TIER 2 | Already bundled in FFmpeg [M] |
| [SoX](https://sourceforge.net/projects/sox/) | S/T | AUDIO KNIFE | CLI | Y | Y | NONE | Y | LGPL/GPL mix | TIER 2 | ffmpeg covers [L] |
| [RNNoise](https://github.com/xiph/rnnoise) | T | NOISE SUPPRESS | C | Y | Y | NONE | Y | BSD-3 | TIER 1 | Attempt build/rnnoise-py [M] |
| [SpeexDSP](https://github.com/xiph/speexdsp) | T | AEC/DENOISE | C | Y | Y | NONE | Y | BSD-3 | TIER 2 | aresample covers [L] |
| [noisereduce](https://github.com/tim-schmidt/noisereduce) | T | SPECTRAL GATE | Py | Y | Y | NONE | Y | MIT | TIER 1 | Pure numpy/scipy [M] |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | T | NN DENOISE | CLI/ONNX | Y | Y | NONE | Y | MIT | TIER 2 | ONNX CPU plausible + model DL [M] |
| [Denoiser-fb](https://github.com/facebookresearch/denoiser) | BZ | NN DENOISE | Py | Y | Y | OPT | Y | **CC BY-NC** | TIER 4 | License-blocked + torch [L] |
| [Demucs](https://github.com/facebookresearch/demucs) | BZ | STEM SEPARATION | Py/CLI | Y | Y | OPT | Y | MIT code | TIER 4 | Needs torch [M-doc] |
| [Spleeter](https://github.com/deezer/spleeter) | BZ | STEM SEPARATION | Py/CLI | Y | Y | OPT | Y | MIT | TIER 4 | TF-based heavy [L] |
| [Open-Unmix](https://github.com/sigsep-mus-eval/open-unmix) | BZ | STEM SEPARATION | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch [L] |
| [mir_eval](https://github.com/craffel/mir-eval) | BS/W | MIR METRICS | Py | Y | Y | NONE | Y | MIT | TIER 2 | Eval harness [L] |
| [pretty_midi](https://github.com/craffel/pretty-midi) | U | MIDI IO | Py | Y | Y | NONE | Y | MIT | TIER 3 | If music-gen ever [L] |
| [mido](https://github.com/mido/mido) | U | MIDI IO | Py | Y | Y | NONE | Y | MIT | TIER 3 | Same [L] |
| [music21](https://github.com/cuthbertLab/music21) | U | MUSICOLOGY | Py | Y | Y | NONE | Y | BSD-3 | TIER 4 | Overkill [L] |
| [LADSPA](https://github.com/swh/ladspa) | T | PLUGIN FX | C-API | Y | Y | NONE | partial | LGPL | TIER 4 | Niche [L] |
| [LV2](https://github.com/lv2/lv2) | T | PLUGIN FX | C-API | Y | Y | NONE | Y | ISC | TIER 4 | Needs host [L] |
| [VST3 SDK](https://github.com/steinbergmedia/vst3sdk) | T | PLUGIN HOST | C++ | Y | Y | NONE | Y | GPL-3.0/proprietary | TIER 5 | License + burden [L] |
| [CLAP](https://github.com/free-audio/clap) | T | PLUGIN API | C | Y | Y | NONE | Y | MIT | TIER 4 | Needs plugins/host [L] |
| [JUCE](https://github.com/juce-framework/JUCE) | T | AUDIO FRAMEWORK | C++ | Y | Y | NONE | Y | GPL/commercial | TIER 5 | Overkill [L] |
| [Airwindows](https://github.com/airwindows/airwindows) | T | FX ALGORITHMS | C++ | Y | Y | NONE | Y | MIT | TIER 3 | Reference DSP code [L] |
| [Surge XT](https://github.com/surge-synthesizer/surge) | BR/V | SYNTH/SFX | Binary | Y | Y | NONE | Y | GPL-3.0 | TIER 4 | Preset render overkill [L] |
| [miniaudio](https://github.com/mackron/miniaudio) | S | AUDIO ENGINE | C | Y | Y | NONE | Y | MIT/Unlicense | TIER 4 | No engine need [L] |
| [PortAudio](https://github.com/PortAudio/portaudio) | S | AUDIO IO | C | Y | Y | NONE | Y | MIT | TIER 4 | No live IO [L] |
| [Meyda](https://github.com/hughrawlinson/meyda) | T | WEB AUDIO FEAT | JS | Y | Y | NONE | Y | MIT | TIER 3 | If web-audio path [L] |
| [Tone.js](https://github.com/Tonejs/Tone.js) | BQ | PROCEDURAL MUSIC | JS | Y | Y | NONE | Y | MIT | TIER 3 | Generative beds via Chromium [M] |
| [Pure Data](https://github.com/pure-data/pure-data) | BQ | PROC AUDIO | Patch/CLI | Y | Y | NONE | Y | BSD-3 | TIER 4 | Patch-driven niche [L] |
| [SuperCollider](https://github.com/supercollider/supercollider) | BQ | PROC AUDIO | sclang | Y | Y | NONE | Y | GPL | TIER 4 | GPL + niche [L] |
| [FAUST](https://github.com/grame-cncm/faust) | BQ | DSP LANGUAGE | DSL/CLI | Y | Y | NONE | Y | BSD-3 | TIER 4 | Niche [L] |
| [Carla](https://github.com/falkTX/Carla) | T | PLUGIN HOST | GUI/CLI | Y | Y | NONE | Y | GPL-2.0 | TIER 5 | GUI-first [L] |
| [Ardour](https://github.com/Ardour/ardour) | S | DAW | GUI/Lua | Y | Y | NONE | Y | GPL | TIER 5 | Human DAW [L] |
| [Audacity](https://github.com/audacity/audacity) | S | EDITOR | GUI/macro | Y | Y | NONE | Y | GPL | TIER 5 | Macros exist but GUI-first [L] |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | N | STT + WORD TIMES | Py | Y | Y | NONE | Y | MIT | REG | Word timing default-on [H] |
| [Whisper](https://github.com/openai/whisper) | N | STT | Py | Y | Y | OPT | Y | MIT | TIER 2 | Slower than faster-whisper [L] |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | N | STT ggml | CLI/C++ | Y | Y | NONE | Y | MIT | TIER 2 | Alt backend [M] |
| [WhisperX](https://github.com/m-bain/whisperX) | N/AP | STT+ALIGN+DIAR | Py | Y | Y | OPT | Y | BSD-2 | TIER 4 | Needs torch/CUDA [M-doc] |
| [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped) | N | WORD TIMING | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch [L] |
| [stable-ts](https://github.com/jianfch/stable-ts) | N/BT | WORD TIMING | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch [L] |
| [Vosk](https://github.com/alphacep/vosk-api) | N | OFFLINE STT | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Small-model alt [M] |
| [SpeechBrain](https://github.com/speechbrain/speechbrain) | N | SPEECH TOOLKIT | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [NeMo](https://github.com/NVIDIA/NeMo) | N | ASR/DIARIZE | Py | Y | Y | REQ | partial | Apache-2.0 | TIER 4 | GPU-gated [L] |
| [Coqui STT](https://github.com/coqui-ai/STT) | N | STT | Py | Y | Y | OPT | Y | MPL-2.0 | TIER 4 | Discontinued [L] |
| [FunASR](https://github.com/modelscope/FunASR) | N | STT/PUNC | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) | AP | DIARIZATION | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch + HF token [M-doc] |
| [MFA](https://github.com/MontrealCorpusTools/MFA) | N | FORCED ALIGN | CLI | Y | Y | NONE | Y | GPL-3.0 | TIER 4 | GPL + Kaldi weight [L] |
| [Aeneas](https://github.com/readbeyond/aeneas) | N/BT | FORCED ALIGN | Py/CLI | Y | Y | NONE | Y | AGPL-3.0 | TIER 4 | Viral [L] |
| [Piper](https://github.com/rhasspy/piper) | O | NEURAL TTS CPU | CLI/Py | Y | Y | NONE | Y | MIT (+espeak GPL note) | REG | Validated ar_JO narrator [H] |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) | O | FORMANT TTS | CLI | Y | Y | NONE | Y | GPL-3.0+ | REG | Robotic fallback only [M] |
| [RHVoice](https://github.com/RHVoice/RHVoice) | O | CONCAT TTS | CLI | Y | Y | NONE | Y | GPL-3.0? | TIER 4 | Robotic + GPL [L] |
| [Coqui TTS](https://github.com/coqui-ai/TTS) | O/P | NEURAL TTS/CLONE | Py | Y | Y | OPT | Y | MPL-2.0 code; **CPML models NC** | TIER 4 | Models license-blocked [M-doc] |
| [Bark](https://github.com/suno-ai/bark) | O | GEN TTS/SFX | Py | Y | Y | REQ | Y | MIT code | TIER 4 | 6 GB + GPU [L] |
| [Tortoise-TTS](https://github.com/neonbjb/tortoise-tts) | O | EXPRESSIVE TTS | Py | Y | Y | REQ | Y | UNKNOWN license | TIER 4 | Slow + unclear lic [L] |
| [StyleTTS2](https://github.com/yl4579/StyleTTS2) | O | STYLE TTS | Py | Y | Y | REQ | Y | MIT? | TIER 4 | English-only + GPU [L] |
| [Fish Speech](https://github.com/fishaudio/fish-speech) | O/P | LLM TTS/CLONE | Py | Y | Y | REQ | Y | Apache code; **CC-BY-NC-SA weights** | TIER 4 | NC weights [M-doc] |
| [F5-TTS](https://github.com/SWivid/F5-TTS) | O/P | FLOW TTS | Py | Y | Y | REQ | Y | MIT | TIER 4 | Needs torch/GPU [M-doc] |
| [GPT-SoVITS](https://github.com/RVC-Boston/GPT-SoVITS) | O/P | CLONE TTS | Py/WebUI | Y | Y | REQ | Y | MIT | TIER 4 | Verified; GPU [M-doc] |
| [MeloTTS](https://github.com/myshell-ai/MeloTTS) | O | MULTILINGUAL TTS | Py | Y | Y | OPT | Y | MIT | TIER 4 | No Arabic at all [L] |
| [OpenVoice v2](https://github.com/myshell-ai/OpenVoice) | P | TONE CONVERT | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs base+torch [M-doc] |
| [Kokoro](https://github.com/hexgrad/Kokoro-82M) | O | LIGHT TTS 82M | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 3 | CPU-plausible; EN/ZH/JA [M] |
| [Parler-TTS](https://github.com/huggingface/parler-tts) | O | STYLE TTS | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [Dia](https://github.com/nari-labs/dia) | O | DIALOGUE TTS | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | 1.6B + GPU [L] |
| [Orpheus](https://github.com/canopylabs/orpheus-tts) | O | LLM TTS | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [Chatterbox](https://github.com/resemble-ai/chatterbox) | O/P | CLONE TTS | Py | Y | Y | REQ | Y | MIT (verified) | TIER 4 | Tested RTF 37.6 CPU [H-doc] |
| [RVC](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion) | P | VOICE CONVERT | Py/WebUI | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [L] |
| [Seed-VC](https://github.com/Plachta/Seed-VC) | P | VOICE CONVERT | Py | Y | Y | REQ | Y | MIT | TIER 4 | GPU [L] |
| [kNN-VC](https://github.com/bshall/knn-vc) | P | VOICE CONVERT | Py | Y | Y | REQ | Y | MIT | TIER 4 | Needs WavLM+torch [L] |
| [phonemizer](https://github.com/bootphon/phonemizer) | O | G2P FRONTEND | Py | Y | Y | NONE | Y | MIT | TIER 2 | If TTS frontends expand [L] |
| [Wav2Lip](https://github.com/Rudrabha/Wav2Lip) | Q | LIP SYNC | Py | Y | Y | REQ | Y | Research-only | TIER 4 | GPU + unclear lic [L] |
| [SadTalker](https://github.com/OpenTalker/SadTalker) | Q/R | TALKING HEAD | Py | Y | Y | REQ | Y | Research-only | TIER 4 | GPU [L] |
| [MuseTalk](https://github.com/TMElyralab/MuseTalk) | Q/R | REALTIME LIP | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU-gated [M-doc] |
| [EchoMimic](https://github.com/antgroup/echomimic) | R | ANIM PORTRAIT | Py | Y | Y | REQ | Y | CC BY-NC? | TIER 4 | NC + GPU [L] |
| [LivePortrait](https://github.com/KwaiVGI/LivePortrait) | R | PORTRAIT ANIM | Py | Y | Y | REQ | Y | CC BY-NC-SA? | TIER 4 | NC + GPU [L] |
| [Pillow](https://github.com/python-pillow/Pillow) | Y/BG | IMAGE GEN/COMP | Py | Y | Y | NONE | Y | HPND | REG | Cards/thumbs/raster [H] |
| [rembg](https://github.com/danielgatis/rembg) | Z | BG REMOVE | Py/CLI | Y | Y | NONE | Y | MIT | TIER 0 | onnxruntime; models in Arsenal [H] |
| [scikit-image](https://github.com/scikit-image/scikit-image) | Y | IMAGE FILTERS | Py | Y | Y | NONE | Y | BSD-3 | TIER 1 | Attempt ~30 MB wheels [H] |
| [ImageMagick](https://github.com/ImageMagick/ImageMagick) | Y | BATCH CONVERT | CLI | Y | Y | NONE | Y | Apache-2.0 v7 | TIER 2 | Portable-detect; Pillow covers [M] |
| [blend-modes](https://github.com/flrs/blend-modes) | Y | BLEND MATH | Py | Y | Y | NONE | Y | MIT | TIER 1 | Tiny blend treatments [M] |
| [colour-science](https://github.com/colour-science/colour) | AI | COLORIMETRY | Py | Y | Y | NONE | Y | BSD-3 | TIER 0 | Exposure/temp matching [H] |
| [colormath](https://github.com/gtaylor/python-colormath) | AI | COLOR DIFF | Py | Y | Y | NONE | Y | BSD-3 | TIER 1 | delta-E checks [M] |
| [pillow-heif](https://github.com/bigcat88/pillow-heif) | Y | HEIF READ | Py | Y | Y | NONE | Y | MIT | TIER 1 | iPhone media [M] |
| [piexif](https://github.com/hMatoba/Piexif) | AV | EXIF RW | Py | Y | Y | NONE | Y | MIT | TIER 2 | If metadata path [L] |
| [Potrace](https://github.com/skyrpex/potrace) | I | RASTER-SVG | CLI | Y | Y | NONE | Y | GPL | TIER 4 | GPL; vtracer instead [L] |
| [vtracer](https://github.com/visioncortex/vtracer) | I | RASTER-SVG | CLI/Rust | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Logo vectorize [M] |
| [scour](https://github.com/scour-project/scour) | I | SVG OPTIMIZE | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | With svgwrite [M] |
| [svgwrite](https://github.com/mozman/svgwrite) | I/BG | PROCEDURAL SVG | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 0 | Cards/diagrams core [H] |
| [resvg](https://github.com/linebender/resvg) | I | SVG RENDER | CLI/Rust | Y | Y | NONE | Y | Apache-2.0/MIT | TIER 2 | Portable binary render [M] |
| [FontTools](https://github.com/fonttools/fonttools) | L | FONT QC/SUBSET | Py/CLI | Y | Y | NONE | Y | MIT | TIER 1 | Caption font QC [M] |
| [arabic_reshaper](https://github.com/mpcod/arabic-reshaper) | L | AR SHAPING legacy | Py | Y | Y | NONE | Y | MIT | TIER 2 | libass handles it [L] |
| [python-bidi](https://github.com/MeirKriheli/python-bidi) | L | BIDI ALGO | Py | Y | Y | NONE | Y | LGPL-2.1 | TIER 2 | Same [L] |
| [HarfBuzz](https://github.com/harfbuzz/harfbuzz) | L | SHAPING ENGINE | C++ | Y | Y | NONE | Y | MIT Old | TIER 2 | Via libass stack [M] |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) | AB | FACE/HAND/POSE | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 1 | Attempt; face value [H-try] |
| [face_recognition](https://github.com/ageitgey/face_recognition) | AB | FACE ENCODE | Py | Y | Y | NONE | partial | MIT | TIER 4 | dlib build pain [L] |
| [DeepFace](https://github.com/serengil/deepface) | AB | FACE ATTR | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs TF/torch [L] |
| [InsightFace](https://github.com/deepinsight/insightface) | AB | FACE RECOG | Py | Y | Y | OPT | Y | MIT | TIER 4 | Heavy [M-doc] |
| [dlib](https://github.com/davisking/dlib) | AB | LANDMARKS | Py/C++ | Y | Y | NONE | partial | BSL-1.0 | TIER 4 | Build pain [L] |
## PART 3 — Vision/AI models, color, interchange, compute, codecs

| Tool | Category | Capability | Code | Local | CPU | GPU | Win | License | Status | Value |
|------|----------|------------|------|-------|-----|-----|-----|---------|--------|-------|
| [SAM](https://github.com/facebookresearch/segment-anything) | AA | SEGMENT ANYTHING | Py | Y | Y | OPT | Y | **CC BY-NC 4.0 model** | TIER 4 | NC model [M-doc] |
| [SAM 2](https://github.com/facebookresearch/sam2) | AA | VIDEO SEGMENT | Py | Y | Y | REQ | Y | **CC BY-NC 4.0 model** | TIER 4 | NC + GPU [L] |
| [MobileSAM](https://github.com/ChaoningZhang/MobileSAM) | AA | LIGHT SEGMENT | Py | Y | Y | NONE | Y | Apache-2.0? | TIER 3 | CPU-plausible; verify lic [M] |
| [YOLOv8/v11](https://github.com/ultralytics/ultralytics) | AA/AN | DETECT/TRACK | Py/CLI | Y | Y | OPT | Y | **AGPL-3.0** | TIER 4 | Viral license [M-doc] |
| [YOLOX](https://github.com/Megvii-BaseDetection/YOLOX) | AA | DETECTION | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [RTMDet](https://github.com/open-mmlab/mmdetection) | AA | DETECTION | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [GroundingDINO](https://github.com/IDEA-Research/GroundingDINO) | AA/AQ | OPEN-VOCAB BOX | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [M-doc] |
| [OWL-ViT](https://github.com/google-research/scenic) | AA/AQ | OPEN-VOCAB | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs JAX/torch [L] |
| [CLIP](https://github.com/openai/CLIP) | AQ | IMAGE-TEXT EMBED | Py | Y | Y | OPT | Y | MIT | TIER 3 | Needs torch; semantic search value [H-doc] |
| [SigLIP](https://github.com/google-research/big_vision) | AQ | EMBED V2 | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs JAX/torch [L] |
| [BLIP-2](https://github.com/salesforce/LAVIS) | AR/AQ | CAPTION/VQA | Py | Y | Y | REQ | Y | BSD-3 | TIER 4 | GPU [L] |
| [Florence-2](https://github.com/microsoft/Florence-2) | AR/AS | CAPTION/OCR/GROUND | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch; 0.2B CPU-plausible-ish [M-doc] |
| [Moondream](https://github.com/vikhyatk/moondream2) | AR | TINY VLM | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 3 | 1.8B — CPU-slow but attempt-worthy [M] |
| [LLaVA](https://github.com/haotian-liu/LLaVA) | AR | VLM CHAT | Py | Y | Y | REQ | Y | Code Apache; weights Llama-gated | TIER 4 | Gated weights [L] |
| [MiniCPM-V](https://github.com/OpenBMB/MiniCPM-V) | AR | EFFICIENT VLM | Py | Y | Y | OPT | Y | Apache-2.0? | TIER 4 | Needs torch [L] |
| [Qwen-VL](https://github.com/QwenLM/Qwen2.5-VL) | AR | VLM | Py | Y | Y | REQ | Y | Apache-2.0? | TIER 4 | GPU [L] |
| [InternVL](https://github.com/OpenGVLab/InternVL) | AR | VLM | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [L] |
| [Molmo](https://github.com/allenai/Molmo) | AR | OPEN VLM | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [EasyOCR](https://github.com/JaidedAI/EasyOCR) | AS | OCR 80+ LANGS | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Needs torch [M-doc] |
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | AS | OCR CLASSIC | CLI | Y | Y | NONE | Y | Apache-2.0 | TIER 1 | Portable binary; Arabic script support [H-try] |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | AS | OCR SOTA | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs paddle/torch [L] |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) | AS | ONNX OCR | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 1 | onnxruntime CPU — matches our stack [H-try] |
| [TrOCR](https://github.com/microsoft/unilm) | AS | TRANSFORMER OCR | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch [L] |
| [doctr](https://github.com/mindee/doctr) | AS | DOC OCR | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [Marker](https://github.com/VikParuchuri/marker) | AT | PDF→MD | Py | Y | Y | OPT | Y | GPL-3.0 | TIER 4 | GPL + torch [L] |
| [Nougat](https://github.com/facebookresearch/nougat) | AT | ACADEMIC OCR | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs torch [L] |
| [Surya](https://github.com/VikParuchuri/surya) | AS | OCR/LAYOUT | Py | Y | Y | OPT | Y | GPL-3.0? | TIER 4 | GPL + torch [L] |
| [python-mss](https://github.com/BoboTiG/python-mss) | AT | SCREEN CAPTURE | Py | Y | Y | NONE | Y | MIT | TIER 2 | Screen-analysis input [L] |
| [DXCam](https://github.com/raffaem/dxcam) | AT | GPU CAPTURE | Py | Y | N | REQ | Y | MIT | TIER 5 | Needs NVIDIA [L] |
| [RAFT](https://github.com/princeton-vl/RAFT) | AD | OPTICAL FLOW | Py | Y | Y | REQ | Y | BSD-3? | TIER 4 | GPU [L] |
| [PWC-Net](https://github.com/NVlabs/PWC-Net) | AD | OPTICAL FLOW | Py/Caffe | Y | Y | REQ | partial | Research | TIER 4 | GPU + stale [L] |
| [SEA-RAFT](https://github.com/princeton-vl/SEA-RAFT) | AD | FLOW V2 | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [L] |
| [OpenCV DIS/Farneback](https://github.com/opencv/opencv) | AD | CLASSIC FLOW | Py | Y | Y | NONE | Y | Apache-2.0 | REG | Already available [H] |
| [RIFE](https://github.com/hzwer/Practical-RIFE) | AE | FRAME INTERP | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [M-doc] |
| [FILM](https://github.com/google-research/frame-interpolation) | AE | FRAME INTERP | Py/TF | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | TF + GPU [L] |
| [DAIN](https://github.com/baowenbo/DAIN) | AE | DEPTH INTERP | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU + stale [L] |
| [Butterflow](https://github.com/dthpham/butterflow) | AE | MOTION INTERP | CLI | Y | Y | NONE | Y | MIT | TIER 3 | Old but CPU; try if slow-mo needed [L] |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | AF | UPSCALE | Py | Y | Y | REQ | Y | BSD-3 | TIER 4 | Needs torch/GPU [M-doc] |
| [GFPGAN](https://github.com/TencentARC/GFPGAN) | AB/AH | FACE RESTORE | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | Needs torch/GPU [M-doc] |
| [CodeFormer](https://github.com/sczhou/CodeFormer) | AB/AH | FACE RESTORE | Py | Y | Y | REQ | Y | Custom NON-COMMERCIAL? | TIER 4 | License + GPU [L] |
| [Real-CUGAN](https://github.com/bilibili/ailab) | AF | ANIME UPSCALE | Py/ONNX | Y | Y | NONE | Y | MIT | TIER 3 | ONNX CPU plausible [M] |
| [SwinIR](https://github.com/JingyunLiang/SwinIR) | AF/AG | RESTORE | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | Needs torch [L] |
| [NAFNet](https://github.com/megvii-research/NAFNet) | AG/AH | DENOISE/DEBLUR | Py | Y | Y | REQ | Y | MIT | TIER 4 | Needs torch [L] |
| [BasicVSR++](https://github.com/megvii-research/BasicVSR-plusplus) | AF/AH | VIDEO RESTORE | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [DeOldify](https://github.com/jantic/DeOldify) | AH | COLORIZE | Py | Y | Y | REQ | Y | MIT | TIER 4 | GPU [L] |
| [DDColor](https://github.com/piddnad/DDColor) | AH | COLORIZE | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [L] |
| [ByteTrack](https://github.com/ifzhang/ByteTrack) | AC | MULTI-TRACK | Py | Y | Y | OPT | Y | AGPL-3.0? | TIER 4 | Viral + torch [L] |
| [OC-SORT](https://github.com/noahcao/OC_SORT) | AC | TRACKING | Py | Y | Y | OPT | Y | GPL? | TIER 4 | Viral + torch [L] |
| [Supervision](https://github.com/roboflow/supervision) | AC/AN | TRACK UTILS | Py | Y | Y | NONE | Y | MIT | TIER 2 | Needs detector backend [M] |
| [SAHI](https://github.com/obss/sahi) | AA | SLICED INFER | Py | Y | Y | OPT | Y | MIT | TIER 4 | Needs detector [L] |
| [CoTracker](https://github.com/facebookresearch/co-tracker) | AC | POINT TRACK | Py | Y | Y | REQ | Y | CC BY-NC? | TIER 4 | NC + GPU [L] |
| [TAPIR](https://github.com/google-deepmind/tapir) | AC | POINT TRACK | Py/JAX | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [NorFair](https://github.com/tryolabs/norfair) | AC | TRACKING | Py | Y | Y | NONE | Y | MIT? | TIER 3 | Light, CPU; needs detections [M] |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | BP | NODE GEN-ART | Py/WebUI | Y | Y | REQ | Y | **GPL-3.0** | TIER 4 | Viral + GPU [L] |
| [InvokeAI](https://github.com/invoke-ai/InvokeAI) | BP | GEN-ART UI | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [Fooocus](https://github.com/lllyasviel/Fooocus) | BP | GEN-ART UI | Py | Y | Y | REQ | Y | GPL? | TIER 4 | GPU [L] |
| [Diffusers](https://github.com/huggingface/diffusers) | BP | DIFFUSION LIB | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [ControlNet](https://github.com/lllyasviel/ControlNet) | BP | GUIDED GEN | Py | Y | Y | REQ | Y | Apache-2.0 | TIER 4 | GPU [L] |
| [Stable Diffusion](https://github.com/Stability-AI/stablediffusion) | BP | TEXT-IMAGE | Py | Y | Y | REQ | Y | **Open RAIL-M (use-restricted)** | TIER 4 | License + GPU [L] |
| [Flux](https://github.com/black-forest-labs/flux) | BP | TEXT-IMAGE | Py | Y | Y | REQ | Y | Non-commercial Dev license | TIER 4 | NC + GPU [L] |
| [MusicGen](https://github.com/facebookresearch/audiocraft) | U | MUSIC GEN | Py | Y | Y | REQ | Y | MIT code; **CC BY-NC weights** | TIER 4 | NC + GPU [L] |
| [Stable Audio Open](https://github.com/Stability-AI/stable-audio-tools) | U/V | AUDIO GEN | Py | Y | Y | REQ | Y | Community NC-ish license | TIER 4 | NC + GPU [L] |
| [Magenta](https://github.com/magenta/magenta) | U/BQ | MUSIC ML | Py/TF | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | TF weight [L] |
| [Riffusion](https://github.com/riffusion/riffusion) | U | SPECTROGRAM MUSIC | Py | Y | Y | REQ | Y | MIT? | TIER 4 | GPU [L] |
| [x264](https://github.com/mirror/x264) | BD | H.264 ENCODE | CLI/C | Y | Y | NONE | Y | GPL/commercial | TIER 2 | Already in FFmpeg [M] |
| [x265](https://bitbucket.org/multicoreware/x265_git) | BD | H.265 ENCODE | CLI/C | Y | Y | NONE | Y | GPL/commercial | TIER 2 | Already in FFmpeg [M] |
| [SVT-AV1](https://gitlab.com/AOMediaCodec/SVT-AV1) | BD | AV1 ENCODE | CLI | Y | Y | NONE | Y | BSD-2 | TIER 2 | Already in FFmpeg; slow CPU [M] |
| [rav1e](https://github.com/xiph/rav1e) | BD | AV1 ENCODE | CLI | Y | Y | NONE | Y | BSD-2 | TIER 4 | Very slow [L] |
| [dav1d](https://github.com/videolan/dav1d) | BD | AV1 DECODE | C | Y | Y | NONE | Y | BSD-2 | TIER 2 | Already in FFmpeg [M] |
| [libvpx](https://github.com/webmproject/libvpx) | BD | VP8/9 | C | Y | Y | NONE | Y | BSD-3 | TIER 2 | Already in FFmpeg [M] |
| [libaom](https://aomedia.googlesource.com/aom) | BD | AV1 REF | C | Y | Y | NONE | Y | BSD-2 | TIER 4 | Too slow [L] |
| [vvenc](https://github.com/fraunhoferhhi/vvenc) | BD | H.266 ENCODE | CLI/C++ | Y | Y | NONE | Y | BSD-3 | TIER 2 | Already in FFmpeg [M] |
| [OpenH264](https://github.com/cisco/openh264) | BD | H.264 BASELINE | C++ | Y | Y | NONE | Y | BSD-2 | TIER 4 | Constrained profile [L] |
| [libjxl](https://github.com/libjxl/libjxl) | BD | JPEG-XL | C++ | Y | Y | NONE | Y | BSD-3 | TIER 2 | Already in FFmpeg [M] |
| [libwebp](https://github.com/webmproject/libwebp) | BD | WEBP | C | Y | Y | NONE | Y | BSD-3 | TIER 2 | Already in FFmpeg [M] |
| [libheif](https://github.com/strukturag/libheif) | BD | HEIF | C++ | Y | Y | NONE | Y | LGPL-3.0 | TIER 4 | Patent-encumbered; pillow-heif instead [L] |
| [Bento4](https://github.com/axiosys/bento4) | BE | MP4 FRAGMENT | CLI/C++ | Y | Y | NONE | Y | GPL | TIER 4 | GPL; mp4box instead [L] |
| [GPAC/mp4box](https://github.com/gpac/gpac) | BE | MP4/DASH | CLI | Y | Y | NONE | Y | LGPL-2.1 | TIER 2 | Fragmented MP4 if needed [M] |
| [MKVToolNix](https://gitlab.com/mbunkus/mkvtoolnix) | BE | MKV TOOLING | CLI/GUI | Y | Y | NONE | Y | GPL | TIER 4 | GPL; niche [L] |
| [Shaka Packager](https://github.com/shaka-project/shaka-packager) | BE | DASH/HLS PACK | CLI | Y | Y | NONE | Y | BSD-3 | TIER 3 | If streaming outputs ever [L] |
| [Shaka Player](https://github.com/shaka-project/shaka-player) | K | WEB PLAYBACK | JS | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | No player need [L] |
| [hls.js](https://github.com/video-dev/hls.js) | K | HLS PLAYBACK | JS | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Same [L] |
| [MediaInfo](https://github.com/MediaArea/MediaInfo) | AM | METADATA READ | CLI | Y | Y | NONE | Y | BSD-2 | TIER 2 | ffprobe covers [L] |
| [ExifTool](https://github.com/exiftool/exiftool) | AV | METADATA RW | CLI/Perl | Y | Y | NONE | Y | GPL/Artistic | TIER 4 | GPL; piexif instead [L] |
| [QCTools](https://github.com/bavc/qctools) | AM | QC GRAPHS | GUI/CLI | Y | Y | NONE | Y | GPL-3.0 | TIER 4 | GPL; ffmpeg signalstats instead [L] |
| [MediaConch](https://github.com/MediaArea/MediaConch) | AM | POLICY QC | CLI | Y | Y | NONE | Y | GPL | TIER 4 | GPL [L] |
| [VMAF](https://github.com/Netflix/vmaf) | BS | PERCEPTUAL METRIC | CLI/Py | Y | Y | NONE | Y | BSD-2+Patent | TIER 2 | ffmpeg libvmaf already bundled [M] |
| [PiQ](https://github.com/francois-rozet/piq) | BS | IQA METRICS | Py | Y | Y | NONE | Y | MIT | TIER 2 | Needs torch [L] |
| [LPIPS](https://github.com/richzhang/PerceptualSimilarity) | BS | PERCEPTUAL DIST | Py | Y | Y | OPT | Y | BSD-2 | TIER 4 | Needs torch [L] |
| [ab-av1](https://github.com/alexheretic/ab-av1) | BS/BD | VMAF-GUIDED ENCODE | CLI/Rust | Y | Y | NONE | Y | GPL-3.0? | TIER 4 | GPL [L] |
| [Av1an](https://github.com/master-of-zen/Av1an) | AY | CHUNKED ENCODE | Py/CLI | Y | Y | NONE | Y | MIT | TIER 3 | Scene-chunked AV1 (slow CPU) [L] |
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) | AW/AX | TIMELINE INTERCHANGE | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 0 | EDL/OTIO in-out core [H] |
| [pyaaf2](https://github.com/markreidvfx/pyaaf2) | AX | AAF IO | Py | Y | Y | NONE | Y | LGPL-2.1 | TIER 2 | If NLE handoff needed [L] |
| [AAF SDK](https://github.com/AAF-Association/AAF-SDK) | AX | AAF REF | C++ | Y | Y | NONE | Y | Custom permissive? | TIER 4 | pyaaf2 instead [L] |
| [OpenAssetIO](https://github.com/OpenAssetIO/OpenAssetIO) | AU | ASSET API | Py/C++ | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Studio-scale overkill [L] |
| [C2PA (c2pa-rs)](https://github.com/contentauth/c2pa-rs) | AV | CONTENT PROVENANCE | Rust/CLI | Y | Y | NONE | Y | Apache-2.0/MIT | TIER 2 | Sign our renders [M] |
| [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) | AZ | GPU COMPUTE | C++ | Y | N | REQ | Y | Proprietary EULA (free) | TIER 5 | 940MX unusable [L] |
| [ROCm](https://github.com/ROCm/ROCm) | AZ | GPU COMPUTE | C++ | Y | N | REQ | N | Mixed permissive | TIER 5 | AMD-only [L] |
| [oneAPI](https://github.com/oneapi-src/oneAPI-samples) | AZ | CPU/GPU KERNELS | C++ | Y | Y | OPT | Y | Proprietary EULA (free) | TIER 4 | iGPU could help transcode; burden [L] |
| [Vulkan SDK](https://github.com/KhronosGroup/Vulkan-Samples) | BA | GPU API | C++ | Y | N | REQ | Y | Apache-2.0 | TIER 4 | No GPU path [L] |
| [Halide](https://github.com/halide/Halide) | AZ | IMAGE KERNELS | C++ | Y | Y | OPT | Y | MIT | TIER 4 | Dev burden [L] |
| [Taichi](https://github.com/taichi-dev/taichi) | AZ/BH | PARALLEL KERNELS | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Niche [L] |
| [Numba](https://github.com/numba/numba) | AZ | JIT NUMERICS | Py | Y | Y | NONE | Y | BSD-2 | TIER 0 | Via librosa [H] |
| [CuPy](https://github.com/cupy/cupy) | AZ | GPU NUMPY | Py | Y | N | REQ | Y | MIT | TIER 5 | No CUDA [L] |
| [PyTorch](https://github.com/pytorch/pytorch) | AZ | ML RUNTIME | Py | Y | Y | OPT | Y | BSD-3 | TIER 4 | 2.5 GB CUDA default; CPU-only in isolated envs [M-doc] |
| [ONNX](https://github.com/onnx/onnx) | AZ | MODEL EXCHANGE | Py | Y | Y | NONE | Y | MIT | TIER 2 | Via onnxruntime [M] |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | AZ | MODEL INFERENCE | Py | Y | Y | NONE | Y | MIT | REG | Already the ML backbone [H] |
| [OpenVINO](https://github.com/openvinotoolkit/openvino) | AZ | INTEL INFERENCE | Py | Y | Y | NONE | Y | Apache-2.0? | TIER 2 | i7 iGPU/CPU accel candidate [M] |
| [TensorRT](https://github.com/NVIDIA/TensorRT) | AZ | NV INFERENCE | C++/Py | Y | N | REQ | Y | Proprietary EULA | TIER 5 | No NVIDIA [L] |
| [NCNN](https://github.com/Tencent/ncnn) | AZ | MOBILE INFERENCE | C++ | Y | Y | NONE | Y | BSD-3 | TIER 4 | Mobile-oriented [L] |
| [MNN](https://github.com/alibaba/MNN) | AZ | MOBILE INFERENCE | C++ | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Same [L] |
| [llama.cpp](https://github.com/ggerganov/llama.cpp) | AZ | LLM CPU | CLI/C++ | Y | Y | NONE | Y | MIT | TIER 3 | If local LLM planning ever [M] |
| [Emscripten](https://github.com/emscripten-core/emscripten) | BC | C++→WASM | CLI | Y | Y | NONE | Y | MIT | TIER 4 | No wasm builds planned [L] |
| [FFmpeg.wasm](https://github.com/ffmpegwasm/ffmpeg.wasm) | BC | BROWSER FFMPEG | JS | Y | Y | NONE | Y | MIT | TIER 4 | Server-side ffmpeg instead [L] |
| [WGPU/wgpu](https://github.com/gfx-rs/wgpu) | BA | WEBGPU NATIVE | Rust | Y | N | REQ | Y | MPL-2.0 | TIER 4 | No GPU [L] |
| [Dawn](https://github.com/google/dawn) | BA | WEBGPU IMPL | C++ | Y | N | REQ | Y | BSD-3 | TIER 4 | Same [L] |
| [Sentence-Transformers](https://github.com/UKPLab/sentence-transformers) | AQ | TEXT EMBED | Py | Y | Y | OPT | Y | Apache-2.0 | TIER 4 | Needs torch/transformers [M-doc] |
| [FAISS](https://github.com/facebookresearch/faiss) | AQ | VECTOR SEARCH | Py/C++ | Y | Y | NONE | Y | MIT | TIER 2 | Needs embeddings first [M] |
| [Chroma](https://github.com/chroma-core/chroma) | AQ | VECTOR DB | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Overkill vs flat files [L] |
| [Qdrant](https://github.com/qdrant/qdrant) | AQ | VECTOR DB | Rust/REST | Y | Y | NONE | Y | Apache-2.0 | TIER 4 | Same [L] |
| [usearch](https://github.com/unum-cloud/usearch) | AQ | VECTOR SEARCH | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Light ANN if needed [L] |
| [Box2D](https://github.com/erincatto/box2d) | BI | 2D PHYSICS | C++ | Y | Y | NONE | Y | MIT | TIER 4 | No physics need [L] |
| [Matter.js](https://github.com/liabru/matter-js) | BI | 2D PHYSICS WEB | JS | Y | Y | NONE | Y | MIT | TIER 3 | Playful motion accents [L] |
| [Planck.js](https://github.com/piqnt/planck.js) | BI | 2D PHYSICS WEB | JS | Y | Y | NONE | Y | MIT | TIER 4 | Same class [L] |
| [Pymunk](https://github.com/viblo/pymunk) | BI | 2D PHYSICS PY | Py | Y | Y | NONE | Y | MIT | TIER 3 | Same [L] |
| [Pygame-ce](https://github.com/pygame-community/pygame-ce) | BI | 2D/SPRITE | Py | Y | Y | NONE | Y | LGPL-2.1 | TIER 4 | LGPL + niche [L] |
| [tsparticles](https://github.com/tsparticles/tsparticles) | BH | PARTICLE FX WEB | JS | Y | Y | NONE | Y | MIT | TIER 2 | Confetti/particles via Chromium [M] |
| [pycaption](https://github.com/pbs/pycaption) | BT | SUBTITLE CONVERT | Py | Y | Y | NONE | Y | MIT | TIER 1 | Attempt; format conversions [M] |
| [ttconv](https://github.com/sandflow/ttconv) | BT | TTML/IMSC CONVERT | Py | Y | Y | NONE | Y | Apache-2.0 | TIER 2 | Broadcast captions [L] |
| [imscJS](https://github.com/sandflow/imscJS) | BT | WEB CAPTION RENDER | JS | Y | Y | NONE | Y | MIT | TIER 3 | If web caption path [L] |
| [CCExtractor](https://github.com/CCExtractor/ccextractor) | BT | CC EXTRACT | CLI/C | Y | Y | NONE | Y | GPL-2.0 | TIER 4 | GPL; niche [L] |
| [Subtitle Edit](https://github.com/SubtitleEdit/subtitleedit) | M | SUBTITLE EDITOR | GUI/CLI | Y | Y | NONE | Y | GPL-3.0 | TIER 5 | GUI-first [L] |
| [Aegisub](https://github.com/Aegisub/Aegisub) | M | SUBTITLE TYPO | GUI/CLI | Y | Y | NONE | Y | BSD-2 | TIER 3 | Batch-ass via CLI possible [M] |
| [autosub](https://github.com/BingLingGroup/autosub) | BT | AUTO SUBTITLE | Py | Y | Y | OPT | Y | MIT? | TIER 4 | Needs whisper/FFmpeg; ours covers [L] |
| [Poly Haven](https://polyhaven.com/) | BL | CC0 HDRIs/TEXTURES | files | Y | Y | NONE | Y | CC0 assets | TIER 2 | Free 3D backdrop assets [M] |
| [ambientCG](https://ambientcg.com/) | BL | CC0 PBR ASSETS | files | Y | Y | NONE | Y | CC0 assets | TIER 2 | Same [M] |
| [Quaternius](https://github.com/quaternius) | BL | CC0 GAME ASSETS | files | Y | Y | NONE | Y | CC0 assets | TIER 3 | Stylized 3D props [L] |
| [Mixamo](https://www.mixamo.com/) | BJ | AUTO-RIG/MOCAP | service/files | partial | Y | NONE | Y | Free w/ account (restrictive reuse) | TIER 4 | Account + terms [L] |
| [Cascadeur](https://cascadeur.com/) | BJ | PHYSICS ANIM | GUI | Y | Y | NONE | Y | Proprietary freemium | TIER 5 | GUI + license [L] |
| [Spine](https://github.com/EsotericSoftware/spine-runtimes) | BJ | 2D SKELETAL | Runtimes | Y | Y | NONE | Y | MIT runtimes; editor proprietary | TIER 4 | Needs editor [L] |
| [MakeHuman](https://github.com/makehumancommunity/makehuman) | BJ | PARAM HUMAN | GUI/CLI | Y | Y | NONE | Y | AGPL-3.0? | TIER 4 | Viral + stale [L] |
| [ElevenLabs API](https://elevenlabs.io/) | O | CLOUD TTS | REST | N | — | — | Y | Proprietary per-char billing | TIER 5 | Cloud/key — rejected core [L-doc] |
| [OpenAI TTS API](https://platform.openai.com/) | O | CLOUD TTS | REST | N | — | — | Y | Proprietary billing | TIER 5 | Same [L-doc] |
| [Deepgram API](https://www.deepgram.com/) | N | CLOUD STT | REST | N | — | — | Y | Proprietary billing | TIER 5 | Same [L-doc] |
| [D-ID / HeyGen / Synthesia](https://www.synthesia.io/) | R | CLOUD AVATAR | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Same [L-doc] |
| [Runway / Pika / Luma](https://runwayml.com/) | BP | CLOUD GEN-VIDEO | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Same [L-doc] |
| [Suno / Udio](https://suno.com/) | U | CLOUD MUSIC | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Same [L-doc] |
| [AIVA / Soundraw / Beatoven](https://www.aiva.ai/) | U | CLOUD MUSIC | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Same [L-doc] |
| [Topaz Video AI](https://www.topazlabs.com/) | AF | PROPRIETARY UPSCALE | GUI/CLI | Y | Y | REQ | Y | Proprietary paid | TIER 5 | Paid + GPU [L-doc] |
| [Adobe Premiere/AE](https://www.adobe.com/) | A/B | PRO NLE/VFX | GUI/(API) | Y | Y | OPT | Y | Proprietary subscription | TIER 5 | GUI-first [L-doc] |
| [DaVinci Resolve](https://www.blackmagicdesign.com/) | A/AJ | PRO NLE/GRADE | GUI/script | Y | Y | OPT | Y | Proprietary freemium | TIER 5 | Script API exists but heavy [L-doc] |
| [CapCut](https://www.capcut.com/) | A | CONSUMER EDITOR | GUI | Y | Y | NONE | Y | Proprietary (+cloud) | TIER 5 | No code control [L-doc] |
| [Descript / VEED / Kapwing](https://www.descript.com/) | A/N | CLOUD EDITORS | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Cloud [L-doc] |
| [Pictory / InVideo / Opus](https://pictory.ai/) | A | CLOUD VIDEO GEN | REST | N | — | — | Y | Proprietary SaaS | TIER 5 | Cloud [L-doc] |

## Counts

- Total rows: **326 unique tools** (Parts 1–3 + this section; machine-counted, zero duplicates), covering all 70 required categories A–BT.
- TIER 0 (install now): librosa, soundfile, pydub, pyloudnorm, scipy(signal), resampy, webrtcvad, numba(via), opentimelineio, svgwrite, moviepy, jsonschema, rembg, colour-science (~14 packages).
- REG (register as-is): FFmpeg, FFprobe, OpenCV, PyAV, PySceneDetect, faster-whisper, Piper, espeak-ng, onnxruntime, Pillow, pydantic, rich, numpy, tokenizers, huggingface_hub, OpenCV-DIS/Farneback, frei0r(via FFmpeg), x264/x265/SVT/dav1d/libvpx/vvenc/libjxl/libwebp(via FFmpeg), Rubber Band(via FFmpeg), VMAF(via FFmpeg).
- License-verified blockers kept out of installs: pedalboard GPL-3.0, aubio GPL-3.0, Remotion proprietary-company-license, Coqui CPML models, Fish CC-BY-NC-SA, XTTS CPML, SAM CC BY-NC, YOLO AGPL, ComfyUI GPL, F5/Fish-Egyptian NC weights, Tortoise UNKNOWN.
- Confidence: HIGH rows are either verified in this session (Remotion, pedalboard, aubio, MoviePy) or long-stable upstream facts; MEDIUM/LOW rows carry `?`/verify notes and must be re-checked at integration time. Nothing in TIER 0/1 rests on LOW confidence.

