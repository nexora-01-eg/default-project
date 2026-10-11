# -*- coding: utf-8 -*-
"""Generate the Mohamed production-test script via official Space API."""
import sys

sys.path.insert(0, r"C:\Users\NOUR SOFT\Documents\Default Project\tools\tts\voicetut-audition")
from run_audition import call_predict, OUT_DIR
import json

SCRIPT = (
    "بص، الذكاء الاصطناعي دلوقتي مش مجرد tool بيساعدك تخلص الشغل أسرع. "
    "هو بدأ يغيّر الـworkflow نفسه، من أول الفكرة لحد الـfinal result. "
    "بس الـcreative decision في الآخر لسه محتاجة إنسان فاهم هو عايز يوصل لإيه. "
    "وعشان كده، استخدام الـAI صح مش معناه إنك تختفي من الصورة، بالعكس، "
    "معناه إنك تركز أكتر على القرار."
)

if __name__ == "__main__":
    print("SCRIPT-CHARS %d" % len(SCRIPT), flush=True)
    rec = call_predict("Mohamed", SCRIPT)
    if rec.get("ok"):
        import shutil
        dest = str(OUT_DIR / "voice_mohamed_production_test.wav")
        shutil.copyfile(rec["wav"], dest)
        rec["production_wav"] = dest
    print(json.dumps(rec, ensure_ascii=True), flush=True)
