"""Shared declarative base + enumerations for the Radar data model (Phase 2).

Design notes
------------
* SQLite-friendly types only (JSON columns, no server-specific types).
* Every timestamp is timezone-aware UTC (`utcnow`).
* Enum-like fields are stored as short strings so the DB stays readable and a
  future Postgres migration is trivial.
* `DataOrigin` is mandatory on raw results and leads: the dashboard MUST be
  able to distinguish REAL data from TEST and SIMULATED data
  (spec rule "DO NOT FAKE RESULTS").
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Timezone-aware UTC now (never naive)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


# ---------------------------------------------------------------------------
# Lead workflow
# ---------------------------------------------------------------------------
class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    REVIEWING = "REVIEWING"
    QUALIFIED = "QUALIFIED"
    IGNORED = "IGNORED"
    CONTACTED = "CONTACTED"
    CONVERTED = "CONVERTED"
    DUPLICATE = "DUPLICATE"


# ---------------------------------------------------------------------------
# AI classification vocabulary (Phase 5)
# ---------------------------------------------------------------------------
class Classification(str, enum.Enum):
    REAL_REQUEST = "REAL_REQUEST"
    POTENTIAL_REQUEST = "POTENTIAL_REQUEST"
    NOT_A_REQUEST = "NOT_A_REQUEST"
    ADVERTISEMENT = "ADVERTISEMENT"
    SELF_PROMOTION = "SELF_PROMOTION"
    DISCUSSION = "DISCUSSION"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"  # finished, but at least one source failed
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class SourceType(str, enum.Enum):
    WEB_SEARCH = "web_search"
    WEBSITE = "website"
    FORUM = "forum"
    REDDIT = "reddit"
    RSS = "rss"
    JOB_BOARD = "job_board"
    VIDEO = "video"
    CUSTOM = "custom"


class SourceHealth(str, enum.Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    CREDENTIAL_REQUIRED = "CREDENTIAL_REQUIRED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class DataOrigin(str, enum.Enum):
    """Provenance marker that the UI must always surface."""

    REAL = "REAL"            # fetched live from a public source
    TEST = "TEST"            # produced by the automated test suite
    SIMULATED = "SIMULATED"  # deliberately generated demo data


class AIStatus(str, enum.Enum):
    PENDING = "PENDING"  # AI unavailable -> analysis still owed
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Urgency(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class LeadType(str, enum.Enum):
    PERSON = "PERSON"
    BUSINESS = "BUSINESS"
    AGENCY_HIRING = "AGENCY_HIRING"
    UNKNOWN = "UNKNOWN"


class NotificationKind(str, enum.Enum):
    LEAD_DISCOVERED = "LEAD_DISCOVERED"
    SCAN_FAILED = "SCAN_FAILED"
    SOURCE_DEGRADED = "SOURCE_DEGRADED"
    INFO = "INFO"


class NotificationChannel(str, enum.Enum):
    DASHBOARD = "dashboard"
    WEBHOOK = "webhook"
    EMAIL = "email"


#: Human-friendly schedule presets exposed to the UI (Phase 12).
SCHEDULE_PRESETS: dict[str, str | None] = {
    "manual": None,
    "every_15_minutes": "*/15 * * * *",
    "every_30_minutes": "*/30 * * * *",
    "hourly": "0 * * * *",
    "every_6_hours": "0 */6 * * *",
    "daily": "0 8 * * *",
    "custom": None,
}