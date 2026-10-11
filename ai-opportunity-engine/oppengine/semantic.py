"""Semantic similarity: LM Studio embeddings (nomic) with token-Jaccard fallback.

Embeddings cached in DB. Cosine similarity in [0,1]-ish mapped to [0,1].
"""
import json
import math
import re
import urllib.request

TOK_RE = re.compile(r"[\w\u0600-\u06FF]+")


def tokens(s):
    return set(t for t in TOK_RE.findall((s or "").lower()) if len(t) > 1)


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _embed_remote(cfg, texts):
    url = cfg["lmstudio_base"].rstrip("/") + "/v1/embeddings"
    out = []
    for t in texts:
        payload = {"model": cfg["embed_model"], "input": (t or "")[:2000]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        out.append(data["data"][0]["embedding"])
    return out


def get_embedding(cfg, db_path, normalized_id, text):
    """Cached embedding; returns (vector|None, provider)."""
    import sqlite3
    from .db import connect
    cx = connect(db_path)
    try:
        row = cx.execute("SELECT vector, dim FROM embeddings WHERE normalized_id=?",
                         (normalized_id,)).fetchone()
        if row:
            return json.loads(row["vector"]), "cache"
    finally:
        cx.close()
    try:
        vec = _embed_remote(cfg, [text])[0]
        cx = connect(db_path)
        try:
            cx.execute("INSERT OR REPLACE INTO embeddings(normalized_id,model,vector,dim)"
                       " VALUES(?,?,?,?)", (normalized_id, cfg["embed_model"],
                                            json.dumps(vec), len(vec)))
            cx.commit()
        finally:
            cx.close()
        return vec, "lmstudio"
    except Exception:
        return None, "fallback"


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def similarity(cfg, db_path, id_a, text_a, id_b, text_b, vec_a=None, vec_b=None):
    """Best-effort similarity: embeddings when both available, else Jaccard blend."""
    if vec_a is None:
        vec_a, _ = get_embedding(cfg, db_path, id_a, text_a)
    if vec_b is None:
        vec_b, _ = get_embedding(cfg, db_path, id_b, text_b)
    if vec_a and vec_b and len(vec_a) == len(vec_b):
        return 0.7 * cosine(vec_a, vec_b) + 0.3 * jaccard(text_a, text_b)
    return jaccard(text_a, text_b)
