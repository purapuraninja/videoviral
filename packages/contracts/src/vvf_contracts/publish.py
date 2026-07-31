"""Publishing contracts (M6).

Publishing happens **on the render PC**, where the video file lives. The VPS
only orchestrates and records results: which platform, which mode, the
resulting post URL. No video bytes and no OAuth credentials ever reach the VPS.

Flow::

    admin -> POST /render-jobs/{id}/publish        (create publish targets)
    agent -> POST /agents/claim-publish            (claim pending targets)
    agent -> POST /agents/jobs/{id}/publish-result (report per-platform result)
    admin -> POST /publish-targets/{id}/manual     (record a manual post URL)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vvf_contracts.common import Platform, PublishMode, PublishStatus, utcnow


class PublishRequest(BaseModel):
    """POST /api/v1/render-jobs/{id}/publish — admin asks for publishing."""

    platforms: list[Platform] = Field(
        default_factory=lambda: [
            Platform.YOUTUBE_SHORTS,
            Platform.TIKTOK,
            Platform.INSTAGRAM_REELS,
        ]
    )
    mode: PublishMode = PublishMode.AUTO
    title: str | None = None
    description: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    # Ask platforms to keep the post private/unlisted where supported.
    private: bool = False

    @field_validator("platforms")
    @classmethod
    def _non_empty(cls, v: list[Platform]) -> list[Platform]:
        if not v:
            raise ValueError("at least one platform is required")
        return list(dict.fromkeys(v))  # dedupe, keep order


class PublishTargetOut(BaseModel):
    """One platform's publish state for one render job."""

    id: str
    job_id: str
    platform: Platform
    mode: PublishMode
    status: PublishStatus
    post_url: str | None = None
    platform_post_id: str | None = None
    error_message: str | None = None
    attempt: int = 0
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    model_config = ConfigDict(from_attributes=True)


class PublishJobPayload(BaseModel):
    """What the agent needs to publish one job (returned by claim-publish).

    ``local_path`` is relative to the agent's preview/tasks root — the agent
    resolves it against its own filesystem. The VPS never sees the bytes.
    """

    job_id: str
    target_ids: list[str] = Field(default_factory=list)
    platforms: list[Platform] = Field(default_factory=list)
    mode: PublishMode = PublishMode.AUTO
    local_path: str
    title: str
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    private: bool = False


class ClaimPublishIn(BaseModel):
    """POST /api/v1/agents/claim-publish."""

    agent_id: str


class ClaimPublishOut(BaseModel):
    claimed: bool = False
    payload: PublishJobPayload | None = None


class PublishResultItem(BaseModel):
    """Outcome for a single platform."""

    platform: Platform
    status: PublishStatus
    post_url: str | None = None
    platform_post_id: str | None = None
    error_message: str | None = None


class AgentPublishResultIn(BaseModel):
    """POST /api/v1/agents/jobs/{id}/publish-result."""

    agent_id: str
    results: list[PublishResultItem] = Field(default_factory=list)


class ManualPublishIn(BaseModel):
    """POST /api/v1/publish-targets/{id}/manual — admin records a hand upload."""

    post_url: str
    platform_post_id: str | None = None

    @field_validator("post_url")
    @classmethod
    def _looks_like_url(cls, v: str) -> str:
        v = (v or "").strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("post_url must be an http(s) URL")
        return v


__all__ = [
    "AgentPublishResultIn",
    "ClaimPublishIn",
    "ClaimPublishOut",
    "ManualPublishIn",
    "PublishJobPayload",
    "PublishRequest",
    "PublishResultItem",
    "PublishTargetOut",
]
