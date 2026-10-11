"""RawResult — an item exactly as discovered, before AI interpretation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
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

from .base import Base, DataOrigin, utcnow


class RawResult(Base):
    """Kept verbatim so re-classification never requires re-fetching."""

    __tablename__ = "raw_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    search_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_searches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, default="")
    url_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(300), default="")
    author_handle: Mapped[str] = mapped_column(String(300), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(10), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    simhash: Mapped[str] = mapped_column(String(32), index=True, default="")
    matched_query: Mapped[str] = mapped_column(String(400), default="")
    data_origin: Mapped[str] = mapped_column(String(20), default=DataOrigin.REAL.value)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped["Source"] = relationship(back_populates="raw_results")  # noqa: F821
    leads: Mapped[list["Lead"]] = relationship(back_populates="raw_result")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("source_id", "url_hash", name="uq_raw_result_source_url"),
        Index("ix_raw_results_discovered_at", "discovered_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RawResult id={self.id} source_id={self.source_id} url={self.url[:60]!r}>"