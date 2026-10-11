# Kinetic Caption Architecture

## Pipeline (`engine/tools/kinetic_captions.py` + whisper adapter)

words.json (STT-true timings ONLY, never invented) → cue chunking (≤8 words, split on >1.2 s gaps) → per-word `\kf` karaoke highlight + Latin-token emphasis color → ASS (Body) + keyword layer (Key) + title/end → libass burn. Max 2 visual layers; overload check in visual_review (events/s + layers).

## Proven / limits (smoke test evidence)

Mechanism proven: karaoke tags render, timings true, Latin emphasis works. Limit found: tiny-Whisper hallucinates on pathological input (2.4 s/char Piper speech → 6 garbage words), so v1 smoke captions were wrong-words — caught by frame review, repaired with span-level verbatim cues (midpoint split, documented approximation). Rule established: word karaoke requires better-than-tiny STT on the actual voice; base/small Whisper needs explicit provisioning (engine policy); STT upgrades needing torch/CUDA are TIER 4 on this hardware. Sidecars preserved (.ass + words.json); pycaption adapter converts SRT→VTT for interchange.
