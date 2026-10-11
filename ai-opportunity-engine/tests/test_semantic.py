from oppengine import semantic as SEM


def test_jaccard_identical():
    assert SEM.jaccard("hello world", "hello world") == 1.0


def test_jaccard_disjoint():
    assert SEM.jaccard("apple orange", "quantum xyzzy") == 0.0


def test_jaccard_arabic_similar():
    a = "محتاج أداة تطلع Reels من الفيديوهات الطويلة"
    b = "برنامج يقص الفيديوهات الطويلة إلى مقاطع قصيرة"
    assert SEM.jaccard(a, b) > 0.0


def test_cosine_bounds():
    assert SEM.cosine([1, 0], [0, 1]) == 0.0
    assert abs(SEM.cosine([1, 1], [1, 1]) - 1.0) < 1e-9


def test_similarity_fallback_offline():
    cfg = {"lmstudio_base": "http://127.0.0.1:9", "embed_model": "x"}
    import tempfile, os
    from oppengine import db as DB
    p = os.path.join(tempfile.mkdtemp(), "s.db")
    DB.init(p)
    s = SEM.similarity(cfg, p, 1, "hello world test", 2, "hello world test")
    assert s == 1.0  # pure jaccard fallback, no network
