# -*- coding: utf-8 -*-
import json
import re

d = json.load(open(
    r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\voicetut-audition\voice_meta.json",
    encoding="utf-16"))
for v in d:
    if "error" in v:
        print(v["voice"], "| ERROR", v["error"])
        continue
    tail = v["raw_tail"]
    chips = re.findall(r"vt-chip..>([^<]+)", tail)
    gender = re.findall(r"vt-gender..>([^<]+)", tail)
    status = "complete" if "event: complete" in tail else (
        "error" if "event: error" in tail else "incomplete")
    print(v["voice"], "|", status, "| gender:", gender, "| chips:", chips)
