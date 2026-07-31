"""Common enums and mixins used across VVF contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    """Timezone-aware UTC 'now' used as the default factory for timestamps."""
    return datetime.now(timezone.utc)


class TimestampMixin(BaseModel):
    """Common audit timestamps shared by all persisted entities."""

    model_config = ConfigDict(populate_by_name=True)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AspectRatio(str, Enum):
    """Supported output aspect ratios. MVP targets vertical 9:16."""

    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    SQUARE = "1:1"


class LanguageCode(str, Enum):
    """BCP-47 language codes the pipeline supports.

    MoneyPrinterTurbo accepts language tags like ``id-ID``; we align our
    contracts to the same scheme so the adapter needs no translation.
    """

    INDONESIAN = "id-ID"
    ENGLISH = "en-US"


class Platform(str, Enum):
    """Destination platforms a video may be formatted for."""

    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"


class PublishMode(str, Enum):
    """How a target is published.

    ``AUTO`` uses the platform's free official API from the render PC.
    ``MANUAL`` means the admin uploads by hand and records the post URL.
    """

    AUTO = "auto"
    MANUAL = "manual"


class PublishStatus(str, Enum):
    """Lifecycle of one publish target (one platform for one render job).

    Normal flow::

        pending -> publishing -> published

    ``manual_required`` means automatic publishing is unavailable (no
    credentials, unsupported API path, or a non-retryable API rejection) and
    the admin must upload manually and record the post URL.
    """

    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"
    SKIPPED = "skipped"


class CandidateStatus(str, Enum):
    """Lifecycle of a content candidate."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ResearchRunStatus(str, Enum):
    """Lifecycle of a discovery/research run."""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RenderJobStatus(str, Enum):
    """Render job lifecycle (see IMPLEMENTATION_PLAN.md §7).

    Normal flow::

        queued -> claimed -> scripting -> assets -> tts -> subtitles
        -> rendering -> uploading -> completed -> publishing -> published

    ``completed`` means the render finished and the file is available on the
    render PC (previewable via Tailscale). ``publishing``/``published`` cover
    the post-render publishing stage (M6).

    Failure states: ``failed``, ``cancelled``, ``retry_waiting``,
    ``publish_failed``.
    """

    QUEUED = "queued"
    CLAIMED = "claimed"
    SCRIPTING = "scripting"
    ASSETS = "assets"
    TTS = "tts"
    SUBTITLES = "subtitles"
    RENDERING = "rendering"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY_WAITING = "retry_waiting"
    PUBLISH_FAILED = "publish_failed"


class RiskFlag(str, Enum):
    """Content risk flags surfaced during discovery."""

    VIOLENCE = "violence"
    MINORS = "minors"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    POLITICAL_MISINFORMATION = "political_misinformation"
    COPYRIGHT = "copyright"
    UNVERIFIED_BREAKING_NEWS = "unverified_breaking_news"
