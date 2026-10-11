# DATA_MODEL.md

SQLite (`data/oppengine.db`), WAL mode, parameterized queries only.

- **sources**(name PK, kind, status, interval_s, last_attempt, last_success, consecutive_errors, backoff_until, meta)
- **raw_requests**(id, source, source_url UNIQUE, external_id, collected_at, published_at, original_text, language, author, author_url, raw_meta JSON, rejected_reason)
  - `source_url` UNIQUE = storage-level dedup. Similar posts are NEVER deleted; they link via normalized→members.
- **PublicContact**: `author/author_url` (+ email/website only if publicly present in text — no enrichment, no private lookup).
- **normalized**(id, raw_id UNIQUE, normalized_text, request_type, problem, desired_result, requirements[], constraints[], urgency, ai_relevance, ai_feasibility, confidence, provider, reasoning, cluster_id, created_at)
- **opportunities**(id, title, normalized_problem, category, request_count, unique_sources, freshness_score, growth_score, ai_feasibility, competition_note, gap_analysis, suggested_solution, local_feasibility, local_why, confidence, status[new|rejected|archived], score, evidence{scoring,sources}, created_at, updated_at)
- **opportunity_members**(opportunity_id, normalized_id UNIQUE, similarity)
- **solutions**(id, opportunity_id, name, url, capabilities, limitations, pricing, complaints, gap, source)
- **feedback**(id, opportunity_id, decision[interesting|ignore|already_solved|too_difficult|investigate|build|archive], reason, created_at)
- **embeddings**(normalized_id PK, model, vector JSON, dim) — cache; recomputed only on model change.
- **runs**(id, started_at, finished_at, source, collected, rejected, analyzed, ai_failures, duplicates, opportunities_new/updated, duration_s, error)
