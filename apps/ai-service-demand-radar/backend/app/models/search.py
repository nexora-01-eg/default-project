"""UserSearch, Source and GeneratedQuery models."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SourceHealth, SourceType, utcnow


class UserSearch(Base):
    """A service the user offers. The unit of discovery work."""

    __tablename__ = "user_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["en"])
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    minimum_intent_score: Mapped[int] = mapped_column(Integer, default=0)
    schedule: Mapped[str] = mapped_column(String(80), default="manual")
    schedule_cron: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    generated_queries: Mapped[list["GeneratedQuery"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )
    leads: Mapped[list["Lead"]] = relationship(back_populates="search")  # noqa: F821
    scan_jobs: Mapped[list["ScanJob"]] = relationship(back_populates="search")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("service_name", name="uq_user_search_service_name"),
        Index("ix_user_searches_enabled", "enabled"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UserSearch id={self.id} service={self.service_name!r}>"


class GeneratedQuery(Base):
    """A search strategy string produced by the query generator (Phase 4).

    Persisted so the user can inspect/reuse exactly what was sent to sources.
    """

    __tablename__ = "generated_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("user_searches.id", ondelete="CASCADE"), index=True
    )
    query_text: Mapped[str] = mapped_column(String(400), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    category: Mapped[str] = mapped_column(String(60), default="intent")
    generator: Mapped[str] = mapped_column(String(40), default="heuristic")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    search: Mapped["UserSearch"] = relationship(back_populates="generated_queries")

    __table_args__ = (
        UniqueConstraint("search_id", "query_text", name="uq_generated_query_text"),
    )


class Source(Base):
    """Registry row for a discovery adapter (Phase 3 / Phase 14)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(40), default=SourceType.CUSTOM.value)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    health_status: Mapped[str] = mapped_column(String(40), default=SourceHealth.UNKNOWN.value)
    health_detail: Mapped[str] = mapped_column(Text, default="")
    requires_credentials: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scan: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    raw_results: Mapped[list["RawResult"]] = relationship(back_populates="source")  # noqa: F821
    leads: Mapped[list["Lead"]] = relationship(back_populates="source")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Source {self.name} enabled={self.enabled} health={self.health_status}>"