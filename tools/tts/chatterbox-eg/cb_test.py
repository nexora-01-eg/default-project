# -*- coding: utf-8 -*-
"""Bounded Chatterbox-EG validation: Test A only. Stages: load_base | fetch_eg | synth."""
import sys
import time
import json
from pathlib import Path

EG_DIR = Path(__file__).resolve().parent
TEST_A = "بص يا جماعة، النهارده هنتكلم عن حاجة مهمة جدًا."
REPO = "AliAbdallah/egyptian-arabic-tts-chatterbox"


def stage_load():
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    dt = time.perf_counter() - t0
    n = sum(p.numel() for p in model.t3.parameters())
    print(json.dumps({"stage": "load_base", "load_s": round(dt, 1),
                      "t3_params": n, "sr": model.sr,
                      "cuda": torch.cuda.is_available()}))


def stage_fetch():
    import os
    from huggingface_hub import hf_hub_download
    t0 = time.perf_counter()
    p = hf_hub_download(repo_id=REPO, filename="model.safetensors")
    dt = time.perf_counter() - t0
    print(json.dumps({"stage": "fetch_eg", "path": p,
                      "bytes": os.path.getsize(p),
                      "fetch_s": round(dt, 1)}))


def stage_synth():
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    load_dt = time.perf_counter() - t0
    ckpt = hf_hub_download(repo_id=REPO, filename="model.safetensors")
    sd = load_file(ckpt, device="cpu")
    missing, unexpected = model.t3.load_state_dict(sd, strict=False)
    model.t3.eval()
    model.s3gen.eval()
    model.ve.eval()
    t1 = time.perf_counter()
    wav = model.generate(TEST_A, language_id="ar", exaggeration=0.5,
                         cfg_weight=0.5, temperature=0.8)
    gen_dt = time.perf_counter() - t1
    import soundfile as sf
    outdir = EG_DIR / "tests"
    outdir.mkdir(parents=True, exist_ok=True)
    out = str(outdir / "testA_eg.wav")
    arr = wav.squeeze(0).cpu().numpy()
    sf.write(out, arr, model.sr)
    dur = wav.shape[-1] / float(model.sr)
    import math
    finite = bool((arr == arr).all()) and math.isfinite(float(abs(arr).max()))
    print(json.dumps({"stage": "synth", "load_s": round(load_dt, 1),
                      "synth_s": round(gen_dt, 1),
                      "audio_s": round(dur, 2),
                      "rtf": round(gen_dt / dur, 3),
                      "sr": model.sr, "out": out,
                      "missing_keys": len(missing), "unexpected_keys": len(unexpected),
                      "peak_abs": round(float(abs(arr).max()), 4),
                      "all_finite": finite}))


if __name__ == "__main__":
    {"load_base": stage_load, "fetch_eg": stage_fetch,
     "synth": stage_synth}[sys.argv[1]]()
