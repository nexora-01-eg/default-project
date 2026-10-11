"""Lead — a distilled, scored opportunity derived from raw results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
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
    DataOrigin,
    LeadStatus,
    LeadType,
    Urgency,
    utcnow,
)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("user_searches.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    raw_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_results.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(300), default="")
    author_handle: Mapped[str] = mapped_column(String(300), default="")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    detected_service: Mapped[str] = mapped_column(String(200), default="")
    detected_need: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    language: Mapped[str] = mapped_column(String(10), default="")
    budget: Mapped[str] = mapped_column(String(120), default="")
    timeline: Mapped[str] = mapped_column(String(200), default="")
    urgency: Mapped[str] = mapped_column(String(20), default=Urgency.UNKNOWN.value)

    intent_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    confidence_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    lead_type: Mapped[str] = mapped_column(String(30), default=LeadType.UNKNOWN.value)
    classification: Mapped[str] = mapped_column(
        String(30), default=Classification.UNKNOWN.value, index=True
    )
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    why_matched: Mapped[str] = mapped_column(Text, default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    contact_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW.value, index=True)
    duplicate_of: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    seen_count: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis_status: Mapped[str] = mapped_column(String(20), default=AIStatus.PENDING.value)
    ai_provider: Mapped[str] = mapped_column(String(60), default="")
    ai_model: Mapped[str] = mapped_column(String(120), default="")
    analyzer: Mapped[str] = mapped_column(String(40), default="heuristic")

    is_high_intent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    data_origin: Mapped[str] = mapped_column(String(20), default=DataOrigin.REAL.value, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    search: Mapped["UserSearch"] = relationship(back_populates="leads")  # noqa: F821
    source: Mapped["Source"] = relationship(back_populates="leads")  # noqa: F821
    raw_result: Mapped["RawResult | None"] = relationship(back_populates="leads")  # noqa: F821
    analyses: Mapped[list["AIAnalysis"]] = relationship(  # noqa: F821
        back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_leads_intent_created", "intent_score", "created_at"),
        Index("ix_leads_status_intent", "status", "intent_score"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lead id={self.id} intent={self.intent_score} status={self.status}>"