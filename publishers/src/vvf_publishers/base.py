"""Publisher base types (M6).

Publishers run **on the render PC**, where the rendered video file lives. Each
publisher takes a local file path plus metadata and returns a
:class:`PublishOutcome` describing what happened.

Design rules:

- Credentials are read from the local environment only. They are never sent to
  the VPS, never logged, and never returned in an outcome.
- A missing/incomplete credential set is **not** an error: the publisher returns
  ``manual_required`` so the admin can upload by hand and record the post URL.
- Only transient failures (network, 5xx, rate limits) are marked retryable;
  everything else is terminal so a bad video never loops forever.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

from vvf_contracts.common import Platform, PublishStatus


@dataclass(slots=True)
class PublishRequestData:
    """Everything a publisher needs for one upload."""

    video_path: str
    title: str
    description: str = ""
    hashtags: list[str] = field(default_factory=list)
    private: bool = False

    def caption(self, limit: int | None = None) -> str:
        """Description plus hashtags, optionally truncated to ``limit`` chars."""
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags if t.strip())
        text = " ".join(part for part in (self.description.strip(), tags) if part).strip()
        if limit is not None and len(text) > limit:
            text = text[: limit - 1].rstrip() + "…"
        return text


@dataclass(slots=True)
class PublishOutcome:
    """Result of a publish attempt. Never carries credentials."""

    platform: Platform
    status: PublishStatus
    post_url: str | None = None
    platform_post_id: str | None = None
    error_message: str | None = None
    retryable: bool = False

    @classmethod
    def published(
        cls, platform: Platform, post_url: str, post_id: str | None = None
    ) -> "PublishOutcome":
        return cls(
            platform=platform,
            status=PublishStatus.PUBLISHED,
            post_url=post_url,
            platform_post_id=post_id,
        )

    @classmethod
    def manual(cls, platform: Platform, reason: str) -> "PublishOutcome":
        return cls(
            platform=platform, status=PublishStatus.MANUAL_REQUIRED, error_message=reason
        )

    @classmethod
    def failed(
        cls, platform: Platform, reason: str, retryable: bool = False
    ) -> "PublishOutcome":
        return cls(
            platform=platform,
            status=PublishStatus.FAILED,
            error_message=reason,
            retryable=retryable,
        )


class PublisherError(Exception):
    """Raised for unexpected publisher failures (mapped to a failed outcome)."""


class Publisher(Protocol):
    """Interface every platform publisher implements."""

    platform: Platform

    def is_configured(self) -> bool:
        """True when all required credentials are present in the environment."""
        ...

    def publish(self, req: PublishRequestData) -> PublishOutcome:
        """Upload the video and return the outcome. Must not raise for expected
        failure modes (missing creds, API rejection) — return an outcome."""
        ...


def env(name: str, default: str = "") -> str:
    """Read a credential/config value from the environment (trimmed)."""
    return (os.getenv(name) or default).strip()


def missing_env(*names: str) -> list[str]:
    """Names of the environment variables that are unset/empty."""
    return [n for n in names if not env(n)]


def is_retryable_status(code: int) -> bool:
    """HTTP status codes worth retrying (transient upstream problems)."""
    return code == 429 or 500 <= code < 600


__all__ = [
    "Publisher",
    "PublisherError",
    "PublishOutcome",
    "PublishRequestData",
    "env",
    "is_retryable_status",
    "missing_env",
]
