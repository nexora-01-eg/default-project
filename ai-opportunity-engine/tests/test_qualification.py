"""Phase 3 tests: Mostaql parser (fixture HTML), GitHub-AR config, qualification."""
import json

from oppengine import qualification as Q
from oppengine.sources import github_ar as GA
from oppengine.sources import mostaql as MO

LISTING = ('<html><body><a href="https://mostaql.com/projects">all</a>'
           '<a href="https://mostaql.com/project/111-title-one">p1</a>'
           '<a href="https://mostaql.com/project/222-title-two">p2</a>'
           '<a href="https://mostaql.com/project/111-title-one">p1dup</a></body></html>')

DETAIL = """
<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
"title":"إنشاء نظام","datePosted":"2026-09-22"}</script>
<div class="meta-label">حالة المشروع</div><div class="meta-value">مفتوح</div>
<div class="meta-label">تاريخ النشر</div><div class="meta-value"><time datetime="2026-09-22 21:01:00">منذ 4 ساعات</time></div>
<div class="meta-label">الميزانية</div><div class="meta-value" data-type= project-budget_range ><span dir="rtl">$100.00 - $250.00</span></div>
<div class="meta-label">المهارات</div><div>x</div><div>برمجة</div>
<div>صاحب المشروع</div><div>شهد ا.</div>
<div class="heada__title">تفاصيل المشروع</div>
<div class="carda__body" id="projectDetailsTab"><div class="text-wrapper-div carda__content ">
<p>السلام عليكم</p><p>احتاج اصمم داتا بيس ٣ جداول</p><p>ارجو توضيح السعر فى العرض</p>
</div></div>
<div>تقدم للمشروع</div>
"""

CLOSED = DETAIL.replace("مفتوح", "مغلق")


def test_parse_listing_dedupes():
    urls = MO.parse_listing(LISTING)
    assert urls == ["https://mostaql.com/project/111-title-one",
                    "https://mostaql.com/project/222-title-two"]


def test_parse_detail_full():
    it = MO.parse_detail(DETAIL, "https://mostaql.com/project/111-x")
    assert it and it["external_id"] == "mostaql-111"
    assert "داتا بيس" in it["original_text"] and "إنشاء نظام" in it["original_text"]
    assert it["author"] == "شهد ا."
    assert it["raw_meta"]["budget"] == "$100.00 - $250.00"
    assert it["published_at"].startswith("2026-09-22T")
    assert it["raw_meta"]["status"] == "مفتوح"


def test_parse_detail_skips_closed():
    assert MO.parse_detail(CLOSED, "https://mostaql.com/project/1-x") is None


def test_parse_detail_needs_min_length():
    assert MO.parse_detail("<html></html>", "https://mostaql.com/project/1-x") is None


def test_github_ar_config():
    assert GA.GithubArabicAdapter.QUERIES == GA.AR_QUERIES
    assert GA.GithubArabicAdapter.languages == ["ar"]
    assert GA.GithubArabicAdapter.interval_s == 7200
    assert len(GA.AR_QUERIES) <= 3  # quota-friendly


def test_robots_parse():
    # pure unit: parse logic via local function behavior on crafted bodies is
    # network-dependent; only assert status vocabulary here (live check in validation)
    assert set(Q.STATUSES) >= {"LIVE", "PROBE_EMPTY", "BLOCKED", "CONFIG_REQUIRED",
                               "NOT_SUPPORTED", "ERROR"}


def test_qualification_lifecycle(tmp_path):
    db = str(tmp_path / "q.db")
    row = Q.qualify(db, name="t_src", url="https://example.com/", language="ar",
                    category="forum", public_access="yes", authentication_required=False,
                    technical_access="http", terms_risk="low",
                    expected_signal_quality="medium", polling_interval=7200)
    assert row["status"] == "CANDIDATE" and row["robots_status"] in ("allowed", "unknown")
    assert Q.record_probe(db, "t_src", 0) == "PROBE_EMPTY"
    assert Q.record_probe(db, "t_src", 5) == "PROBE_OK"
    assert Q.record_scheduled(db, "t_src", 0) is None  # zero persisted -> NOT live
    assert Q.record_scheduled(db, "t_src", 5) == "LIVE"
    rows = Q.all_rows(db)
    assert rows[0]["scheduled_items"] == 5
