# -*- coding: utf-8 -*-
import json

d = json.load(open(
    r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\voicetut-audition\voice_meta.json",
    encoding="utf-16"))
for v in d:
    if v["voice"] in ("Essam", "Ahmed", "Abdelrahman", "Hossam"):
        print("=" * 20, v["voice"])
        print(v["raw_tail"][-600:])
