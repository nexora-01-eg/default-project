"""GitHub Arabic: public issues search with Arabic buyer phrasing (unauth, rate-limited).

Same endpoint/etiquette as GithubAdapter; 2 queries, 10 results each, 2h interval so
the shared unauthenticated search quota (10 req/min) is never stressed.
"""
from .github import GithubAdapter

AR_QUERIES = ["محتاج مساعدة sort:updated-desc", "مطلوب مطور sort:updated-desc"]


class GithubArabicAdapter(GithubAdapter):
    name = "github_ar"
    kind = "api"
    interval_s = 7200
    languages = ["ar"]
    source_type = "api"
    timeout_s = 20
    QUERIES = AR_QUERIES
    QUALIFY = {"url": "https://api.github.com/search/issues", "language": "ar",
               "category": "developer Q&A/issues", "public_access": "yes, public API (unauth quota)",
               "authentication_required": False, "technical_access": "JSON API",
               "terms_risk": "low: official API, 2 queries per 2h",
               "expected_signal_quality": "medium: Arabic help requests in issues",
               "polling_interval": 7200}
