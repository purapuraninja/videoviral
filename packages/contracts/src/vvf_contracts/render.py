"""Render-related contracts: profiles, jobs, events, outputs, and the job payload."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vvf_contracts.common import (
    AspectRatio,
    LanguageCode,
    Platform,
    RenderJobStatus,
    TimestampMixin,
    utcnow,
)


class RenderProfileCreate(BaseModel):
    """Admin-defined preset for a target platform/format."""

    name: str = Field(..., examples=["TikTok ID 45s"])
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT
    resolution: str = Field("1080x1920", examples=["1080x1920", "1920x1080"])
    duration_seconds: int = Field(45, ge=5, le=180)
    language: LanguageCode = LanguageCode.INDONESIAN
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.TIKTOK])
    voice_config: dict[str, Any] = Field(
        default_factory=lambda: {"provider": "edge", "voice": "id-ID-ArdiNeural"}
    )
    subtitle_config: dict[str, Any] = Field(
        default_factory=lambda: {"style": "bold-center", "position": "bottom"}
    )
    music_config: dict[str, Any] = Field(
        default_factory=lambda: {"profile": "news-modern"}
    )


class RenderProfileOut(RenderProfileCreate, TimestampMixin):
    id: str
    model_config = ConfigDict(from_attributes=True)


class ApprovalOut(TimestampMixin):
    id: str
    candidate_id: str
    render_profile_id: str
    approved_by: str
    model_config = ConfigDict(from_attributes=True)


class RenderJobOut(TimestampMixin):
    id: str
    candidate_id: str
    render_profile_id: str
    status: RenderJobStatus = RenderJobStatus.QUEUED
    payload_json: dict[str, Any] | None = None
    claimed_by_agent_id: str | None = None
    attempt: int = 0
    error_message: str | None = None
    idempotency_key: str
    model_config = ConfigDict(from_attributes=True)


class RenderJobEventOut(BaseModel):
    id: str
    job_id: str
    agent_id: str | None = None
    status: RenderJobStatus
    message: str = ""
    progress: int = Field(0, ge=0, le=100)
    log: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    model_config = ConfigDict(from_attributes=True)


class VideoOutputOut(BaseModel):
    id: str
    job_id: str
    artifact_type: str  # mp4 | thumbnail | srt | script | provenance
    storage_url: str
    local_path: str | None = None
    agent_id: str | None = None  # render PC holding a binary artifact (Tailscale preview)
    size_bytes: int | None = None
    duration_seconds: float | None = None
    checksum: str | None = None
    # Computed dashboard-facing preview URL (API proxy over Tailscale); empty when unavailable.
    preview_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Render job payload (the immutable contract handed to a local render agent)
# ---------------------------------------------------------------------------


class JobCandidate(BaseModel):
    """Candidate slice embedded in the render job payload (denormalized)."""

    title: str = Field(..., examples=["Topik yang disetujui"])
    facts: list[str] = Field(default_factory=list)
    summary: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)


class JobVideo(BaseModel):
    aspect_ratio: AspectRatio = AspectRatio.PORTRAIT
    resolution: str = "1080x1920"
    duration_seconds: int = 45
    language: LanguageCode = LanguageCode.INDONESIAN
    platforms: list[Platform] = Field(default_factory=lambda: [Platform.TIKTOK])


class JobCreative(BaseModel):
    hook: str | None = None
    tone: str = "informative-fast"
    voice: str = "id-ID-ArdiNeural"
    subtitle_style: str = "bold-center"
    music_profile: str = "news-modern"
    video_source: str = "pexels"


class RenderJobPayload(BaseModel):
    """Immutable payload a local render agent downloads and executes.

    Matches the example in IMPLEMENTATION_PLAN.md §10. Carries everything the
    MoneyPrinterTurbo adapter needs to render one video, plus the provenance
    needed to build the output manifest.
    """

    job_id: str
    idempotency_key: str
    candidate: JobCandidate
    video: JobVideo = Field(default_factory=JobVideo)
    creative: JobCreative = Field(default_factory=JobCreative)
    sources: list[dict[str, Any]] = Field(default_factory=list)


__all__ = [
    "ApprovalOut",
    "JobCandidate",
    "JobCreative",
    "JobVideo",
    "RenderJobEventOut",
    "RenderJobOut",
    "RenderJobPayload",
    "RenderJobStatus",
    "RenderProfileCreate",
    "RenderProfileOut",
    "VideoOutputOut",
]
