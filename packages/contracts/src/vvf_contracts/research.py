"""Research/discovery contracts: research runs, source documents, candidates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vvf_contracts.common import (
    CandidateStatus,
    LanguageCode,
    ResearchRunStatus,
    RiskFlag,
    TimestampMixin,
)


class ResearchRunCreate(BaseModel):
    """Body of POST /api/v1/research-runs."""

    keyword: str = Field(..., min_length=2, examples=["gempa bumi terkini"])
    research_prompt: str = Field(
        "",
        description="Optional admin guidance that shapes query variations and scoring.",
    )
    language: LanguageCode = LanguageCode.INDONESIAN
    source_filters: dict[str, Any] = Field(
        default_factory=lambda: {"allowed_domains": [], "blocked_domains": []}
    )
    period_days: int = Field(7, ge=1, le=365)
    platforms: list[str] = Field(default_factory=lambda: ["tiktok"])
    render_profile_id: str | None = None
    created_by: str = "admin"


class ResearchRunOut(ResearchRunCreate, TimestampMixin):
    id: str
    status: ResearchRunStatus = ResearchRunStatus.DRAFT
    candidate_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class SourceDocumentRaw(BaseModel):
    """Raw normalized result coming out of the wigolo adapter."""

    canonical_url: str
    title: str = ""
    publisher: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    excerpt: str = ""
    full_text_ref: str | None = None
    content_hash: str | None = None
    source_quality_score: float | None = None


class SourceDocumentOut(SourceDocumentRaw, TimestampMixin):
    id: str
    research_run_id: str
    model_config = ConfigDict(from_attributes=True)


class CandidateCreate(BaseModel):
    """Internal model used by the discovery worker when persisting a candidate."""

    research_run_id: str
    title: str
    summary: str = ""
    facts: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_links: list[dict[str, Any]] = Field(default_factory=list)
    virality_score: float = 0.0
    freshness_score: float = 0.0
    source_score: float = 0.0
    relevance_score: float = 0.0
    risk_score: float = 0.0
    final_score: float = 0.0
    rank: int = 0
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    language: LanguageCode = LanguageCode.INDONESIAN


class CandidateOut(CandidateCreate, TimestampMixin):
    id: str
    status: CandidateStatus = CandidateStatus.PROPOSED
    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "CandidateCreate",
    "CandidateOut",
    "CandidateStatus",
    "ResearchRunCreate",
    "ResearchRunOut",
    "ResearchRunStatus",
    "SourceDocumentOut",
    "SourceDocumentRaw",
]
