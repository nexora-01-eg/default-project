"""AIAnalysis, ScanJob and NotificationEvent models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    AIStatus,
    Base,
    Classification,
    NotificationChannel,
    NotificationKind,
    ScanStatus,
    utcnow,
)


class AIAnalysis(Base):
    """One AI classification pass over one lead (audit trail, Phase 5)."""

    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(60), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    classification: Mapped[str] = mapped_column(
        String(30), default=Classification.UNKNOWN.value
    )
    intent_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default=AIStatus.PENDING.value)
    error: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="analyses")  # noqa: F821


class ScanJob(Base):
    """A single execution of the discovery pipeline."""

    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("user_searches.id", ondelete="CASCADE"), index=True
    )
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual|schedule|cli
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ScanStatus.PENDING.value, index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    sources_scanned: Mapped[int] = mapped_column(Integer, default=0)
    sources_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, default=0)
    results_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    filtered_out: Mapped[int] = mapped_column(Integer, default=0)
    queries_used: Mapped[int] = mapped_column(Integer, default=0)
    ai_pending: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    log_path: Mapped[str] = mapped_column(Text, default="")

    search: Mapped["UserSearch"] = relationship(back_populates="scan_jobs")  # noqa: F821

    __table_args__ = (Index("ix_scan_jobs_search_started", "search_id", "started_at"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScanJob id={self.id} status={self.status} leads={self.leads_found}>"


class NotificationEvent(Base):
    """An alert produced by the alert engine (Phase 13).

    A dashboard notification is always written; webhook/email delivery is
    attempted only when the operator configured it. We never contact leads.
    """

    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), default=NotificationKind.INFO.value)
    channel: Mapped[str] = mapped_column(
        String(20), default=NotificationChannel.DASHBOARD.value
    )
    lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scan_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_error: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )