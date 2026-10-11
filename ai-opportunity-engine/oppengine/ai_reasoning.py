"""AI reasoning layer: LM Studio chat (Qwen Coder) with deterministic fallback.

Every row stores provider ('lmstudio'|'rules') + confidence. Never pretends certainty.
"""
import json
import urllib.request

from . import normalize as nz
from .logging_utils import log
from .security import sanitize_text

FEASIBILITY_STATES = ["clearly_feasible", "feasible_with_human", "feasible_with_local_tools",
                      "feasible_with_external", "experimental", "difficult", "impractical",
                      "not_ai", "insufficient_info"]

SYSTEM = ("You are a demand-analysis assistant. Given a public request (Arabic or English), "
          "reply with ONLY a compact JSON object, no markdown, with keys: problem, desired_result, "
          "requirements(list), constraints(list), ai_relevance(high|medium|low|none), "
          "ai_feasibility(one of: clearly_feasible, feasible_with_human, feasible_with_local_tools, "
          "feasible_with_external, experimental, difficult, impractical, not_ai, insufficient_info), "
          "confidence(0-1), category(short slug), reasoning(one sentence).")


def _chat(cfg, text, lang):
    url = cfg["lmstudio_base"].rstrip("/") + "/v1/chat/completions"
    payload = {"model": cfg["chat_model"],
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": f"[{lang}] {text[:800]}"}],
               "temperature": 0.1, "max_tokens": 220}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg.get("ai_timeout_s", 90)) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    content = data["choices"][0]["message"]["content"].strip()
    # tolerate code fences
    if content.startswith("```"):
        content = content.strip("`").split("\n", 1)[-1]
        if content.lower().startswith("json"):
            content = content[4:]
    return json.loads(content)


def _rules_result(norm, rtype, relevance, conf, reason):
    feas = {"explicit_ai": "feasible_with_local_tools", "implicit_ai": "feasible_with_human",
            "automation": "experimental", "human_service": "not_ai",
            "not_ai": "not_ai", "unclear": "insufficient_info"}[rtype]
    return {"problem": norm["problem"], "desired_result": norm["desired_result"],
            "requirements": [], "constraints": [], "ai_relevance": relevance,
            "ai_feasibility": feas, "confidence": round(min(conf, 0.65), 2),
            "category": "general" if feas in ("not_ai", "insufficient_info") else "ai-service",
            "reasoning": reason, "provider": "rules"}


def analyze(text, lang, cfg, use_llm=True):
    """Return structured analysis dict incl. provider + confidence.

    Internal keys _llm_latency_ms / _llm_tokens carry usage stats (not stored)."""
    import time
    clean = sanitize_text(text)
    norm = nz.extract_fields(clean, lang)
    rtype, relevance, conf, reason = nz.classify_request(clean)
    base = _rules_result(norm, rtype, relevance, conf, reason)
    base.update({"normalized_text": norm["normalized_text"], "request_type": rtype,
                 "urgency": norm["urgency"], "language": lang})
    if not use_llm or (rtype in ("human_service", "unclear") and relevance == "none"):
        base["_llm_latency_ms"] = 0
        base["_llm_tokens"] = 0
        return base  # don't waste LLM budget on clearly non-AI or when budget spent
    t0 = time.time()
    try:
        llm = _chat(cfg, clean, lang)
        base["_llm_latency_ms"] = int((time.time() - t0) * 1000)
        base["_llm_tokens"] = 0  # usage block not exposed by all servers; UNKNOWN unless parsed
        if isinstance(llm, dict) and isinstance(llm.get("_usage_tokens"), int):
            base["_llm_tokens"] = llm["_usage_tokens"]
        feas = llm.get("ai_feasibility", base["ai_feasibility"])
        if feas not in FEASIBILITY_STATES:
            feas = base["ai_feasibility"]
        try:
            lconf = float(llm.get("confidence", 0.5))
        except (TypeError, ValueError):
            lconf = 0.5
        base.update({"problem": sanitize_text(str(llm.get("problem", base["problem"])), 500),
                     "desired_result": sanitize_text(str(llm.get("desired_result", "")), 500),
                     "requirements": [sanitize_text(str(x), 200) for x in (llm.get("requirements") or [])][:8],
                     "constraints": [sanitize_text(str(x), 200) for x in (llm.get("constraints") or [])][:8],
                     "ai_relevance": llm.get("ai_relevance", relevance) if llm.get("ai_relevance") in
                     ("high", "medium", "low", "none") else relevance,
                     "ai_feasibility": feas, "confidence": round(max(0.0, min(1.0, lconf)), 2),
                     "category": sanitize_text(str(llm.get("category", "general")), 60) or "general",
                     "reasoning": sanitize_text(str(llm.get("reasoning", reason)), 500),
                     "provider": "lmstudio"})
        return base
    except Exception as exc:  # LLM down/invalid JSON -> honest rules fallback
        log("analyze", "llm_fallback", status="warn", output={"error": str(exc)[:200]})
        base["ai_failure"] = True
        try:
            base["_llm_latency_ms"] = int((time.time() - t0) * 1000)
        except Exception:
            base["_llm_latency_ms"] = 0
        base["_llm_tokens"] = 0
        return base
