"""Phase 3 tests: Arabic dialects, Arabizi, mixed, regions, buyer categories."""
from oppengine import arabic_lang as AL
from oppengine import region as RG
from oppengine import revenue as REV


def test_egyptian_multi_signal():
    r = AL.analyze("عايز حد يعمللي برنامج، ازاي ألاقي حد كويس؟ فين المبرمجين؟")
    assert r["language"] == "ar" and r["dialect"] == "egyptian"
    assert len(r["signals"]["markers"]["egyptian"]) >= 2


def test_single_keyword_never_decides():
    # only one shared word (مش) -> must fall back to msa, not levantine/egyptian
    r = AL.analyze("انا مش متأكد من القرار الصحيح في هذا الموضوع المهم جدا")
    assert r["dialect"] == "msa"


def test_gulf():
    r = AL.analyze("ابغي مصمم، وش رايكم؟ شلون اتواصل معاه الحين؟")
    assert r["dialect"] == "gulf"


def test_levantine():
    r = AL.analyze("بدي حد يساعدني، شو الحل؟ كتير ضروري هلق")
    assert r["dialect"] == "levantine"


def test_maghrebi():
    r = AL.analyze("بغيت نخدم مع شي حد، واش كاين؟ بزاف ديال الخدمة")
    assert r["dialect"] == "maghrebi"


def test_iraqi():
    r = AL.analyze("اريد واحد يسويلي شغل، هسه اكو حد؟ شكو ماكو")
    assert r["dialect"] == "iraqi"


def test_sudanese():
    r = AL.analyze("داير زول يشتغل معاي، يا زول وينك؟")
    assert r["dialect"] == "sudanese"


def test_msa():
    r = AL.analyze("السلام عليكم، أحتاج نظام لإدارة المخزون في الشركة")
    assert r["language"] == "ar" and r["dialect"] == "msa"


def test_arabizi():
    r = AL.analyze("3ayez 7ad ye3mely el sho3'l da 3shan mehtag floos")
    assert r["language"] == "ar" and r["dialect"] == "arabizi"


def test_arabizi_not_english():
    r = AL.analyze("I need someone to build a dashboard for my startup")
    assert r["language"] == "en"


def test_mixed_ar_en():
    r = AL.analyze("عايز أعمل automation للـ invoices بتاعة الشركة")
    assert r["language"] == "ar" and r["mixed"] is True


def test_empty_unknown():
    assert AL.analyze("")["language"] == "unknown"
    assert AL.analyze("123 !!!")["language"] == "unknown"


def test_region_explicit_city():
    r = RG.detect_region("مطلوب مصمم في جدة، التواصل واتساب")
    assert r["region"] == "Saudi Arabia" and r["confidence"] == "high"
    assert "جده" in r["evidence"] or "جدة" in r["evidence"]


def test_region_demonym_medium():
    r = RG.detect_region("أحتاج فويس أوفر سعودي لمقطع قصير")
    assert r["region"] == "Saudi Arabia" and r["confidence"] == "medium"


def test_region_egypt_english():
    r = RG.detect_region("Looking for a Cairo-based designer, budget $200")
    assert r["region"] == "Egypt"


def test_region_unknown_no_inference_from_dialect():
    r = RG.detect_region("عايز حد يعمللي برنامج ازاي؟")  # clearly Egyptian, no place
    assert r["region"] == "Unknown"


def test_region_oman_ambiguous():
    r = RG.detect_region("مطلوب مندوب في عمان براتب مغري")
    assert r["region"] == "Unknown" and "ambiguous" in r["evidence"]


def test_region_oman_disambiguated_jordan():
    r = RG.detect_region("مطلوب مندوب في عمان، الأردن، براتب مغري")
    assert r["region"] == "Jordan"


def test_region_oman_disambiguated_muscat():
    r = RG.detect_region("مطلوب مندوب في عمان، مسقط، براتب مغري")
    assert r["region"] == "Oman"


def test_buyer_hiring_ar():
    r = REV.classify_revenue("محتاج حد يعمل برنامج مخزن")
    assert r["level"] in ("high", "medium")
    assert "hiring" in r["categories"] or "service_request" in r["categories"]


def test_buyer_service_request():
    r = REV.classify_revenue("عاوز شركة تعمل موقع للعيادة")
    assert "service_request" in r["categories"]


def test_buyer_software_request():
    r = REV.classify_revenue("السلام عليكم احتاج اصمم داتا بيس، ارجو توضيح السعر فى العرض وكم مده التنفيذ")
    assert "software_request" in r["categories"] and "price_request" in r["categories"]


def test_buyer_automation_request():
    r = REV.classify_revenue("محتاج اوتوميشن للشغل اليومي")
    assert "automation_request" in r["categories"] or "automation" in r["categories"]


def test_buyer_implementation_high():
    r = REV.classify_revenue("حد ينفذ المشروع ده لشركتنا، التواصل خاص")
    assert r["level"] == "high"
    assert "implementation_request" in r["categories"]


def test_buyer_price_request():
    r = REV.classify_revenue("كام تكلفة بناء متجر إلكتروني؟")
    assert "price_request" in r["categories"]


def test_buyer_business_problem_manual():
    r = REV.classify_revenue("بنعمل يدوي كل يوم وبياخد وقت كبير، محتاج حل")
    assert "business_problem" in r["categories"]
    assert "repeated_manual_work" in r["categories"]


def test_buyer_alternative():
    r = REV.classify_revenue("عايز بديل لبرنامج الحسابات الحالي")
    assert "alternative_request" in r["categories"]


def test_buyer_complaint_intent():
    r = REV.classify_revenue("جربت أدوات كتير ومش شغال، محتاج حد يعمل حل مخصوص")
    assert "complaint_with_solution_intent" in r["categories"]


def test_buyer_urgent_evidence():
    r = REV.classify_revenue("عاجل محتاج حد يخلص الشغل ده اليوم")
    assert "urgent_need" in r["categories"] and r["urgency"] == "high"


def test_arabic_text_not_commercial_by_itself():
    r = REV.classify_revenue("الطقس اليوم جميل والسماء صافية في المساء")
    assert r["level"] in ("unknown", "not_commercial")


def test_mostaql_sample_end_to_end():
    t = ("السلام عليكم احتاج اصمم داتا بيس ٣ جداول، ارجو توضيح السعر فى العرض "
         "وكم مده التنفيذ، الميزانية $100 - $250")
    lang = AL.analyze(t)
    assert lang["language"] == "ar"
    rev = REV.classify_revenue(t)
    assert rev["level"] in ("high", "medium")
    assert rev["payment_language"]  # budget present
    reg = RG.detect_region(t)
    assert reg["region"] == "Unknown"  # no place mentioned: no inference
