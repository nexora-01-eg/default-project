"""Radar data model package (Phase 2).

Import everything from here so the rest of the codebase never needs to know
how the model modules are split:

    from .models import Base, UserSearch, Lead, LeadStatus
"""

from .base import (
    AIStatus,
    Base,
    Classification,
    DataOrigin,
    LeadStatus,
    LeadType,
    NotificationChannel,
    NotificationKind,
    SCHEDULE_PRESETS,
    ScanStatus,
    SourceHealth,
    SourceType,
    Urgency,
    utcnow,
)
from .jobs import AIAnalysis, NotificationEvent, ScanJob
from .leads import Lead
from .results import RawResult
from .search import GeneratedQuery, Source, UserSearch

__all__ = [
    # base
    "AIStatus",
    "Base",
    "Classification",
    "DataOrigin",
    "LeadStatus",
    "LeadType",
    "NotificationChannel",
    "NotificationKind",
    "SCHEDULE_PRESETS",
    "ScanStatus",
    "SourceHealth",
    "SourceType",
    "Urgency",
    "utcnow",
    # search
    "GeneratedQuery",
    "Source",
    "UserSearch",
    # results
    "Lead",
    "RawResult",
    # jobs
    "AIAnalysis",
    "NotificationEvent",
    "ScanJob",
]