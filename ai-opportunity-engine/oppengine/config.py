"""Layered config: defaults < config.yaml < env vars < CLI overrides. No secrets in files."""
import os

DEFAULTS = {
    "db_path": "data/oppengine.db",
    "lmstudio_base": "http://localhost:127.0.0.1:1234",
    "chat_model": "qwen2.5-coder-7b-instruct",
    "embed_model": "text-embedding-nomic-embed-text-v1.5",
    "ai_timeout_s": 75,
    "max_llm_per_cycle": 4,
    "max_analyze_per_cycle": 60,
    "cycle_seconds": 600,
    "dashboard_host": "127.0.0.1",
    "dashboard_port": 8765,
    "lang": "ar",
    "theme": "dark",
    "http_timeout_s": 20,
    "http_user_agent": "AIOpportunityEngine/0.1 (local research; contact: owner-local)",
    "max_collect_per_source": 40,
    "dedup_threshold": 0.82,
    "cluster_threshold": 0.60,
    "min_requests_for_opportunity": 2,
    # Phase 2: comma-separated strings (simple yaml parser) or lists
    "disabled_sources": "",
    "reddit_subs": "",
    "rss_feeds": "",
    "telegram_channels": "",
    "marketplace_feeds": "",
}

ENV_MAP = {
    "OPPENGINE_DB": "db_path",
    "LMSTUDIO_BASE": "lmstudio_base",
    "OPPENGINE_PORT": "dashboard_port",
}


def load(yaml_path="config.yaml", overrides=None):
    cfg = dict(DEFAULTS)
    if yaml_path and os.path.exists(yaml_path):
        try:
            import re
            with open(yaml_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k in cfg:
                        if isinstance(cfg[k], int):
                            try:
                                cfg[k] = int(v)
                            except ValueError:
                                pass
                        elif isinstance(cfg[k], float):
                            try:
                                cfg[k] = float(v)
                            except ValueError:
                                pass
                        else:
                            cfg[k] = v
        except OSError:
            pass
    for env, key in ENV_MAP.items():
        if os.environ.get(env):
            v = os.environ[env]
            if isinstance(cfg[key], int):
                try:
                    cfg[key] = int(v)
                except ValueError:
                    continue
            else:
                cfg[key] = v
    for k, v in (overrides or {}).items():
        if v is not None:
            cfg[k] = v
    return cfg


def cfg_list(cfg, key):
    """Comma-separated string or list -> clean list."""
    v = cfg.get(key)
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).split(",") if x.strip()]
