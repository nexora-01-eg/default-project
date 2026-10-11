"""Source adapter contract (Phase 3 + Phase 14).

Every discovery source implements `SourceAdapter`. The core engine only ever
talks to this interface, so a new source can be added by dropping a module in
`app/sources/` and registering it — no engine change required.

Legal / ethical policy baked into the contract:
  * `search()` may only read publicly accessible endpoints.
  * No authentication bypass, no CAPTCHA solving, no paywall circumvention.
  * No private groups, no DMs, no automated outreach of any kind.
  * `robots.txt` is honoured when `respect_robots_txt` is enabled.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..models import DataOrigin, SourceHealth, SourceType


# ---------------------------------------------------------------------------
# Errors — all non-fatal: one failing source must never abort a scan.
# ---------------------------------------------------------------------------
class SourceError(Exception):
    """Base class for adapter failures."""

    retryable = True

    def __init__(self, message: str, *, url: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class SourceUnavailable(SourceError):
    """Network failure, DNS failure, 5xx, timeout."""


class SourceRateLimited(SourceError):
    """429 / explicit rate-limit signal."""

    retryable = True

    def __init__(self, message: str, *, retry_after: float | None = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.retry_after = retry_after


class CredentialRequired(SourceError):
    """Adapter is implemented but cannot run without operator-supplied creds."""

    retryable = False


class RobotsDisallowed(SourceError):
    """robots.txt forbids fetching this URL; we comply and skip it."""

    retryable = False


class NotImplementedAdapter(SourceError):
    """Placeholder adapter that is intentionally not implemented yet."""

    retryable = False


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class NormalizedResult:
    """The single normalized shape every adapter must return."""

    url: str
    title: str = ""
    text: str = ""
    author: str = ""
    author_handle: str = ""
    published_at: datetime | None = None
    external_id: str | None = None
    language: str = ""
    source_name: str = ""
    matched_query: str = ""
    score_hint: float = 0.0
    data_origin: str = DataOrigin.REAL.value
    metadata: dict[str, Any] = field(default_factory=dict)

    def combined_text(self, limit: int = 6000) -> str:
        return f"{self.title}\n{self.text}".strip()[:limit]


@dataclass
class AdapterCapabilities:
    supports_search: bool = True
    supports_fetch: bool = False
    supports_locations: bool = False
    supports_languages: bool = False
    requires_credentials: bool = False
    respects_robots: bool = True
    max_results_per_query: int = 25
    notes: str = ""


@dataclass
class HealthReport:
    status: SourceHealth
    detail: str = ""
    latency_ms: int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value if isinstance(self.status, SourceHealth) else str(self.status),
            "detail": self.detail,
            "latency_ms": self.latency_ms,
            "checked_at": self.checked_at.isoformat(),
        }


class SourceAdapter(abc.ABC):
    """Common interface implemented by every discovery source."""

    name: str = "unnamed"
    display_name: str = "Unnamed source"
    source_type: SourceType = SourceType.CUSTOM
    capabilities: AdapterCapabilities = AdapterCapabilities()

    def __init__(self, configuration: dict[str, Any] | None = None) -> None:
        self.configuration: dict[str, Any] = dict(configuration or {})
        self.rate_limit_hits = 0

    # -- required ---------------------------------------------------------
    @abc.abstractmethod
    def search(self, query: str, *, limit: int = 25) -> list[NormalizedResult]:
        """Return normalized public results for one query string."""

    # -- optional ---------------------------------------------------------
    def fetch(self, url: str) -> NormalizedResult | None:
        """Fetch and normalize a single public URL (used by detail views)."""
        raise CredentialRequired(f"{self.name} does not support single-URL fetch")

    def normalize(self, raw: Any) -> NormalizedResult | None:
        """Map a provider-specific record into `NormalizedResult`."""
        return raw if isinstance(raw, NormalizedResult) else None

    def health_check(self) -> HealthReport:
        """Cheap liveness probe. Must never raise."""
        return HealthReport(SourceHealth.UNKNOWN, "no health check implemented")

    # -- metadata ---------------------------------------------------------
    def describe(self) -> dict[str, Any]:
        caps = self.capabilities
        return {
            "name": self.name,
            "display_name": self.display_name,
            "type": self.source_type.value,
            "capabilities": {
                "supports_search": caps.supports_search,
                "supports_fetch": caps.supports_fetch,
                "supports_locations": caps.supports_locations,
                "supports_languages": caps.supports_languages,
                "requires_credentials": caps.requires_credentials,
                "respects_robots": caps.respects_robots,
                "max_results_per_query": caps.max_results_per_query,
            },
            "notes": caps.notes,
            "configuration_keys": sorted(self.configuration.keys()),
        }