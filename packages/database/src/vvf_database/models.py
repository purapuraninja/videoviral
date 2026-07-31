"""ORM models for Viral Video Factory.

Table set matches IMPLEMENTATION_PLAN.md section 7 plus the ``agents`` table
needed for the local-render-agent registration/claim protocol. Uses SQLAlchemy
2.0 ``Mapped`` style with prefixed UUID primary keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vvf_database.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    """Prefixed id, e.g. ``usr_...``."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("usr"))
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    research_runs: Mapped[list[ResearchRun]] = relationship(back_populates="created_by_user")
    approvals: Mapped[list[Approval]] = relationship(back_populates="approver")


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("rr"))
    status: Mapped[str] = mapped_column(String(24), default="draft")
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    research_prompt: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(16), default="id-ID")
    source_filters: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    period_days: Mapped[int] = mapped_column(Integer, default=7)
    platforms: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    render_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("render_profiles.id", use_alter=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    created_by_user: Mapped[User] = relationship(back_populates="research_runs")
    queries: Mapped[list[ResearchQuery]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    source_documents: Mapped[list[SourceDocument]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    candidates: Mapped[list[ContentCandidate]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ResearchQuery(Base):
    __tablename__ = "research_queries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("rq"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    query_text: Mapped[str] = mapped_column(String(1024), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_response_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped[ResearchRun] = relationship(back_populates="queries")


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("src"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), default="")
    publisher: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, default="")
    full_text_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped[ResearchRun] = relationship(back_populates="source_documents")
    candidate_links: Mapped[list[CandidateSource]] = relationship(
        back_populates="source_document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("research_run_id", "canonical_url", name="uq_source_doc_run_url"),
        Index("ix_source_doc_hash", "content_hash"),
    )


class ContentCandidate(Base):
    __tablename__ = "content_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("cand"))
    research_run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    facts_json: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    source_links: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=list)
    virality_score: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0)
    source_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    risk_flags: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(16), default="id-ID")
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    run: Mapped[ResearchRun] = relationship(back_populates="candidates")
    source_links_rel: Mapped[list[CandidateSource]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    approval: Mapped[Approval | None] = relationship(
        back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    render_jobs: Mapped[list[RenderJob]] = relationship(back_populates="candidate")

    __table_args__ = (
        CheckConstraint(
            "status in ('proposed','approved','rejected','expired')",
            name="candidate_status_valid",
        ),
        Index("ix_candidate_run_status", "research_run_id", "status"),
    )


class CandidateSource(Base):
    """Many-to-many join between candidates and source documents."""

    __tablename__ = "candidate_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("cs"))
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("content_candidates.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False
    )
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    candidate: Mapped[ContentCandidate] = relationship(back_populates="source_links_rel")
    source_document: Mapped[SourceDocument] = relationship(back_populates="candidate_links")

    __table_args__ = (
        UniqueConstraint("candidate_id", "source_document_id", name="uq_cand_source"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("apv"))
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("content_candidates.id", ondelete="CASCADE"), nullable=False
    )
    render_profile_id: Mapped[str] = mapped_column(
        ForeignKey("render_profiles.id"), nullable=False
    )
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    candidate: Mapped[ContentCandidate] = relationship(back_populates="approval")
    approver: Mapped[User] = relationship(back_populates="approvals")
    render_profile: Mapped[RenderProfile] = relationship()
    render_job: Mapped[RenderJob | None] = relationship(
        back_populates="approval", uselist=False, cascade="all, delete-orphan"
    )


class RenderProfile(Base):
    __tablename__ = "render_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("rp"))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(8), default="9:16")
    resolution: Mapped[str] = mapped_column(String(16), default="1080x1920")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=45)
    language: Mapped[str] = mapped_column(String(16), default="id-ID")
    platforms: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    voice_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    subtitle_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    music_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    jobs: Mapped[list[RenderJob]] = relationship(back_populates="render_profile")


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("rj"))
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("content_candidates.id"), nullable=False
    )
    render_profile_id: Mapped[str] = mapped_column(
        ForeignKey("render_profiles.id"), nullable=False
    )
    approval_id: Mapped[str | None] = mapped_column(
        ForeignKey("approvals.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="queued")
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    claimed_by_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id"), nullable=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    candidate: Mapped[ContentCandidate] = relationship(back_populates="render_jobs")
    render_profile: Mapped[RenderProfile] = relationship(back_populates="jobs")
    approval: Mapped[Approval | None] = relationship(back_populates="render_job")
    events: Mapped[list[RenderJobEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    outputs: Mapped[list[VideoOutput]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    publish_targets: Mapped[list[PublishTarget]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    claimed_agent: Mapped[Agent | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status in ('queued','claimed','scripting','assets','tts','subtitles',"
            "'rendering','uploading','completed','publishing','published',"
            "'failed','cancelled','retry_waiting','publish_failed')",
            name="render_job_status_valid",
        ),
        Index("ix_render_job_status", "status"),
    )


class RenderJobEvent(Base):
    __tablename__ = "render_job_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("rje"))
    job_id: Mapped[str] = mapped_column(
        ForeignKey("render_jobs.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    job: Mapped[RenderJob] = relationship(back_populates="events")
    __table_args__ = (Index("ix_render_job_events_job", "job_id", "created_at"),)


class VideoOutput(Base):
    __tablename__ = "video_outputs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("vo"))
    job_id: Mapped[str] = mapped_column(
        ForeignKey("render_jobs.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # For binary artifacts this is the same as local_path (the VPS never stores the file).
    # For inline text artifacts this is a data: URI.
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The render PC that holds this artifact (for Tailscale preview resolution).
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped[RenderJob] = relationship(back_populates="outputs")
    __table_args__ = (Index("ix_video_outputs_job_type", "job_id", "artifact_type"),)


class PublishTarget(Base):
    """One platform's publish state for one render job (M6).

    Publishing runs on the render PC (where the video lives); this table records
    only the outcome — platform, mode, status, and the resulting post URL. No
    video bytes and no OAuth credentials are ever stored here.
    """

    __tablename__ = "publish_targets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("pt"))
    job_id: Mapped[str] = mapped_column(
        ForeignKey("render_jobs.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), default="auto")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    # Publishing metadata the agent uses (title/description/hashtags/private).
    request_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    claimed_by_agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    job: Mapped[RenderJob] = relationship(back_populates="publish_targets")

    __table_args__ = (
        CheckConstraint(
            "status in ('pending','publishing','published','failed',"
            "'manual_required','skipped')",
            name="publish_target_status_valid",
        ),
        CheckConstraint("mode in ('auto','manual')", name="publish_target_mode_valid"),
        UniqueConstraint("job_id", "platform", name="uq_publish_target_job_platform"),
        Index("ix_publish_targets_status", "status"),
    )


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("ag"))
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    mpt_base_url: Mapped[str] = mapped_column(String(255), default="http://127.0.0.1:8080")
    # Tailscale preview server (e.g. http://100.x.y.z:8090); empty = no preview.
    preview_base_url: Mapped[str] = mapped_column(String(255), default="")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    available_disk_gb: Mapped[float] = mapped_column(Float, default=0.0)
    mpt_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    active_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    claimed_jobs: Mapped[list[RenderJob]] = relationship(back_populates="claimed_agent")




